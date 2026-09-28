"""Saved-search alerts end to end on SQLite (TASK-014). The worker is driven
synchronously; concurrency and scale are proven on PostgreSQL in
test_saved_search_alerts_pg.py."""

import json
import re
import smtplib

import pytest
from sqlalchemy import delete, func, select, update

from app.core import ratelimit as rl
from app.core.config import settings
from app.modules.alerts import delivery, worker
from app.modules.alerts.models import (
    AlertDelivery,
    SavedSearchMatch,
    UnsubscribeToken,
    UserNotification,
)
from app.modules.events import worker as events_worker
from app.modules.events.models import Notification
from app.modules.events.providers import DeliveryResult
from app.modules.geography.models import Locality
from app.modules.identity.models import User
from app.modules.properties.models import ClassifiedOffer, ListingPublicGeneration
from tests.conftest import (
    TestingSession,
    auth,
    last_code,
    register_and_login,
    verify_ownership,
)
from tests.test_geography import geo  # noqa: F401 — fixture

PROPERTY = {"category": "APARTMENT", "area_m2": 50, "rooms": 2, "capacity": 2}
OFFER = {"title": "Alert", "rent_amount": 250000, "min_term_months": 12,
         "contact_mode": "phone", "contact_phone": "+48 533 444 555"}
RENTER_EMAIL = "renter-alerts@example.com"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class Mailbox:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body, idem_key):
        self.sent.append({"to": to, "subject": subject, "body": body, "idem_key": idem_key})
        return DeliveryResult(ok=True)


@pytest.fixture
def mailbox(monkeypatch):
    box = Mailbox()
    monkeypatch.setattr(delivery, "channel_for", lambda name: box)
    return box


@pytest.fixture
def owner(client):
    return register_and_login(client, "owner-alerts@example.com", "host")


def _verified_renter(client, email=RENTER_EMAIL):
    token = register_and_login(client, email, "guest")
    assert client.post("/v1/me/verify/email/start", headers=auth(token)).status_code == 200
    assert client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                       headers=auth(token)).status_code == 200
    return token


@pytest.fixture
def renter(client):
    return _verified_renter(client)


_n = {"i": 0}


def _listing(client, owner, geo, *, publish=True, **offer):
    _n["i"] += 1
    made = client.post("/v1/properties", json={
        **PROPERTY, "locality_id": geo["krakow"], "thoroughfare": "ul. Tajna",
        "building_number": f"{_n['i']}Q", "unit_number": "SEC7", "postcode": "30-777"},
        headers=auth(owner))
    assert made.status_code == 201, made.text
    verify_ownership(client, owner, made.json()["id"])
    oid = client.post(f"/v1/properties/{made.json()['id']}/classifieds",
                      json={**OFFER, **offer}, headers=auth(owner)).json()["id"]
    if publish:
        assert client.post(f"/v1/classifieds/{oid}/publish",
                           headers=auth(owner)).status_code == 200
    return oid


def _search(client, token, query, name="Kraków"):
    r = client.post("/v1/me/saved-searches", json={"name": name, "query": query},
                    headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _run():
    return worker.process_work(TestingSession), worker.process_deliveries(TestingSession)


def _deliveries(**where):
    with TestingSession() as db:
        stmt = select(AlertDelivery)
        for k, v in where.items():
            stmt = stmt.where(getattr(AlertDelivery, k) == v)
        return list(db.scalars(stmt.order_by(AlertDelivery.channel)))


def _inbox(client, token):
    r = client.get("/v1/me/inbox", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


# --- no initial flood; only NEW public episodes ------------------------------------------------


def test_existing_matches_never_alert(client, owner, renter, geo, mailbox):
    existing = _listing(client, owner, geo)
    sid = _search(client, renter, f"locality_id={geo['krakow']}")
    assert _run()[0] == {"no_match": 1}  # its episode began before the baseline
    assert _deliveries() == [] and mailbox.sent == [] and _inbox(client, renter)["total"] == 0
    shown = client.get(f"/v1/me/saved-searches/{sid}/matches", headers=auth(renter)).json()
    assert [i["id"] for i in shown["items"]] == [existing]  # visible, just not notified


def test_a_new_public_listing_alerts_once_per_channel(client, owner, renter, geo, mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}&max_rent=300000")
    oid = _listing(client, owner, geo)
    work, sent = _run()
    assert work == {"matched": 1} and sent == {"delivered": 2}
    assert [d.channel for d in _deliveries()] == ["EMAIL", "IN_APP"]
    inbox = _inbox(client, renter)
    assert inbox["total"] == 1 and inbox["unread"] == 1
    entry = inbox["items"][0]
    assert entry["category"] == "PRODUCT" and entry["notification_type"] == "SAVED_SEARCH_MATCH"
    assert entry["data"]["listing_id"] == oid
    assert len(mailbox.sent) == 1 and mailbox.sent[0]["to"] == RENTER_EMAIL
    assert oid in mailbox.sent[0]["body"]
    # Idempotent: running again sends nothing new.
    assert _run() == ({}, {})
    assert len(mailbox.sent) == 1 and _inbox(client, renter)["total"] == 1


def test_email_needs_a_verified_address(client, owner, geo, mailbox):
    unverified = register_and_login(client, "unverified@example.com", "guest")
    _search(client, unverified, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    assert [d.channel for d in _deliveries()] == ["IN_APP"]
    assert mailbox.sent == []


def test_reconfirmation_and_edits_while_public_never_alert(client, owner, renter, geo, mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}")
    oid = _listing(client, owner, geo)
    _run()
    before = len(_deliveries())
    client.post(f"/v1/classifieds/{oid}/confirm", headers=auth(owner))
    client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner))
    version = client.get(f"/v1/classifieds/{oid}").json()["version"]
    client.put(f"/v1/classifieds/{oid}/price", json={"rent_amount": 190000,
               "expected_version": version}, headers=auth(owner))
    assert _run() == ({}, {})
    assert len(_deliveries()) == before


def test_republication_after_pause_is_a_new_alert(client, owner, renter, geo, mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}")
    oid = _listing(client, owner, geo)
    _run()
    client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
    client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner))
    _run()
    assert sorted({d.public_generation for d in _deliveries(listing_id=oid)}) == [1, 2]
    assert _inbox(client, renter)["total"] == 2


def test_two_matching_searches_make_one_delivery_per_channel(client, owner, renter, geo, mailbox):
    a = _search(client, renter, f"locality_id={geo['krakow']}", name="A")
    b = _search(client, renter, "max_rent=300000", name="B")
    oid = _listing(client, owner, geo)
    _run()
    with TestingSession() as db:
        matches = db.scalar(select(func.count()).select_from(SavedSearchMatch))
    assert matches == 2
    assert [d.channel for d in _deliveries()] == ["EMAIL", "IN_APP"]
    assert len(mailbox.sent) == 1
    entry = _inbox(client, renter)["items"][0]
    assert sorted(entry["data"]["saved_search_ids"]) == sorted([a, b])
    assert entry["data"]["listing_id"] == oid


def test_a_search_that_does_not_match_is_not_notified(client, owner, renter, geo, mailbox):
    _search(client, renter, f"locality_id={geo['warszawa']}")
    _search(client, renter, "max_rent=100000", name="Tanio")
    _listing(client, owner, geo)
    assert _run()[0] == {"no_match": 1}
    assert _deliveries() == []


# --- queued is not authority to send ------------------------------------------------------------


def _queue(client, owner, renter, geo, query=None):
    sid = _search(client, renter, query or f"locality_id={geo['krakow']}&max_rent=300000")
    oid = _listing(client, owner, geo)
    assert worker.process_work(TestingSession) == {"matched": 1}
    assert {d.status for d in _deliveries()} == {"pending"}
    return sid, oid


def _suppressed_because(reason):
    ds = _deliveries()
    assert ds and all(d.status == "suppressed" and d.outcome == reason for d in ds), [
        (d.channel, d.status, d.outcome) for d in ds]


def test_paused_search_suppresses_queued_delivery(client, owner, renter, geo, mailbox):
    sid, _ = _queue(client, owner, renter, geo)
    client.patch(f"/v1/me/saved-searches/{sid}", json={"expected_version": 1, "status": "paused"},
                 headers=auth(renter))
    worker.process_deliveries(TestingSession)
    _suppressed_because("search_inactive")
    assert mailbox.sent == [] and _inbox(client, renter)["total"] == 0


def test_deleted_search_suppresses_queued_delivery(client, owner, renter, geo, mailbox):
    sid, _ = _queue(client, owner, renter, geo)
    client.delete(f"/v1/me/saved-searches/{sid}", headers=auth(renter))
    worker.process_deliveries(TestingSession)
    _suppressed_because("search_deleted")


def test_listing_no_longer_public_suppresses_queued_delivery(client, owner, renter, geo, mailbox):
    _, oid = _queue(client, owner, renter, geo)
    client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
    worker.process_deliveries(TestingSession)
    _suppressed_because("listing_not_public")


def test_listing_no_longer_matching_suppresses_queued_delivery(client, owner, renter, geo,
                                                              mailbox):
    _, oid = _queue(client, owner, renter, geo)
    version = client.get(f"/v1/classifieds/{oid}").json()["version"]
    client.put(f"/v1/classifieds/{oid}/price", json={"rent_amount": 450000,
               "expected_version": version}, headers=auth(owner))
    worker.process_deliveries(TestingSession)
    _suppressed_because("no_longer_matches")


def test_disabled_preference_suppresses_queued_delivery(client, owner, renter, geo, mailbox):
    _queue(client, owner, renter, geo)
    for channel in ("IN_APP", "EMAIL"):
        assert client.put("/v1/me/notification-preferences", json={
            "category": "PRODUCT", "channel": channel, "enabled": False},
            headers=auth(renter)).status_code == 200
    worker.process_deliveries(TestingSession)
    _suppressed_because("preference_disabled")


def test_invalid_stored_query_never_alerts(client, owner, renter, geo, mailbox):
    """A retired place makes the stored query INVALID: it matches nothing — it
    is never rewritten into a broader search that would match this listing."""
    _search(client, renter, f"locality_id={geo['krakow']}")
    oid = _listing(client, owner, geo, publish=False)  # a Kraków flat, drafted before …
    with TestingSession() as db:
        db.execute(update(Locality).where(Locality.id == geo["krakow"]).values(status="RETIRED"))
        db.commit()
    assert client.post(f"/v1/classifieds/{oid}/publish",  # … published after the retirement
                       headers=auth(owner)).status_code == 200
    assert _run()[0] == {"no_match": 1}
    assert _deliveries() == []


# --- unsubscribe -----------------------------------------------------------------------------


def _tokens(body):
    return re.findall(r"unsubscribe\?token=([A-Za-z0-9_-]+)", body)


def test_unsubscribe_from_one_search_suppresses_its_queued_delivery(client, owner, renter, geo,
                                                                   mailbox):
    sid = _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    search_token, all_token = _tokens(mailbox.sent[0]["body"])
    _listing(client, owner, geo)
    worker.process_work(TestingSession)  # queued …
    r = client.post("/v1/notifications/unsubscribe", json={"token": search_token})
    assert r.status_code == 200 and r.json() == {"status": "ok"}  # … unsubscribed …
    worker.process_deliveries(TestingSession)  # … the worker tries to send
    pending_gen = [d for d in _deliveries() if d.completed_at and d.status == "suppressed"]
    assert pending_gen and {d.outcome for d in pending_gen} == {"search_inactive"}
    assert len(mailbox.sent) == 1
    body = client.get(f"/v1/me/saved-searches/{sid}", headers=auth(renter)).json()
    assert body["notifications_enabled"] is False  # the search itself is kept


def test_global_unsubscribe_stops_saved_search_emails_only(client, owner, renter, geo, mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    _, all_token = _tokens(mailbox.sent[0]["body"])
    client.post("/v1/notifications/unsubscribe", json={"token": all_token})
    prefs = client.get("/v1/me/notification-preferences", headers=auth(renter)).json()
    assert {(p["channel"], p["enabled"]) for p in prefs} == {("EMAIL", False), ("IN_APP", True)}
    _listing(client, owner, geo)
    _run()
    assert len(mailbox.sent) == 1  # no second email …
    assert _inbox(client, renter)["total"] == 2  # … the in-app alert still arrives


def test_unsubscribe_tokens_are_random_hashed_and_reveal_nothing(client, owner, renter, geo,
                                                                mailbox):
    sid = _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    tokens = _tokens(mailbox.sent[0]["body"])
    assert len(tokens) == 2
    with TestingSession() as db:
        user_id = db.scalar(select(User.id).where(User.email == RENTER_EMAIL))
        rows = list(db.scalars(select(UnsubscribeToken)))
    stored = json.dumps([[r.token_hash, r.user_id, r.scope, r.saved_search_id] for r in rows])
    for token in tokens:
        assert len(token) >= 43  # 32 random bytes = 256 bits, url-safe base64
        assert token not in stored  # only the hash is persisted
        for secret in (user_id, sid, RENTER_EMAIL, RENTER_EMAIL.split("@")[0]):
            assert secret not in token
    responses = {client.post("/v1/notifications/unsubscribe", json={"token": t}).text
                 for t in (tokens[0], "x" * 43, "totally-unknown-token-000")}
    assert responses == {'{"status":"ok"}'}  # no enumeration signal


# --- inbox, preferences, privacy, metrics --------------------------------------------------------


def test_inbox_is_private_and_carries_no_private_details(client, owner, renter, geo, mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    entry = _inbox(client, renter)["items"][0]
    other = register_and_login(client, "nosy@example.com", "guest")
    assert _inbox(client, other)["total"] == 0
    assert client.post(f"/v1/me/inbox/{entry['id']}/read",
                       headers=auth(other)).status_code == 404
    read = client.post(f"/v1/me/inbox/{entry['id']}/read", headers=auth(renter)).json()
    assert read["read_at"] is not None and _inbox(client, renter)["unread"] == 0
    text = json.dumps(_inbox(client, renter)) + mailbox.sent[0]["body"]
    for secret in ("ul. Tajna", "SEC7", "30-777", "533 444 555", "owner-alerts@example.com",
                   RENTER_EMAIL):
        assert secret not in text, secret


def test_preferences_default_on_and_are_per_channel(client, renter):
    prefs = client.get("/v1/me/notification-preferences", headers=auth(renter)).json()
    assert prefs == [{"category": "PRODUCT", "channel": "IN_APP", "enabled": True},
                     {"category": "PRODUCT", "channel": "EMAIL", "enabled": True}]
    assert client.put("/v1/me/notification-preferences", json={
        "category": "MARKETING", "channel": "EMAIL", "enabled": True},
        headers=auth(renter)).status_code == 422  # PRODUCT is not marketing consent


def test_alert_metrics_carry_no_identifiers(client, owner, renter, geo, mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    worker.reconcile(TestingSession())
    scrape = client.get("/metrics").text
    lines = [line for line in scrape.splitlines()
             if line.startswith(("homies_saved", "homies_alert", "homies_unsubscribe"))]
    assert any(line.startswith("homies_alert_delivery_total{") for line in lines)
    for line in lines:
        assert not UUID.search(line) and "@" not in line and "locality" not in line, line


def test_new_routes_have_write_budgets():
    assert rl.resolve_policy("POST", "/v1/me/saved-listings/x") is rl.SAVED_WRITE
    assert rl.resolve_policy("DELETE", "/v1/me/saved-searches/x") is rl.SAVED_WRITE
    assert rl.resolve_policy("PATCH", "/v1/me/saved-searches/x") is rl.SAVED_WRITE
    assert rl.resolve_policy("POST", "/v1/me/inbox/x/read") is rl.SAVED_WRITE
    assert rl.resolve_policy("PUT", "/v1/me/notification-preferences") is rl.PREFERENCE_WRITE
    assert rl.resolve_policy("POST", "/v1/notifications/unsubscribe") is rl.UNSUBSCRIBE


# --- recovery ---------------------------------------------------------------------------------


def test_reconcile_restores_a_lost_work_item_and_reclaims_stale_claims(client, owner, renter,
                                                                       geo, mailbox):
    _search(client, renter, f"locality_id={geo['krakow']}")
    oid = _listing(client, owner, geo)
    with TestingSession() as db:
        db.execute(delete(ListingPublicGeneration))
        db.commit()
    with TestingSession() as db:
        assert worker.reconcile(db)["restored_work"] == 1
        db.commit()
    assert _run()[0] == {"matched": 1}
    # A claim abandoned by a crashed worker goes back to pending.
    with TestingSession() as db:
        db.execute(update(ListingPublicGeneration).values(
            alert_status="processing", claimed_at=func.datetime("now", "-1 hour")))
        db.commit()
        assert worker.reconcile(db)["reclaimed_work"] == 1
        db.commit()
    assert _run()[0] == {"matched": 1}  # idempotent re-evaluation …
    assert len(_deliveries(listing_id=oid)) == 2  # … no duplicate delivery


# --- SMTP recipient (Phase-A defect) -----------------------------------------------------------


class FakeSMTP:
    sent: list = []

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
        FakeSMTP.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "email_provider", "smtp")
    return FakeSMTP.sent


def test_alert_email_goes_to_the_verified_address_never_the_user_id(client, owner, renter, geo,
                                                                    smtp):
    _search(client, renter, f"locality_id={geo['krakow']}")
    _listing(client, owner, geo)
    _run()
    with TestingSession() as db:
        user_id = db.scalar(select(User.id).where(User.email == RENTER_EMAIL))
    assert [m["To"] for m in smtp] == [RENTER_EMAIL]
    assert user_id not in smtp[0]["To"]


def test_transactional_email_resolves_the_address_at_send_time(client, smtp):
    register_and_login(client, "account@example.com", "guest")
    with TestingSession() as db:
        user = db.scalar(select(User).where(User.email == "account@example.com"))
        note = Notification(event_id="e", event_type="BookingCreated", correlation_id="c",
                            recipient_role="guest", recipient_user_id=user.id, channel="email",
                            template_id="BookingCreated", payload={})
        orphan = Notification(event_id="e", event_type="BookingCreated", correlation_id="c",
                              recipient_role="guest", recipient_user_id="no-such-user",
                              channel="email", template_id="BookingCreated", payload={})
        db.add_all([note, orphan])
        db.commit()
        # The address changed after queueing: the CURRENT one is used.
        user.email = "renamed@example.com"
        db.commit()
        assert events_worker.deliver_one(db, note) == "delivered"
        assert events_worker.deliver_one(db, orphan) == "dead"
        assert orphan.last_error == "no recipient email address"
    assert [m["To"] for m in smtp] == ["renamed@example.com"]
