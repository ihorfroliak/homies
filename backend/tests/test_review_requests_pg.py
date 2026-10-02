"""TASK-015 Slice 5 on PostgreSQL: review requests under real locks.

S5-R1 duplicate request race · R2 review vs release (both orders) · R3 review
vs keep-hold (both orders) · R4 the 3-per-episode cap across keep-holds and
under concurrency · R5 release ends the episode, a new hold starts a fresh
one · R6 a rolled-back decision leaves the request OPEN · R7 decision COMMIT
outcome unknown (PR-003 proxy, both branches) · R8 queue re-entry and exit ·
R9 an organisation agent whose account role is guest closes the loop, a
stranger does not · plus parallel stress with no deadlock.

Waits are proven with `pg_blocking_pids` (`_blocked_on`), never sleeps; the
critical sections call the services on their own sessions (no HTTP/JWT).
"""

import time

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.modules.trust import decisions, moderation, reviews
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login
from tests.test_organizations import _org, _org_property
from tests.test_publication_authority_race_pg import _blocked_on
from tests.test_reports_moderation_pg import (
    OFFER,
    _account,
    _decide,
    _deadlocks,
    _file_and_commit,
    _listing,
    _pid,
    _run,
    _scalar,
    _session,
    _user,
)

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


def _hold(engine, offer, moderator, expected=None, action="VISIBILITY_LIMITED"):
    with _session(engine) as db:
        applied = _decide(db, offer, action, expected=expected, moderator=moderator)
        db.commit()
        return applied


def _request(db, owner_email, offer, note=None):
    return reviews.request_review(db, requester=_user(db, owner_email), listing_id=offer,
                                  note=note)


def _request_and_commit(engine, owner_email, offer):
    with _session(engine) as db:
        done = _request(db, owner_email, offer)
        db.commit()
        return done.request.id


def _rows(engine, offer):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT r.id, r.status, r.decision_id, r.answered_by_decision_id "
            "FROM moderation_review_requests r JOIN moderation_decisions d "
            "ON d.id = r.decision_id WHERE d.target_id = :o ORDER BY r.created_at"),
            {"o": offer}).all()


def _head_id(engine, offer):
    return _scalar(engine,
                   "SELECT d.id FROM moderation_decisions d WHERE d.target_id = :o AND NOT "
                   "EXISTS (SELECT 1 FROM moderation_decisions s "
                   "WHERE s.supersedes_decision_id = d.id)", o=offer)


# --- R1 ----------------------------------------------------------------------------------

def test_s5_r1_two_simultaneous_requests_make_one(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    owner, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    _hold(eng, offer, mod)
    a = _session(eng)
    result: dict = {}
    try:
        first = _request(a, owner, offer)
        b = _session(eng)

        def second():
            try:
                return _request(b, owner, offer)
            finally:
                b.rollback()
                b.close()
        t = _run(result, "b", second)
        assert _blocked_on(eng, "properties", _pid(a)), "the second request did not wait"
        a.commit()
        t.join(15)
    finally:
        a.close()
    assert isinstance(result["b"], reviews.AlreadyOpen)
    rows = _rows(eng, offer)
    assert [(r.id, r.status) for r in rows] == [(first.request.id, "OPEN")]


# --- R2 / R3 -----------------------------------------------------------------------------

@pytest.mark.parametrize("answer", ["release", "keep"])
def test_s5_r2_r3_review_committed_first_is_answered_by_the_decision(
        pg_client, pg_migrated_engine, answer):
    eng = pg_migrated_engine
    owner, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    h0 = _hold(eng, offer, mod).decision_id
    r = _session(eng)
    result: dict = {}
    try:
        rid = _request(r, owner, offer).request.id
        d = _session(eng)

        def decide():
            if answer == "release":
                out = _decide(d, offer, "NO_ACTION", expected=h0, moderator=mod)
            else:
                out = _decide(d, offer, "CONTENT_EDIT_REQUIRED", expected=h0, moderator=mod,
                              reason="MISLEADING_PRICE")
            d.commit()
            d.close()
            return out
        t = _run(result, "d", decide)
        assert _blocked_on(eng, "properties", _pid(r))
        r.commit()
        t.join(15)
    finally:
        r.close()
    applied = result["d"]
    assert applied.answered_review_request_id == rid
    [row] = _rows(eng, offer)
    assert (row.status, row.answered_by_decision_id) == ("ANSWERED", applied.decision_id)


@pytest.mark.parametrize("answer", ["release", "keep"])
def test_s5_r2_r3_decision_committed_first_decides_what_the_review_sees(
        pg_client, pg_migrated_engine, answer):
    eng = pg_migrated_engine
    owner, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    h0 = _hold(eng, offer, mod).decision_id
    d = _session(eng)
    result: dict = {}
    try:
        if answer == "release":
            applied = _decide(d, offer, "NO_ACTION", expected=h0, moderator=mod)
        else:
            applied = _decide(d, offer, "CONTENT_EDIT_REQUIRED", expected=h0, moderator=mod,
                              reason="MISLEADING_PRICE")
        r = _session(eng)

        def request():
            try:
                done = _request(r, owner, offer)
                r.commit()
                return done
            finally:
                r.close()
        t = _run(result, "r", request)
        assert _blocked_on(eng, "properties", _pid(d))
        d.commit()
        t.join(15)
    finally:
        d.close()
    rows = _rows(eng, offer)
    if answer == "release":
        assert isinstance(result["r"], reviews.NotHeld) and rows == []
    else:  # attached to the new current hold, never to the superseded one
        assert [(x.status, x.decision_id) for x in rows] == [("OPEN", applied.decision_id)]
    assert not [x for x in rows if x.decision_id == h0]


# --- R4 / R5 -----------------------------------------------------------------------------

def test_s5_r4_three_per_continuous_episode_and_r5_release_starts_afresh(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    owner, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    head = _hold(eng, offer, mod).decision_id
    for _ in range(3):
        _request_and_commit(eng, owner, offer)
        head = _hold(eng, offer, mod, expected=head, action="CONTENT_EDIT_REQUIRED").decision_id
    with _session(eng) as db, pytest.raises(reviews.CapReached):
        _request(db, owner, offer)
    assert [r.status for r in _rows(eng, offer)] == ["ANSWERED"] * 3
    # concurrent attempts at the cap: all refused, nothing written
    result: dict = {}
    threads = []
    for k in range(3):
        def attempt(k=k):
            with _session(eng) as db:
                return _request(db, owner, offer)
        threads.append(_run(result, k, attempt))
    for t in threads:
        t.join(15)
    assert all(isinstance(v, reviews.CapReached) for v in result.values()), result
    # R5: a release ends the episode; no request while released
    with _session(eng) as db:
        released = _decide(db, offer, "NO_ACTION", expected=head, moderator=mod)
        db.commit()
    with _session(eng) as db, pytest.raises(reviews.NotHeld):
        _request(db, owner, offer)
    # a later hold is a new episode: a fresh allowance
    head = _hold(eng, offer, mod, expected=released.decision_id).decision_id
    for _ in range(3):
        _request_and_commit(eng, owner, offer)
        head = _hold(eng, offer, mod, expected=head, action="CONTENT_EDIT_REQUIRED").decision_id
    with _session(eng) as db, pytest.raises(reviews.CapReached):
        _request(db, owner, offer)
    assert len(_rows(eng, offer)) == 6


# --- R6 ------------------------------------------------------------------------------------

def test_s5_r6_a_rolled_back_decision_leaves_the_request_open(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    owner, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    h0 = _hold(eng, offer, mod).decision_id
    rid = _request_and_commit(eng, owner, offer)
    with _session(eng) as db:
        applied = _decide(db, offer, "NO_ACTION", expected=h0, moderator=mod)
        assert applied.answered_review_request_id == rid
        db.rollback()
    [row] = _rows(eng, offer)
    assert (row.status, row.answered_by_decision_id) == ("OPEN", None)
    assert _head_id(eng, offer) == h0


# --- R7 ------------------------------------------------------------------------------------

@pytest.mark.parametrize("branch", ["committed", "rolled_back"])
def test_s5_r7_unknown_decision_commit_never_leaves_a_half_state(
        pg_client, pg_migrated_engine, branch):
    from sqlalchemy.engine import make_url

    from app.core import db as core_db
    from app.core.db_failures import unavailability_reason
    from tests.pg_fault_proxy import FreezableProxy
    from tests.test_db_deadlines_pg import DEADLINE_S, FAST, SLACK_S, _bounded

    eng = pg_migrated_engine
    owner, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    h0 = _hold(eng, offer, mod).decision_id
    rid = _request_and_commit(eng, owner, offer)
    target = make_url(TEST_DATABASE_URL)
    proxy = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    pe = core_db.create_bounded_engine(proxy.url(), deadlines=FAST, pool_size=1, max_overflow=0)
    try:
        s = _session(pe)
        first = _decide(s, offer, "NO_ACTION", expected=h0, moderator=mod)
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
            done = _head_id(eng, offer) != h0
            gone = not _scalar(eng, "SELECT count(*) FROM pg_stat_activity WHERE pid = :p",
                               p=server_pid)
            if (branch == "committed" and done) or (branch == "rolled_back" and gone):
                break
            time.sleep(0.05)
        [row] = _rows(eng, offer)
        if branch == "committed":
            assert (row.status, row.answered_by_decision_id) == ("ANSWERED", first.decision_id)
            with _session(eng) as retry, pytest.raises(decisions.StaleHead):
                _decide(retry, offer, "NO_ACTION", expected=h0, moderator=mod)
        else:
            assert (row.status, row.answered_by_decision_id) == ("OPEN", None)
            with _session(eng) as retry:
                again = _decide(retry, offer, "NO_ACTION", expected=h0, moderator=mod)
                retry.commit()
            assert again.answered_review_request_id == rid
        # never a decision whose superseded hold still has an OPEN request
        assert _scalar(eng, "SELECT count(*) FROM moderation_review_requests r WHERE "
                            "r.status = 'OPEN' AND EXISTS (SELECT 1 FROM moderation_decisions "
                            "s WHERE s.supersedes_decision_id = r.decision_id)") == 0
    finally:
        proxy.resume()
        proxy.stop()
        pe.dispose()


# --- R8 ------------------------------------------------------------------------------------

def test_s5_r8_a_review_brings_a_resolved_target_back_and_the_answer_takes_it_out(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    owner, _t, offer = _listing(pg_client)
    _file_and_commit(eng, _account(eng), offer, "SCAM")
    mod = _account(eng, role="admin")
    h0 = _hold(eng, offer, mod).decision_id  # resolves the report

    def in_queue():
        with _session(eng) as db:
            items, _total = moderation.queue(db, limit=100, offset=0)
            return {i.target_id: i for i in items}.get(offer)
    assert in_queue() is None
    _request_and_commit(eng, owner, offer)
    item = in_queue()
    assert item is not None and item.live_reports == 0 and item.max_severity is None
    assert item.has_open_review_request and item.held
    _hold(eng, offer, mod, expected=h0, action="CONTENT_EDIT_REQUIRED")
    assert in_queue() is None


# --- R9 ------------------------------------------------------------------------------------

def test_s5_r9_an_agent_with_a_guest_account_closes_the_loop(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    boss = register_and_login(pg_client, "boss-s5pg@agencja.pl", "host")
    org = _org(pg_client, boss, slug="agencja-s5pg")
    prop = _org_property(pg_client, boss, org["id"], address="ul. Rewizyjna 9")
    agent = register_and_login(pg_client, "agent-s5pg@agencja.pl", "guest")
    assert pg_client.post(f"/v1/organizations/{org['id']}/members",
                          json={"email": "agent-s5pg@agencja.pl", "role": "AGENT"},
                          headers=auth(boss)).status_code == 202
    assert pg_client.post(f"/v1/organizations/{org['id']}/membership/accept",
                          headers=auth(agent)).status_code == 200
    offer = pg_client.post(f"/v1/properties/{prop['id']}/classifieds", json=OFFER,
                           headers=auth(boss)).json()["id"]
    assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                          headers=auth(boss)).status_code == 200
    mod = _account(eng, role="admin")
    _hold(eng, offer, mod)
    assert _scalar(eng, "SELECT role FROM users WHERE email = 'agent-s5pg@agencja.pl'") == "guest"
    inbox = pg_client.get("/v1/me/inbox", headers=auth(agent)).json()["items"]
    assert [i["notification_type"] for i in inbox] == ["MODERATION_LISTING_HELD"]
    mine = pg_client.get("/v1/me/classifieds", headers=auth(agent)).json()
    assert [i["id"] for i in mine] == [offer] and mine[0]["moderation"]["state"] == "HELD"
    created = pg_client.post(f"/v1/classifieds/{offer}/moderation-review", json={},
                             headers=auth(agent))
    assert created.status_code == 201, created.text
    stranger = register_and_login(pg_client, "stranger-s5pg@example.com", "guest")
    assert pg_client.get("/v1/me/classifieds", headers=auth(stranger)).json() == []
    refused = pg_client.post(f"/v1/classifieds/{offer}/moderation-review", json={},
                             headers=auth(stranger))
    missing = pg_client.post("/v1/classifieds/00000000-0000-0000-0000-000000000000/"
                             "moderation-review", json={}, headers=auth(stranger))
    assert refused.status_code == missing.status_code == 404
    assert refused.json() == missing.json()


# --- lock order: reviews and decisions in parallel ---------------------------------------

def test_s5_reviews_and_decisions_in_parallel_never_deadlock(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    deadlocks = _deadlocks(eng)
    for _ in range(5):
        owner, _t, offer = _listing(pg_client)
        mod = _account(eng, role="admin")
        _file_and_commit(eng, _account(eng), offer)  # resolved by the hold
        h0 = _hold(eng, offer, mod).decision_id
        result: dict = {}

        def review(offer=offer, owner=owner):
            with _session(eng) as db:
                try:
                    _request(db, owner, offer)
                    db.commit()
                    return "requested"
                except reviews.ReviewRefused as exc:
                    return type(exc).__name__

        def decide(offer=offer, mod=mod, h0=h0):
            with _session(eng) as db:
                _decide(db, offer, "NO_ACTION", expected=h0, moderator=mod)
                db.commit()
                return "released"
        threads = [_run(result, "r", review), _run(result, "d", decide)]
        for t in threads:
            t.join(15)
        assert result["d"] == "released" and result["r"] in ("requested", "NotHeld"), result
        assert _scalar(eng, "SELECT count(*) FROM moderation_review_requests r JOIN "
                            "moderation_decisions d ON d.id = r.decision_id WHERE "
                            "d.target_id = :o AND r.status = 'OPEN'", o=offer) == 0
    assert _deadlocks(eng) == deadlocks


def test_s5_a_conflicted_moderator_still_cannot_answer(pg_client, pg_migrated_engine):
    """A review request does not soften conflict of interest: a moderator
    who manages the property is still refused, even answering a review."""
    eng = pg_migrated_engine
    owner, _t, offer = _listing(pg_client)
    mod = _account(eng, role="admin")
    h0 = _hold(eng, offer, mod).decision_id
    _request_and_commit(eng, owner, offer)
    with eng.begin() as conn:  # the requesting manager is also a moderator
        conn.execute(text("UPDATE users SET role = 'admin' WHERE email = :e"), {"e": owner})
    mod = owner
    from app.modules.trust import router as trust_router
    body = trust_router.DecisionIn(target_type="LISTING", target_id=offer, action="NO_ACTION",
                                   reason_code="REINSTATED_REMEDIED",
                                   expected_head_decision_id=h0)
    with _session(eng) as db, pytest.raises(HTTPException) as refused:
        trust_router.decide(body, moderator=_user(db, mod), db=db)
    assert refused.value.status_code == 403
    assert [r.status for r in _rows(eng, offer)] == ["OPEN"]
