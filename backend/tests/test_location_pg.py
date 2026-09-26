"""Map search on real PostGIS (Domain Schema v1 §9, §106).

Viewport and radius search run against the PUBLIC point, geodesically, with a
GiST index the planner can actually use — and the migration that introduced
all this is proved on a database that already has listings.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from app.core.schema import alembic_config
from app.modules.properties import location
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

# Kraków, Rynek Główny, and two points measured from it.
RYNEK = (50.061700, 19.937400)
# ~445 m due north: 0.004° of latitude.
NORTH_445M = (50.065700, 19.937400)
# ~3.3 km due east: 0.046° of longitude at 50°N.
EAST_3KM = (50.061700, 19.983400)

PROPERTY = {
    "property_type": "apartment",
    "city": "Kraków",
    "municipality": "Kraków",
    "area_m2": 45,
    "rooms": 2,
    "capacity": 3,
}


def _listed(pg_client, token, point, precision="APPROXIMATE", address=None):
    prop = pg_client.post(
        "/v1/properties",
        json={**PROPERTY, "address": address or f"ul. {point}", "latitude": point[0],
              "longitude": point[1]},
        headers=auth(token),
    )
    assert prop.status_code == 201, prop.text
    verify_ownership(pg_client, token, prop.json()["id"])
    offer = pg_client.post(
        f"/v1/properties/{prop.json()['id']}/classifieds",
        json={"title": "Mapa", "rent_amount": 200000, "min_term_months": 12,
              "contact_mode": "message", "public_location_precision": precision},
        headers=auth(token),
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]
    pg_client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(token))
    return prop.json()["id"], offer_id


def _ids(pg_client, **params):
    resp = pg_client.get("/v1/classifieds", params=params)
    assert resp.status_code == 200, resp.text
    return {o["id"] for o in resp.json()["items"]}


@pytest.fixture
def owner(pg_client):
    return register_and_login(pg_client, "map-owner@example.com", "host")


# --- the generated columns ----------------------------------------------------


def test_exact_geog_is_generated_from_the_coordinates(pg_client, pg_session, owner):
    prop, _ = _listed(pg_client, owner, RYNEK)
    lat, lon = pg_session.execute(
        text("SELECT ST_Y(exact_geog::geometry), ST_X(exact_geog::geometry) "
             "FROM properties WHERE id = :id"),
        {"id": prop},
    ).one()
    assert (round(lat, 6), round(lon, 6)) == RYNEK


def test_public_geog_follows_the_public_point_not_the_flat(pg_client, pg_session, owner):
    _, offer = _listed(pg_client, owner, RYNEK, precision="APPROXIMATE")
    lat, lon = pg_session.execute(
        text("SELECT ST_Y(public_geog::geometry), ST_X(public_geog::geometry) "
             "FROM classified_offers WHERE id = :id"),
        {"id": offer},
    ).one()
    expected = location.public_point(Decimal(str(RYNEK[0])), Decimal(str(RYNEK[1])),
                                     "APPROXIMATE")
    assert (round(lat, 6), round(lon, 6)) == tuple(float(v) for v in expected)
    assert (round(lat, 6), round(lon, 6)) != RYNEK


def test_a_district_only_listing_has_no_geography(pg_client, pg_session, owner):
    _, offer = _listed(pg_client, owner, RYNEK, precision="DISTRICT")
    assert pg_session.execute(
        text("SELECT public_geog FROM classified_offers WHERE id = :id"), {"id": offer}
    ).scalar_one() is None


# --- search -------------------------------------------------------------------


def test_viewport_search(pg_client, owner):
    _, inside = _listed(pg_client, owner, RYNEK)
    _, outside = _listed(pg_client, owner, EAST_3KM)
    # A box around the old town only.
    found = _ids(pg_client, bbox="19.930,50.058,19.945,50.066")
    assert inside in found
    assert outside not in found


def test_radius_search_is_in_metres_on_the_ground(pg_client, owner):
    """Around the centre's public (grid) point — the only point search sees
    since public EXACT was prohibited (D-58). The three flats fall in three
    different cells: the north one's is 0.005° (~556 m) away, the east one's
    ~2.9 km."""
    _, centre = _listed(pg_client, owner, RYNEK)
    _, north = _listed(pg_client, owner, NORTH_445M)
    _, east = _listed(pg_client, owner, EAST_3KM)

    lat, lon = location.public_point(Decimal(str(RYNEK[0])), Decimal(str(RYNEK[1])),
                                     "APPROXIMATE")
    near = dict(near_lat=float(lat), near_lon=float(lon))
    assert _ids(pg_client, **near, radius_m=100) == {centre}
    assert _ids(pg_client, **near, radius_m=1000) == {centre, north}
    assert _ids(pg_client, **near, radius_m=5000) == {centre, north, east}


def test_map_search_ignores_listings_without_a_point(pg_client, owner):
    """A district-only listing has no position to be inside a box or a
    circle. It is still found by district."""
    _, hidden = _listed(pg_client, owner, RYNEK, precision="DISTRICT")
    assert hidden not in _ids(pg_client, near_lat=RYNEK[0], near_lon=RYNEK[1], radius_m=5000)
    assert hidden in _ids(pg_client, city="Kraków")


def test_map_search_never_sees_the_exact_point(pg_client, owner):
    """Searching a tiny circle around the flat itself must not find an
    APPROXIMATE listing — otherwise the radius search is an oracle for the
    exact position."""
    _, offer = _listed(pg_client, owner, RYNEK, precision="APPROXIMATE")
    assert offer not in _ids(pg_client, near_lat=RYNEK[0], near_lon=RYNEK[1], radius_m=5)


def test_the_gist_index_serves_a_radius_query(pg_client, pg_session, owner):
    """§106: evidence that the representative query can use the index, not
    only that the index exists. Sequential scans are disabled for the
    EXPLAIN so the planner shows what it would do on a table large enough to
    matter."""
    _listed(pg_client, owner, RYNEK)
    pg_session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(
        row[0] for row in pg_session.execute(
            text("EXPLAIN SELECT id FROM classified_offers WHERE ST_DWithin(public_geog, "
                 "ST_SetSRID(ST_MakePoint(19.9374, 50.0617), 4326)::geography, 1000)")
        )
    )
    pg_session.rollback()
    assert "ix_classified_offers_public_geog" in plan, plan


# --- the migration, on data ---------------------------------------------------

BEFORE = "d4e8b2c61a95"
AFTER = "f1a7c3d9e2b4"


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


def _migrate(url: str, revision: str, down: bool = False) -> None:
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", url)
    (command.downgrade if down else command.upgrade)(cfg, revision)


def test_existing_listings_get_an_approximate_point(scratch_url):
    _migrate(scratch_url, BEFORE)
    engine = create_engine(scratch_url)
    now = datetime.now(timezone.utc)
    ids = {k: str(uuid.uuid4()) for k in ("user", "prop", "space", "offer",
                                           "prop2", "space2", "offer2")}
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (id, email, password_hash, full_name, role, created_at) "
                     "VALUES (:id, 'geo-mig@example.com', 'x', '', 'host', :now)"),
                {"id": ids["user"], "now": now},
            )
            for prop, space, offer, lat, lon in (
                (ids["prop"], ids["space"], ids["offer"], RYNEK[0], RYNEK[1]),
                (ids["prop2"], ids["space2"], ids["offer2"], None, None),
            ):
                conn.execute(
                    text("INSERT INTO properties (id, owner_id, city, district, postcode, "
                         "municipality, address, latitude, longitude, capacity, bedrooms, "
                         "bathrooms, has_elevator, furnished, parking, pets_allowed, "
                         "attributes, created_at) VALUES (:id, :u, 'Kraków', '', '', "
                         "'Kraków', :a, :lat, :lon, 2, 1, 1, false, 'full', 'none', false, "
                         "'{}', :now)"),
                    {"id": prop, "u": ids["user"], "a": f"ul. {prop[:6]}", "lat": lat,
                     "lon": lon, "now": now},
                )
                conn.execute(
                    text("INSERT INTO spaces (id, property_id, space_type, status, created_at, "
                         "updated_at, version) VALUES (:id, :p, 'WHOLE_PROPERTY', 'ACTIVE', "
                         "now(), now(), 1)"),
                    {"id": space, "p": prop},
                )
                conn.execute(
                    text("INSERT INTO classified_offers (id, property_id, space_id, owner_id, "
                         "title, description, status, currency, utilities_included, "
                         "other_costs, min_term_months, open_ended, contact_phone, "
                         "contact_mode, created_at, version) VALUES (:id, :p, :s, :u, 'T', '', "
                         "'active', 'PLN', false, '', 12, false, '', 'message', :now, 1)"),
                    {"id": offer, "p": prop, "s": space, "u": ids["user"], "now": now},
                )

        _migrate(scratch_url, AFTER)

        with engine.connect() as conn:
            located = conn.execute(
                text("SELECT public_location_precision, public_latitude, public_longitude, "
                     "public_geog IS NOT NULL FROM classified_offers WHERE id = :id"),
                {"id": ids["offer"]},
            ).one()
            unlocated = conn.execute(
                text("SELECT public_latitude, public_geog IS NULL FROM classified_offers "
                     "WHERE id = :id"),
                {"id": ids["offer2"]},
            ).one()
    finally:
        engine.dispose()

    expected = location.public_point(Decimal(str(RYNEK[0])), Decimal(str(RYNEK[1])),
                                     "APPROXIMATE")
    assert located == ("APPROXIMATE", expected[0], expected[1], True)
    assert unlocated == (None, True)


def test_the_location_migration_reverses(scratch_url):
    _migrate(scratch_url, AFTER)
    _migrate(scratch_url, BEFORE, down=True)
    engine = create_engine(scratch_url)
    try:
        with engine.connect() as conn:
            left = conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE "
                     "(table_name = 'classified_offers' AND column_name LIKE 'public_%') "
                     "OR (table_name = 'properties' AND column_name = 'exact_geog')")
            ).fetchall()
    finally:
        engine.dispose()
    assert left == []
