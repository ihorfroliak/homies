"""TASK-015 Slice 1 on PostgreSQL: the moderation hold under real locks.

C1 hold vs publish · C2 hold vs confirm · C3 two decisions on one head and
direct fork attempts · C4 release vs republish · C5 retry after an ambiguous
COMMIT · C6 lock order (no deadlock) · plus the application role's effective
privileges on the immutable decisions.

Every interleaving is proven with database evidence — the waiter is shown
blocked by the holder's backend (`pg_blocking_pids`) — never with sleeps.
Critical sections call the router/domain functions directly on their own
sessions (no HTTP, no JWT: the local clock-step flake stays out of them).
Holders release well within the 2 s lock_timeout of the bounded engine.
"""

import threading
import time

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.admin import router as admin_router
from app.modules.identity.models import User
from app.modules.properties import router as props
from app.modules.trust import decisions, hold
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership
from tests.test_publication_authority_race_pg import _blocked_on
from tests.test_publication_race_pg import _authority_id, _pause_publication_at

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

WAIT = 15
PROPERTY = {"category": "APARTMENT", "city": "Gdańsk", "address": "ul. Wstrzymana 3",
            "area_m2": 41, "rooms": 2, "capacity": 2}
OFFER = {"title": "Pod moderacją", "rent_amount": 240000, "min_term_months": 12,
         "contact_mode": "phone", "contact_phone": "+48 600 100 200"}

_n = {"i": 0}


def _listing(pg_client, *, publish=True):
    _n["i"] += 1
    email = f"mod-pg-owner-{_n['i']}@example.com"
    owner = register_and_login(pg_client, email, "host")
    prop = pg_client.post("/v1/properties", json={**PROPERTY, "address": f"ul. W {_n['i']}"},
                          headers=auth(owner)).json()["id"]
    verify_ownership(pg_client, owner, prop)
    offer = pg_client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                           headers=auth(owner)).json()["id"]
    if publish:
        assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                              headers=auth(owner)).status_code == 200
    return email, prop, offer


def _moderator(engine, name="m") -> str:
    _n["i"] += 1
    email = f"mod-pg-{name}-{_n['i']}@example.com"
    with Session(engine) as db:
        user = User(email=email, password_hash=hash_password("x-123456789"), role="admin")
        db.add(user)
        db.commit()
    return email


def _user(db, email) -> User:
    return db.scalar(select(User).where(User.email == email))


def _session(engine) -> Session:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def _decide(db, offer, action, *, expected, moderator, reason=None):
    reason = reason or ("REINSTATED_REMEDIED" if action == "NO_ACTION" else "SCAM")
    return decisions.apply_listing_decision(
        db, actor=_user(db, moderator), listing_id=offer, action=action, reason_code=reason,
        expected_head_decision_id=expected)


def _pid(db) -> int:
    return db.scalar(text("SELECT pg_backend_pid()"))


def _row(engine, offer):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT status, public_generation, last_confirmed_available_at "
            "FROM classified_offers WHERE id = :o"), {"o": offer}).one()


def _became_public(engine, offer) -> int:
    with engine.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM domain_events WHERE dedup_key LIKE :k"),
                           {"k": f"ListingBecamePublic:{offer}:%"})


def _chain(engine, offer):
    """(id, action, supersedes) from the first decision to the head."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "WITH RECURSIVE c AS ("
            " SELECT id, action, supersedes_decision_id, 1 AS n FROM moderation_decisions"
            " WHERE target_type = 'LISTING' AND target_id = :o AND supersedes_decision_id IS NULL"
            " UNION ALL SELECT d.id, d.action, d.supersedes_decision_id, c.n + 1"
            " FROM moderation_decisions d JOIN c ON d.supersedes_decision_id = c.id)"
            # the total in the SAME statement: one snapshot, so a decision
            # committing meanwhile cannot make the two disagree
            " SELECT id, action, supersedes_decision_id, (SELECT count(*) FROM "
            " moderation_decisions WHERE target_type = 'LISTING' AND target_id = :o) AS total"
            " FROM c ORDER BY n"), {"o": offer}).all()
    if rows:
        assert len(rows) == rows[0].total, "a decision outside the single line: the chain forked"
    return rows


def _run(result, key, fn):
    def target():
        try:
            result[key] = fn()
        except Exception as exc:  # noqa: BLE001 — the outcome is asserted
            result[key] = exc
    t = threading.Thread(target=target, daemon=True)
    t.start()
    return t


def _offer_row_free(engine, offer) -> bool:
    """Nobody holds the listing's row lock (NOWAIT probe, never waits)."""
    with engine.connect() as conn, conn.begin() as tx:
        try:
            conn.execute(text("SELECT 1 FROM classified_offers WHERE id = :o FOR UPDATE NOWAIT"),
                         {"o": offer})
            return True
        except OperationalError as exc:
            assert exc.orig.sqlstate == "55P03"
            return False
        finally:
            tx.rollback()


def _publish(engine, offer, owner_email):
    db = _session(engine)
    try:
        return props.publish_classified(offer, user=_user(db, owner_email), db=db)
    finally:
        db.close()


def _confirm(engine, offer, owner_email):
    db = _session(engine)
    try:
        return props.confirm_classified(offer, user=_user(db, owner_email), db=db)
    finally:
        db.close()


def _held_409(outcome) -> bool:
    return (isinstance(outcome, HTTPException) and outcome.status_code == 409
            and outcome.detail == props.HELD_BY_MODERATION)


# --- C1 hold vs publish ----------------------------------------------------------


@pytest.mark.parametrize("prior", ["active", "paused"])
def test_c1_a_publish_waiting_behind_a_hold_is_refused(pg_client, pg_migrated_engine, prior):
    eng = pg_migrated_engine
    owner, _prop, offer = _listing(pg_client)
    if prior == "paused":
        with eng.begin() as conn:
            conn.execute(text("UPDATE classified_offers SET status = 'paused' WHERE id = :o"),
                         {"o": offer})
    mod = _moderator(eng)
    generation, events = _row(eng, offer).public_generation, _became_public(eng, offer)

    m = _session(eng)
    try:
        _decide(m, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        result: dict = {}
        t = _run(result, "publish", lambda: _publish(eng, offer, owner))
        assert _blocked_on(eng, "properties", _pid(m)), "publish never waited on the hold"
        m.commit()
    finally:
        m.close()
    t.join(WAIT)
    assert _held_409(result["publish"]), result
    row = _row(eng, offer)
    assert row.status == "paused" and row.public_generation == generation
    assert _became_public(eng, offer) == events
    assert pg_client.get(f"/v1/classifieds/{offer}").status_code == 404


def test_c1_a_hold_waiting_behind_a_publication_takes_it_down(pg_client, pg_migrated_engine,
                                                             monkeypatch):
    eng = pg_migrated_engine
    owner, _prop, offer = _listing(pg_client, publish=False)
    mod = _moderator(eng)
    reached, resume = _pause_publication_at(monkeypatch, "protected")
    result: dict = {}
    t = _run(result, "publish", lambda: _publish(eng, offer, owner))
    try:
        assert reached.wait(WAIT)
        d = _session(eng)
        mt = _run(result, "hold", lambda: (_decide(d, offer, "VISIBILITY_LIMITED",
                                                   expected=None, moderator=mod), d.commit()))
        assert _blocked_on(eng, "properties", reached.pid), "the hold did not wait on publish"
        assert _offer_row_free(eng, offer), "the moderator holds the listing before the property"
    finally:
        resume.set()
    t.join(WAIT)
    mt.join(WAIT)
    d.close()
    assert not isinstance(result["publish"], Exception), result
    assert not isinstance(result["hold"], Exception), result
    row = _row(eng, offer)
    assert row.status == "paused" and row.public_generation == 1  # opened, then held
    assert _chain(eng, offer)[-1].action == "VISIBILITY_LIMITED"


def test_c1_the_head_is_read_after_the_row_lock_is_granted(pg_client, pg_migrated_engine):
    """A writer holding only the listing row (no property lock) commits a hold
    while publish waits inside make_public: the hold must still be seen (it
    would be missed if the head were read in, or before, the locking statement)."""
    eng = pg_migrated_engine
    owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    raw = eng.connect()
    tx = raw.begin()
    try:
        raw.execute(text("SELECT 1 FROM classified_offers WHERE id = :o FOR UPDATE"), {"o": offer})
        moderator_id = raw.scalar(text("SELECT id FROM users WHERE email = :e"), {"e": mod})
        raw.execute(text(
            "INSERT INTO moderation_decisions (id, target_type, target_id, listing_id, action, "
            "reason_code, decided_by_user_id) VALUES (gen_random_uuid()::text, 'LISTING', :o, :o, "
            "'VISIBILITY_LIMITED', 'SCAM', :m)"), {"o": offer, "m": moderator_id})
        raw_pid = raw.scalar(text("SELECT pg_backend_pid()"))
        result: dict = {}
        t = _run(result, "publish", lambda: _publish(eng, offer, owner))
        assert _blocked_on(eng, "classified_offers", raw_pid)
        tx.commit()
    finally:
        raw.close()
    t.join(WAIT)
    assert _held_409(result["publish"]), result


# --- C2 hold vs confirm ----------------------------------------------------------


def test_c2_a_confirm_waiting_behind_a_hold_is_refused(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    before = _row(eng, offer)
    m = _session(eng)
    try:
        _decide(m, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        result: dict = {}
        t = _run(result, "confirm", lambda: _confirm(eng, offer, owner))
        assert _blocked_on(eng, "properties", _pid(m))
        m.commit()
    finally:
        m.close()
    t.join(WAIT)
    assert isinstance(result["confirm"], HTTPException) and result["confirm"].status_code == 409
    after = _row(eng, offer)
    assert after.status == "paused"
    assert after.last_confirmed_available_at == before.last_confirmed_available_at


@pytest.mark.parametrize("skew", ["active", "stale"])
def test_c2_confirm_and_publish_refuse_the_n_minus_1_skew_state(pg_client, pg_migrated_engine,
                                                                 skew):
    """Held but `active`/`stale` — what a previous release ignoring holds can
    leave. Both entries into `active` must refuse, with no side effects."""
    eng = pg_migrated_engine
    owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    with _session(eng) as m:
        _decide(m, offer, "CONTENT_EDIT_REQUIRED", expected=None, moderator=mod,
                reason="MISLEADING_PRICE")
        m.commit()
    with eng.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET status = :s WHERE id = :o"),
                     {"s": skew, "o": offer})
    before = _row(eng, offer)
    with eng.connect() as conn:
        audits = conn.scalar(text("SELECT count(*) FROM audit_log WHERE entity_id = :o"),
                             {"o": offer})
        evts = conn.scalar(text("SELECT count(*) FROM domain_events WHERE correlation_id = :o"),
                           {"o": offer})
    for call in (_confirm, _publish):
        with pytest.raises(HTTPException) as caught:
            call(eng, offer, owner)
        assert caught.value.status_code == 409
        assert caught.value.detail == props.HELD_BY_MODERATION
    assert _row(eng, offer) == before
    with eng.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM audit_log WHERE entity_id = :o"),
                           {"o": offer}) == audits
        assert conn.scalar(text("SELECT count(*) FROM domain_events WHERE correlation_id = :o"),
                           {"o": offer}) == evts


# --- C3 two decisions on one head; forks -----------------------------------------


@pytest.mark.parametrize("from_hold", [False, True])
def test_c3_two_moderators_on_one_head_exactly_one_wins(pg_client, pg_migrated_engine,
                                                        from_hold):
    eng = pg_migrated_engine
    _owner, _prop, offer = _listing(pg_client)
    m1, m2 = _moderator(eng, "a"), _moderator(eng, "b")
    h0 = None
    if from_hold:
        with _session(eng) as s:
            h0 = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=m1).decision_id
            s.commit()
    a = _session(eng)
    result: dict = {}
    try:
        won = _decide(a, offer, "CONTENT_EDIT_REQUIRED" if from_hold else "VISIBILITY_LIMITED",
                      expected=h0, moderator=m1, reason="FAKE")
        b = _session(eng)
        t = _run(result, "b", lambda: (_decide(
            b, offer, "NO_ACTION" if from_hold else "CONTENT_EDIT_REQUIRED", expected=h0,
            moderator=m2, reason="REINSTATED_DECISION_ERROR" if from_hold else "OTHER"),
            b.commit()))
        assert _blocked_on(eng, "properties", _pid(a))
        a.commit()
    finally:
        a.close()
    t.join(WAIT)
    b.close()
    assert isinstance(result["b"], decisions.StaleHead), result
    assert result["b"].current_head_id == won.decision_id
    chain = _chain(eng, offer)
    assert [r.id for r in chain] == [*([h0] if h0 else []), won.decision_id]


def _insert(conn, offer, moderator_id, supersedes, target=None):
    target = target or offer
    conn.execute(text(
        "INSERT INTO moderation_decisions (id, target_type, target_id, listing_id, action, "
        "reason_code, decided_by_user_id, supersedes_decision_id) VALUES "
        "(gen_random_uuid()::text, 'LISTING', :t, :t, 'NO_ACTION', 'REINSTATED_REMEDIED', :m, :s)"),
        {"t": target, "m": moderator_id, "s": supersedes})


@pytest.mark.parametrize("winner_commits", [True, False])
def test_c3_a_direct_fork_of_a_decision_is_refused_by_the_database(
        pg_client, pg_migrated_engine, winner_commits):
    eng = pg_migrated_engine
    _owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    with _session(eng) as s:
        h0 = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod).decision_id
        mid = _user(s, mod).id
        s.commit()
    x = eng.connect()
    xt = x.begin()
    result: dict = {}
    try:
        _insert(x, offer, mid, h0)
        xpid = x.scalar(text("SELECT pg_backend_pid()"))

        def second():
            with eng.begin() as y:
                _insert(y, offer, mid, h0)
        t = _run(result, "y", second)
        assert _blocked_on(eng, "moderation_decisions", xpid)
        xt.commit() if winner_commits else xt.rollback()
    finally:
        x.close()
    t.join(WAIT)
    if winner_commits:
        assert isinstance(result["y"], IntegrityError), result
        assert result["y"].orig.diag.constraint_name == "uq_moderation_decisions_supersedes"
    else:
        assert not isinstance(result.get("y"), Exception), result
    assert len(_chain(eng, offer)) == 2


def test_c3_a_second_first_decision_and_a_cross_target_supersede_are_refused(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o1, _p1, offer = _listing(pg_client)
    _o2, _p2, other = _listing(pg_client)
    mod = _moderator(eng)
    with _session(eng) as s:
        h0 = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod).decision_id
        mid = _user(s, mod).id
        s.commit()
    with pytest.raises(IntegrityError) as caught, eng.begin() as conn:
        _insert(conn, offer, mid, None)
    assert caught.value.orig.diag.constraint_name == "uq_moderation_decisions_first_per_target"
    with pytest.raises(IntegrityError) as caught, eng.begin() as conn:
        _insert(conn, offer, mid, h0, target=other)
    assert caught.value.orig.diag.constraint_name == \
        "fk_moderation_decisions_supersedes_same_target"
    with eng.begin() as conn:  # another target's own first decision is fine
        _insert(conn, other, mid, None)
    with _session(eng) as s:
        assert hold.listing_held(s, offer) and not hold.listing_held(s, other)


# --- C4 release vs republish -----------------------------------------------------


def test_c4_release_never_republishes_and_republish_after_it_opens_a_generation(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    g = _row(eng, offer).public_generation
    with _session(eng) as s:
        h = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod).decision_id
        s.commit()
    with pytest.raises(HTTPException) as caught:
        _publish(eng, offer, owner)
    assert caught.value.detail == props.HELD_BY_MODERATION
    with eng.connect() as conn:
        xmin = conn.scalar(text("SELECT xmin::text FROM classified_offers WHERE id = :o"),
                           {"o": offer})
    m = _session(eng)
    result: dict = {}
    try:
        _decide(m, offer, "NO_ACTION", expected=h, moderator=mod)
        t = _run(result, "publish", lambda: _publish(eng, offer, owner))
        assert _blocked_on(eng, "properties", _pid(m))
        m.commit()
    finally:
        m.close()
    t.join(WAIT)
    assert not isinstance(result["publish"], Exception), result  # after the release: allowed
    row = _row(eng, offer)
    assert row.status == "active" and row.public_generation == g + 1
    with eng.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM domain_events WHERE dedup_key = :k"),
                           {"k": f"ListingBecamePublic:{offer}:{g + 1}"}) == 1
        assert conn.scalar(text("SELECT count(*) FROM listing_public_generations WHERE "
                                "listing_id = :o AND public_generation = :g"),
                           {"o": offer, "g": g + 1}) == 1
    assert xmin  # the release itself wrote nothing to the listing row:
    with _session(eng) as s:  # (a second, standalone release proves it below)
        h2 = _decide(s, offer, "VISIBILITY_LIMITED", expected=_chain(eng, offer)[-1].id,
                     moderator=mod).decision_id
        s.commit()
    with eng.connect() as conn:
        before = conn.scalar(text("SELECT xmin::text FROM classified_offers WHERE id = :o"),
                             {"o": offer})
    with _session(eng) as s:
        _decide(s, offer, "NO_ACTION", expected=h2, moderator=mod,
                reason="REINSTATED_DECISION_ERROR")
        s.commit()
    with eng.connect() as conn:
        assert conn.scalar(text("SELECT xmin::text FROM classified_offers WHERE id = :o"),
                           {"o": offer}) == before
    assert _row(eng, offer).status == "paused"


def test_c4_a_publish_holding_the_lock_is_refused_once_it_sees_the_hold(
        pg_client, pg_migrated_engine, monkeypatch):
    """Owner publish took the property lock first, while the hold is current;
    the release waits; publish refuses (409), then the release commits and a
    later publish succeeds."""
    eng = pg_migrated_engine
    owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    with _session(eng) as s:
        h = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod).decision_id
        s.commit()
    reached, resume = _pause_publication_at(monkeypatch, "protected")
    result: dict = {}
    t = _run(result, "publish", lambda: _publish(eng, offer, owner))
    try:
        assert reached.wait(WAIT)
        r = _session(eng)
        rt = _run(result, "release", lambda: (_decide(r, offer, "NO_ACTION", expected=h,
                                                      moderator=mod), r.commit()))
        assert _blocked_on(eng, "properties", reached.pid)
    finally:
        resume.set()
    t.join(WAIT)
    rt.join(WAIT)
    r.close()
    assert _held_409(result["publish"]), result
    assert not isinstance(result["release"], Exception), result
    monkeypatch.undo()
    assert _publish(eng, offer, owner) is not None
    assert _row(eng, offer).status == "active"


# --- C5 retry after an ambiguous COMMIT ------------------------------------------


def test_c5_a_retry_with_the_old_head_after_a_committed_decision_is_stale(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    with _session(eng) as s:
        first = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        s.commit()  # the caller never learns this (commit_unknown)
    with _session(eng) as s, pytest.raises(decisions.StaleHead) as caught:
        _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
    assert caught.value.current_head_id == first.decision_id
    assert [r.id for r in _chain(eng, offer)] == [first.decision_id]


@pytest.mark.parametrize("branch", ["committed", "rolled_back"])
def test_c5_a_real_unknown_commit_never_branches_the_chain(pg_client, pg_migrated_engine, branch):
    """PR-003 fault proxy: the decision's COMMIT is frozen before the server
    sees it. Committed branch: the held COMMIT reaches the server; the retry
    sees the new head. Rolled-back branch: the server session is terminated
    while frozen; the retry succeeds. Either way one decision supersedes h0."""
    from sqlalchemy.engine import make_url

    from app.core import db as core_db
    from app.core.db_failures import unavailability_reason
    from tests.pg_fault_proxy import FreezableProxy
    from tests.test_db_deadlines_pg import DEADLINE_S, FAST, SLACK_S, _bounded

    eng = pg_migrated_engine
    _owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    with _session(eng) as s:
        h0 = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod).decision_id
        s.commit()
    target = make_url(TEST_DATABASE_URL)
    proxy = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    pe = core_db.create_bounded_engine(proxy.url(), deadlines=FAST, pool_size=1, max_overflow=0)
    try:
        s = _session(pe)
        _decide(s, offer, "NO_ACTION", expected=h0, moderator=mod)
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
        while time.monotonic() < deadline:
            done = len(_chain(eng, offer)) == 2
            if done or branch == "rolled_back":
                break
            time.sleep(0.05)
        time.sleep(0.5 if branch == "rolled_back" else 0)
        with _session(eng) as retry:
            if branch == "committed":
                with pytest.raises(decisions.StaleHead):
                    _decide(retry, offer, "NO_ACTION", expected=h0, moderator=mod)
            else:
                _decide(retry, offer, "NO_ACTION", expected=h0, moderator=mod)
                retry.commit()
        with eng.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM moderation_decisions WHERE "
                                    "supersedes_decision_id = :h"), {"h": h0}) == 1
        assert len(_chain(eng, offer)) == 2
    finally:
        proxy.resume()
        proxy.stop()
        pe.dispose()


# --- C6 lock order: no deadlock with the other property-lock takers ---------------


def _deadlocks(engine) -> int:
    with engine.connect() as conn:
        return conn.scalar(text(
            "SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()"))


def test_c6_hold_and_authority_revoke_serialise_in_both_orders(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    for first in ("moderator", "revoke"):
        _owner, prop, offer = _listing(pg_client)
        mod = _moderator(eng)
        aid = _authority_id(eng, prop)
        deadlocks = _deadlocks(eng)
        result: dict = {}
        m, r = _session(eng), _session(eng)

        def moderate():
            _decide(m, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
            m.commit()

        def revoke():
            return admin_router.revoke_property_authority(aid, admin=_user(r, mod), db=r)

        try:
            if first == "moderator":
                _decide(m, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
                t = _run(result, "revoke", revoke)
                assert _blocked_on(eng, "properties", _pid(m))
                m.commit()
                t.join(WAIT)
            else:
                from app.modules.properties import coordination
                coordination.lock_property(r, prop)
                rpid = _pid(r)
                t = _run(result, "moderate", moderate)
                assert _blocked_on(eng, "properties", rpid)
                assert _offer_row_free(eng, offer)  # the moderator holds nothing below
                r.rollback()
                t.join(WAIT)
                result["revoke"] = revoke()
        finally:
            m.close()
            r.close()
        for key, value in result.items():
            assert not isinstance(value, Exception), (first, key, value)
        assert _row(eng, offer).status == "paused"
        with _session(eng) as s:
            assert hold.listing_held(s, offer)
        assert _deadlocks(eng) == deadlocks


def test_c6_hold_and_owner_pause_serialise(pg_client, pg_migrated_engine):
    """Owner pause takes only the listing row; the moderator waits on it after
    the property lock — never the reverse — and both complete."""
    eng = pg_migrated_engine
    _owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    raw = eng.connect()
    tx = raw.begin()
    result: dict = {}
    try:
        raw.execute(text("UPDATE classified_offers SET status = 'paused' WHERE id = :o"),
                    {"o": offer})
        pause_pid = raw.scalar(text("SELECT pg_backend_pid()"))
        m = _session(eng)
        t = _run(result, "hold", lambda: (_decide(m, offer, "VISIBILITY_LIMITED", expected=None,
                                                  moderator=mod), m.commit()))
        assert _blocked_on(eng, "classified_offers", pause_pid)
        tx.commit()
    finally:
        raw.close()
    t.join(WAIT)
    m.close()
    assert not isinstance(result["hold"], Exception), result
    assert _row(eng, offer).status == "paused"


def test_c6_an_archived_listing_stays_archived_under_a_hold(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    with eng.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET status = 'archived' WHERE id = :o"),
                     {"o": offer})
    with _session(eng) as s:
        applied = _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        s.commit()
    assert applied.listing_status_after == "archived"
    assert _row(eng, offer).status == "archived"


# --- immutability at the database and role level ---------------------------------


def test_decisions_are_append_only_for_everyone_and_unwritable_for_the_app_role(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _owner, _prop, offer = _listing(pg_client)
    mod = _moderator(eng)
    with _session(eng) as s:
        _decide(s, offer, "VISIBILITY_LIMITED", expected=None, moderator=mod)
        s.commit()
    for statement in ("UPDATE moderation_decisions SET reason_code = 'OTHER'",
                      "DELETE FROM moderation_decisions"):
        with pytest.raises(DBAPIError) as caught, eng.begin() as conn:  # even the owner
            conn.execute(text(statement))
        assert "append-only" in str(caught.value.orig)
    with eng.connect() as conn:
        assert conn.scalar(text(
            "SELECT count(*) FROM pg_trigger WHERE tgname = 'moderation_decisions_append_only'"
        )) == 1
