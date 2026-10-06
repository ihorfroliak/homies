"""TASK-015 Slice 4a — message reports, bounded moderator evidence, redaction
(SQLite, through HTTP).

Eligibility (participants only, not one's own or a SYSTEM message, the same
404 for strangers and missing messages), reasons and shared quota, the queue
row, the 2-before/2-after evidence window and its audit, CONTENT_REMOVED
redaction (participants never get the stored body; moderators still do),
NO_ACTION, participant conflict of interest, and privacy canaries. Races and
unknown COMMITs: test_message_moderation_pg.py.
"""

import json
import logging

import pytest
from sqlalchemy import event, func, select

from app.core.audit import AuditLog
from app.modules.alerts.models import UserNotification
from app.modules.engagement.models import Message
from app.modules.engagement.router import MessageOut
from app.modules.events.models import DomainEvent
from app.modules.identity.models import User
from app.modules.trust import moderation, reports
from app.modules.trust.models import ModerationDecision, Report
from tests.conftest import TestingSession, auth, engine, last_code, register_and_login
from tests.test_organizations import _org, _org_property
from tests.test_reports_moderation import OFFER, _keys, _listing, _me, _moderator, _verified

CANARY = "zx-canary-7Q-private-message-body"
TEXT_CANARY = "zx-canary-report-text-91"


def _verify_email(client, token):
    assert client.post("/v1/me/verify/email/start", headers=auth(token)).status_code == 200
    assert client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                       headers=auth(token)).status_code == 200


def _thread(client, extra_messages=0):
    """A listing, its verified owner (provider side), a verified tenant, and
    a conversation: tenant → owner (CANARY) → tenant …"""
    owner, offer = _listing(client)
    _verify_email(client, owner)
    tenant = _verified(client, "tenant")
    started = client.post(f"/v1/classifieds/{offer}/conversations",
                          json={"body": "Dzień dobry, czy aktualne?"}, headers=auth(tenant))
    assert started.status_code == 201, started.text
    conv = started.json()["conversation"]["id"]
    reply = client.post(f"/v1/conversations/{conv}/messages",
                        json={"body": f"Proszę o przelew zaliczki {CANARY}"}, headers=auth(owner))
    assert reply.status_code == 201
    for i in range(extra_messages):
        who = tenant if i % 2 == 0 else owner
        assert client.post(f"/v1/conversations/{conv}/messages", json={"body": f"m{i}"},
                           headers=auth(who)).status_code == 201
    return owner, tenant, offer, conv, reply.json()["id"]


def _report(client, token, message_id, reason="SCAM", text=None):
    body = {"target_type": "MESSAGE", "target_id": message_id, "reason": reason}
    if text is not None:
        body["text"] = text
    return client.post("/v1/reports", json=body, headers=auth(token))


def _decide(client, token, message_id, action, reason, head=None):
    return client.post("/v1/admin/moderation/decisions", json={
        "target_type": "MESSAGE", "target_id": message_id, "action": action,
        "reason_code": reason, "expected_head_decision_id": head}, headers=auth(token))


def _messages(client, token, conv):
    resp = client.get(f"/v1/conversations/{conv}", headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["messages"]


# --- reporting ------------------------------------------------------------------

def test_participants_report_each_others_messages_once(client):
    owner, tenant, _offer, conv, owner_msg = _thread(client)
    tenant_msg = _messages(client, tenant, conv)[0]["id"]
    first = _report(client, tenant, owner_msg, "SCAM")
    assert first.status_code == 201, first.text
    again = _report(client, tenant, owner_msg, "HARASSMENT")
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert _report(client, owner, tenant_msg, "SPAM").status_code == 201
    with TestingSession() as db:
        row = db.scalar(select(Report).where(Report.target_id == owner_msg))
        assert (row.target_type, row.conversation_id, row.severity) == ("MESSAGE", conv, "HIGH")
        assert row.snapshot is None  # no part of the conversation is copied
        assert db.scalar(select(Report.severity).where(Report.target_id == tenant_msg)) == "NORMAL"


def test_strangers_and_missing_messages_get_the_same_404(client):
    _owner, tenant, _offer, _conv, owner_msg = _thread(client)
    stranger = _verified(client, "stranger")
    hidden = _report(client, stranger, owner_msg)
    missing = _report(client, stranger, "00000000-0000-0000-0000-000000000000")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    # BP-12: no verified contact is needed for a MESSAGE report, so an
    # unverified stranger meets the same 404 as any stranger — the exception
    # is not an access bypass, and it reveals nothing about the message.
    plain = register_and_login(client, "plain-s4a@example.com", "guest")
    unverified_stranger = _report(client, plain, owner_msg)
    assert unverified_stranger.status_code == 404
    assert unverified_stranger.json() == missing.json()
    assert _report(client, tenant, owner_msg).status_code == 201
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(Report)) == 1


# --- BP-12: no verified contact for a MESSAGE report (D-105 / OD-7) ----------------


def _unverified_thread(client):
    """A conversation whose two sides have no verified email or phone: a
    tenant who only signed in (messaging needs nothing more) and the owner,
    whose property authority is verified but whose contact is not."""
    owner, offer = _listing(client)
    tenant = register_and_login(client, f"plain-tenant-{_me_count()}@example.com", "guest")
    started = client.post(f"/v1/classifieds/{offer}/conversations",
                          json={"body": "Dzień dobry"}, headers=auth(tenant))
    assert started.status_code == 201, started.text
    conv = started.json()["conversation"]["id"]
    reply = client.post(f"/v1/conversations/{conv}/messages", json={"body": "Proszę o zaliczkę"},
                        headers=auth(owner))
    assert reply.status_code == 201
    tenant_msg = _messages(client, tenant, conv)[0]["id"]
    with TestingSession() as db:
        for uid in (_me(client, owner), _me(client, tenant)):
            user = db.get(User, uid)
            assert user.email_verified_at is None and user.phone_verified_at is None
    return owner, tenant, offer, conv, reply.json()["id"], tenant_msg


_seq = {"n": 0}


def _me_count() -> int:
    _seq["n"] += 1
    return _seq["n"]


def _reports_count() -> int:
    with TestingSession() as db:
        return db.scalar(select(func.count()).select_from(Report)) or 0


def test_an_unverified_side_reports_the_other_sides_message(client):
    owner, tenant, _offer, conv, owner_msg, tenant_msg = _unverified_thread(client)
    by_tenant = _report(client, tenant, owner_msg, "SCAM")
    assert by_tenant.status_code == 201, by_tenant.text
    assert (by_tenant.json()["target_type"], by_tenant.json()["created"]) == ("MESSAGE", True)
    by_provider = _report(client, owner, tenant_msg, "HARASSMENT")
    assert by_provider.status_code == 201, by_provider.text
    with TestingSession() as db:
        row = db.scalar(select(Report).where(Report.target_id == owner_msg))
        assert (row.target_type, row.conversation_id, row.reporter_user_id) == (
            "MESSAGE", conv, _me(client, tenant))
        assert row.snapshot is None  # the message row stays the evidence


def test_an_unverified_side_still_follows_every_other_message_rule(client):
    owner, tenant, _offer, conv, owner_msg, tenant_msg = _unverified_thread(client)
    own = _report(client, tenant, tenant_msg)
    assert own.status_code == 409
    with TestingSession() as db:
        system = Message(conversation_id=conv, message_type="SYSTEM", body="Viewing booked")
        db.add(system)
        db.commit()
        system_id = system.id
    assert _report(client, tenant, system_id).status_code == 409
    assert _report(client, tenant, owner_msg, "OTHER", "za krótko").status_code == 422
    assert _report(client, tenant, owner_msg, "OTHER").status_code == 422
    assert _report(client, tenant, owner_msg, "FAKE").status_code == 422  # a listing reason
    assert _reports_count() == 0

    first = _report(client, tenant, owner_msg, "SPAM")
    again = _report(client, tenant, owner_msg, "SCAM")
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"] and again.json()["created"] is False
    assert _reports_count() == 1
    assert client.post("/v1/reports", json={"target_type": "MESSAGE", "target_id": owner_msg,
                                            "reason": "SCAM"}).status_code == 401


def test_an_unverified_message_reporter_draws_on_the_shared_quota(client, monkeypatch):
    owner, tenant, _offer, conv, owner_msg, _tenant_msg = _unverified_thread(client)
    second = client.post(f"/v1/conversations/{conv}/messages", json={"body": "Drugi raz"},
                         headers=auth(owner)).json()["id"]
    monkeypatch.setattr(reports, "DAILY_LIMIT", 1)
    assert _report(client, tenant, owner_msg).status_code == 201
    capped = _report(client, tenant, second)
    assert capped.status_code == 429
    assert int(capped.headers["Retry-After"]) > 0
    assert _reports_count() == 1


def test_the_listing_gate_stays_for_the_same_unverified_account(client):
    """BP-12 is MESSAGE only: the account that may report a message without a
    verified contact is still refused a LISTING report."""
    _owner, tenant, offer, _conv, owner_msg, _tenant_msg = _unverified_thread(client)
    assert _report(client, tenant, owner_msg).status_code == 201
    listing = client.post("/v1/reports", json={"target_type": "LISTING", "target_id": offer,
                                               "reason": "SCAM"}, headers=auth(tenant))
    assert listing.status_code == 403
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(Report).where(
            Report.target_type == "LISTING")) == 0


def test_own_and_system_messages_are_not_reportable(client):
    owner, tenant, _offer, conv, owner_msg = _thread(client)
    tenant_msg = _messages(client, tenant, conv)[0]["id"]
    own = _report(client, tenant, tenant_msg)
    assert own.status_code == 409 and "own" in own.json()["detail"]
    with TestingSession() as db:
        system = Message(conversation_id=conv, message_type="SYSTEM", body="Viewing booked")
        db.add(system)
        db.commit()
        system_id = system.id
    refused = _report(client, tenant, system_id)
    assert refused.status_code == 409 and "system" in refused.json()["detail"]
    assert _report(client, owner, owner_msg).status_code == 409
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(Report)) == 0


@pytest.mark.parametrize("reason", ["FAKE", "MISLEADING_PRICE", "STOLEN_MEDIA", "DUPLICATE",
                                    "ILLEGAL_CONTENT", "IMPERSONATION"])
def test_listing_and_moderator_reasons_are_not_message_reasons(client, reason):
    _owner, tenant, _offer, _conv, owner_msg = _thread(client)
    assert _report(client, tenant, owner_msg, reason).status_code == 422
    other = client.post("/v1/reports", json={"target_type": "MESSAGE", "target_id": owner_msg,
                                             "reason": "SCAM", "severity": "URGENT"},
                        headers=auth(tenant))
    assert other.status_code == 422


def test_a_hidden_listing_does_not_end_reportability(client):
    owner, tenant, offer, _conv, owner_msg = _thread(client)
    assert client.post(f"/v1/classifieds/{offer}/pause", headers=auth(owner)).status_code == 200
    assert _report(client, tenant, owner_msg, "HARASSMENT").status_code == 201


def test_listing_and_message_reports_share_one_quota(client, monkeypatch):
    monkeypatch.setattr(reports, "DAILY_LIMIT", 2)
    owner, tenant, offer, conv, owner_msg = _thread(client)
    _, other_offer = _listing(client)
    assert client.post("/v1/reports", json={"target_type": "LISTING", "target_id": other_offer,
                                            "reason": "SCAM"},
                       headers=auth(tenant)).status_code == 201
    assert _report(client, tenant, owner_msg).status_code == 201
    second = client.post(f"/v1/conversations/{conv}/messages", json={"body": "again"},
                         headers=auth(owner)).json()["id"]
    assert _report(client, tenant, second).status_code == 429


# --- moderator: queue, evidence --------------------------------------------------

def test_queue_row_for_a_message_carries_ids_only(client):
    _owner, tenant, offer, conv, owner_msg = _thread(client)
    moderator = _moderator(client)
    _report(client, tenant, owner_msg, "HARASSMENT", f"he insulted me {TEXT_CANARY}")
    items = client.get("/v1/admin/moderation/queue", headers=auth(moderator)).json()["items"]
    [row] = [i for i in items if i["target_id"] == owner_msg]
    assert (row["target_type"], row["conversation_id"], row["listing_id"]) == ("MESSAGE", conv,
                                                                              offer)
    assert (row["live_reports"], row["max_severity"], row["held"]) == (1, "HIGH", False)
    flat = json.dumps(items)
    assert CANARY not in flat and TEXT_CANARY not in flat


def test_evidence_is_two_before_target_two_after_and_audited(client):
    owner, tenant, _offer, conv, _first = _thread(client, extra_messages=6)
    ordered = _messages(client, tenant, conv)          # 8 messages, oldest first
    target = ordered[4]
    reporter = owner if target["sender_user_id"] == _me(client, tenant) else tenant
    rid = _report(client, reporter, target["id"], "SPAM").json()["id"]
    moderator = _moderator(client)
    resp = client.get(f"/v1/admin/moderation/targets/MESSAGE/{target['id']}",
                      headers=auth(moderator))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [m["id"] for m in body["evidence"]] == [m["id"] for m in ordered[2:7]]
    assert [m["is_target"] for m in body["evidence"]] == [False, False, True, False, False]
    assert body["conversation"]["id"] == conv
    [report] = body["reports"]
    assert report["id"] == rid and report["status"] == "IN_REVIEW"
    assert not _keys(body) & {"email", "phone", "address", "contact_phone"}
    with TestingSession() as db:
        [entry] = db.scalars(select(AuditLog).where(
            AuditLog.action == "moderation.message_evidence_viewed")).all()
        assert set(entry.data) == {"message_id", "conversation_id", "evidence_message_ids",
                                   "report_ids"}
        assert entry.data["evidence_message_ids"] == [m["id"] for m in ordered[2:7]]
        assert entry.data["report_ids"] == [rid]
    # the edges: the first message has no messages before it
    edge = client.get(f"/v1/admin/moderation/targets/MESSAGE/{ordered[0]['id']}",
                      headers=auth(moderator)).json()
    assert [m["id"] for m in edge["evidence"]] == [m["id"] for m in ordered[0:3]]


def test_evidence_window_reads_five_rows_in_bounded_statements(client):
    _owner, tenant, _offer, conv, _first = _thread(client, extra_messages=10)
    target = _messages(client, tenant, conv)[6]["id"]
    moderator = _moderator(client)
    seen: list[str] = []

    def capture(conn, cursor, statement, *args):
        if "FROM messages" in statement:
            seen.append(statement)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert client.get(f"/v1/admin/moderation/targets/MESSAGE/{target}",
                          headers=auth(moderator)).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    window = [s for s in seen if "ORDER BY" in s]
    assert len(window) == 2 and all("LIMIT" in s for s in window)
    assert len(seen) <= 3  # the target by id + the two bounded neighbours


def test_message_routes_are_moderator_only(client):
    _owner, tenant, _offer, _conv, owner_msg = _thread(client)
    for token in (tenant, register_and_login(client, "h-s4a@example.com", "host")):
        assert client.get(f"/v1/admin/moderation/targets/MESSAGE/{owner_msg}",
                          headers=auth(token)).status_code == 403
        assert _decide(client, token, owner_msg, "CONTENT_REMOVED", "SCAM").status_code == 403
    moderator = _moderator(client)
    assert client.get("/v1/admin/moderation/targets/MESSAGE/00000000-0000-0000-0000-000000000000",
                      headers=auth(moderator)).status_code == 404


# --- decisions and redaction ----------------------------------------------------------

def test_content_removed_redacts_for_participants_and_keeps_the_evidence(client):
    owner, tenant, _offer, conv, owner_msg = _thread(client)
    rid = _report(client, tenant, owner_msg, "SCAM", f"deposit scam {TEXT_CANARY}").json()["id"]
    moderator = _moderator(client)
    resp = _decide(client, moderator, owner_msg, "CONTENT_REMOVED", "SCAM")
    assert resp.status_code == 201, resp.text
    out = resp.json()
    assert out["target_type"] == "MESSAGE" and out["resolved_reports"] == 1
    assert out["listing_status"] is None and out["notified_managers"] == 0
    for token in (tenant, owner):
        [removed] = [m for m in _messages(client, token, conv) if m["id"] == owner_msg]
        assert removed["body"] is None and removed["moderation_state"] == "REMOVED"
        assert CANARY not in json.dumps(_messages(client, token, conv))
    with TestingSession() as db:
        row = db.get(Message, owner_msg)
        assert CANARY in row.body                          # never overwritten
        assert row.redacted_at is not None and row.redaction_reason_code == "SCAM"
        assert db.get(Report, rid).status == "RESOLVED"
    evidence = client.get(f"/v1/admin/moderation/targets/MESSAGE/{owner_msg}",
                          headers=auth(moderator)).json()
    [target] = [m for m in evidence["evidence"] if m["is_target"]]
    assert CANARY in target["body"] and target["redacted_at"] and evidence["removed"]
    # nothing else changed: the conversation stays open, both can still write
    assert client.post(f"/v1/conversations/{conv}/messages", json={"body": "still here"},
                       headers=auth(tenant)).status_code == 201
    assert client.get("/v1/me/inbox", headers=auth(owner)).json()["total"] == 0


def test_no_action_dismisses_and_removal_is_not_reversed(client):
    _owner, tenant, _offer, conv, owner_msg = _thread(client)
    _report(client, tenant, owner_msg, "SPAM")
    moderator = _moderator(client)
    dismissed = _decide(client, moderator, owner_msg, "NO_ACTION", "NOT_A_VIOLATION")
    assert dismissed.status_code == 201
    [kept] = [m for m in _messages(client, tenant, conv) if m["id"] == owner_msg]
    assert kept["moderation_state"] == "NONE" and CANARY in kept["body"]
    head = dismissed.json()["decision_id"]
    assert _decide(client, moderator, owner_msg, "NO_ACTION", "SCAM", head).status_code == 422
    removed = _decide(client, moderator, owner_msg, "CONTENT_REMOVED", "SCAM", head)
    assert removed.status_code == 201
    head = removed.json()["decision_id"]
    for action, reason in (("NO_ACTION", "NOT_A_VIOLATION"),
                           ("NO_ACTION", "REINSTATED_DECISION_ERROR"),
                           ("CONTENT_REMOVED", "SCAM")):
        refused = _decide(client, moderator, owner_msg, action, reason, head)
        assert refused.status_code == 422, (action, reason)
    stale = _decide(client, moderator, owner_msg, "CONTENT_REMOVED", "SCAM", None)
    assert stale.status_code == 409 and stale.json()["detail"].startswith("STALE_HEAD")
    for bad in ("VISIBILITY_LIMITED", "CONTENT_EDIT_REQUIRED"):
        assert _decide(client, moderator, owner_msg, bad, "SCAM", head).status_code == 422


def test_participants_cannot_decide_on_their_conversation(client):
    owner, tenant, _offer, _conv, owner_msg = _thread(client)
    with TestingSession() as db:
        for uid in (_me(client, tenant), _me(client, owner)):
            db.get(User, uid).role = "admin"
        db.commit()
    for token in (tenant, owner):
        refused = _decide(client, token, owner_msg, "CONTENT_REMOVED", "HARASSMENT")
        assert refused.status_code == 403
        assert refused.json()["detail"].startswith("CONFLICT_OF_INTEREST")
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(ModerationDecision)) == 0
    assert _decide(client, _moderator(client), owner_msg, "CONTENT_REMOVED",
                   "HARASSMENT").status_code == 201


def test_a_former_provider_is_not_conflicted_by_history_alone(client):
    boss = register_and_login(client, "boss-s4a@agencja.pl", "host")
    org = _org(client, boss, slug="agencja-s4a")
    prop = _org_property(client, boss, org["id"], address="ul. Wiadomości 4")
    agent = register_and_login(client, "agent-s4a@agencja.pl", "host")
    assert client.post(f"/v1/organizations/{org['id']}/members",
                       json={"email": "agent-s4a@agencja.pl", "role": "AGENT"},
                       headers=auth(boss)).status_code == 202
    assert client.post(f"/v1/organizations/{org['id']}/membership/accept",
                       headers=auth(agent)).status_code == 200
    offer = client.post(f"/v1/properties/{prop['id']}/classifieds", json=OFFER,
                        headers=auth(boss)).json()["id"]
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(boss)).status_code == 200
    tenant = _verified(client, "tenant-org")
    conv = client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "Hej"},
                       headers=auth(tenant)).json()["conversation"]["id"]
    tenant_msg = _messages(client, tenant, conv)[0]["id"]
    agent_msg = client.post(f"/v1/conversations/{conv}/messages", json={"body": "Agent here"},
                            headers=auth(agent)).json()["id"]
    agent_id = _me(client, agent)
    with TestingSession() as db:
        db.get(User, agent_id).role = "admin"
        db.commit()
    assert _decide(client, agent, tenant_msg, "NO_ACTION",
                   "NOT_A_VIOLATION").status_code == 403  # current provider side
    assert client.post(f"/v1/organizations/{org['id']}/members/{agent_id}/revoke",
                       headers=auth(boss)).status_code == 200
    assert client.get(f"/v1/conversations/{conv}", headers=auth(agent)).status_code == 404
    # no current right: history alone does not conflict; their own message does
    assert _decide(client, agent, tenant_msg, "NO_ACTION", "NOT_A_VIOLATION").status_code == 201
    own = _decide(client, agent, agent_msg, "CONTENT_REMOVED", "SPAM")
    assert own.status_code == 403 and "wrote" in own.json()["detail"]


def test_message_out_never_carries_a_redacted_body():
    data = {"id": "m", "sender_user_id": "u", "sender_organization_id": None,
            "message_type": "USER", "body": CANARY, "created_at": "2026-10-02T10:00:00Z",
            "redacted_at": "2026-10-02T11:00:00Z"}
    out = MessageOut.model_validate(data)
    assert out.body is None and out.moderation_state == "REMOVED"
    row = Message(id="m", conversation_id="c", sender_user_id="u", message_type="USER",
                  body=CANARY)
    row.created_at = row.redacted_at = __import__("datetime").datetime(2026, 10, 2)
    assert MessageOut.model_validate(row).body is None
    assert CANARY not in MessageOut.model_validate(row).model_dump_json()


# --- privacy -----------------------------------------------------------------------

def test_bodies_and_report_text_stay_out_of_audit_events_notices_logs_metrics(client, caplog):
    caplog.set_level(logging.DEBUG)
    owner, tenant, _offer, conv, owner_msg = _thread(client, extra_messages=2)
    _report(client, tenant, owner_msg, "HARASSMENT", f"threats {TEXT_CANARY}")
    moderator = _moderator(client)
    client.get(f"/v1/admin/moderation/targets/MESSAGE/{owner_msg}", headers=auth(moderator))
    _decide(client, moderator, owner_msg, "CONTENT_REMOVED", "HARASSMENT")
    with TestingSession() as db:
        written = [
            *(e.data for e in db.scalars(select(AuditLog))),
            *(e.payload for e in db.scalars(select(DomainEvent))),
            *(n.data for n in db.scalars(select(UserNotification))),
        ]
    from prometheus_client import generate_latest
    surfaces = json.dumps(written) + caplog.text + generate_latest().decode()
    surfaces += json.dumps(client.get("/v1/me/reports", headers=auth(tenant)).json())
    surfaces += json.dumps(client.get(f"/v1/classifieds/{_offer}").json())
    for secret in (CANARY, TEXT_CANARY):
        assert secret not in surfaces
    assert moderation.EVIDENCE_AROUND == 2
