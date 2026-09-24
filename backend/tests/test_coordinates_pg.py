"""Coordinate integrity at the database boundary (TASK-001 F-07) — real PostGIS.

The API refuses bad coordinates; these tests prove the database does too, for
writes that do not come through the API, and that the numeric columns and
the generated geography never describe two different places.
"""

import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DataError, IntegrityError

from app.core.schema import alembic_config
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

BEFORE = "d5e7f9a1b3c4"
AFTER = "a7c9e1f3b5d2"

PROPERTY = {"property_type": "apartment", "city": "Gdańsk", "municipality": "Gdańsk",
            "address": "ul. Równikowa 2", "area_m2": 40, "rooms": 2, "capacity": 2}


def _insert_property(conn, owner_id, lat, lon):
    pid = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO properties (id, owner_id, property_type, city, district, postcode, "
             "municipality, address, latitude, longitude, area_m2, rooms, capacity, bedrooms, "
             "bathrooms, has_elevator, furnished, parking, pets_allowed, attributes, created_at) "
             "VALUES (:id, :owner, 'apartment', 'X', '', '', 'X', 'ul. X', :lat, :lon, 40, 2, 2, "
             "1, 1, false, 'full', 'none', false, '{}', now())"),
        {"id": pid, "owner": owner_id, "lat": lat, "lon": lon},
    )
    return pid


def _owner_id(conn):
    uid = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO users (id, email, password_hash, full_name, role, created_at) "
             "VALUES (:id, :email, 'x', '', 'host', now())"),
        {"id": uid, "email": f"{uid}@example.com"},
    )
    return uid


@pytest.mark.parametrize(
    ("lat", "lon", "constraint"),
    [
        (100, 20, "ck_properties_coordinates_latitude_range"),
        (-90.5, 20, "ck_properties_coordinates_latitude_range"),
        (50, 200, "ck_properties_coordinates_longitude_range"),
        (50, -180.5, "ck_properties_coordinates_longitude_range"),
        ("NaN", 20, "ck_properties_coordinates_latitude_range"),
        (50, "NaN", "ck_properties_coordinates_longitude_range"),
        (50, None, "ck_properties_coordinates_pair"),
        (None, 20, "ck_properties_coordinates_pair"),
    ],
)
def test_the_database_refuses_invalid_exact_positions(pg_session, lat, lon, constraint):
    owner = _owner_id(pg_session)
    with pytest.raises(IntegrityError) as caught:
        _insert_property(pg_session, owner, lat, lon)
        pg_session.flush()
    pg_session.rollback()
    assert caught.value.orig.sqlstate == "23514"  # check_violation
    assert caught.value.orig.diag.constraint_name == constraint


@pytest.mark.parametrize("infinite", ["Infinity", "-Infinity"])
def test_the_column_type_refuses_infinity(pg_session, infinite):
    """numeric(9,6) cannot hold ±Infinity at all (SQLSTATE 22003), before any
    CHECK is consulted. Recorded so a later type change does not lose it."""
    owner = _owner_id(pg_session)
    with pytest.raises(DataError) as caught:
        _insert_property(pg_session, owner, 50, infinite)
        pg_session.flush()
    pg_session.rollback()
    assert caught.value.orig.sqlstate == "22003"


def _insert_offer(conn, pid, owner, public, status="active"):
    now = datetime.now(timezone.utc)
    space = conn.scalar(text(
        "INSERT INTO spaces (id, property_id, space_type, status, version, created_at, "
        "updated_at) VALUES (gen_random_uuid()::text, :p, 'WHOLE_PROPERTY', 'ACTIVE', 1, "
        ":n, :n) RETURNING id"), {"p": pid, "n": now})
    return conn.scalar(text(
        "INSERT INTO classified_offers (id, property_id, space_id, owner_id, title, "
        "description, status, currency, utilities_included, other_costs, contact_mode, contact_phone, "
        "open_ended, public_location_precision, public_latitude, public_longitude, "
        "version, created_at) VALUES (gen_random_uuid()::text, :p, :s, :o, "
        "'t', '', :st, 'PLN', false, '', 'message', '', true, 'APPROXIMATE', :la, :lo, "
        "1, :n) RETURNING id"),
        {"p": pid, "s": space, "o": owner, "st": status, "la": public[0], "lo": public[1],
         "n": now})


@pytest.mark.parametrize(
    ("public", "constraint"),
    [
        ((90.0025, 20.004), "ck_classified_offers_public_coordinates_latitude_range"),
        ((50.0, 180.004), "ck_classified_offers_public_coordinates_longitude_range"),
        ((50.0, None), "ck_classified_offers_public_coordinates_pair"),
    ],
)
def test_the_database_refuses_an_off_globe_public_point(pg_session, public, constraint):
    owner = _owner_id(pg_session)
    pid = _insert_property(pg_session, owner, 50, 20)
    with pytest.raises(IntegrityError) as caught:
        _insert_offer(pg_session, pid, owner, public)
        pg_session.flush()
    pg_session.rollback()
    assert caught.value.orig.sqlstate == "23514"
    assert caught.value.orig.diag.constraint_name == constraint


@pytest.mark.parametrize(("lat", "lon"), [(90, 180), (-90, -180), (54.35, 18.65)])
def test_numeric_columns_and_geography_agree(pg_client, pg_migrated_engine, lat, lon):
    owner = register_and_login(pg_client, "geo-agree@example.com", "host")
    made = pg_client.post("/v1/properties", json={**PROPERTY, "latitude": lat, "longitude": lon},
                          headers=auth(owner))
    assert made.status_code == 201, made.text
    with pg_migrated_engine.connect() as conn:
        row = conn.execute(
            text("SELECT latitude, longitude, ST_Y(exact_geog::geometry), "
                 "ST_X(exact_geog::geometry) FROM properties WHERE id = :p"),
            {"p": made.json()["id"]},
        ).one()
    assert float(row[0]) == pytest.approx(row[2], abs=1e-9)
    assert float(row[1]) == pytest.approx(row[3], abs=1e-9)


def test_the_invalid_pair_from_the_audit_is_refused(pg_client, pg_migrated_engine):
    """TASK-001 reproduction: (100, 200) used to answer 201 and be stored as a
    geography of (80, -160)."""
    owner = register_and_login(pg_client, "badgeo@example.com", "host")
    response = pg_client.post(
        "/v1/properties", json={**PROPERTY, "latitude": 100, "longitude": 200},
        headers=auth(owner),
    )
    assert response.status_code == 422, response.text
    with pg_migrated_engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM properties")) == 0


# --- the migration ------------------------------------------------------------


def _with_database(url: str, database: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{database}"


@pytest.fixture
def scratch_url(monkeypatch):
    name = f"homies_geo_{uuid.uuid4().hex[:8]}"
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


def test_the_migration_refuses_to_guess_an_invalid_location(scratch_url):
    _upgrade(scratch_url, BEFORE)
    engine = create_engine(scratch_url)
    with engine.begin() as conn:
        bad = _insert_property(conn, _owner_id(conn), 100, 200)
    with pytest.raises(RuntimeError, match="will not guess a location") as caught:
        _upgrade(scratch_url, AFTER)
    assert bad in str(caught.value)
    with engine.connect() as conn:
        # Untouched: not normalised, not wrapped, not deleted.
        row = conn.execute(text("SELECT latitude, longitude FROM properties WHERE id = :p"),
                           {"p": bad}).one()
        assert (float(row[0]), float(row[1])) == (100.0, 200.0)
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == BEFORE
    engine.dispose()


def test_the_migration_repairs_only_derived_edge_points(scratch_url):
    """A listing whose flat sits exactly on 90° N had an off-globe public
    point under the old grid. The migration recomputes it; ordinary rows are
    left as they were."""
    _upgrade(scratch_url, BEFORE)
    engine = create_engine(scratch_url)
    with engine.begin() as conn:
        owner = _owner_id(conn)
        edge = _insert_property(conn, owner, 90, 20)
        ordinary = _insert_property(conn, owner, 50.0617, 19.9374)
        offers = {
            "edge": _insert_offer(conn, edge, owner, (90.0025, 20.004)),
            "ordinary": _insert_offer(conn, ordinary, owner, (50.0625, 19.94)),
        }
    _upgrade(scratch_url, AFTER)
    with engine.connect() as conn:
        def point(offer):
            row = conn.execute(text(
                "SELECT public_latitude, public_longitude FROM classified_offers WHERE id = :o"),
                {"o": offer}).one()
            return float(row[0]), float(row[1])
        assert point(offers["edge"]) == (89.9975, 20.004)
        assert point(offers["ordinary"]) == (50.0625, 19.94)
    engine.dispose()
