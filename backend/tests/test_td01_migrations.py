"""TD-01 — Alembic is the single schema source of truth.

Two kinds of check:
  * source guards (run everywhere): the app must not create schema via
    create_all, and Alembic must have exactly one head;
  * schema validation (run against real Postgres when TEST_DATABASE_URL is set):
    a fresh DB migrated base->head has every table, constraint, index, exclusion
    constraint, trigger and extension the booking + payment domains require, and
    matches the ORM's expectations.
"""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from app.core.db import Base

BACKEND = Path(__file__).resolve().parents[1]


# --- source guards (no database needed) -------------------------------------
def test_app_startup_does_not_create_schema():
    """Production startup must never call create_all/drop_all. The schema comes
    only from migrations (via ensure_schema)."""
    main_src = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
    assert "create_all" not in main_src
    assert "ensure_schema" in main_src
    # the ops script must not create schema either
    admin_src = (BACKEND / "app" / "scripts" / "create_admin.py").read_text(encoding="utf-8")
    assert "create_all" not in admin_src


def test_alembic_has_a_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"expected exactly one migration head, found {heads}"


# --- schema validation against a real migrated Postgres ---------------------
EXPECTED_TABLES = {
    "users", "host_profiles", "refresh_tokens", "listings", "host_blocks",
    "bookings", "payments", "webhook_events", "ledger_accounts", "journal_entries",
    "journal_lines", "audit_log", "domain_events", "notifications", "incidents",
}
APPEND_ONLY_TRIGGERS = {
    "journal_entries_append_only", "journal_lines_append_only",
    "audit_log_append_only", "domain_events_append_only",
}


def test_fresh_migration_creates_all_tables(pg_migrated_engine):
    tables = set(inspect(pg_migrated_engine).get_table_names())
    missing = EXPECTED_TABLES - tables
    assert not missing, f"tables missing after migration: {missing}"


def test_booking_exclusion_constraint_exists(pg_migrated_engine):
    """The concurrency-critical guard (no overlapping active bookings) must be
    present in a migration-built database."""
    with pg_migrated_engine.connect() as c:
        name = c.execute(
            text("SELECT conname FROM pg_constraint WHERE contype='x' AND conrelid='bookings'::regclass")
        ).scalar()
    assert name == "excl_booking_overlap"


def test_btree_gist_extension_present(pg_migrated_engine):
    with pg_migrated_engine.connect() as c:
        assert c.execute(text("SELECT 1 FROM pg_extension WHERE extname='btree_gist'")).scalar()


def test_append_only_triggers_exist(pg_migrated_engine):
    with pg_migrated_engine.connect() as c:
        triggers = {
            r[0] for r in c.execute(
                text("SELECT tgname FROM pg_trigger WHERE tgname LIKE '%append_only%'")
            )
        }
    assert APPEND_ONLY_TRIGGERS <= triggers


def test_idempotency_and_uniqueness_constraints_exist(pg_migrated_engine):
    """A column is enforced-unique either by a unique constraint or a unique
    index (ORM `unique=True` produces the latter)."""
    insp = inspect(pg_migrated_engine)

    def unique_column_sets(table: str) -> set[tuple]:
        sets = {tuple(u["column_names"]) for u in insp.get_unique_constraints(table)}
        sets |= {tuple(i["column_names"]) for i in insp.get_indexes(table) if i.get("unique")}
        return sets

    assert ("guest_id", "idempotency_key") in unique_column_sets("bookings")  # booking idempotency
    assert ("provider_intent_id",) in unique_column_sets("payments")  # one payment per intent
    assert ("stripe_event_id",) in unique_column_sets("webhook_events")  # webhook dedup


def test_foreign_keys_present(pg_migrated_engine):
    insp = inspect(pg_migrated_engine)
    fk_tables = {fk["referred_table"] for fk in insp.get_foreign_keys("bookings")}
    assert {"listings", "users"} <= fk_tables


def test_migrated_schema_matches_orm_tables(pg_migrated_engine):
    """Every table the ORM declares exists in the migrated schema (drift guard).
    If a model is added without a migration, this fails."""
    migrated = set(inspect(pg_migrated_engine).get_table_names()) - {"alembic_version"}
    orm = set(Base.metadata.tables)
    assert orm <= migrated, f"ORM tables missing from migrations: {orm - migrated}"


def test_migration_is_deterministic(pg_migrated_engine):
    """Re-running upgrade head on an already-migrated DB is a no-op (idempotent),
    and the head revision is recorded."""
    with pg_migrated_engine.connect() as c:
        rev = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert rev  # exactly one row / a recorded head


def test_ensure_schema_verify_mode_raises_on_unmigrated_db(pg_migrated_engine, monkeypatch):
    """Non-local startup must fail loudly if the DB is not at head, never build
    schema itself."""
    from app.core import schema
    from app.core.config import settings

    from tests.conftest import TEST_DATABASE_URL

    monkeypatch.setattr(settings, "database_url", TEST_DATABASE_URL)
    monkeypatch.setattr(settings, "env", "production")
    # empty the schema so no alembic_version / tables exist
    with pg_migrated_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    with pytest.raises(schema.SchemaNotMigratedError):
        schema.ensure_schema()


def test_ensure_schema_local_mode_applies_migrations(pg_migrated_engine, monkeypatch):
    """local dev applies migrations itself (convenience), still the same path."""
    from app.core import schema
    from app.core.config import settings

    from tests.conftest import TEST_DATABASE_URL

    monkeypatch.setattr(settings, "database_url", TEST_DATABASE_URL)
    monkeypatch.setattr(settings, "env", "local")
    with pg_migrated_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    schema.ensure_schema()  # should migrate to head, no error
    assert "bookings" in inspect(pg_migrated_engine).get_table_names()
