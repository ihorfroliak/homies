"""TASK-015 Slices 2+3 on PostgreSQL: reports and the moderation loop under real
locks.

R1 duplicate race · R2 quota races (24 h window, live cap, DB-time aging) ·
R3 report retry after an unknown COMMIT · R4 two moderators open a target ·
R5 two decisions through the HTTP handler · R6 reporter conflict of interest
(several reporters; the moderator's own report racing the decision) · R7 notice
transaction and lock order · R8 decision + notices after an unknown COMMIT ·
R9 owner projection and queue under concurrent decisions.

Waits are proven with `pg_blocking_pids` (the waiter is blocked by the
holder's backend), never with sleeps. Critical sections call the services or
route functions on their own sessions — no HTTP/JWT inside a race.
"""

import threading
import time

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.models import User
from app.modules.properties import router as props
from app.modules.trust import decisions, moderation, reports
from app.modules.trust import router as trust_router
from tests.conftest import TEST_DATABASE_URL, auth, last_code, register_and_login, verify_ownership
from tests.test_publication_authority_race_pg import _blocked_on

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

PROPERTY = {"category": "APARTMENT", "city": "Łódź", "address": "ul. Zgłoszeń 1",
            "area_m2": 38, "rooms": 1, "capacity": 2}
OFFER = {"title": "Zgłaszane mieszkanie", "rent_amount": 199000, "min_term_months": 12,
         "contact_mode": "phone", "contact_phone": "+48 600 300 400"}

_n = {"i": 0}


def _next() -> int:
    _n["i"] += 1
    return _n["i"]


def _listing(pg_client):
    i = _next()
    email = f"rep-pg-owner-{i}@example.com"
    owner = register_and_login(pg_client, email, "host")
    prop = pg_client.post("/v1/properties", json={**PROPERTY, "address": f"ul. Z {i}"},
                          headers=auth(owner)).json()["id"]
    verify_ownership(pg_client, owner, prop)
    offer = pg_client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                           headers=auth(owner)).json()["id"]
    assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                          headers=auth(owner)).status_code == 200
    return email, owner, offer


def _account(engine, *, role="guest", verified=True) -> str:
    email = f"rep-pg-{role}-{_next()}@example.com"
    with Session(engine) as db:
        db.add(User(email=email, password_hash=hash_password("x-123456789"), role=role,
                    email_verified_at=db.scalar(text("SELECT now()")) if verified else None))
        db.commit()
    return email


def _user(db, email) -> User:
    return db.scalar(select(User).where(User.email == email))


def _session(engine) -> Session:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def _pid(db) -> int:
    return db.scalar(text("SELECT pg_backend_pid()"))


def _file(db, reporter, offer, category="SCAM", text_=None):
    return reports.file_listing_report(db, reporter=_user(db, reporter), listing_id=offer,
                                       category=category, text=text_,
                                       public_projection=trust_router._public_dict)


def _file_and_commit(engine, reporter, offer, category="SCAM"):
    with _session(engine) as db:
        filed = _file(db, reporter, offer, category)
        db.commit() if filed.created else db.rollback()
        return filed.report.id, filed.created


def _decide(db, offer, action, *, expected, moderator, reason=None):
    reason = reason or ("REINSTATED_REMEDIED" if action == "NO_ACTION" else "SCAM")
    return decisions.apply_listing_decision(
        db, actor=_user(db, moderator), listing_id=offer, action=action, reason_code=reason,
        expected_head_decision_id=expected)


def _run(result, key, fn):
    def target():
        try:
            result[key] = fn()
        except Exception as exc:  # noqa: BLE001 — the outcome is asserted
            result[key] = exc
    t = threading.Thread(target=target, daemon=True)
    t.start()
    return t


def _hold_users_row(engine, email) -> Session:
    """Take the reporter's coordination lock the way filing does, and keep it."""
    s = _session(engine)
    s.execute(text("SELECT id FROM users WHERE email = :e FOR NO KEY UPDATE"), {"e": email})
    return s


def _scalar(engine, sql, **params):
    with engine.connect() as conn:
        return conn.scalar(text(sql), params)


def _live(engine, reporter=None, offer=None) -> int:
    return _scalar(engine,
                   "SELECT count(*) FROM reports r JOIN users u ON u.id = r.reporter_user_id "
                   "WHERE r.status IN ('OPEN','IN_REVIEW') "
                   "AND (CAST(:e AS text) IS NULL OR u.email = :e) "
                   "AND (CAST(:o AS text) IS NULL OR r.target_id = :o)", e=reporter, o=offer)


def _deadlocks(engine) -> int:
    return _scalar(engine, "SELECT deadlocks FROM pg_stat_database "
                           "WHERE datname = current_database()")


def _notices(engine, decision_id) -> int:
    return _scalar(engine, "SELECT count(*) FROM user_notifications "
                           "WHERE data->>'decision_id' = :d", d=decision_id)


# --- R1 duplicate race --------------------------------------------------------------

def test_r1_two_simultaneous_reports_by_one_reporter_make_one(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    reporter = _account(eng)
    holder = _hold_users_row(eng, reporter)
    result: dict = {}
    try:
        threads = [_run(result, k, lambda: _file_and_commit(eng, reporter, offer))
                   for k in ("a", "b")]
        assert _blocked_on(eng, "users", _pid(holder)), "filing did not wait on the reporter lock"
    finally:
        holder.rollback()
        holder.close()
    for t in threads:
        t.join(15)
    outcomes = sorted([result["a"], result["b"]], key=lambda r: not r[1])
    assert [created for _id, created in outcomes] == [True, False]
    assert outcomes[0][0] == outcomes[1][0]  # the duplicate answers with the same report
    assert _live(eng, reporter, offer) == 1


def test_r1_the_database_refuses_a_second_live_report_even_without_the_lock(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    reporter = _account(eng)
    rid, _ = _file_and_commit(eng, reporter, offer)
    with eng.connect() as conn, pytest.raises(Exception) as caught:
        conn.execute(text(
            "INSERT INTO reports (id, reporter_user_id, target_type, target_id, category, "
            "severity, status, version) SELECT gen_random_uuid()::text, reporter_user_id, "
            "target_type, target_id, 'FAKE', 'HIGH', 'OPEN', 1 FROM reports WHERE id = :r"),
            {"r": rid})
    assert "uq_reports_live_per_reporter_target" in str(caught.value)


def test_r1_the_savepoint_backstop_answers_with_the_existing_report(
        pg_client, pg_migrated_engine, monkeypatch):
    """If a path ever skipped the reporter lock, the UNIQUE decides and the
    loser is answered with the live report — no 500, no text in an error."""
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    reporter = _account(eng)
    first = _session(eng)
    try:
        filed = _file(first, reporter, offer)  # uncommitted: holds the lock and the row
        assert filed.created
        monkeypatch.setattr(reports, "live_report", _live_report_after_first(first))
        result: dict = {}
        second = _session(eng)
        t = _run(result, "b", lambda: _file_lockless(second, reporter, offer))
        assert _blocked_on(eng, "reports", _pid(first))
        first.commit()
        t.join(15)
        second.commit()
        second.close()
    finally:
        first.close()
    assert result["b"].created is False and result["b"].report.id == filed.report.id
    assert _live(eng, reporter, offer) == 1


def _live_report_after_first(first_session):
    real = reports.live_report.__wrapped__ if hasattr(reports.live_report, "__wrapped__") \
        else reports.live_report
    calls = {"n": 0}

    def patched(db, reporter_id, target_type, target_id):
        if db is first_session:
            return real(db, reporter_id, target_type, target_id)
        calls["n"] += 1
        # The lockless filer's pre-insert checks see nothing (the first is
        # uncommitted); its backstop lookup after the UNIQUE refusal sees it.
        return None if calls["n"] <= 2 else real(db, reporter_id, target_type, target_id)
    return patched


def _file_lockless(db, reporter, offer):
    original = db.execute

    def execute(statement, *args, **kwargs):
        if "FOR NO KEY UPDATE" in str(statement.compile(dialect=db.bind.dialect)) \
                and "users" in str(statement):
            return None  # the bypass: no reporter lock
        return original(statement, *args, **kwargs)
    db.execute = execute  # type: ignore[method-assign]
    try:
        return _file(db, reporter, offer)
    finally:
        db.execute = original  # type: ignore[method-assign]


# --- R2 quota races -----------------------------------------------------------------

@pytest.mark.parametrize("cap", ["daily", "live"])
def test_r2_concurrent_reports_cannot_pass_the_quota(pg_client, pg_migrated_engine, monkeypatch,
                                                      cap):
    eng = pg_migrated_engine
    if cap == "daily":
        monkeypatch.setattr(reports, "DAILY_LIMIT", 2)
    else:
        monkeypatch.setattr(reports, "LIVE_LIMIT", 2)
        monkeypatch.setattr(reports, "DAILY_LIMIT", 100)
    reporter = _account(eng)
    offers = [_listing(pg_client)[2] for _ in range(4)]
    _file_and_commit(eng, reporter, offers[0])  # one slot left
    holder = _hold_users_row(eng, reporter)
    result: dict = {}
    try:
        threads = [_run(result, i, lambda o=o: _file_and_commit(eng, reporter, o))
                   for i, o in enumerate(offers[1:])]
        assert _blocked_on(eng, "users", _pid(holder))
    finally:
        holder.rollback()
        holder.close()
    for t in threads:
        t.join(15)
    outcomes = list(result.values())
    assert sum(1 for o in outcomes if isinstance(o, tuple) and o[1]) == 1
    assert sum(1 for o in outcomes if isinstance(o, reports.QuotaExceeded)) == 2
    assert _live(eng, reporter) == 2


def test_r2_the_window_is_database_time_and_duplicates_are_free(pg_client, pg_migrated_engine,
                                                                 monkeypatch):
    eng = pg_migrated_engine
    monkeypatch.setattr(reports, "DAILY_LIMIT", 2)
    reporter = _account(eng)
    offers = [_listing(pg_client)[2] for _ in range(3)]
    first, _ = _file_and_commit(eng, reporter, offers[0])
    _file_and_commit(eng, reporter, offers[1])
    with _session(eng) as db, pytest.raises(reports.QuotaExceeded) as over:
        _file(db, reporter, offers[2])
    assert 0 < over.value.retry_after <= 24 * 3600
    assert _file_and_commit(eng, reporter, offers[0]) == (first, False)  # at quota: still 200
    with eng.begin() as conn:  # the oldest ages out of the database-time window
        conn.execute(text("UPDATE reports SET created_at = now() - interval '25 hours' "
                          "WHERE id = :r"), {"r": first})
    assert _file_and_commit(eng, reporter, offers[2])[1] is True


# --- R3 report retry after an unknown COMMIT ------------------------------------------

@pytest.mark.parametrize("branch", ["committed", "rolled_back"])
def test_r3_a_report_retry_after_an_unknown_commit_never_duplicates(
        pg_client, pg_migrated_engine, branch):
    from sqlalchemy.engine import make_url

    from app.core import db as core_db
    from app.core.db_failures import unavailability_reason
    from tests.pg_fault_proxy import FreezableProxy
    from tests.test_db_deadlines_pg import DEADLINE_S, FAST, SLACK_S, _bounded

    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    reporter = _account(eng)
    target = make_url(TEST_DATABASE_URL)
    proxy = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    pe = core_db.create_bounded_engine(proxy.url(), deadlines=FAST, pool_size=1, max_overflow=0)
    try:
        s = _session(pe)
        first = _file(s, reporter, offer)
        assert first.created
        server_pid = _pid(s)
        proxy.freeze_on = b"COMMIT"
        outcome, _took = _bounded(s.commit, DEADLINE_S + SLACK_S + 3)
        assert proxy.frozen_on_marker.is_set()
        assert unavailability_reason(outcome) == "commit_unknown", outcome
        if branch == "rolled_back":
            with eng.connect() as admin:
                admin.execute(text("SELECT pg_terminate_backend(:p)"), {"p": server_pid})
        proxy.resume()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and branch == "committed":
            if _live(eng, reporter, offer) == 1:
                break
            time.sleep(0.05)
        if branch == "rolled_back":
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and _scalar(
                    eng, "SELECT count(*) FROM pg_stat_activity WHERE pid = :p", p=server_pid):
                time.sleep(0.05)
        rid, created = _file_and_commit(eng, reporter, offer)
        if branch == "committed":
            assert (rid, created) == (first.report.id, False)
        else:
            assert created is True
        assert _live(eng, reporter, offer) == 1
    finally:
        proxy.resume()
        proxy.stop()
        pe.dispose()


# --- R4 two moderators open the same target ---------------------------------------------

def test_r4_two_moderators_opening_a_target_set_first_review_once(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    for _ in range(3):
        _file_and_commit(eng, _account(eng), offer)
    m1, m2 = _account(eng, role="admin"), _account(eng, role="admin")
    a = _session(eng)
    result: dict = {}
    try:
        first = moderation.review_listing(a, moderator=_user(a, m1), listing_id=offer)
        assert first.moved_to_review == 3
        b = _session(eng)
        t = _run(result, "b", lambda: (moderation.review_listing(
            b, moderator=_user(b, m2), listing_id=offer), b.commit()))
        assert _blocked_on(eng, "reports", _pid(a)), "the second review did not wait"
        stamps = {r.report.id: r.report.first_reviewed_at for r in first.reports}
        a.commit()
        t.join(15)
        b.close()
    finally:
        a.close()
    second, _ = result["b"]
    assert second.moved_to_review == 0
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT id, status, first_reviewed_at, version FROM reports "
                                 "WHERE target_id = :o"), {"o": offer}).all()
    assert {r.status for r in rows} == {"IN_REVIEW"} and {r.version for r in rows} == {2}
    assert {r.id: r.first_reviewed_at for r in rows} == stamps


def test_r4_a_review_after_a_decision_never_reopens_resolved_reports(pg_client,
                                                                     pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    for _ in range(2):
        _file_and_commit(eng, _account(eng), offer)
    mod, viewer = _account(eng, role="admin"), _account(eng, role="admin")
    d = _session(eng)
    result: dict = {}
    try:
        _decide(d, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        v = _session(eng)
        t = _run(result, "v", lambda: (moderation.review_listing(
            v, moderator=_user(v, viewer), listing_id=offer), v.commit()))
        assert _blocked_on(eng, "reports", _pid(d))
        d.commit()
        t.join(15)
        v.close()
    finally:
        d.close()
    review, _ = result["v"]
    assert review.moved_to_review == 0 and review.reports == []
    assert _scalar(eng, "SELECT count(*) FROM reports WHERE target_id = :o AND status = "
                        "'RESOLVED' AND first_reviewed_at IS NULL", o=offer) == 2


# --- R5 two decisions through the HTTP handler -------------------------------------------

def test_r5_two_moderators_one_wins_the_other_gets_409(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    m1, m2 = _account(eng, role="admin"), _account(eng, role="admin")
    body = trust_router.DecisionIn(target_type="LISTING", target_id=offer,
                                   action="VISIBILITY_LIMITED", reason_code="SCAM",
                                   expected_head_decision_id=None)
    a = _session(eng)
    result: dict = {}
    try:
        _decide(a, offer, "CONTENT_EDIT_REQUIRED", expected=None, moderator=m1,
                reason="MISLEADING_PRICE")
        b = _session(eng)
        t = _run(result, "b", lambda: trust_router.decide(body, moderator=_user(b, m2), db=b))
        assert _blocked_on(eng, "properties", _pid(a))
        a.commit()
        t.join(15)
        b.close()
    finally:
        a.close()
    assert isinstance(result["b"], HTTPException) and result["b"].status_code == 409
    assert result["b"].detail.startswith("STALE_HEAD")
    assert _scalar(eng, "SELECT count(*) FROM moderation_decisions WHERE target_id = :o",
                   o=offer) == 1


# --- R6 reporter conflict of interest -----------------------------------------------------

def test_r6_one_of_several_reporters_cannot_decide(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    _file_and_commit(eng, _account(eng), offer, "FAKE")
    _file_and_commit(eng, mod, offer, "SCAM")
    _file_and_commit(eng, _account(eng), offer, "SAFETY")
    body = trust_router.DecisionIn(target_type="LISTING", target_id=offer,
                                   action="VISIBILITY_LIMITED", reason_code="SCAM",
                                   expected_head_decision_id=None)
    with _session(eng) as db, pytest.raises(HTTPException) as refused:
        trust_router.decide(body, moderator=_user(db, mod), db=db)
    assert refused.value.status_code == 403
    assert _scalar(eng, "SELECT count(*) FROM moderation_decisions WHERE target_id = :o",
                   o=offer) == 0
    assert _live(eng, offer=offer) == 3


def test_r6_the_moderators_own_report_racing_the_decision_is_caught(pg_client,
                                                                     pg_migrated_engine):
    """The moderator's report insert holds the listing's KEY SHARE; the
    decision's row lock waits for it, then sees the report: 403. No deadlock
    on the moderator's own users row (NO KEY UPDATE vs the decision's FK)."""
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    deadlocks = _deadlocks(eng)
    r = _session(eng)
    result: dict = {}
    try:
        assert _file(r, mod, offer).created  # uncommitted
        d = _session(eng)

        def decide():
            try:
                return _decide(d, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
            finally:
                d.rollback()
                d.close()
        t = _run(result, "d", decide)
        assert _blocked_on(eng, "classified_offers", _pid(r))
        r.commit()
        t.join(15)
    finally:
        r.close()
    assert isinstance(result["d"], decisions.ConflictOfInterest)
    assert _deadlocks(eng) == deadlocks


# --- R7 notices live and die with the decision; lock order ----------------------------------

def test_r7_a_rolled_back_decision_leaves_no_notice(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    with _session(eng) as db:
        applied = _decide(db, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        assert len(applied.notified_user_ids) == 1
        db.flush()
        assert db.scalar(text("SELECT count(*) FROM user_notifications WHERE "
                              "data->>'decision_id' = :d"), {"d": applied.decision_id}) == 1
        db.rollback()
    assert _notices(eng, applied.decision_id) == 0
    with _session(eng) as db:
        applied = _decide(db, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        db.commit()
    assert _notices(eng, applied.decision_id) == 1
    with _session(eng) as db:
        dismissal = _decide(db, offer, "NO_ACTION", expected=applied.decision_id, moderator=mod,
                            reason="REINSTATED_DECISION_ERROR")
        db.commit()
    assert _notices(eng, dismissal.decision_id) == 1  # a release is notified
    _o2, _t2, other = _listing(pg_client)
    with _session(eng) as db:
        quiet = _decide(db, other, "NO_ACTION", expected=None, moderator=mod,
                        reason="NOT_A_VIOLATION")
        db.commit()
    assert _notices(eng, quiet.decision_id) == 0


def test_r7_both_report_lockers_lock_in_id_order(pg_client, pg_migrated_engine):
    """Deadlock freedom between a review and a decision rests on both locking
    a target's reports in id order — asserted on the statements they send."""
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    for _ in range(2):
        _file_and_commit(eng, _account(eng), offer)
    mod, viewer = _account(eng, role="admin"), _account(eng, role="admin")
    seen: list[str] = []

    def capture(conn, cursor, statement, *args):
        if "FROM reports" in statement and "FOR UPDATE" in statement:
            seen.append(statement)
    event.listen(eng, "before_cursor_execute", capture)
    try:
        with _session(eng) as v:
            moderation.review_listing(v, moderator=_user(v, viewer), listing_id=offer)
            v.commit()
        with _session(eng) as d:
            _decide(d, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
            d.commit()
    finally:
        event.remove(eng, "before_cursor_execute", capture)
    assert len(seen) == 2
    assert all("ORDER BY reports.id" in s for s in seen)


def test_r7_reviews_and_decisions_in_parallel_never_deadlock(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    deadlocks = _deadlocks(eng)
    for _ in range(5):
        _o, _t, offer = _listing(pg_client)
        for _ in range(4):
            _file_and_commit(eng, _account(eng), offer)
        mod, viewer = _account(eng, role="admin"), _account(eng, role="admin")
        result: dict = {}

        def review(offer=offer, viewer=viewer):
            with _session(eng) as v:
                moderation.review_listing(v, moderator=_user(v, viewer), listing_id=offer)
                v.commit()

        def decide(offer=offer, mod=mod):
            with _session(eng) as d:
                _decide(d, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
                d.commit()
        threads = [_run(result, "v", review), _run(result, "d", decide)]
        for t in threads:
            t.join(15)
        assert result["v"] is None and result["d"] is None, result
        assert _live(eng, offer=offer) == 0
    assert _deadlocks(eng) == deadlocks


# --- R8 decision + notices after an unknown COMMIT -----------------------------------------

@pytest.mark.parametrize("branch", ["committed", "rolled_back"])
def test_r8_an_unknown_decision_commit_never_duplicates_decision_or_notice(
        pg_client, pg_migrated_engine, branch):
    from sqlalchemy.engine import make_url

    from app.core import db as core_db
    from app.core.db_failures import unavailability_reason
    from tests.pg_fault_proxy import FreezableProxy
    from tests.test_db_deadlines_pg import DEADLINE_S, FAST, SLACK_S, _bounded

    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    _file_and_commit(eng, _account(eng), offer)
    mod = _account(eng, role="admin")
    target = make_url(TEST_DATABASE_URL)
    proxy = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    pe = core_db.create_bounded_engine(proxy.url(), deadlines=FAST, pool_size=1, max_overflow=0)
    try:
        s = _session(pe)
        first = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
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
            done = _scalar(eng, "SELECT count(*) FROM moderation_decisions WHERE target_id = :o",
                           o=offer)
            gone = not _scalar(eng, "SELECT count(*) FROM pg_stat_activity WHERE pid = :p",
                               p=server_pid)
            if (branch == "committed" and done) or (branch == "rolled_back" and gone):
                break
            time.sleep(0.05)
        body = trust_router.DecisionIn(target_type="LISTING", target_id=offer,
                                       action="VISIBILITY_LIMITED", reason_code="SCAM",
                                       expected_head_decision_id=None)
        with _session(eng) as retry:
            if branch == "committed":
                with pytest.raises(HTTPException) as stale:
                    trust_router.decide(body, moderator=_user(retry, mod), db=retry)
                assert stale.value.status_code == 409
                assert first.decision_id in stale.value.detail
                assert _notices(eng, first.decision_id) == 1
            else:
                out = trust_router.decide(body, moderator=_user(retry, mod), db=retry)
                assert _notices(eng, first.decision_id) == 0  # the lost attempt left nothing
                assert _notices(eng, out.decision_id) == 1
        assert _scalar(eng, "SELECT count(*) FROM moderation_decisions WHERE target_id = :o",
                       o=offer) == 1
        assert _scalar(eng, "SELECT count(*) FROM user_notifications n JOIN "
                            "moderation_decisions d ON d.id = n.data->>'decision_id' "
                            "WHERE d.target_id = :o", o=offer) == 1
    finally:
        proxy.resume()
        proxy.stop()
        pe.dispose()


# --- R9 owner projection and queue under concurrent decisions --------------------------------

def test_r9_the_owner_sees_before_or_after_a_decision_never_between(pg_client,
                                                                    pg_migrated_engine):
    eng = pg_migrated_engine
    owner_email, owner, offer = _listing(pg_client)
    reporter = _account(eng)
    _file_and_commit(eng, reporter, offer)
    mod = _account(eng, role="admin")
    reporter_id = _scalar(eng, "SELECT id FROM users WHERE email = :e", e=reporter)

    def owner_view():
        with _session(eng) as db:
            items = props.my_classifieds(user=_user(db, owner_email), db=db)
            return next(i for i in items if i.id == offer)

    d = _session(eng)
    try:
        held = _decide(d, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        during = owner_view()  # the decision is not committed: nothing of it shows
        assert during.moderation.state == "NONE" and during.status == "active"
        d.commit()
    finally:
        d.close()
    after = owner_view()
    assert after.moderation.state == "HELD" and after.status == "paused"
    assert after.moderation.since is not None
    with _session(eng) as db:
        released = _decide(db, offer, "NO_ACTION", expected=held.decision_id, moderator=mod)
        db.commit()
    assert released.held is False
    final = owner_view()
    assert final.moderation.state == "NONE" and final.status == "paused"
    dumped = str(after.model_dump()) + str(final.model_dump())
    assert reporter_id not in dumped and reporter not in dumped
    inbox = pg_client.get("/v1/me/inbox", headers=auth(owner)).json()
    assert reporter_id not in str(inbox)


def test_r9_queue_order_with_urgent_high_and_normal(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    offers = [_listing(pg_client)[2] for _ in range(3)]
    normal, high, urgent = offers
    _file_and_commit(eng, _account(eng), normal, "DUPLICATE")
    _file_and_commit(eng, _account(eng), high, "SCAM")
    rid, _ = _file_and_commit(eng, _account(eng), urgent, "DUPLICATE")
    with eng.begin() as conn:  # URGENT is not derived in 1A; it must still sort first
        conn.execute(text("UPDATE reports SET severity = 'URGENT' WHERE id = :r"), {"r": rid})
    with _session(eng) as db:
        items, total = moderation.queue(db, limit=50, offset=0)
    order = [i.target_id for i in items if i.target_id in offers]
    assert order == [urgent, high, normal]
    assert [i.max_severity for i in items if i.target_id in offers] == ["URGENT", "HIGH", "NORMAL"]
    assert total >= 3


def test_reporting_is_verified_users_only_on_postgres_too(pg_client, pg_migrated_engine):
    """The HTTP surface on the migration-built schema: verification gate,
    201/200 and the moderator detail."""
    eng = pg_migrated_engine
    _o, _t, offer = _listing(pg_client)
    token = register_and_login(pg_client, f"rep-pg-http-{_next()}@example.com", "guest")
    body = {"target_type": "LISTING", "target_id": offer, "reason": "SAFETY"}
    assert pg_client.post("/v1/reports", json=body, headers=auth(token)).status_code == 403
    assert pg_client.post("/v1/me/verify/email/start", headers=auth(token)).status_code == 200
    assert pg_client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                          headers=auth(token)).status_code == 200
    first = pg_client.post("/v1/reports", json=body, headers=auth(token))
    assert first.status_code == 201, first.text
    again = pg_client.post("/v1/reports", json=body, headers=auth(token))
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert _live(eng, offer=offer) == 1
