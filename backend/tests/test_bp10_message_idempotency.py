"""BP-10 (D-108): idempotent conversation start and message append.

What must hold (proof obligations INV-1…INV-14 of the BP-10 contract; the
PostgreSQL ones — locks, races, COMMIT outcome unknown — live in
test_bp10_message_idempotency_pg.py):

* one logical send writes at most one message, whichever of the two routes
  carries it and however often it is retried (same key → 201, same message);
* the same key with another body or target is 409 IDEMPOTENCY_KEY_REUSED,
  writes nothing, and the original send still replays;
* a replay writes nothing and shows the message as it is now — closed,
  redacted — and an account that lost access gets 404;
* a send committed before a later refusal (closure, G-14, quota, the listing
  withdrawn) still replays, a refused send leaves its key unused;
* the key is never logged, echoed to anyone, or exposed by a database error.

SQLite proves behaviour here, never locking.
"""

import json
import logging
import re
import tokenize
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.audit import AuditLog
from app.core.config import settings
from app.main import app
from app.modules.engagement import router as engagement
from app.modules.engagement.models import Conversation, ConversationParticipant, Message
from app.modules.events.models import DomainEvent
from tests.conftest import TestingSession, admin_login, auth, register_and_login
from tests.test_conversations import _listing as _owner_listing
from tests.test_engagement_safety import _decide as _decide_target
from tests.test_message_moderation import _decide as _decide_message
from tests.test_reports_moderation import _listing, _moderator, _verified

BODY = "Dzień dobry, czy mieszkanie jest dostępne?"


def _key() -> str:
    return str(uuid4())


def _start(client, token, offer, key, body=BODY):
    return client.post(f"/v1/classifieds/{offer}/conversations",
                       json={"body": body, "client_message_id": key}, headers=auth(token))


def _append(client, token, conv, key, body="Tak, zapraszam."):
    return client.post(f"/v1/conversations/{conv}/messages",
                       json={"body": body, "client_message_id": key}, headers=auth(token))


def _count(model, **where) -> int:
    with TestingSession() as db:
        q = select(func.count()).select_from(model)
        for column, value in where.items():
            q = q.where(getattr(model, column) == value)
        return db.scalar(q)


def _instant(value: str) -> datetime:
    """A response timestamp as an instant. Columns are timezone-aware UTC
    (DateTime(timezone=True)) and the app writes UTC; SQLite drops the zone
    when it stores one, so a value read back from it is naive UTC. PostgreSQL
    keeps it — the PG suite compares the strings exactly."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _conv_state(conv_id) -> tuple:
    with TestingSession() as db:
        c = db.get(Conversation, conv_id)
        return (c.status, c.last_message_at, c.updated_at, c.version, c.provider_stage)


@pytest.fixture
def board(client):
    """A public listing, its verified owner, a verified tenant."""
    owner, offer = _listing(client)
    tenant = _verified(client, "bp10-tenant")
    return {"owner": owner, "tenant": tenant, "offer": offer}


def _thread(client, board, key=None):
    key = key or _key()
    resp = _start(client, board["tenant"], board["offer"], key)
    assert resp.status_code == 201, resp.text
    return resp.json()["conversation"]["id"], resp.json()["messages"][0]["id"], key


# --- T1 same key, same request: one message, the same 201 -----------------------------------


def test_t1_a_repeated_start_is_one_message_and_the_same_answer(client, board):
    key = _key()
    first = _start(client, board["tenant"], board["offer"], key)
    again = _start(client, board["tenant"], board["offer"], key)
    assert first.status_code == again.status_code == 201
    one, two = first.json(), again.json()
    assert two["conversation"]["id"] == one["conversation"]["id"]
    assert [m["id"] for m in two["messages"]] == [m["id"] for m in one["messages"]]
    assert _instant(two["messages"][0]["created_at"]) == \
        _instant(one["messages"][0]["created_at"])
    assert _count(Message, client_message_id=key) == 1
    assert _count(Conversation) == 1


def test_t1_a_repeated_append_is_one_message_and_the_same_answer(client, board):
    conv, _m, _k = _thread(client, board)
    key = _key()
    first = _append(client, board["owner"], conv, key)
    again = _append(client, board["owner"], conv, key)
    assert first.status_code == again.status_code == 201
    one, two = first.json(), again.json()
    assert _instant(two.pop("created_at")) == _instant(one.pop("created_at"))
    assert two == one  # id, sender, type, body, moderation state
    assert _count(Message, client_message_id=key) == 1


def test_one_namespace_a_start_retried_as_an_append_replays(client, board):
    """The client lost the start's response, re-read the thread and sent the
    same draft by appending — the same logical send: a replay, not a 409."""
    conv, message_id, key = _thread(client, board)
    replay = _append(client, board["tenant"], conv, key, BODY)
    assert replay.status_code == 201 and replay.json()["id"] == message_id
    assert _count(Message, client_message_id=key) == 1


def test_one_namespace_an_append_retried_as_a_start_replays(client, board):
    conv, _m, _k = _thread(client, board)
    key = _key()
    sent = _append(client, board["tenant"], conv, key, "Drugie pytanie")
    assert sent.status_code == 201
    replay = _start(client, board["tenant"], board["offer"], key, "Drugie pytanie")
    assert replay.status_code == 201
    assert replay.json()["conversation"]["id"] == conv
    assert [m["id"] for m in replay.json()["messages"]] == [sent.json()["id"]]
    assert _count(Message, client_message_id=key) == 1


# --- T2 same key, different request: 409, nothing written, the original intact -------------


def _untouched(conv) -> tuple:
    """Everything a send could write besides the message itself."""
    return (_count(Message), _count(Conversation), _count(ConversationParticipant),
            _count(AuditLog), _count(DomainEvent), _conv_state(conv))


def test_t2_the_same_key_with_another_body_is_refused(client, board):
    conv, message_id, key = _thread(client, board)
    before = _untouched(conv)
    conflicts = {r: _idempotency(r, "conflict") for r in ("start", "append")}
    for resp in (_start(client, board["tenant"], board["offer"], key, "Coś innego"),
                 _append(client, board["tenant"], conv, key, "Coś innego")):
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"].startswith("IDEMPOTENCY_KEY_REUSED: ")
    assert _untouched(conv) == before
    assert {r: _idempotency(r, "conflict") for r in conflicts} == \
        {r: n + 1 for r, n in conflicts.items()}
    # the original send still replays with its own key
    retry = _start(client, board["tenant"], board["offer"], key)
    assert retry.status_code == 201 and retry.json()["messages"][0]["id"] == message_id


def test_t2_the_same_key_for_another_conversation_or_listing_is_refused(client, board):
    conv, _m, key = _thread(client, board)
    other_owner, other_offer = _listing(client)
    other = _start(client, board["tenant"], other_offer, _key()).json()["conversation"]["id"]
    before, other_before = _untouched(conv), _conv_state(other)
    to_listing = _start(client, board["tenant"], other_offer, key)
    to_conversation = _append(client, board["tenant"], other, key, BODY)
    for resp in (to_listing, to_conversation):
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"].startswith("IDEMPOTENCY_KEY_REUSED: ")
    assert _untouched(conv) == before and _conv_state(other) == other_before
    assert _append(client, board["tenant"], conv, key, BODY).status_code == 201  # still replays


def test_t2_a_start_cannot_replay_a_message_the_caller_sent_in_someone_elses_thread(
        client, board):
    """The owner's append key reused on start: the stored conversation's
    requester is not the caller — 409, never OWN_LISTING or a new thread."""
    conv, _m, _k = _thread(client, board)
    key = _key()
    assert _append(client, board["owner"], conv, key, BODY).status_code == 201
    resp = _start(client, board["owner"], board["offer"], key, BODY)
    assert resp.status_code == 409
    assert resp.json()["detail"].startswith("IDEMPOTENCY_KEY_REUSED: ")


# --- T3 different keys: different messages, whatever the body -------------------------------


def test_t3_two_keys_with_the_same_body_are_two_messages(client, board):
    conv, _m, _k = _thread(client, board)
    a = _append(client, board["tenant"], conv, _key(), "ok")
    b = _append(client, board["tenant"], conv, _key(), "ok")
    assert a.status_code == b.status_code == 201 and a.json()["id"] != b.json()["id"]
    assert _count(Message, conversation_id=conv, body="ok") == 2


def test_another_account_with_the_same_uuid_sends_its_own_message(client, board):
    """INV-7: keys are scoped to the sender — no replay, no leak, no 409."""
    conv, message_id, key = _thread(client, board)
    other = _verified(client, "bp10-other")
    resp = _start(client, other, board["offer"], key)
    assert resp.status_code == 201
    assert resp.json()["conversation"]["id"] != conv
    assert resp.json()["messages"][0]["id"] != message_id
    assert _count(Message, client_message_id=key) == 2


# --- T9/T11 committed then lost; refused leaves the key unused ------------------------------


def test_t9_a_committed_send_whose_answer_was_lost_replays(client, board):
    conv, _m, _k = _thread(client, board)
    key = _key()
    with TestingSession() as db:  # the route ran and committed; the HTTP answer never arrived
        user = db.get(engagement.User, _me(client, board["owner"]))
        engagement.send_message(conv, engagement.MessageIn(body="Tak", client_message_id=key),
                                user, db)
    retry = _append(client, board["owner"], conv, key, "Tak")
    assert retry.status_code == 201
    assert _count(Message, client_message_id=key) == 1


def test_t11_a_refused_send_does_not_use_its_key(client, board, monkeypatch):
    conv, _m, _k = _thread(client, board)
    key = _key()
    # quota refusal (a new thread), then the same key sends once allowed
    _o, other_offer = _listing(client)
    monkeypatch.setattr(settings, "conversation_daily_quota", 1)
    refused = _start(client, board["tenant"], other_offer, key)
    assert refused.status_code == 429 and _count(Message, client_message_id=key) == 0
    monkeypatch.setattr(settings, "conversation_daily_quota", 30)
    assert _start(client, board["tenant"], other_offer, key).status_code == 201
    # closed conversation refusal, then the same key elsewhere
    with TestingSession() as db:
        db.get(Conversation, conv).status = "CLOSED"
        db.commit()
    second = _key()
    closed = _append(client, board["tenant"], conv, second)
    assert closed.status_code == 409 and closed.json()["detail"].startswith("CONVERSATION_CLOSED")
    assert _count(Message, client_message_id=second) == 0
    other_conv = _start(client, board["tenant"], other_offer, _key()).json()["conversation"]["id"]
    assert _append(client, board["tenant"], other_conv, second).status_code == 201


# --- T13–T16 the world changed after the send committed --------------------------------------


def test_t13_a_send_committed_before_closure_replays_on_both_routes(client, board):
    conv, _m, _k = _thread(client, board)
    key = _key()
    sent = _append(client, board["tenant"], conv, key, BODY).json()
    moderator = _moderator(client)
    closed = _decide_target(client, moderator, "CONVERSATION", conv, "FEATURE_RESTRICTED",
                            "HARASSMENT")
    assert closed.status_code == 201, closed.text
    via_append = _append(client, board["tenant"], conv, key, BODY)
    assert via_append.status_code == 201 and via_append.json()["id"] == sent["id"]
    via_start = _start(client, board["tenant"], board["offer"], key)  # not RECONTACT_BLOCKED
    assert via_start.status_code == 201, via_start.text
    assert via_start.json()["conversation"]["status"] == "CLOSED"
    assert [m["id"] for m in via_start.json()["messages"]] == [sent["id"]]
    # a new send is refused as before
    blocked = _start(client, board["tenant"], board["offer"], _key())
    assert blocked.status_code == 409 and blocked.json()["detail"].startswith(
        "RECONTACT_BLOCKED")


def test_t14_a_provider_who_lost_the_right_gets_404_on_a_retry(client):
    """FD-6: current access outranks replay — the key is no capability."""
    owner = register_and_login(client, "bp10-revoked-owner@example.com", "host")
    tenant = register_and_login(client, "bp10-revoked-tenant@example.com", "guest")
    prop, offer = _owner_listing(client, owner, "ul. Odebrana 1")
    conv = _start(client, tenant, offer, _key()).json()["conversation"]["id"]
    key = _key()
    assert _append(client, owner, conv, key).status_code == 201
    admin = admin_login(client)
    authority_id = client.get(f"/v1/admin/properties/{prop['id']}/authorities",
                              headers=auth(admin)).json()[0]["id"]
    assert client.post(f"/v1/admin/property-authorities/{authority_id}/revoke",
                       headers=auth(admin)).status_code == 200
    before = _untouched(conv)
    retry = _append(client, owner, conv, key)
    assert retry.status_code == 404
    assert retry.json()["detail"] == "Conversation not found"  # nothing about the key
    # Through start the key resolves to someone else's thread: 409, no thread opened.
    via_start = _start(client, owner, offer, key, "Tak, zapraszam.")
    assert via_start.status_code == 409
    assert via_start.json()["detail"].startswith("IDEMPOTENCY_KEY_REUSED: ")
    assert _untouched(conv) == before


def test_t15_a_redacted_message_replays_without_its_body(client, board):
    conv, _m, _k = _thread(client, board)
    key = _key()
    secret = f"Proszę o przelew zaliczki {uuid4().hex}"
    sent = _append(client, board["owner"], conv, key, secret).json()
    moderator = _moderator(client)
    assert _decide_message(client, moderator, sent["id"], "CONTENT_REMOVED",
                           "SCAM").status_code == 201
    retry = _append(client, board["owner"], conv, key, secret)
    assert retry.status_code == 201, retry.text
    out = retry.json()
    assert (out["id"], out["body"], out["moderation_state"]) == (sent["id"], None, "REMOVED")
    assert secret not in retry.text
    assert _count(Message, client_message_id=key) == 1


def test_t15_a_redacted_first_message_replays_without_its_body_through_start(client, board):
    secret = f"Przelej zaliczkę {uuid4().hex}"
    key = _key()
    conv, message_id, _k = _thread(client, board, key)
    moderator = _moderator(client)
    with TestingSession() as db:  # the start's message carries the secret
        db.get(Message, message_id).body = secret
        db.commit()
    assert _decide_message(client, moderator, message_id, "CONTENT_REMOVED",
                           "SCAM").status_code == 201
    retry = _start(client, board["tenant"], board["offer"], key, secret)
    assert retry.status_code == 201, retry.text
    [shown] = retry.json()["messages"]
    assert (shown["id"], shown["body"], shown["moderation_state"]) == (message_id, None,
                                                                       "REMOVED")
    assert secret not in retry.text


def test_t16_a_start_committed_before_the_listing_was_withdrawn_replays(client, board):
    key = _key()
    conv, message_id, _k = _thread(client, board, key)
    assert client.post(f"/v1/classifieds/{board['offer']}/pause",
                       headers=auth(board["owner"])).status_code == 200
    assert _start(client, board["tenant"], board["offer"], _key()).status_code == 404
    retry = _start(client, board["tenant"], board["offer"], key)
    assert retry.status_code == 201, retry.text
    assert retry.json()["conversation"]["id"] == conv
    assert retry.json()["messages"][0]["id"] == message_id


# --- T17–T21 a replay changes nothing --------------------------------------------------------


def test_t17_t18_t20_a_replay_writes_nothing(client, board):
    key = _key()
    conv, _m, _k = _thread(client, board, key)
    audits = _count(AuditLog, action="conversation.started")
    events = _count(DomainEvent)
    participants = _count(ConversationParticipant, conversation_id=conv)
    state = _conv_state(conv)
    for _ in range(3):
        assert _start(client, board["tenant"], board["offer"], key).status_code == 201
        assert _append(client, board["tenant"], conv, key, BODY).status_code == 201
    assert audits == _count(AuditLog, action="conversation.started") == 1
    assert _count(DomainEvent) == events
    assert _count(ConversationParticipant, conversation_id=conv) == participants
    assert _conv_state(conv) == state  # status, last_message_at, updated_at, version, stage
    assert _count(Message, conversation_id=conv) == 1


def test_t19_a_providers_first_reply_moves_the_lead_once(client, board):
    conv, _m, _k = _thread(client, board)
    key = _key()
    assert _append(client, board["owner"], conv, key).status_code == 201
    assert _conv_state(conv)[4] == "REPLIED"
    assert client.post(f"/v1/conversations/{conv}/stage", json={"provider_stage": "VIEWING"},
                       headers=auth(board["owner"])).status_code == 200
    state = _conv_state(conv)
    assert _append(client, board["owner"], conv, key).status_code == 201
    assert _conv_state(conv) == state  # still VIEWING; nothing touched


def test_t21_a_committed_start_replays_past_the_quota(client, board, monkeypatch):
    monkeypatch.setattr(settings, "conversation_daily_quota", 1)
    key = _key()
    conv, _m, _k = _thread(client, board, key)
    retry = _start(client, board["tenant"], board["offer"], key)
    assert retry.status_code == 201 and retry.json()["conversation"]["id"] == conv
    _o, other_offer = _listing(client)
    fresh = _start(client, board["tenant"], other_offer, _key())
    assert fresh.status_code == 429 and fresh.json()["detail"].startswith("CONVERSATION_QUOTA")


# --- T23 the key itself --------------------------------------------------------------------


@pytest.mark.parametrize("route", ["start", "append"])
@pytest.mark.parametrize("value", [None, "", "not-a-uuid", "12345",
                                   str(uuid.uuid1()), "00000000-0000-0000-0000-000000000000"])
def test_t23_a_missing_or_non_v4_key_is_refused(client, board, value, route):
    conv, _m, _k = _thread(client, board)
    url = (f"/v1/classifieds/{board['offer']}/conversations" if route == "start"
           else f"/v1/conversations/{conv}/messages")
    payload = {"body": BODY} if value is None else {"body": BODY, "client_message_id": value}
    before = _count(Message)
    resp = client.post(url, json=payload, headers=auth(board["tenant"]))
    assert resp.status_code == 422
    assert ["body", "client_message_id"] in [e["loc"] for e in resp.json()["detail"]]
    assert _count(Message) == before


def test_t23_other_spellings_of_one_uuid_are_one_key(client, board):
    raw = uuid4()
    conv, message_id, _k = _thread(client, board, str(raw).upper())
    with TestingSession() as db:
        stored = db.scalar(select(Message.client_message_id).where(Message.id == message_id))
    assert stored == str(raw)  # canonical: lowercase, hyphenated
    for spelling in (raw.hex, "{" + str(raw) + "}", f"urn:uuid:{raw}", str(raw)):
        again = _start(client, board["tenant"], board["offer"], spelling)
        assert again.status_code == 201 and again.json()["messages"][0]["id"] == message_id
    assert _count(Message, client_message_id=str(raw)) == 1


# --- T24 privacy: never echoed, never logged -------------------------------------------------


def test_t24_the_key_is_never_shown_to_anyone(client, board):
    key, reply_key = _key(), _key()
    first = _start(client, board["tenant"], board["offer"], key)
    conv = first.json()["conversation"]["id"]
    reply = _append(client, board["owner"], conv, reply_key)
    shown = [first.text, reply.text,
             _start(client, board["tenant"], board["offer"], key).text,
             _append(client, board["tenant"], conv, key, BODY).text]
    for token in (board["tenant"], board["owner"]):
        shown.append(client.get(f"/v1/conversations/{conv}", headers=auth(token)).text)
        shown.append(client.get("/v1/conversations", headers=auth(token)).text)
    # moderation: a report on the message and the moderator's evidence view
    report = client.post("/v1/reports", json={"target_type": "MESSAGE",
                                              "target_id": reply.json()["id"],
                                              "reason": "SCAM"},
                         headers=auth(board["tenant"]))
    assert report.status_code == 201, report.text
    moderator = _moderator(client)
    evidence = client.get(f"/v1/admin/moderation/targets/MESSAGE/{reply.json()['id']}",
                          headers=auth(moderator))
    assert evidence.status_code == 200, evidence.text
    shown += [report.text, evidence.text]
    for text_ in shown:
        assert key not in text_ and reply_key not in text_
        assert "client_message_id" not in text_


def test_t24_a_refused_reuse_logs_neither_body_nor_key(client, board, caplog):
    conv, _m, key = _thread(client, board)
    secret = f"tajne {uuid4().hex}"
    with caplog.at_level(logging.DEBUG):
        resp = _append(client, board["tenant"], conv, key, secret)
    assert resp.status_code == 409
    assert secret not in resp.text and key not in resp.text
    assert secret not in caplog.text and key not in caplog.text


class _Orig(Exception):
    """A driver error whose text carries the failing row, as PostgreSQL's
    DETAIL does (`Failing row contains (…, body, key)`)."""

    def __init__(self, detail):
        super().__init__(detail)
        self.sqlstate = "23514"
        self.diag = SimpleNamespace(constraint_name="ck_messages_user_message_has_sender")


def test_t24_an_unexpected_integrity_error_is_sanitized(client, board, monkeypatch, caplog):
    """INV-12 / L4-7: an integrity failure that is not the key's own race
    leaves the route as a sanitized error — not its DETAIL, not the original
    exception — and nothing is logged but SQLSTATE and constraint."""
    conv, _m, _k = _thread(client, board)
    key, secret = _key(), f"sekret {uuid4().hex}"

    def failing_post(db, user, conv_, side, body, client_message_id):
        raise IntegrityError("INSERT INTO messages …", {"body": body},
                             _Orig(f"Failing row contains ({body}, {client_message_id})"))

    monkeypatch.setattr(engagement, "_post", failing_post)
    with caplog.at_level(logging.DEBUG), TestClient(app, raise_server_exceptions=False) as raw:
        resp = _append(raw, board["tenant"], conv, key, secret)
        start = _start(raw, board["tenant"], board["offer"], _key(), secret)
    assert resp.status_code == start.status_code == 500
    for text_ in (resp.text, start.text, caplog.text):
        assert secret not in text_ and key not in text_ and "Failing row" not in text_
    assert "constraint=ck_messages_user_message_has_sender" in caplog.text
    assert "integrity: ck_messages_user_message_has_sender" in caplog.text
    assert _count(Message, client_message_id=key) == 0

    # The raised error carries no chained original (no DETAIL in any traceback).
    with TestingSession() as db:
        user = db.get(engagement.User, _me(client, board["tenant"]))
        with pytest.raises(RuntimeError) as caught:
            engagement.send_message(conv, engagement.MessageIn(body=secret,
                                                               client_message_id=key), user, db)
    assert str(caught.value) == "integrity: ck_messages_user_message_has_sender"
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_a_lost_unique_race_on_sqlite_is_answered_with_the_winner(client, board, monkeypatch):
    """The recovery path itself (functional; the real race is proven on
    PostgreSQL): a send whose INSERT lost to an already committed message of
    the same key is rolled back whole and replays the winner."""
    conv, _m, _k = _thread(client, board)
    key = _key()
    winner = _append(client, board["tenant"], conv, key, BODY).json()
    real_keyed = engagement._keyed
    calls = {"n": 0}

    def blind_first_lookup(db, user_id, client_message_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_keyed(db, user_id, client_message_id)

    monkeypatch.setattr(engagement, "_keyed", blind_first_lookup)
    metric = {o: _idempotency("append", o) for o in ("replay", "race_recovered", "conflict")}
    resp = _append(client, board["tenant"], conv, key, BODY)
    assert resp.status_code == 201 and resp.json()["id"] == winner["id"]
    assert _count(Message, client_message_id=key) == 1
    assert _idempotency("append", "race_recovered") == metric["race_recovered"] + 1
    assert _idempotency("append", "replay") == metric["replay"]
    assert _idempotency("append", "conflict") == metric["conflict"]


def _idempotency(route: str, outcome: str) -> float:
    from prometheus_client import REGISTRY

    value = REGISTRY.get_sample_value("homies_message_idempotency_total",
                                      {"route": route, "outcome": outcome})
    return 0.0 if value is None else value


# --- T28 (unit half) the advisory key ---------------------------------------------------------


def test_t28_the_lock_key_is_a_signed_int4_of_sender_and_key_only():
    for n in range(2000):
        obj = engagement.send_lock_key(f"user-{n}", str(uuid.UUID(int=n, version=4)))
        assert -(2 ** 31) <= obj < 2 ** 31
    # Known answer, pinning the contract's formula: SHA-256 of
    # b"bp10.message-send\0" + user id + b"\0" + key, first 4 bytes, big-endian, signed.
    assert engagement.send_lock_key("bp10-user", "00000000-0000-4000-8000-000000000001") \
        == 1551370989 == int.from_bytes(bytes.fromhex("5c780aed"), "big", signed=True)
    assert engagement.SEND_LOCK_CLASS == 0x42503130  # "BP10"
    assert engagement.send_lock_key("u", "k") == engagement.send_lock_key("u", "k")
    assert engagement.send_lock_key("u", "k") != engagement.send_lock_key("v", "k")
    assert -(2 ** 31) <= engagement.SEND_LOCK_CLASS < 2 ** 31


_ADVISORY_NAME = re.compile(r"\bpg_(?:try_)?advisory_\w+\s*\(")


def _calls_in(sql: str):
    """`pg_…advisory…(…)` calls in `sql`, each with its balanced argument list."""
    for match in _ADVISORY_NAME.finditer(sql):
        depth, end = 0, match.end() - 1
        for end in range(match.end() - 1, len(sql)):
            depth += {"(": 1, ")": -1}.get(sql[end], 0)
            if depth == 0:
                break
        yield sql[match.start():end + 1]


def _advisory_calls() -> dict[str, list[str]]:
    """Every PostgreSQL advisory-lock call the application executes: SQL
    lives in string literals, so string tokens are scanned (comments are not
    tokens of that kind) for a function *call* — prose that only names a
    function has no argument list."""
    from pathlib import Path

    app_dir = Path(engagement.__file__).resolve().parents[2]
    calls: dict[str, list[str]] = {}
    for path in sorted(app_dir.rglob("*.py")):
        with path.open("rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if token.type != tokenize.STRING:
                    continue
                for call in _calls_in(token.string):
                    rel = str(path.relative_to(app_dir)).replace("\\", "/")
                    calls.setdefault(rel, []).append(call)
    return calls


def test_t28_the_lock_class_is_the_repositorys_only_two_int_advisory_class():
    """Only two places take advisory locks: BP-10's send lock, in the
    (int4, int4) key space with explicit casts, and the migration job's lock,
    a single bigint key — a disjoint key space (probe P8). So no other
    two-int class exists that the BP-10 class could collide with."""
    calls = _advisory_calls()
    assert calls == {
        "modules/engagement/router.py": [
            "pg_advisory_xact_lock(CAST(:cls AS integer), CAST(:obj AS integer))"],
        "scripts/migrate.py": ["pg_try_advisory_lock(:k)", "pg_advisory_unlock(:k)"],
    }
    two_int = [c for found in calls.values() for c in found if "," in c]
    assert two_int == ["pg_advisory_xact_lock(CAST(:cls AS integer), CAST(:obj AS integer))"]
    from app.scripts import migrate

    assert isinstance(migrate.LOCK_KEY, int) and not -(2 ** 31) <= migrate.LOCK_KEY < 2 ** 31


def _me(client, token) -> str:
    return client.get("/v1/me", headers=auth(token)).json()["id"]


def test_the_stored_body_not_the_projection_decides_a_match(client, board):
    """A redacted message's projection has no body; an honest retry still
    matches the stored body (and a different one still conflicts)."""
    conv, _m, _k = _thread(client, board)
    key = _key()
    sent = _append(client, board["tenant"], conv, key, "do usunięcia").json()
    with TestingSession() as db:
        db.get(Message, sent["id"]).redacted_at = db.get(Message, sent["id"]).created_at
        db.commit()
    assert _append(client, board["tenant"], conv, key, "do usunięcia").status_code == 201
    assert _append(client, board["tenant"], conv, key, "inne").status_code == 409
    assert json.loads(_append(client, board["tenant"], conv, key,
                              "do usunięcia").text)["body"] is None
