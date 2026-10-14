"""BP-6: observed PostgreSQL serialization, atomic cleanup and generation boundaries."""

from datetime import timedelta

import pytest
from sqlalchemy import select, text

from app.modules.engagement import viewings
from app.modules.engagement.models import Viewing
from app.modules.events.models import DomainEvent
from app.modules.alerts.models import UserNotification
from app.modules.trust import decisions, notices
from tests.conftest import TEST_DATABASE_URL, auth
from tests.test_engagement_safety import _slot
from tests.test_engagement_safety_pg import _setup, _paused, _restrict, _blocked_count
from tests.test_reports_moderation_pg import _account, _deadlocks, _pid, _run, _session, _user

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


def _act(db, setup, moderator, action):
    if action == "restrict":
        result = _restrict(db, setup["conv"], moderator)
        db.commit()
        return result
    if action == "request":
        return viewings.request_viewing(
            setup["offer"], viewings.ViewingRequest(starts_at=_slot(setup["day"], 11)),
            user=_user(db, setup["tenant"]), db=db)
    actor = setup["tenant"] if action == "requester_cancel" else setup["owner"]
    fn = viewings.confirm if action == "confirm" else viewings.cancel
    return fn(setup["viewing"], user=_user(db, actor), db=db)


def _facts(db, viewing_id):
    return list(db.scalars(select(DomainEvent).where(
        DomainEvent.event_type == "ViewingCancelled", DomainEvent.correlation_id == viewing_id)))


def _notices(db, viewing_id):
    return [n for n in db.scalars(select(UserNotification).where(
        UserNotification.notification_type == notices.VIEWING_CANCELLED))
            if n.data["viewing_id"] == viewing_id]


@pytest.mark.parametrize("other", ["confirm", "request", "requester_cancel", "provider_cancel"])
@pytest.mark.parametrize("restriction_first", [True, False])
def test_restriction_serializes_both_orders(pg_client, pg_migrated_engine, other, restriction_first):
    engine = pg_migrated_engine
    setup = _setup(pg_client, viewing=None if other == "request" else "REQUESTED")
    moderator = _account(engine, role="admin")
    deadlocks = _deadlocks(engine)
    paused, gate, reached = _paused(engine)
    blocker = _pid(paused)
    first, second = ("restrict", other) if restriction_first else (other, "restrict")
    results, threads = {}, []
    try:
        threads.append(_run(results, first, lambda: _act(paused, setup, moderator, first)))
        assert reached.wait(15), "first operation never reached COMMIT"

        def next_operation():
            with _session(engine) as db:
                return _act(db, setup, moderator, second)
        threads.append(_run(results, second, next_operation))
        assert _blocked_count(engine, blocker, 1), "second transaction did not wait on first"
    finally:
        gate.set()
        for thread in threads:
            thread.join(25)
        paused.close()
        assert all(not t.is_alive() for t in threads), "race worker did not terminate"
    assert not isinstance(results[first], Exception), results[first]
    if restriction_first:
        assert getattr(results[other], "status_code", None) == 409, results[other]
        expected = "RECONTACT_BLOCKED" if other == "request" else "VIEWING_STATE_CONFLICT"
        assert results[other].detail.startswith(expected)
    else:
        assert not isinstance(results["restrict"], Exception), results["restrict"]
    with _session(engine) as db:
        rows = list(db.scalars(select(Viewing).where(Viewing.listing_id == setup["offer"])))
        if restriction_first and other == "request":
            assert rows == []
            assert list(db.scalars(select(DomainEvent).where(
                DomainEvent.event_type == "ViewingCancelled"))) == []
            assert list(db.scalars(select(UserNotification).where(
                UserNotification.notification_type == notices.VIEWING_CANCELLED))) == []
        else:
            assert len(rows) == 1
            row = rows[0]
            party_won = not restriction_first and other.endswith("cancel")
            source = ("REQUESTER" if other == "requester_cancel" else "PROVIDER") \
                if party_won else "HOMIES"
            assert (row.status, row.cancelled_by) == ("CANCELLED", source)
            facts = _facts(db, row.id)
            assert len(facts) == 1
            assert facts[0].payload["cancelled_by"] == source
            decision = results["restrict"]
            assert facts[0].payload["moderation_decision_id"] == (None if party_won else decision.decision_id)
            if not party_won:
                assert row.cancelled_at == decision.effective_from
                assert set(n.user_id for n in _notices(db, row.id)) == {
                    _user(db, setup["owner"]).id, _user(db, setup["tenant"]).id}
                assert len(_notices(db, row.id)) == 2
            else:
                assert _notices(db, row.id) == []
    assert _deadlocks(engine) == deadlocks


def test_strict_database_boundary_isolation_repeats_and_rollback(pg_client, pg_migrated_engine):
    engine = pg_migrated_engine
    setup = _setup(pg_client)
    other = _setup(pg_client)
    moderator = _account(engine, role="admin")
    with _session(engine) as db:
        tenant = _user(db, setup["tenant"]).id
        outsider = _user(db, other["tenant"]).id
        instant = db.scalar(text("SELECT now()"))
        cases = [
            ("past", setup["offer"], tenant, "CONFIRMED", -1),
            ("equal", setup["offer"], tenant, "REQUESTED", 0),
            ("future_requested", setup["offer"], tenant, "REQUESTED", 1),
            ("future_confirmed", setup["offer"], tenant, "CONFIRMED", 1),
            ("other_requester", setup["offer"], outsider, "REQUESTED", 1),
            ("other_listing", other["offer"], tenant, "CONFIRMED", 1),
            ("declined", setup["offer"], tenant, "DECLINED", 1),
            ("completed", setup["offer"], tenant, "COMPLETED", 1),
            ("no_show", setup["offer"], tenant, "NO_SHOW", 1),
            ("cancelled", setup["offer"], tenant, "CANCELLED", 1),
        ]
        seeded = {}
        for name, listing, requester, state, delta in cases:
            start = instant + timedelta(microseconds=delta)
            row = Viewing(listing_id=listing, requester_user_id=requester, status=state,
                          starts_at=start, ends_at=start + timedelta(minutes=30),
                          cancelled_by="PROVIDER" if state == "CANCELLED" else None,
                          cancelled_at=instant if state == "CANCELLED" else None)
            db.add(row)
            db.flush()
            seeded[name] = row.id
        # A savepoint fixes the same database transaction instant for exact equality,
        # while preserving fixtures when the moderation transaction is rolled back.
        db.flush()
        savepoint = db.begin_nested()
        result = _restrict(db, setup["conv"], moderator)
        assert result.effective_from == instant
        expected = {seeded["future_requested"], seeded["future_confirmed"]}
        assert set(result.cancelled_viewing_ids) == expected
        db.flush()
        assert all(len(_facts(db, v)) == 1 and len(_notices(db, v)) == 2 for v in expected)
        savepoint.rollback()
        db.expire_all()
        for name, _, _, state, _ in cases:
            assert db.get(Viewing, seeded[name]).status == state
        assert all(_facts(db, v) == [] and _notices(db, v) == [] for v in expected)
        assert db.scalar(text("SELECT count(*) FROM moderation_decisions")) == 0
        assert db.scalar(text("SELECT count(*) FROM messages WHERE message_type='SYSTEM'")) == 0
        result = _restrict(db, setup["conv"], moderator)
        assert set(result.cancelled_viewing_ids) == expected
        db.commit()
        for name, _, _, state, _ in cases:
            db.expire_all()
            row = db.get(Viewing, seeded[name])
            assert row.status == ("CANCELLED" if row.id in expected else state)
            if row.id in expected:
                assert row.cancelled_by == "HOMIES" and row.cancelled_at == instant
                assert len(_facts(db, row.id)) == 1
                ns = _notices(db, row.id)
                assert len(ns) == 2
                assert all(set(n.data) == set(notices.VIEWING_NOTICE_DATA_KEYS) for n in ns)
        for head, error in [(None, decisions.StaleHead), (result.decision_id, decisions.InvalidDecision)]:
            with pytest.raises(error):
                _restrict(db, setup["conv"], moderator, expected=head)
            db.rollback()
        assert all(len(_facts(db, v)) == 1 and len(_notices(db, v)) == 2 for v in expected)


def test_cleanup_crosses_generation_but_new_engagement_gate_does_not(pg_client, pg_migrated_engine):
    engine = pg_migrated_engine
    setup = _setup(pg_client, viewing="CONFIRMED")
    moderator = _account(engine, role="admin")
    with _session(engine) as db:
        previous_generation = db.scalar(text(
            "SELECT public_generation FROM classified_offers WHERE id=:id"), {"id": setup["offer"]})
    for action in ("pause", "publish"):
        assert pg_client.post(f"/v1/classifieds/{setup['offer']}/{action}",
                              headers=auth(setup["owner_token"])).status_code == 200
    # Active conversations continue across republish; the viewing created
    # before it must still be included by the later restriction.
    conversation = setup["conv"]
    with _session(engine) as db:
        assert db.scalar(text("SELECT public_generation FROM classified_offers WHERE id=:id"),
                         {"id": setup["offer"]}) == previous_generation + 1
    with _session(engine) as db:
        result = _restrict(db, conversation, moderator)
        db.commit()
        assert result.cancelled_viewing_ids == (setup["viewing"],)
        assert db.get(Viewing, setup["viewing"]).cancelled_by == "HOMIES"
    request_url = f"/v1/classifieds/{setup['offer']}/viewings"
    refused = pg_client.post(request_url, json={"starts_at": _slot(setup["day"], 11)},
                             headers=auth(setup["tenant_token"]))
    assert refused.status_code == 409 and refused.json()["detail"].startswith("RECONTACT_BLOCKED")
    for action in ("pause", "publish"):
        assert pg_client.post(f"/v1/classifieds/{setup['offer']}/{action}",
                              headers=auth(setup["owner_token"])).status_code == 200
    new = pg_client.post(request_url, json={"starts_at": _slot(setup["day"], 11)},
                         headers=auth(setup["tenant_token"]))
    assert new.status_code == 201, new.text
    assert new.json()["cancelled_by"] is None
    with _session(engine) as db:
        assert db.get(Viewing, setup["viewing"]).cancelled_by == "HOMIES"
        assert len(_facts(db, setup["viewing"])) == 1
