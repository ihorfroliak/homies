"""TASK-014R — repairs after the independent audit TASK-014A.

F-1 unsubscribe links are durable before SMTP and stable across retries;
N-3 single-use effect with an idempotent generic answer; F-2 stored-query
integrity (INVALID, never broadened); F-5 SMTP classification without provider
text or addresses; N-4 honest terminal reasons; F-6 behavioural tests for the
auditor's surviving mutants (X06, X07, X08, X10, X13, X18).
"""

import re
import smtplib
import socket
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.modules.alerts import delivery, worker
from app.modules.alerts.models import AlertDelivery, SavedSearchMatch, UnsubscribeToken
from app.modules.events import worker as events_worker
from app.modules.events.models import Notification
from app.modules.events.providers import DeliveryResult, SmtpEmailChannel, classify_smtp_error
from app.modules.identity.models import User
from app.modules.properties.models import ClassifiedOffer, ListingPublicGeneration
from app.modules.saved import service as saved_service
from app.modules.saved.models import SavedSearch
from tests.conftest import TestingSession, auth, register_and_login
from tests.saved_support import load_geo
from tests.test_saved_search_alerts import (
    RENTER_EMAIL,
    Mailbox,
    _deliveries,
    _listing,
    _run,
    _search,
    _verified_renter,
)


@pytest.fixture
def geo(client):
    return load_geo(TestingSession)


@pytest.fixture
def owner(client):
    return register_and_login(client, "owner-alerts@example.com", "host")


@pytest.fixture
def renter(client):
    return _verified_renter(client)


@pytest.fixture
def mailbox(monkeypatch):
    box = Mailbox()
    monkeypatch.setattr(delivery, "channel_for", lambda name: box)
    return box

TOKEN = re.compile(r"/unsubscribe\?token=([A-Za-z0-9_-]+)")


def _links(body: str) -> list[str]:
    return TOKEN.findall(body)


def _unsubscribe(client, token):
    response = client.post("/v1/notifications/unsubscribe", json={"token": token})
    assert response.status_code == 200
    return response.json()


def _search_row(search_id) -> SavedSearch:
    with TestingSession() as db:
        row = db.get(SavedSearch, search_id)
        assert row is not None
        return row


def _state(client, token, search_id):
    return client.get(f"/v1/me/saved-searches/{search_id}", headers=auth(token)).json()


# --- F-1: durable, stable unsubscribe capabilities --------------------------------------------


class AcceptThenCrash(Mailbox):
    """The provider accepts the message; then the worker dies before its
    transaction commits (the TASK-014A crash window)."""

    def send(self, to, subject, body, idem_key):
        super().send(to, subject, body, idem_key)
        raise RuntimeError("worker crashed after SMTP accepted the message")


@pytest.fixture
def crashing(monkeypatch):
    box = AcceptThenCrash()
    monkeypatch.setattr(delivery, "channel_for", lambda name: box)
    return box


def _age_claims():
    """Let reconcile treat the crashed claim as stale (STALE_CLAIM passed)."""
    with TestingSession() as db:
        db.execute(update(AlertDelivery).where(AlertDelivery.status == "processing")
                   .values(claimed_at=datetime.now(timezone.utc) - timedelta(hours=1)))
        db.commit()


def test_a_link_from_an_email_sent_before_a_crash_works(client, owner, renter, geo, crashing):
    sid = _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    assert len(crashing.sent) == 1  # accepted by the provider …
    email = _deliveries(channel="EMAIL")[0]
    assert email.status == "processing"  # … but the delivery never committed
    per_search, _all = _links(crashing.sent[0]["body"])
    assert _unsubscribe(client, per_search) == {"status": "ok"}
    assert _search_row(sid).notifications_enabled is False  # the link really worked


def test_a_retry_after_a_crash_reuses_the_same_working_links(client, owner, renter, geo,
                                                              crashing, monkeypatch):
    _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    first = _links(crashing.sent[0]["body"])
    with TestingSession() as db:
        assert db.scalar(select(UnsubscribeToken.token_hash).where(
            UnsubscribeToken.token_hash == delivery.token_hash(first[1]))) is not None
    # Reconcile, then the retry succeeds: at-least-once — a second copy.
    _age_claims()
    with TestingSession() as db:
        worker.reconcile(db)
        db.commit()
    box = Mailbox()
    monkeypatch.setattr(delivery, "channel_for", lambda name: box)
    worker.process_deliveries(TestingSession)
    assert len(box.sent) == 1 and _deliveries(channel="EMAIL")[0].status == "delivered"
    second = _links(box.sent[0]["body"])
    assert second == first  # same logical delivery, same capabilities
    with TestingSession() as db:
        tokens = db.scalars(select(UnsubscribeToken.token_hash)).all()
    assert len(tokens) == 2  # no fresh set per attempt
    # A link from the duplicate works too: stop all PRODUCT email.
    assert _unsubscribe(client, second[1]) == {"status": "ok"}
    assert client.get("/v1/me/notification-preferences", headers=auth(renter)).json()[1] == {
        "category": "PRODUCT", "channel": "EMAIL", "enabled": False}


def test_capabilities_are_256_bit_opaque_and_keyed(monkeypatch):
    a = delivery.capability("d-1", "SAVED_SEARCH", "s-1")
    assert len(a) == 43 and re.fullmatch(r"[A-Za-z0-9_-]{43}", a)
    assert a == delivery.capability("d-1", "SAVED_SEARCH", "s-1")  # stable per delivery
    assert a != delivery.capability("d-2", "SAVED_SEARCH", "s-1")
    assert a != delivery.capability("d-1", "PRODUCT_EMAIL", None)
    assert a != delivery.capability("d-1", "SAVED_SEARCH", "s-2")
    for part in ("d-1", "s-1", "SAVED_SEARCH"):
        assert part not in a
    monkeypatch.setattr(settings, "jwt_secret", "another-secret-" + "x" * 32)
    assert delivery.capability("d-1", "SAVED_SEARCH", "s-1") != a  # needs the key


# --- N-3: single-use effect, idempotent generic answer ------------------------------------------


def test_an_old_link_cannot_undo_a_later_re_enable(client, owner, renter, geo, mailbox):
    sid = _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    per_search, every = _links(mailbox.sent[0]["body"])
    assert _unsubscribe(client, per_search) == {"status": "ok"}
    assert _search_row(sid).notifications_enabled is False
    version = _state(client, renter, sid)["version"]
    assert client.patch(f"/v1/me/saved-searches/{sid}", headers=auth(renter), json={
        "expected_version": version, "notifications_enabled": True}).status_code == 200
    # The old link is replayed: same answer, no effect.
    assert _unsubscribe(client, per_search) == {"status": "ok"}
    assert _search_row(sid).notifications_enabled is True
    # Same for the all-email link.
    assert _unsubscribe(client, every) == {"status": "ok"}
    client.put("/v1/me/notification-preferences", headers=auth(renter),
               json={"category": "PRODUCT", "channel": "EMAIL", "enabled": True})
    assert _unsubscribe(client, every) == {"status": "ok"}
    assert client.get("/v1/me/notification-preferences", headers=auth(renter)).json()[1][
        "enabled"] is True


def test_unknown_expired_and_used_tokens_answer_identically(client, owner, renter, geo, mailbox):
    """X08: an expired token has no effect, and nothing tells the caller why."""
    sid = _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    per_search, _every = _links(mailbox.sent[0]["body"])
    with TestingSession() as db:
        db.execute(update(UnsubscribeToken).where(
            UnsubscribeToken.token_hash == delivery.token_hash(per_search)).values(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    answers = [
        client.post("/v1/notifications/unsubscribe", json={"token": per_search}),
        client.post("/v1/notifications/unsubscribe", json={"token": "u" * 43}),
    ]
    assert [(r.status_code, r.json()) for r in answers] == [(200, {"status": "ok"})] * 2
    assert _search_row(sid).notifications_enabled is True  # expired: no effect


# --- F-2: stored query integrity ----------------------------------------------------------------


def _corrupt(search_id, **values):
    with TestingSession() as db:
        db.execute(update(SavedSearch).where(SavedSearch.id == search_id).values(**values))
        db.commit()


@pytest.mark.parametrize("corruption", [
    "zeroed_fingerprint", "other_valid_fingerprint", "dropped_filter", "non_canonical",
    "unsupported_version",
])
def test_a_corrupted_stored_query_is_invalid_everywhere(client, owner, renter, geo, corruption):
    query = f"locality_id={geo['krakow']}&max_rent=100000"
    sid = _search(client, renter, query)
    row = _search_row(sid)
    canonical = row.canonical_query
    if corruption == "zeroed_fingerprint":
        _corrupt(sid, query_fingerprint="0" * 64)
    elif corruption == "other_valid_fingerprint":
        _corrupt(sid, query_fingerprint=saved_service.fingerprint(1, f"locality_id={geo['krakow']}"))
    elif corruption == "dropped_filter":  # the broader query, old fingerprint kept
        _corrupt(sid, canonical_query=f"locality_id={geo['krakow']}")
    elif corruption == "non_canonical":  # reordered, with its own matching fingerprint
        reordered = "&".join(reversed(canonical.split("&")))
        assert reordered != canonical
        _corrupt(sid, canonical_query=reordered,
                 query_fingerprint=saved_service.fingerprint(1, reordered))
    else:
        _corrupt(sid, query_schema_version=2)
    state = _state(client, renter, sid)
    assert state["query_state"] == "INVALID", state
    assert client.get(f"/v1/me/saved-searches/{sid}/matches",
                      headers=auth(renter)).status_code == 409
    # The worker never matches it — not even a listing only the broader query admits.
    _listing(client, owner, geo, rent_amount=250000)
    _run()
    with TestingSession() as db:
        assert db.scalars(select(SavedSearchMatch).where(
            SavedSearchMatch.saved_search_id == sid)).all() == []


def test_an_unchanged_stored_query_stays_valid(client, renter, geo):
    sid = _search(client, renter, f"locality_id={geo['krakow']}&max_rent=100000")
    assert _state(client, renter, sid)["query_state"] == "VALID"


def test_corruption_after_queueing_suppresses_the_send(client, owner, renter, geo, mailbox):
    sid = _search(client, renter, f"locality_id={geo['krakow']}&max_rent=300000")
    _listing(client, owner, geo)
    worker.process_work(TestingSession)
    _corrupt(sid, canonical_query=f"locality_id={geo['krakow']}")
    worker.process_deliveries(TestingSession)
    assert {(d.status, d.outcome) for d in _deliveries()} == {("suppressed", "query_invalid")}
    assert mailbox.sent == []


# --- F-5 / N-4: SMTP classification, no provider text, honest endings -------------------------


@pytest.mark.parametrize("exc, transient, reason", [
    (smtplib.SMTPRecipientsRefused({"victim@example.com": (550, b"5.1.1 unknown; pw=hunter2")}),
     False, "SMTPRecipientsRefused:550"),
    (smtplib.SMTPRecipientsRefused({"victim@example.com": (450, b"mailbox busy")}),
     True, "SMTPRecipientsRefused:450"),
    (smtplib.SMTPDataError(554, b"rejected victim@example.com"), False, "SMTPDataError:554"),
    (smtplib.SMTPDataError(451, b"try later"), True, "SMTPDataError:451"),
    (smtplib.SMTPSenderRefused(553, b"no", "from@example.com"), False, "SMTPSenderRefused:553"),
    (smtplib.SMTPAuthenticationError(535, b"bad credentials"), False,
     "SMTPAuthenticationError:535"),
    (smtplib.SMTPNotSupportedError("STARTTLS"), False, "SMTPNotSupportedError"),
    (smtplib.SMTPConnectError(421, b"busy"), True, "SMTPConnectError:421"),
    (smtplib.SMTPServerDisconnected("gone"), True, "SMTPServerDisconnected"),
    (TimeoutError("timed out"), True, "TimeoutError"),
    (ConnectionRefusedError(111, "refused"), True, "ConnectionRefusedError"),
    (socket.gaierror(-2, "Name or service not known"), True, "gaierror"),
])
def test_smtp_errors_are_classified_by_code_without_provider_text(exc, transient, reason):
    got = classify_smtp_error(exc)
    assert got == (transient, reason)
    for leak in ("victim", "@", "hunter2", "credentials", "unknown", "busy"):
        assert leak not in got[1]


class _RefusingSMTP:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, *a):
        pass

    def send_message(self, msg):
        raise smtplib.SMTPRecipientsRefused(
            {msg["To"]: (550, f"5.1.1 <{msg['To']}> user unknown; pw=hunter2".encode())})


def test_the_smtp_channel_reports_a_machine_reason_only(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _RefusingSMTP)
    result = SmtpEmailChannel().send("victim@example.com", "s", "b", "idem")
    assert result == DeliveryResult(ok=False, transient=False, error="SMTPRecipientsRefused:550")


def test_a_refused_transactional_email_stores_no_address(client, monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _RefusingSMTP)
    monkeypatch.setattr(settings, "email_provider", "smtp")
    register_and_login(client, "victim@example.com", "guest")
    with TestingSession() as db:
        user = db.scalar(select(User).where(User.email == "victim@example.com"))
        note = Notification(event_id="e", event_type="BookingCreated", correlation_id="c",
                            recipient_role="guest", recipient_user_id=user.id, channel="email",
                            template_id="BookingCreated", payload={})
        db.add(note)
        db.commit()
        assert events_worker.deliver_one(db, note) == "dead"  # 5xx: permanent, not retried
        assert note.last_error == "SMTPRecipientsRefused:550"


class _Failing:
    def __init__(self, transient, error):
        self.result = DeliveryResult(ok=False, transient=transient, error=error)

    def send(self, to, subject, body, idem_key):
        return self.result


def test_a_permanent_refusal_and_exhausted_retries_end_differently(
        client, owner, renter, geo, monkeypatch):
    _search(client, renter, f"locality_id={geo['krakow']}")
    monkeypatch.setattr(delivery, "channel_for",
                        lambda name: _Failing(False, "SMTPRecipientsRefused:550"))
    _listing(client, owner, geo)
    _run()
    assert _deliveries(channel="EMAIL")[0].outcome == "provider_rejected:SMTPRecipientsRefused:550"
    # Transient failures until the attempts run out: not "permanent".
    monkeypatch.setattr(settings, "notification_max_attempts", 1)
    monkeypatch.setattr(delivery, "channel_for", lambda name: _Failing(True, "TimeoutError"))
    _listing(client, owner, geo)
    _run()
    last = [d for d in _deliveries(channel="EMAIL") if d.outcome != (
        "provider_rejected:SMTPRecipientsRefused:550")]
    assert [(d.status, d.outcome) for d in last] == [("dead", "retries_exhausted")]


# --- F-6: behaviour behind the auditor's surviving mutants --------------------------------------


def test_x13_another_users_search_never_keeps_a_delivery_alive(client, owner, renter, geo,
                                                                mailbox):
    query = f"locality_id={geo['krakow']}"
    mine = _search(client, renter, query)
    other = _verified_renter(client, "other-alerts@example.com")
    _search(client, other, query)  # same query, same listing, different user
    _listing(client, owner, geo)
    worker.process_work(TestingSession)
    client.delete(f"/v1/me/saved-searches/{mine}", headers=auth(renter))
    worker.process_deliveries(TestingSession)
    with TestingSession() as db:
        renter_id = db.scalar(select(User.id).where(User.email == RENTER_EMAIL))
    mine_out = {(d.status, d.outcome) for d in _deliveries(user_id=renter_id)}
    assert mine_out == {("suppressed", "search_deleted")}
    assert all(m["to"] != RENTER_EMAIL for m in mailbox.sent)
    assert [m["to"] for m in mailbox.sent] == ["other-alerts@example.com"]


def test_x18_a_paused_search_is_never_a_candidate(client, owner, renter, geo, mailbox):
    sid = _search(client, renter, f"locality_id={geo['krakow']}")
    assert client.patch(f"/v1/me/saved-searches/{sid}", headers=auth(renter), json={
        "expected_version": 1, "status": "paused"}).status_code == 200
    _listing(client, owner, geo)
    worker.process_work(TestingSession)
    with TestingSession() as db:
        assert db.scalars(select(SavedSearchMatch).where(
            SavedSearchMatch.saved_search_id == sid)).all() == []  # not even recorded
    assert _deliveries() == []


def test_x06_an_address_unverified_after_queueing_is_not_emailed(client, owner, renter, geo,
                                                                  mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    worker.process_work(TestingSession)
    with TestingSession() as db:
        db.execute(update(User).where(User.email == RENTER_EMAIL).values(email_verified_at=None))
        db.commit()
    worker.process_deliveries(TestingSession)
    outcome = {d.channel: (d.status, d.outcome) for d in _deliveries()}
    assert outcome == {"EMAIL": ("suppressed", "email_not_verified"),
                       "IN_APP": ("delivered", "")}
    assert mailbox.sent == []


def test_x07_a_delivery_for_an_older_episode_is_superseded(client, owner, renter, geo, mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}")
    oid = _listing(client, owner, geo)
    worker.process_work(TestingSession)
    client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
    assert client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner)).status_code == 200
    worker.process_deliveries(TestingSession)  # generation 1's deliveries, listing now in 2
    assert {(d.public_generation, d.status, d.outcome) for d in _deliveries()} == {
        (1, "suppressed", "superseded")}
    assert mailbox.sent == []


def test_x10_reconcile_restores_only_recent_episodes(client, owner, geo):
    recent = _listing(client, owner, geo)
    old = _listing(client, owner, geo)
    now = datetime.now(timezone.utc)
    with TestingSession() as db:
        db.execute(delete(ListingPublicGeneration))
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == recent).values(
            public_since=now - timedelta(days=6)))
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == old).values(
            public_since=now - timedelta(days=8)))
        db.commit()
        result = worker.reconcile(db)
        db.commit()
        restored = {r.listing_id for r in db.scalars(select(ListingPublicGeneration))}
    assert result["restored_work"] == 1 and restored == {recent}
