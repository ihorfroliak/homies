"""Space guarantees that only the real database can prove (Schema v1 §28, §89).

SQLite in the fast suite does not enforce foreign keys unless asked, so the
composite key that stops a listing pointing at another flat's room is proved
here. So is the migration's backfill, on a database that already has
properties and listings — every other test migrates an empty schema, where a
backfill runs over nothing.
"""

import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.schema import alembic_config
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

BEFORE = "b7e4f19a2c60"
AFTER = "c9d3a5e71f28"

PROPERTY = {
    "property_type": "apartment",
    "city": "Poznań",
    "municipality": "Poznań",
    "address": "ul. Kluczowa 1",
    "area_m2": 55,
    "rooms": 3,
    "capacity": 4,
}


def _register(pg_client, token, address):
    resp = pg_client.post(
        "/v1/properties", json={**PROPERTY, "address": address}, headers=auth(token)
    )
    assert resp.status_code == 201, resp.text
    verify_ownership(pg_client, token, resp.json()["id"])
    return resp.json()["id"]


def test_the_database_refuses_a_listing_on_another_flats_room(pg_client, pg_session):
    """Bypasses the API on purpose: this is the guarantee that holds when the
    application check has a bug."""
    owner = register_and_login(pg_client, "pg-spaces@example.com", "host")
    here = _register(pg_client, owner, "ul. Tutaj 1")
    there = _register(pg_client, owner, "ul. Tam 2")
    foreign_room = pg_client.post(
        f"/v1/properties/{there}/spaces", json={"label": "Pokój 1"}, headers=auth(owner)
    ).json()["id"]
    offer_id = pg_client.post(
        f"/v1/properties/{here}/classifieds",
        json={"title": "Oferta", "rent_amount": 100000, "min_term_months": 12,
              "contact_mode": "message"},
        headers=auth(owner),
    ).json()["id"]

    with pytest.raises(IntegrityError) as excinfo:
        pg_session.execute(
            text("UPDATE classified_offers SET space_id = :s WHERE id = :o"),
            {"s": foreign_room, "o": offer_id},
        )
        pg_session.commit()
    pg_session.rollback()
    assert "fk_classified_offers_space_same_property" in str(excinfo.value)


def test_the_database_allows_one_active_whole_space(pg_client, pg_session):
    owner = register_and_login(pg_client, "pg-whole@example.com", "host")
    property_id = _register(pg_client, owner, "ul. Cała 3")

    with pytest.raises(IntegrityError) as excinfo:
        pg_session.execute(
            text("INSERT INTO spaces (id, property_id, space_type, status, created_at, "
                 "updated_at, version) VALUES (:id, :p, 'WHOLE_PROPERTY', 'ACTIVE', now(), "
                 "now(), 1)"),
            {"id": str(uuid.uuid4()), "p": property_id},
        )
        pg_session.commit()
    pg_session.rollback()
    assert "uq_spaces_one_active_whole" in str(excinfo.value)


def test_an_archived_whole_space_does_not_block_a_new_one(pg_client, pg_session):
    """The index is partial: history is kept, only the *active* one is unique."""
    owner = register_and_login(pg_client, "pg-rewhole@example.com", "host")
    property_id = _register(pg_client, owner, "ul. Nowa 4")

    pg_session.execute(
        text("UPDATE spaces SET status = 'ARCHIVED', archived_at = now() "
             "WHERE property_id = :p"),
        {"p": property_id},
    )
    pg_session.execute(
        text("INSERT INTO spaces (id, property_id, space_type, status, created_at, "
             "updated_at, version) VALUES (:id, :p, 'WHOLE_PROPERTY', 'ACTIVE', now(), "
             "now(), 1)"),
        {"id": str(uuid.uuid4()), "p": property_id},
    )
    pg_session.commit()


# --- the migration, on data ---------------------------------------------------


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


def test_upgrading_a_populated_database_gives_every_listing_its_whole_space(scratch_url):
    _upgrade(scratch_url, BEFORE)
    engine = create_engine(scratch_url)
    now = datetime.now(timezone.utc)
    user_id = str(uuid.uuid4())
    properties = [str(uuid.uuid4()) for _ in range(2)]
    offers = []
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (id, email, password_hash, full_name, role, created_at) "
                     "VALUES (:id, 'mig@example.com', 'x', '', 'host', :now)"),
                {"id": user_id, "now": now},
            )
            for n, pid in enumerate(properties):
                conn.execute(
                    text("INSERT INTO properties (id, owner_id, city, district, postcode, "
                         "municipality, address, capacity, bedrooms, bathrooms, has_elevator, "
                         "furnished, parking, pets_allowed, attributes, created_at) "
                         "VALUES (:id, :owner, 'Poznań', '', '', 'Poznań', :addr, 2, 1, 1, "
                         "false, 'full', 'none', false, '{}', :now)"),
                    {"id": pid, "owner": user_id, "addr": f"ul. M {n}", "now": now},
                )
                for _ in range(2):  # two listings per property
                    oid = str(uuid.uuid4())
                    conn.execute(
                        text("INSERT INTO classified_offers (id, property_id, owner_id, title, "
                             "description, status, rent_amount, currency, admin_fee, "
                             "utilities_amount, utilities_included, parking_fee, "
                             "deposit_amount, other_costs, min_term_months, open_ended, "
                             "contact_phone, contact_mode, created_at) VALUES (:id, :p, :u, "
                             "'T', '', 'active', 100000, 'PLN', 0, 0, false, 0, 0, '', 12, "
                             "false, '', 'message', :now)"),
                        {"id": oid, "p": pid, "u": user_id, "now": now},
                    )
                    offers.append((oid, pid))

        _upgrade(scratch_url, AFTER)

        with engine.connect() as conn:
            spaces = conn.execute(
                text("SELECT property_id, space_type, status FROM spaces")
            ).fetchall()
            attached = dict(
                conn.execute(
                    text("SELECT o.id, s.property_id FROM classified_offers o "
                         "JOIN spaces s ON s.id = o.space_id")
                ).fetchall()
            )
    finally:
        engine.dispose()

    assert sorted(spaces) == sorted((pid, "WHOLE_PROPERTY", "ACTIVE") for pid in properties)
    assert attached == dict(offers), "a listing was attached to the wrong property's space"


def test_the_spaces_migration_reverses(scratch_url):
    _upgrade(scratch_url, AFTER)
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", scratch_url)
    command.downgrade(cfg, BEFORE)

    engine = create_engine(scratch_url)
    try:
        with engine.connect() as conn:
            gone = conn.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'spaces'")
            ).scalar_one()
            column = conn.execute(
                text("SELECT COUNT(*) FROM information_schema.columns "
                     "WHERE table_name = 'classified_offers' AND column_name = 'space_id'")
            ).scalar_one()
    finally:
        engine.dispose()
    assert (gone, column) == (0, 0)
