"""TASK-015 Slice 4b on PostgreSQL: engagement safety under real locks.

E-R1 send vs conversation closure (both orders) · E-R2 two moderators
restrict one conversation · E-R3 close_engagement vs send (both orders) ·
E-R4 close_engagement vs viewing confirm (both orders) · E-R5 close_engagement
vs a new viewing request / a new conversation · E-R6 close_engagement vs the
requester's own cancel · E-R7 photo restriction vs public serve · E-R8 photo
restriction vs attach · E-R9 rolled-back decision · E-R10 decision COMMIT
outcome unknown (PR-003 proxy) · stress: no deadlock.

Waits are proven with `pg_blocking_pids` (`_blocked_on`). "X first" means X
ran to its COMMIT and is held there (`_paused`) with every lock it took, so
the other side demonstrably waits on X's own locks.
"""

import threading
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event, text

from app.modules.engagement import router as conversations
from app.modules.engagement import viewings
from app.modules.media import router as media_router
from app.modules.trust import decisions, effects
from tests.conftest import TEST_DATABASE_URL, auth, last_code, register_and_login
from tests.test_engagement_safety import WARSAW, _slot
from tests.test_media import _approved
from tests.test_publication_authority_race_pg import _blocked_on
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

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

_n = {"i": 0}


def _verify(pg_client, token):
    assert pg_client.post("/v1/me/verify/email/start", headers=auth(token)).status_code == 200
    assert pg_client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                          headers=auth(token)).status_code == 200


def _tenant(pg_client):
    _n["i"] += 1
    email = f"s4b-pg-tenant-{_n['i']}@example.com"
    token = register_and_login(pg_client, email, "guest")
    _verify(pg_client, token)
    return email, token


def _setup(pg_client, *, viewing=None):
    """A public listing, its owner, a tenant with a conversation, and (when
    asked) a future viewing in state `viewing` (REQUESTED or CONFIRMED)."""
    owner_email, owner, offer = _listing(pg_client)
    _verify(pg_client, owner)
    tenant_email, tenant = _tenant(pg_client)
    started = pg_client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "Hej"},
                             headers=auth(tenant))
    assert started.status_code == 201, started.text
    out = {"owner": owner_email, "owner_token": owner, "tenant": tenant_email,
           "tenant_token": tenant, "offer": offer,
           "conv": started.json()["conversation"]["id"]}
    day = datetime.now(WARSAW).date() + timedelta(days=4)
    assert pg_client.put(f"/v1/classifieds/{offer}/viewing-settings", json={
        "booking_mode": "REQUEST_APPROVAL", "duration_minutes": 30,
        "minimum_notice_minutes": 0, "max_concurrent_bookings": 5},
        headers=auth(owner)).status_code == 200
    assert pg_client.post(f"/v1/classifieds/{offer}/viewing-windows", json={
        "window_type": "ONE_OFF", "local_date": day.isoformat(), "local_start_time": "10:00",
        "local_end_time": "14:00"}, headers=auth(owner)).status_code == 201
    out["day"] = day
    if viewing:
        v = pg_client.post(f"/v1/classifieds/{offer}/viewings",
                           json={"starts_at": _slot(day, 10)}, headers=auth(tenant))
        assert v.status_code == 201, v.text
        out["viewing"] = v.json()["id"]
        if viewing == "CONFIRMED":
            assert pg_client.post(f"/v1/viewings/{out['viewing']}/confirm",
                                  headers=auth(owner)).status_code == 200
    return out


def _paused(engine):
    """A session whose COMMIT waits for `gate` — the code under test runs to
    its commit and holds every lock it took until released."""
    s = _session(engine)
    gate, reached = threading.Event(), threading.Event()

    @event.listens_for(s, "before_commit")
    def _wait(_session):
        reached.set()
        assert gate.wait(20), "the paused commit was never released"
    return s, gate, reached


def _close_engagement(db, offer, mod, expected=None, reason="SCAM"):
    return decisions.apply_listing_decision(
        db, actor=_user(db, mod), listing_id=offer, action="VISIBILITY_LIMITED",
        reason_code=reason, expected_head_decision_id=expected, close_engagement=True)


def _restrict(db, conv, mod, expected=None):
    return decisions.apply_conversation_decision(
        db, actor=_user(db, mod), conversation_id=conv, action="FEATURE_RESTRICTED",
        reason_code="HARASSMENT", expected_head_decision_id=expected)


def _send(engine_or_session, conv, email, body="late message"):
    def go(db):
        return conversations.send_message(conv, conversations.MessageIn(body=body),
                                          user=_user(db, email), db=db)
    if hasattr(engine_or_session, "execute"):
        return go(engine_or_session)
    with _session(engine_or_session) as db:
        return go(db)


def _status(engine, table, row_id):
    return _scalar(engine, f"SELECT status FROM {table} WHERE id = :i", i=row_id)  # noqa: S608


def _user_messages(engine, conv) -> int:
    """USER messages in the conversation. Counted, not ordered by time: the
    application and database clocks are different clocks (MICRO-002)."""
    return _scalar(engine, "SELECT count(*) FROM messages WHERE conversation_id = :c AND "
                           "message_type = 'USER'", c=conv)


def _blocked_count(engine, blocker: int, n: int) -> bool:
    """True once at least `n` backends are blocked by `blocker`."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            waiting = conn.scalar(text(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                "AND :b = ANY(pg_blocking_pids(pid))"), {"b": blocker})
        if waiting >= n:
            return True
        time.sleep(0.05)
    return False


def _wait_for(reached):
    assert reached.wait(20), "the first transaction never reached its commit"


# --- E-R1 send vs conversation closure ----------------------------------------------

def test_e_r1a_closure_first_the_send_waits_and_is_refused(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        _restrict(a, s["conv"], mod)
        t = _run(result, "send", lambda: _send(eng, s["conv"], s["tenant"]))
        assert _blocked_on(eng, "conversations", _pid(a))
        a.commit()
        t.join(15)
    finally:
        a.close()
    assert getattr(result["send"], "status_code", None) == 409
    assert result["send"].detail.startswith("CONVERSATION_CLOSED")
    assert _status(eng, "conversations", s["conv"]) == "CLOSED"
    assert _user_messages(eng, s["conv"]) == 1


def test_e_r1b_send_first_the_closure_waits_and_the_message_stands(pg_client,
                                                                   pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t_send = _run(result, "send", lambda: _send(p, s["conv"], s["tenant"], "first in"))
        _wait_for(reached)

        def close():
            with _session(eng) as d:
                _restrict(d, s["conv"], mod)
                d.commit()
        t_close = _run(result, "close", close)
        assert _blocked_on(eng, "conversations", _pid(p))
        gate.set()
        t_send.join(15)
        t_close.join(15)
    finally:
        gate.set()
        p.close()
    assert result["close"] is None and not isinstance(result["send"], Exception)
    assert _status(eng, "conversations", s["conv"]) == "CLOSED"
    assert _user_messages(eng, s["conv"]) == 2  # committed before the closure; it stands
    assert _last_message(eng, s["conv"]) == "SYSTEM"
    assert _scalar(eng, "SELECT count(*) FROM messages WHERE conversation_id = :c AND "
                        "body = 'first in'", c=s["conv"]) == 1


def test_e_r1c_continuing_a_thread_waits_for_its_closure_and_is_barred(pg_client,
                                                                       pg_migrated_engine):
    """`start_conversation` on a listing with an ACTIVE thread continues it:
    that path locks the thread too, so it waits for a restriction in
    progress, then finds it closed — and G-14 bars a new one."""
    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        _restrict(a, s["conv"], mod)

        def again():
            with _session(eng) as r:
                return conversations.start_conversation(
                    s["offer"], conversations.MessageIn(body="me again"),
                    user=_user(r, s["tenant"]), db=r)
        t = _run(result, "start", again)
        assert _blocked_on(eng, "conversations", _pid(a))
        a.commit()
        t.join(15)
    finally:
        a.close()
    assert getattr(result["start"], "status_code", None) == 409
    assert result["start"].detail.startswith("RECONTACT_BLOCKED")
    assert _user_messages(eng, s["conv"]) == 1
    assert _scalar(eng, "SELECT count(*) FROM conversations WHERE listing_id = :o",
                   o=s["offer"]) == 1


# --- E-R2 two moderators -----------------------------------------------------------

def test_e_r2_two_moderators_restrict_once(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    m1, m2 = _account(eng, role="admin"), _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        first = _restrict(a, s["conv"], m1)
        b = _session(eng)

        def second():
            try:
                return _restrict(b, s["conv"], m2)
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
    assert _scalar(eng, "SELECT count(*) FROM moderation_decisions WHERE target_id = :c",
                   c=s["conv"]) == 1
    assert _scalar(eng, "SELECT count(*) FROM messages WHERE conversation_id = :c AND "
                        "message_type = 'SYSTEM'", c=s["conv"]) == 1


# --- E-R3 close_engagement vs send ------------------------------------------------

def test_e_r3a_close_engagement_first_the_send_is_refused(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        _close_engagement(a, s["offer"], mod)
        t = _run(result, "send", lambda: _send(eng, s["conv"], s["owner"]))
        assert _blocked_on(eng, "conversations", _pid(a))
        a.commit()
        t.join(15)
    finally:
        a.close()
    assert getattr(result["send"], "status_code", None) == 409
    assert _user_messages(eng, s["conv"]) == 1


def test_e_r3b_send_first_close_engagement_waits_then_closes(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t_send = _run(result, "send", lambda: _send(p, s["conv"], s["tenant"]))
        _wait_for(reached)

        def close():
            with _session(eng) as d:
                applied = _close_engagement(d, s["offer"], mod)
                d.commit()
                return applied
        t_close = _run(result, "close", close)
        assert _blocked_on(eng, "conversations", _pid(p))
        gate.set()
        t_send.join(15)
        t_close.join(15)
    finally:
        gate.set()
        p.close()
    assert result["close"].closed_conversation_ids == (s["conv"],)
    assert _user_messages(eng, s["conv"]) == 2
    assert _last_message(eng, s["conv"]) == "SYSTEM"


# --- E-R4 close_engagement vs viewing confirm -------------------------------------

def test_e_r4a_decision_first_the_confirm_waits_and_finds_the_hold(pg_client,
                                                                   pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client, viewing="REQUESTED")
    mod = _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        _close_engagement(a, s["offer"], mod)

        def confirm():
            with _session(eng) as c:
                return viewings.confirm(s["viewing"], user=_user(c, s["owner"]), db=c)
        t = _run(result, "confirm", confirm)
        assert _blocked_on(eng, "classified_offers", _pid(a))
        a.commit()
        t.join(15)
    finally:
        a.close()
    assert getattr(result["confirm"], "status_code", None) == 409
    assert result["confirm"].detail.startswith("LISTING_HELD")
    assert _status(eng, "viewings", s["viewing"]) == "CANCELLED"


def test_e_r4b_confirm_first_the_decision_waits_then_cancels_it(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client, viewing="REQUESTED")
    mod = _account(eng, role="admin")
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t_confirm = _run(result, "confirm", lambda: viewings.confirm(
            s["viewing"], user=_user(p, s["owner"]), db=p))
        _wait_for(reached)

        def close():
            with _session(eng) as d:
                applied = _close_engagement(d, s["offer"], mod)
                d.commit()
                return applied
        t_close = _run(result, "close", close)
        assert _blocked_on(eng, "classified_offers", _pid(p))
        gate.set()
        t_confirm.join(15)
        t_close.join(15)
    finally:
        gate.set()
        p.close()
    assert not isinstance(result["confirm"], Exception), result["confirm"]
    assert result["close"].cancelled_viewing_ids == (s["viewing"],)
    assert _status(eng, "viewings", s["viewing"]) == "CANCELLED"  # confirmed, then cancelled


# --- E-R5 close_engagement vs new engagement --------------------------------------

def test_e_r5_nothing_new_is_opened_behind_close_engagement(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    newcomer_email, _newcomer = _tenant(pg_client)
    mod = _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        _close_engagement(a, s["offer"], mod)

        def request():
            with _session(eng) as r:
                return viewings.request_viewing(
                    s["offer"], viewings.ViewingRequest(starts_at=_slot(s["day"], 11)),
                    user=_user(r, newcomer_email), db=r)

        def start():
            with _session(eng) as r:
                return conversations.start_conversation(
                    s["offer"], conversations.MessageIn(body="hi"),
                    user=_user(r, newcomer_email), db=r)
        threads = [_run(result, "request", request), _run(result, "start", start)]
        # Both must be waiting on the decision before it commits — otherwise a
        # thread that has not yet read the listing would simply see the
        # committed hold, and the test would not prove the lock (found when a
        # mutation that removed start's listing lock survived intermittently).
        assert _blocked_count(eng, _pid(a), 2)
        a.commit()
        for t in threads:
            t.join(15)
    finally:
        a.close()
    assert getattr(result["request"], "status_code", None) == 404
    assert getattr(result["start"], "status_code", None) == 404
    assert _scalar(eng, "SELECT count(*) FROM conversations WHERE listing_id = :o AND "
                        "status = 'ACTIVE'", o=s["offer"]) == 0
    assert _scalar(eng, "SELECT count(*) FROM viewings WHERE listing_id = :o AND "
                        "status IN ('REQUESTED','CONFIRMED')", o=s["offer"]) == 0


def test_e_r5b_a_start_first_is_closed_by_the_decision_that_waited(pg_client,
                                                                   pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    newcomer_email, _newcomer = _tenant(pg_client)
    mod = _account(eng, role="admin")
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t_start = _run(result, "start", lambda: conversations.start_conversation(
            s["offer"], conversations.MessageIn(body="hi"), user=_user(p, newcomer_email),
            db=p))
        _wait_for(reached)

        def close():
            with _session(eng) as d:
                applied = _close_engagement(d, s["offer"], mod)
                d.commit()
                return applied
        t_close = _run(result, "close", close)
        assert _blocked_on(eng, "classified_offers", _pid(p))
        gate.set()
        t_start.join(15)
        t_close.join(15)
    finally:
        gate.set()
        p.close()
    new_conv = result["start"].conversation.id
    assert set(result["close"].closed_conversation_ids) == {s["conv"], new_conv}
    assert _scalar(eng, "SELECT count(*) FROM conversations WHERE listing_id = :o AND "
                        "status = 'ACTIVE'", o=s["offer"]) == 0


# --- E-R6 close_engagement vs the requester's cancel ------------------------------

def test_e_r6_a_cancel_first_stays_the_requesters_own(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client, viewing="CONFIRMED")
    mod = _account(eng, role="admin")
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t_cancel = _run(result, "cancel", lambda: viewings.cancel(
            s["viewing"], user=_user(p, s["tenant"]), db=p))
        _wait_for(reached)

        def close():
            with _session(eng) as d:
                applied = _close_engagement(d, s["offer"], mod)
                d.commit()
                return applied
        t_close = _run(result, "close", close)
        assert _blocked_on(eng, "viewings", _pid(p))
        gate.set()
        t_cancel.join(15)
        t_close.join(15)
    finally:
        gate.set()
        p.close()
    assert result["close"].cancelled_viewing_ids == ()
    assert _status(eng, "viewings", s["viewing"]) == "CANCELLED"
    mine = pg_client.get("/v1/me/viewings", headers=auth(s["tenant_token"])).json()
    assert [v["cancelled_by_homies"] for v in mine if v["id"] == s["viewing"]] == [False]


# --- E-R7 / E-R8 photos ------------------------------------------------------------

def _listing_photo(pg_client, eng, s):
    prop = _scalar(eng, "SELECT property_id FROM classified_offers WHERE id = :o", o=s["offer"])
    asset = _approved(pg_client, s["owner_token"], prop)
    assert pg_client.post(f"/v1/classifieds/{s['offer']}/media",
                          json={"media_asset_id": asset, "is_cover": True},
                          headers=auth(s["owner_token"])).status_code == 201
    return prop, asset


def _remove_photo(db, asset, mod, expected=None):
    return decisions.apply_media_decision(
        db, actor=_user(db, mod), media_asset_id=asset, action="CONTENT_REMOVED",
        reason_code="STOLEN_MEDIA", expected_head_decision_id=expected)


def test_e_r7_a_photo_is_served_until_its_restriction_commits_then_never(pg_client,
                                                                         pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    _prop, asset = _listing_photo(pg_client, eng, s)
    mod = _account(eng, role="admin")
    a = _session(eng)
    try:
        _remove_photo(a, asset, mod)
        # read committed: before the commit, the committed (approved) state
        assert pg_client.get(f"/v1/media/{asset}").status_code == 200
        a.commit()
    finally:
        a.close()
    assert pg_client.get(f"/v1/media/{asset}").status_code == 404
    assert _scalar(eng, "SELECT count(*) FROM listing_media WHERE media_asset_id = :a",
                   a=asset) == 1


def test_e_r8_an_attach_waits_for_the_restriction_and_is_refused(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    prop = _scalar(eng, "SELECT property_id FROM classified_offers WHERE id = :o", o=s["offer"])
    asset = _approved(pg_client, s["owner_token"], prop)
    mod = _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        _remove_photo(a, asset, mod)

        def attach():
            with _session(eng) as r:
                return media_router.attach(s["offer"], media_router.AttachIn(
                    media_asset_id=asset, is_cover=True), user=_user(r, s["owner"]), db=r)
        t = _run(result, "attach", attach)
        assert _blocked_on(eng, "media_assets", _pid(a))
        a.commit()
        t.join(15)
    finally:
        a.close()
    assert getattr(result["attach"], "status_code", None) == 409
    assert _scalar(eng, "SELECT count(*) FROM listing_media WHERE media_asset_id = :a",
                   a=asset) == 0


# --- E-R9 rollback -----------------------------------------------------------------

def test_e_r9_a_rolled_back_close_engagement_leaves_nothing(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client, viewing="CONFIRMED")
    mod = _account(eng, role="admin")
    counts = {t: _scalar(eng, f"SELECT count(*) FROM {t}")  # noqa: S608
              for t in ("domain_events", "audit_log", "user_notifications",
                        "moderation_decisions", "messages")}
    with _session(eng) as db:
        applied = _close_engagement(db, s["offer"], mod)
        db.flush()
        assert applied.closed_conversation_ids and applied.cancelled_viewing_ids
        db.rollback()
    assert _status(eng, "conversations", s["conv"]) == "ACTIVE"
    assert _status(eng, "viewings", s["viewing"]) == "CONFIRMED"
    assert _status(eng, "classified_offers", s["offer"]) == "active"
    assert {t: _scalar(eng, f"SELECT count(*) FROM {t}") for t in counts} == counts  # noqa: S608


# --- E-R10 unknown COMMIT ------------------------------------------------------------

@pytest.mark.parametrize("branch", ["committed", "rolled_back"])
def test_e_r10_unknown_commit_closes_exactly_once(pg_client, pg_migrated_engine, branch):
    from sqlalchemy.engine import make_url

    from app.core import db as core_db
    from app.core.db_failures import unavailability_reason
    from tests.pg_fault_proxy import FreezableProxy
    from tests.test_db_deadlines_pg import DEADLINE_S, FAST, SLACK_S, _bounded

    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    target = make_url(TEST_DATABASE_URL)
    proxy = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    pe = core_db.create_bounded_engine(proxy.url(), deadlines=FAST, pool_size=1, max_overflow=0)
    try:
        sess = _session(pe)
        first = _restrict(sess, s["conv"], mod)
        server_pid = _pid(sess)
        proxy.freeze_on = b"COMMIT"
        outcome, _took = _bounded(sess.commit, DEADLINE_S + SLACK_S + 3)
        assert unavailability_reason(outcome) == "commit_unknown", outcome
        if branch == "rolled_back":
            with eng.connect() as admin:
                admin.execute(text("SELECT pg_terminate_backend(:p)"), {"p": server_pid})
        proxy.resume()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            done = _status(eng, "conversations", s["conv"]) == "CLOSED"
            gone = not _scalar(eng, "SELECT count(*) FROM pg_stat_activity WHERE pid = :p",
                               p=server_pid)
            if (branch == "committed" and done) or (branch == "rolled_back" and gone):
                break
            time.sleep(0.05)
        if branch == "committed":
            with _session(eng) as retry, pytest.raises(decisions.StaleHead) as stale:
                _restrict(retry, s["conv"], mod)
            assert stale.value.current_head_id == first.decision_id
        else:
            assert _status(eng, "conversations", s["conv"]) == "ACTIVE"
            with _session(eng) as retry:
                _restrict(retry, s["conv"], mod)
                retry.commit()
        assert _status(eng, "conversations", s["conv"]) == "CLOSED"
        assert _scalar(eng, "SELECT count(*) FROM messages WHERE conversation_id = :c AND "
                            "body = :b", c=s["conv"], b=effects.CLOSED_BY_HOMIES) == 1
    finally:
        proxy.resume()
        proxy.stop()
        pe.dispose()


# --- stress ---------------------------------------------------------------------------

def test_decisions_sends_confirms_and_cancels_in_parallel_never_deadlock(pg_client,
                                                                        pg_migrated_engine):
    eng = pg_migrated_engine
    deadlocks = _deadlocks(eng)
    for _ in range(4):
        s = _setup(pg_client, viewing="REQUESTED")
        mod = _account(eng, role="admin")
        result: dict = {}

        def decide(s=s, mod=mod):
            with _session(eng) as d:
                _close_engagement(d, s["offer"], mod)
                d.commit()

        def restrict(s=s):
            m2 = _account(eng, role="admin")
            with _session(eng) as d:
                try:
                    _restrict(d, s["conv"], m2)
                    d.commit()
                except decisions.DecisionRefused:
                    d.rollback()

        def send(s=s):
            try:
                _send(eng, s["conv"], s["tenant"])
            except Exception as exc:  # noqa: BLE001 — 409 after a closure is expected
                assert getattr(exc, "status_code", None) == 409, exc

        def confirm(s=s):
            with _session(eng) as c:
                try:
                    viewings.confirm(s["viewing"], user=_user(c, s["owner"]), db=c)
                except Exception as exc:  # noqa: BLE001 — 409 after the hold is expected
                    assert getattr(exc, "status_code", None) == 409, exc
        threads = [_run(result, k, f) for k, f in
                   (("d", decide), ("r", restrict), ("s", send), ("c", confirm))]
        for t in threads:
            t.join(20)
        assert all(result.get(k) is None for k in "drsc"), result
        assert _status(eng, "conversations", s["conv"]) == "CLOSED"
        assert _status(eng, "viewings", s["viewing"]) == "CANCELLED"
    assert _deadlocks(eng) == deadlocks


def _last_message(engine, conv):
    return _scalar(engine, "SELECT message_type FROM messages WHERE conversation_id = :c "
                           "ORDER BY created_at DESC, id DESC LIMIT 1", c=conv)


def test_the_closure_line_is_last_and_cancellations_carry_the_decisions_instant(
        pg_client, pg_migrated_engine):
    """The SYSTEM line is the conversation's last message even when a message
    committed while the decision waited (its transaction began earlier); a
    cancelled viewing carries exactly the decision's instant, which is what
    `cancelled_by_homies` matches."""
    eng = pg_migrated_engine
    s = _setup(pg_client, viewing="REQUESTED")
    mod = _account(eng, role="admin")
    with eng.begin() as conn:  # the latest message is stamped ahead of the database clock
        conn.execute(text("UPDATE messages SET created_at = now() + interval '1 hour' "
                          "WHERE conversation_id = :c"), {"c": s["conv"]})
        conn.execute(text("UPDATE conversations SET last_message_at = now() + interval '1 hour' "
                          "WHERE id = :c"), {"c": s["conv"]})
    with _session(eng) as d:
        applied = _close_engagement(d, s["offer"], mod, reason="SAFETY")
        d.commit()
    at = _scalar(eng, "SELECT created_at FROM messages WHERE conversation_id = :c AND "
                      "message_type = 'SYSTEM'", c=s["conv"])
    cancelled = _scalar(eng, "SELECT cancelled_at FROM viewings WHERE id = :v", v=s["viewing"])
    assert cancelled == applied.effective_from < at
    assert _last_message(eng, s["conv"]) == "SYSTEM"
    mine = pg_client.get("/v1/me/viewings", headers=auth(s["tenant_token"])).json()
    assert [v["cancelled_by_homies"] for v in mine if v["id"] == s["viewing"]] == [True]


# --- adversarial review repairs (S4b) ---------------------------------------------

def _paused_at_head(monkeypatch, target_type):
    """Hold a decision of `target_type` right after its locks are taken and
    before it inserts (the head read sits exactly there)."""
    real = decisions.hold.head
    gate, reached = threading.Event(), threading.Event()

    def head(db, t, target_id):
        if t == target_type and not reached.is_set():
            reached.set()
            assert gate.wait(20), "never released"
        return real(db, t, target_id)
    monkeypatch.setattr(decisions.hold, "head", head)
    return gate, reached


def _race_decision_against_close_engagement(eng, s, monkeypatch, target_type, decide):
    """T1 = the conversation/message decision, held between its locks and its
    insert; T2 = close_engagement on the listing. With the listing taken first
    by T1, T2 waits at the listing and both finish. Without it, T2 holds the
    listing and waits for T1's conversation while T1's insert (a foreign-key
    check, FOR KEY SHARE on the listing) waits for T2: a deadlock."""
    m2 = _account(eng, role="admin")
    deadlocks = _deadlocks(eng)
    gate, reached = _paused_at_head(monkeypatch, target_type)
    result: dict = {}
    t1 = _run(result, "decision", decide)
    try:
        assert reached.wait(20)

        def close():
            with _session(eng) as d:
                applied = _close_engagement(d, s["offer"], m2)
                d.commit()
                return applied
        t2 = _run(result, "close", close)
        time.sleep(0.5)  # let T2 take whatever it can before T1 inserts
        gate.set()
        t1.join(20)
        t2.join(20)
    finally:
        gate.set()
    assert not isinstance(result["decision"], Exception), result["decision"]
    assert not isinstance(result["close"], Exception), result["close"]
    assert _deadlocks(eng) == deadlocks
    return result


def test_e_r11_a_conversation_decision_and_close_engagement_do_not_deadlock(
        pg_client, pg_migrated_engine, monkeypatch):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    m1 = _account(eng, role="admin")

    def restrict():
        with _session(eng) as d:
            applied = _restrict(d, s["conv"], m1)
            d.commit()
            return applied
    result = _race_decision_against_close_engagement(eng, s, monkeypatch, "CONVERSATION",
                                                     restrict)
    assert result["decision"].closed_conversation_ids == (s["conv"],)
    assert result["close"].closed_conversation_ids == ()  # already closed


def test_e_r12_a_message_decision_and_close_engagement_do_not_deadlock(
        pg_client, pg_migrated_engine, monkeypatch):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    m1 = _account(eng, role="admin")
    owner_msg = pg_client.post(f"/v1/conversations/{s['conv']}/messages",
                               json={"body": "transfer first"},
                               headers=auth(s["owner_token"])).json()["id"]

    def remove():
        with _session(eng) as d:
            applied = decisions.apply_message_decision(
                d, actor=_user(d, m1), message_id=owner_msg, action="CONTENT_REMOVED",
                reason_code="SCAM", expected_head_decision_id=None)
            d.commit()
            return applied
    result = _race_decision_against_close_engagement(eng, s, monkeypatch, "MESSAGE", remove)
    assert result["close"].closed_conversation_ids == (s["conv"],)


# --- F6: a G-14 restriction also covers viewings --------------------------------

def _request_viewing(eng, s, hour):
    """Request as the tenant in its own transaction; the id, or the exception."""
    with _session(eng) as c:
        v = viewings.request_viewing(s["offer"], viewings.ViewingRequest(
            starts_at=_slot(s["day"], hour)), user=_user(c, s["tenant"]), db=c)
        return v.id


def _viewings_of(eng, offer) -> int:
    return _scalar(eng, "SELECT count(*) FROM viewings WHERE listing_id = :o", o=offer)


def test_f6a_restriction_committed_first_the_viewing_is_refused(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    with _session(eng) as a:
        _restrict(a, s["conv"], mod)
        a.commit()
    result: dict = {}
    _run(result, "request", lambda: _request_viewing(eng, s, 10)).join(15)
    assert getattr(result["request"], "status_code", None) == 409
    assert result["request"].detail.startswith("RECONTACT_BLOCKED")
    assert _viewings_of(eng, s["offer"]) == 0


def test_f6b_a_restriction_in_flight_neither_blocks_the_request_nor_is_bypassed_after(
        pg_client, pg_migrated_engine):
    """The request takes the listing FOR SHARE, the decision FOR KEY SHARE:
    they do not wait for each other. A request that reads before the decision
    commits orders before it (as a viewing that already existed would); once
    the decision is committed, the same requester is refused."""
    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        _restrict(a, s["conv"], mod)  # uncommitted: conversation FOR UPDATE, listing KEY SHARE
        t = _run(result, "first", lambda: _request_viewing(eng, s, 10))
        t.join(15)
        assert not t.is_alive(), "the viewing request waited on the decision"
        assert isinstance(result["first"], str), result["first"]
        a.commit()
    finally:
        a.close()
    assert _status(eng, "viewings", result["first"]) == "REQUESTED"
    # The requester calls it off and tries again: now the restriction stands.
    with _session(eng) as c:
        viewings.cancel(result["first"], user=_user(c, s["tenant"]), db=c)
    _run(result, "again", lambda: _request_viewing(eng, s, 11)).join(15)
    assert getattr(result["again"], "status_code", None) == 409
    assert result["again"].detail.startswith("RECONTACT_BLOCKED")
    assert _viewings_of(eng, s["offer"]) == 1
