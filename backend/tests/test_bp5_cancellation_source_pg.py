"""BP-5 migration evidence on a disposable PostgreSQL schema, including old writers."""

import json
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.schema import alembic_config
from tests.conftest import TEST_DATABASE_URL
from tests.test_engagement_safety_pg import _setup

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")
OLD, NEW = "11d778ab87a3", "23e89acb98b4"


def _refused(engine, sql, params, *, constraint=None, message=None):
    with pytest.raises(DBAPIError) as caught, engine.begin() as conn:
        conn.execute(text(sql), params)
    assert caught.value.orig.sqlstate == "23514"
    if constraint:
        assert caught.value.orig.diag.constraint_name == constraint
    if message:
        assert message in str(caught.value.orig)


def test_backfill_guards_old_writer_and_non_destructive_round_trip(pg_client, pg_migrated_engine):
    setup = _setup(pg_client, viewing="REQUESTED")
    engine = pg_migrated_engine
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    cases = ["REQUESTER", "PROVIDER", "HOMIES", "missing", "malformed", "conflicting"]
    ids = {case: str(uuid4()) for case in cases}
    try:
        command.downgrade(cfg, OLD)
        with engine.begin() as conn:
            for case, viewing in ids.items():
                conn.execute(text(
                    "INSERT INTO viewings (id, listing_id, requester_user_id, starts_at, ends_at, "
                    "status, attendee_count, created_at, cancelled_at, version) "
                    "SELECT :id, listing_id, requester_user_id, starts_at, ends_at, 'CANCELLED', "
                    "attendee_count, created_at, now(), 2 FROM viewings WHERE id=:seed"),
                    {"id": viewing, "seed": setup["viewing"]})
                if case == "missing":
                    continue
                source = case if case in ("REQUESTER", "PROVIDER", "HOMIES") else "REQUESTER"
                payload = {"viewing_id": viewing, "listing_id": setup["offer"],
                           "prior_status": "REQUESTED", "cancelled_by": source,
                           "cancelled_at": "2026-01-01T00:00:00Z", "moderation_decision_id": None}
                if case == "malformed":
                    payload["listing_id"] = str(uuid4())
                variants = [payload]
                if case == "conflicting":
                    variants.append({**payload, "cancelled_by": "PROVIDER"})
                for n, fact in enumerate(variants):
                    conn.execute(text(
                        "INSERT INTO domain_events (id, event_type, correlation_id, dedup_key, "
                        "payload, occurred_at) VALUES (:id, 'ViewingCancelled', :v, :key, "
                        "CAST(:payload AS json), now())"),
                        {"id": str(uuid4()), "v": viewing,
                         "key": f"ViewingCancelled:{viewing}" if n == 0 else f"conflict:{viewing}",
                         "payload": json.dumps(fact)})
            before = conn.execute(text(
                "SELECT id, status, cancelled_at FROM viewings ORDER BY id")).all()
        command.upgrade(cfg, NEW)
        with engine.connect() as conn:
            after = conn.execute(text(
                "SELECT id, status, cancelled_at FROM viewings ORDER BY id")).all()
            assert after == before
            rows = {r.id: (r.cancelled_by, r.cancellation_source_legacy) for r in conn.execute(text(
                "SELECT id, cancelled_by, cancellation_source_legacy FROM viewings"))}
        for case in cases:
            expected = (case, False) if case in ("REQUESTER", "PROVIDER", "HOMIES") else (None, True)
            assert rows[ids[case]] == expected
        assert rows[setup["viewing"]] == (None, False)

        # The previous release's exact cancellation shape is incompatible: BARRIER.
        _refused(engine, "UPDATE viewings SET status='CANCELLED', cancelled_at=now() WHERE id=:id",
                 {"id": setup["viewing"]}, constraint="ck_viewings_cancellation_source_state")
        _refused(engine, "UPDATE viewings SET cancelled_by='PROVIDER' WHERE id=:id",
                 {"id": ids["REQUESTER"]}, message="source is immutable")
        _refused(engine, "UPDATE viewings SET cancelled_by=NULL WHERE id=:id",
                 {"id": ids["HOMIES"]}, message="source is immutable")
        _refused(engine, "UPDATE viewings SET cancellation_source_legacy=true WHERE id=:id",
                 {"id": setup["viewing"]}, message="source is immutable")
        _refused(engine,
                 "INSERT INTO viewings (id, listing_id, requester_user_id, starts_at, ends_at, "
                 "status, attendee_count, created_at, cancelled_at, version, cancellation_source_legacy) "
                 "SELECT :id, listing_id, requester_user_id, starts_at, ends_at, status, "
                 "attendee_count, created_at, cancelled_at, version, true FROM viewings WHERE id=:old",
                 {"id": str(uuid4()), "old": ids["missing"]}, message="migration-only")
        # A second development round trip retains rows and deterministically restores attribution.
        command.downgrade(cfg, OLD)
        command.upgrade(cfg, NEW)
        with engine.connect() as conn:
            assert conn.execute(text(
                "SELECT id, status, cancelled_at FROM viewings ORDER BY id")).all() == before
            restored = {r.id: (r.cancelled_by, r.cancellation_source_legacy) for r in conn.execute(text(
                "SELECT id, cancelled_by, cancellation_source_legacy FROM viewings"))}
            assert restored == rows
    finally:
        # Leave the shared disposable fixture at head even when an assertion fails.
        command.upgrade(cfg, "head")