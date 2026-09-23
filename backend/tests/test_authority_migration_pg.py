"""The authority migration against a database that already has data.

Every other Postgres test migrates an empty schema, so the backfill in
b7e4f19a2c60 never runs on a single row there. A backfill that only ever ran on
nothing is a backfill that fails on the first real deploy, halfway through,
with the schema at a revision nobody planned for. Schema v1 §89 asks for exactly
this: an upgrade from a populated previous schema, not only a fresh one.
"""

import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from app.core.schema import alembic_config
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres migration tests skipped"
)

BEFORE = "a1c6d2e8b407"
AFTER = "b7e4f19a2c60"


def _with_database(url: str, database: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{database}"


@pytest.fixture
def scratch_url(monkeypatch):
    name = f"homies_mig_{uuid.uuid4().hex[:8]}"
    admin = create_engine(_with_database(TEST_DATABASE_URL, "postgres"),
                          isolation_level="AUTOCOMMIT")
    with admin.begin() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = _with_database(TEST_DATABASE_URL, name)
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    try:
        yield url
    finally:
        with admin.begin() as conn:
            conn.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                     "WHERE datname = :d AND pid <> pg_backend_pid()"),
                {"d": name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


def _upgrade(url: str, revision: str) -> None:
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, revision)


def _seed_before(conn) -> dict:
    """Two owners, three properties — one owner with two, so the backfill has
    to reuse a legal party rather than mint one per property."""
    now = datetime.now(timezone.utc)
    ids = {"alice": str(uuid.uuid4()), "bob": str(uuid.uuid4())}
    for key, email, name in (("alice", "alice@example.com", "Alice Owner"),
                             ("bob", "bob@example.com", "")):
        conn.execute(
            text("INSERT INTO users (id, email, password_hash, full_name, role, created_at) "
                 "VALUES (:id, :email, 'x', :name, 'host', :now)"),
            {"id": ids[key], "email": email, "name": name, "now": now},
        )
    props = []
    for owner, address in (("alice", "ul. A 1"), ("alice", "ul. A 2"), ("bob", "ul. B 1")):
        pid = str(uuid.uuid4())
        conn.execute(
            text("INSERT INTO properties (id, owner_id, city, district, postcode, "
                 "municipality, address, capacity, bedrooms, bathrooms, has_elevator, "
                 "furnished, parking, pets_allowed, attributes, created_at) "
                 "VALUES (:id, :owner, 'Warszawa', '', '', 'Warszawa', :addr, 2, 1, 1, "
                 "false, 'full', 'none', false, '{}', :now)"),
            {"id": pid, "owner": ids[owner], "addr": address, "now": now},
        )
        props.append((pid, owner))
    return {"users": ids, "properties": props}


def test_upgrading_a_populated_database_backfills_every_property(scratch_url):
    _upgrade(scratch_url, BEFORE)
    engine = create_engine(scratch_url)
    try:
        with engine.begin() as conn:
            seeded = _seed_before(conn)

        _upgrade(scratch_url, AFTER)

        with engine.connect() as conn:
            authorities = conn.execute(
                text("SELECT property_id, authority_type, status, verification_state "
                     "FROM property_authorities")
            ).fetchall()
            parties = conn.execute(
                text("SELECT p.linked_user_id, l.display_name FROM person_legal_parties p "
                     "JOIN legal_parties l ON l.id = p.legal_party_id")
            ).fetchall()
            scopes = conn.execute(
                text("SELECT COUNT(*) FROM property_authority_scopes")
            ).scalar_one()
    finally:
        engine.dispose()

    assert {row[0] for row in authorities} == {pid for pid, _ in seeded["properties"]}
    assert {row[1:] for row in authorities} == {("OWNER", "ACTIVE", "UNVERIFIED")}, (
        "the backfill must not mark anything verified: nothing was checked"
    )

    # One legal person per account, reused across that account's properties.
    assert len(parties) == 2
    names = {user: name for user, name in parties}
    assert names[seeded["users"]["alice"]] == "Alice Owner"
    # No full name on record: the email stands in rather than an empty string.
    assert names[seeded["users"]["bob"]] == "bob@example.com"

    assert scopes == len(seeded["properties"]) * 5


def test_the_migration_reverses(scratch_url):
    """A downgrade that has never been run is a rollback plan on paper."""
    _upgrade(scratch_url, AFTER)
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", scratch_url)
    command.downgrade(cfg, BEFORE)

    engine = create_engine(scratch_url)
    try:
        with engine.connect() as conn:
            remaining = conn.execute(
                text("SELECT table_name FROM information_schema.tables "
                     "WHERE table_schema = 'public' AND table_name IN "
                     "('legal_parties', 'person_legal_parties', 'property_authorities', "
                     "'property_authority_scopes')")
            ).fetchall()
    finally:
        engine.dispose()
    assert remaining == []
