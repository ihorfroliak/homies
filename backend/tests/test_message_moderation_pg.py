"""TASK-015 Slice 4a on PostgreSQL: message reports and redaction under real
locks.

M-R1 duplicate report race · M-R2 reporting while the reporter's provider
authority is revoked · M-R3 two moderators decide · M-R4 redaction vs a
participant's read · M-R5 rolled-back decision · M-R6 decision COMMIT outcome
unknown (PR-003 proxy, both branches) · M-R7 a conflicted moderator · M-R8 the
evidence window is fixed by id and stays inside its conversation.

Waits are proven with `pg_blocking_pids` (`_blocked_on`); critical sections
call the services and route functions on their own sessions.
"""

import time
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text

from app.modules.admin import router as admin_router
from app.modules.engagement import router as conversations
from app.modules.trust import decisions, moderation, reports
from app.modules.trust import router as trust_router
from tests.conftest import TEST_DATABASE_URL, auth, last_code, register_and_login
from tests.test_publication_authority_race_pg import _blocked_on
from tests.test_publication_race_pg import _authority_id
from tests.test_reports_moderation_pg import (
    _account,
    _deadlocks,
    _listing,
    _pid,
    _run,
    _scalar,
    _session,
    _user,
)
from tests.test_conversations import send_json

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

CANARY = "zx-canary-pg-private-body"
_n = {"i": 0}


def _verify(pg_client, token):
    assert pg_client.post("/v1/me/verify/email/start", headers=auth(token)).status_code == 200
    assert pg_client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                          headers=auth(token)).status_code == 200


def _thread(pg_client):
    """(owner_email, tenant_email, offer, conversation, owner's message, tenant's message)"""
    _n["i"] += 1
    owner_email, owner, offer = _listing(pg_client)
    _verify(pg_client, owner)
    tenant_email = f"s4a-pg-tenant-{_n['i']}@example.com"
    tenant = register_and_login(pg_client, tenant_email, "guest")
    _verify(pg_client, tenant)
    started = pg_client.post(f"/v1/classifieds/{offer}/conversations", json=send_json("Hej"),
                             headers=auth(tenant))
    assert started.status_code == 201, started.text
    conv = started.json()["conversation"]["id"]
    tenant_msg = started.json()["messages"][0]["id"]
    owner_msg = pg_client.post(f"/v1/conversations/{conv}/messages",
                               json=send_json(f"Wire the deposit {CANARY}"),
                               headers=auth(owner)).json()["id"]
    return owner_email, tenant_email, offer, conv, owner_msg, tenant_msg


def _file(engine, reporter, message_id, category="SCAM"):
    with _session(engine) as db:
        filed = reports.file_message_report(db, reporter=_user(db, reporter),
                                            message_id=message_id, category=category, text=None)
        db.commit() if filed.created else db.rollback()
        return filed.report.id, filed.created


def _remove(db, message_id, moderator, expected=None, action="CONTENT_REMOVED", reason="SCAM"):
    return decisions.apply_message_decision(
        db, actor=_user(db, moderator), message_id=message_id, action=action,
        reason_code=reason, expected_head_decision_id=expected)


def _message(engine, message_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT body, redacted_at FROM messages WHERE id = :m"),
                            {"m": message_id}).one()


def _decisions(engine, message_id):
    return _scalar(engine, "SELECT count(*) FROM moderation_decisions WHERE target_id = :m",
                   m=message_id)


def _participant_body(engine, conv, reader, message_id):
    with _session(engine) as db:
        detail = conversations.read_conversation(conv, user=_user(db, reader), db=db)
        [m] = [m for m in detail.messages if m.id == message_id]
        return m.body, m.moderation_state


# --- M-R1 ------------------------------------------------------------------------------

def test_m_r1_two_simultaneous_reports_make_one(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, tenant, _offer, _conv, owner_msg, _t = _thread(pg_client)
    holder = _session(eng)
    holder.execute(text("SELECT id FROM users WHERE email = :e FOR NO KEY UPDATE"),
                   {"e": tenant})
    result: dict = {}
    try:
        threads = [_run(result, k, lambda: _file(eng, tenant, owner_msg)) for k in ("a", "b")]
        assert _blocked_on(eng, "users", _pid(holder))
    finally:
        holder.rollback()
        holder.close()
    for t in threads:
        t.join(15)
    outcomes = sorted([result["a"], result["b"]], key=lambda r: not r[1])
    assert [c for _i, c in outcomes] == [True, False] and outcomes[0][0] == outcomes[1][0]
    assert _scalar(eng, "SELECT count(*) FROM reports WHERE target_id = :m AND status IN "
                        "('OPEN','IN_REVIEW')", m=owner_msg) == 1


# --- M-R2 ------------------------------------------------------------------------------

def test_m_r2_a_right_revoked_before_the_decision_point_refuses_the_report(
        pg_client, pg_migrated_engine):
    """The provider (owner) reports the tenant's message while an admin
    revokes the owner's authority. The access is re-read after the reporter
    lock is granted: a revoke committed by then wins."""
    eng = pg_migrated_engine
    owner, _tenant, offer, _conv, _om, tenant_msg = _thread(pg_client)
    prop = _scalar(eng, "SELECT property_id FROM classified_offers WHERE id = :o", o=offer)
    aid = _authority_id(eng, prop)
    admin = _account(eng, role="admin")
    holder = _session(eng)
    holder.execute(text("SELECT id FROM users WHERE email = :e FOR NO KEY UPDATE"),
                   {"e": owner})
    result: dict = {}
    try:
        t = _run(result, "r", lambda: _file(eng, owner, tenant_msg, "HARASSMENT"))
        assert _blocked_on(eng, "users", _pid(holder))  # past the first access check
        with _session(eng) as r:
            admin_router.revoke_property_authority(aid, admin=_user(r, admin), db=r)
    finally:
        holder.rollback()
        holder.close()
    t.join(15)
    assert isinstance(result["r"], reports.NotReportable)
    assert _scalar(eng, "SELECT count(*) FROM reports WHERE target_id = :m", m=tenant_msg) == 0


# --- M-R3 ------------------------------------------------------------------------------

def test_m_r3_two_moderators_one_successor(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, tenant, _offer, _conv, owner_msg, _t = _thread(pg_client)
    _file(eng, tenant, owner_msg)
    m1, m2 = _account(eng, role="admin"), _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        first = _remove(a, owner_msg, m1)
        b = _session(eng)

        def second():
            try:
                return _remove(b, owner_msg, m2)
            finally:
                b.rollback()
                b.close()
        t = _run(result, "b", second)
        assert _blocked_on(eng, "conversations", _pid(a))
        a.commit()
        t.join(15)
    finally:
        a.close()
    assert isinstance(result["b"], decisions.StaleHead)
    assert result["b"].current_head_id == first.decision_id
    assert _decisions(eng, owner_msg) == 1


# --- M-R4 ------------------------------------------------------------------------------

def test_m_r4_after_the_redaction_commits_no_read_returns_the_body(pg_client,
                                                                   pg_migrated_engine):
    eng = pg_migrated_engine
    owner, tenant, _offer, conv, owner_msg, _t = _thread(pg_client)
    mod = _account(eng, role="admin")
    d = _session(eng)
    try:
        _remove(d, owner_msg, mod)
        # read committed: a read before the commit sees the committed state —
        # the message as it was (documented; not a leak of a removal yet to be)
        body, state = _participant_body(eng, conv, tenant, owner_msg)
        assert CANARY in body and state == "NONE"
        d.commit()
    finally:
        d.close()
    for reader in (tenant, owner):
        assert _participant_body(eng, conv, reader, owner_msg) == (None, "REMOVED")
    assert CANARY in _message(eng, owner_msg).body


# --- M-R5 ------------------------------------------------------------------------------

def test_m_r5_a_rolled_back_decision_leaves_nothing(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, tenant, _offer, conv, owner_msg, _t = _thread(pg_client)
    rid, _ = _file(eng, tenant, owner_msg)
    mod = _account(eng, role="admin")
    events_before = _scalar(eng, "SELECT count(*) FROM domain_events")
    with _session(eng) as db:
        applied = _remove(db, owner_msg, mod)
        db.flush()
        assert db.scalar(text("SELECT redacted_at FROM messages WHERE id = :m"),
                         {"m": owner_msg}) is not None
        db.rollback()
    assert _message(eng, owner_msg).redacted_at is None
    assert _decisions(eng, owner_msg) == 0
    assert _scalar(eng, "SELECT status FROM reports WHERE id = :r", r=rid) == "OPEN"
    assert _scalar(eng, "SELECT count(*) FROM audit_log WHERE data::text LIKE :d",
                   d=f"%{applied.decision_id}%") == 0
    assert _scalar(eng, "SELECT count(*) FROM domain_events") == events_before
    assert _participant_body(eng, conv, tenant, owner_msg)[1] == "NONE"


# --- M-R6 ------------------------------------------------------------------------------

@pytest.mark.parametrize("branch", ["committed", "rolled_back"])
def test_m_r6_unknown_decision_commit_redacts_exactly_once(pg_client, pg_migrated_engine,
                                                            branch):
    from sqlalchemy.engine import make_url

    from app.core import db as core_db
    from app.core.db_failures import unavailability_reason
    from tests.pg_fault_proxy import FreezableProxy
    from tests.test_db_deadlines_pg import DEADLINE_S, FAST, SLACK_S, _bounded

    eng = pg_migrated_engine
    _o, tenant, _offer, _conv, owner_msg, _t = _thread(pg_client)
    _file(eng, tenant, owner_msg)
    mod = _account(eng, role="admin")
    target = make_url(TEST_DATABASE_URL)
    proxy = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    pe = core_db.create_bounded_engine(proxy.url(), deadlines=FAST, pool_size=1, max_overflow=0)
    try:
        s = _session(pe)
        first = _remove(s, owner_msg, mod)
        server_pid = _pid(s)
        proxy.freeze_on = b"COMMIT"
        outcome, _took = _bounded(s.commit, DEADLINE_S + SLACK_S + 3)
        assert unavailability_reason(outcome) == "commit_unknown", outcome
        if branch == "rolled_back":
            with eng.connect() as admin:
                admin.execute(text("SELECT pg_terminate_backend(:p)"), {"p": server_pid})
        proxy.resume()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            done = _decisions(eng, owner_msg) == 1
            gone = not _scalar(eng, "SELECT count(*) FROM pg_stat_activity WHERE pid = :p",
                               p=server_pid)
            if (branch == "committed" and done) or (branch == "rolled_back" and gone):
                break
            time.sleep(0.05)
        if branch == "committed":
            assert _message(eng, owner_msg).redacted_at is not None
            with _session(eng) as retry, pytest.raises(decisions.StaleHead) as stale:
                _remove(retry, owner_msg, mod)
            assert stale.value.current_head_id == first.decision_id
        else:
            assert _message(eng, owner_msg).redacted_at is None
            with _session(eng) as retry:
                _remove(retry, owner_msg, mod)
                retry.commit()
        assert _decisions(eng, owner_msg) == 1
        row = _message(eng, owner_msg)
        assert row.redacted_at is not None and CANARY in row.body
    finally:
        proxy.resume()
        proxy.stop()
        pe.dispose()


# --- M-R7 ------------------------------------------------------------------------------

def test_m_r7_a_conflicted_moderator_cannot_get_around_the_checks(pg_client,
                                                                  pg_migrated_engine):
    eng = pg_migrated_engine
    _o, tenant, _offer, _conv, owner_msg, _t = _thread(pg_client)
    _file(eng, tenant, owner_msg, "HARASSMENT")
    with eng.begin() as conn:  # the reporting tenant is also a moderator
        conn.execute(text("UPDATE users SET role = 'admin' WHERE email = :e"), {"e": tenant})
    with pytest.raises(ValidationError):  # no caller-selected report
        trust_router.DecisionIn(target_type="MESSAGE", target_id=owner_msg,
                                action="CONTENT_REMOVED", reason_code="HARASSMENT",
                                expected_head_decision_id=None, report_id="x")
    body = trust_router.DecisionIn(target_type="MESSAGE", target_id=owner_msg,
                                   action="CONTENT_REMOVED", reason_code="HARASSMENT",
                                   expected_head_decision_id=None)
    with _session(eng) as db, pytest.raises(HTTPException) as refused:
        trust_router.decide(body, moderator=_user(db, tenant), db=db)
    assert refused.value.status_code == 403
    assert _decisions(eng, owner_msg) == 0 and _message(eng, owner_msg).redacted_at is None


# --- M-R8 ------------------------------------------------------------------------------

def test_m_r8_the_window_is_fixed_by_id_and_never_crosses_conversations(pg_client,
                                                                       pg_migrated_engine):
    eng = pg_migrated_engine
    owner, tenant, _offer, conv, owner_msg, tenant_msg = _thread(pg_client)
    _o2, _t2, _offer2, other_conv, other_msg, other_tenant_msg = _thread(pg_client)
    with eng.begin() as conn:  # the other conversation's rows share our timestamps
        stamp = conn.scalar(text("SELECT created_at FROM messages WHERE id = :m"),
                            {"m": owner_msg})
        conn.execute(text("UPDATE messages SET created_at = :s WHERE conversation_id = :c"),
                     {"s": stamp, "c": other_conv})
    mod = _account(eng, role="admin")
    result: dict = {}
    r = _session(eng)
    try:
        review = moderation.review_message(r, moderator=_user(r, mod), message_id=owner_msg)

        def write_more():  # new messages committed while the review is open
            with _session(eng) as w:
                conversations.send_message(
                    conv, conversations.MessageIn(client_message_id=uuid4(), body="later"),
                    user=_user(w, tenant), db=w)
        t = _run(result, "w", write_more)
        t.join(15)
        r.commit()
    finally:
        r.close()
    ids = [m.id for m in review.evidence]
    assert review.message.id == owner_msg and ids == [tenant_msg, owner_msg]
    assert {m.conversation_id for m in review.evidence} == {conv}
    assert other_msg not in ids and other_tenant_msg not in ids
    with _session(eng) as again:
        later = moderation.review_message(again, moderator=_user(again, mod),
                                          message_id=owner_msg)
        again.commit()
    assert later.message.id == owner_msg and len(later.evidence) == 3
    assert {m.conversation_id for m in later.evidence} == {conv}


def test_m_reviews_and_message_decisions_in_parallel_never_deadlock(pg_client,
                                                                    pg_migrated_engine):
    eng = pg_migrated_engine
    deadlocks = _deadlocks(eng)
    for _ in range(4):
        _o, tenant, _offer, _conv, owner_msg, _t = _thread(pg_client)
        _file(eng, tenant, owner_msg)
        mod, viewer = _account(eng, role="admin"), _account(eng, role="admin")
        result: dict = {}

        def review(owner_msg=owner_msg, viewer=viewer):
            with _session(eng) as v:
                moderation.review_message(v, moderator=_user(v, viewer), message_id=owner_msg)
                v.commit()

        def decide(owner_msg=owner_msg, mod=mod):
            with _session(eng) as d:
                _remove(d, owner_msg, mod)
                d.commit()
        threads = [_run(result, "v", review), _run(result, "d", decide)]
        for t in threads:
            t.join(15)
        assert result["v"] is None and result["d"] is None, result
    assert _deadlocks(eng) == deadlocks
