"""Geography, address and classification guarantees at the database (TASK-010).

Real PostgreSQL/PostGIS. Every refusal is asserted by SQLSTATE and constraint
name, so a test cannot pass on an unrelated error. The migration is proved on
a database upgraded from Foundation Baseline 002's head with existing rows.
"""

import threading
import time
import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.schema import alembic_config
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

BASELINE_002_HEAD = "d3f5b7a9c1e4"
HEAD = "e4f6a8b0c2d4"


def _uid() -> str:
    return str(uuid.uuid4())


def _area(conn, country="PL", parent=None, level=1, kind="PL_VOIVODESHIP", name="A"):
    aid = _uid()
    conn.execute(text(
        "INSERT INTO admin_areas (id, country_code, parent_id, level, kind_code, official_name, "
        "status, created_at, updated_at) VALUES (:id, :c, :p, :l, :k, :n, 'ACTIVE', now(), now())"),
        {"id": aid, "c": country, "p": parent, "l": level, "k": kind, "n": name})
    return aid


def _country(conn, code="DE", currency="EUR"):
    conn.execute(text(
        "INSERT INTO countries (code, name, default_currency, is_active_market, created_at) "
        "VALUES (:c, :c, :cur, false, now()) ON CONFLICT DO NOTHING"), {"c": code, "cur": currency})


def _refused(engine, sql, params, sqlstate, constraint=None):
    with pytest.raises((IntegrityError, DBAPIError)) as caught, engine.begin() as conn:
        conn.execute(text(sql), params)
    assert caught.value.orig.sqlstate == sqlstate, caught.value.orig
    if constraint:
        assert caught.value.orig.diag.constraint_name == constraint


# --- countries and the hierarchy ----------------------------------------------------


@pytest.mark.parametrize(("code", "sqlstate", "constraint"), [
    ("pl", "23514", "ck_countries_code"),
    ("P1", "23514", "ck_countries_code"),
    ("POL", "22001", None),  # varchar(2) refuses it before the CHECK is reached
])
def test_country_codes_are_iso_alpha_2(pg_session, pg_migrated_engine, code, sqlstate,
                                       constraint):
    _refused(pg_migrated_engine,
             "INSERT INTO countries (code, name, default_currency, is_active_market, created_at) "
             "VALUES (:c, 'x', 'EUR', false, now())", {"c": code}, sqlstate, constraint)


def test_an_area_cannot_be_its_own_parent(pg_session, pg_migrated_engine):
    """On INSERT the BEFORE trigger refuses first (the parent does not exist
    yet); an UPDATE with a level that satisfies the trigger reaches the CHECK."""
    aid = _uid()
    _refused(pg_migrated_engine,
             "INSERT INTO admin_areas (id, country_code, parent_id, level, kind_code, "
             "official_name, created_at, updated_at) VALUES (:id, 'PL', :id, 2, 'PL_COUNTY', "
             "'x', now(), now())", {"id": aid}, "23514", "ck_admin_areas_hierarchy")
    with pg_migrated_engine.begin() as conn:
        top = _area(conn)
    _refused(pg_migrated_engine,
             "UPDATE admin_areas SET parent_id = id, level = 2 WHERE id = :id",
             {"id": top}, "23514", "ck_admin_areas_not_own_parent")


def test_levels_must_follow_the_parent(pg_session, pg_migrated_engine):
    with pg_migrated_engine.begin() as conn:
        top = _area(conn)
    _refused(pg_migrated_engine,
             "INSERT INTO admin_areas (id, country_code, parent_id, level, kind_code, "
             "official_name, created_at, updated_at) VALUES (:id, 'PL', :p, 3, 'PL_COUNTY', "
             "'x', now(), now())", {"id": _uid(), "p": top}, "23514", "ck_admin_areas_hierarchy")
    _refused(pg_migrated_engine,
             "INSERT INTO admin_areas (id, country_code, parent_id, level, kind_code, "
             "official_name, created_at, updated_at) VALUES (:id, 'PL', NULL, 2, 'PL_COUNTY', "
             "'x', now(), now())", {"id": _uid()}, "23514", "ck_admin_areas_root_level")


def test_a_cycle_cannot_be_written(pg_session, pg_migrated_engine):
    """Re-parenting the top of a chain under its own grandchild: the level
    rule makes any cycle impossible, and the trigger says so."""
    with pg_migrated_engine.begin() as conn:
        a = _area(conn)
        b = _area(conn, parent=a, level=2, kind="PL_COUNTY")
        c = _area(conn, parent=b, level=3, kind="PL_MUNICIPALITY")
    # Moving `a` under `c` needs level 4 for a — but a has children.
    _refused(pg_migrated_engine,
             "UPDATE admin_areas SET parent_id = :c, level = 4 WHERE id = :a",
             {"a": a, "c": c}, "23514", "ck_admin_areas_hierarchy")
    # Keeping level 1 under a parent: the BEFORE trigger refuses it (level
    # must be the parent's + 1) before the root-level CHECK is reached.
    _refused(pg_migrated_engine, "UPDATE admin_areas SET parent_id = :c WHERE id = :a",
             {"a": a, "c": c}, "23514", "ck_admin_areas_hierarchy")


def test_two_concurrent_reparentings_cannot_close_a_loop(pg_session, pg_migrated_engine):
    """X and Y are leaves at level 2 under different roots. T1 moves X under Y
    and holds; T2 tries to move Y under X. T2's trigger reads X FOR SHARE, so
    it waits for T1 and then sees X at level 3 — its own level 3 no longer
    follows, and it is refused. Without the share lock both would commit a
    loop X→Y→X."""
    with pg_migrated_engine.begin() as conn:
        r1 = _area(conn, name="R1")
        r2 = _area(conn, name="R2")
        x = _area(conn, parent=r1, level=2, kind="PL_COUNTY", name="X")
        y = _area(conn, parent=r2, level=2, kind="PL_COUNTY", name="Y")
    t1 = pg_migrated_engine.connect()
    tx = t1.begin()
    t1.execute(text("UPDATE admin_areas SET parent_id = :y, level = 3 WHERE id = :x"),
               {"x": x, "y": y})
    outcome: dict = {}

    def second():
        try:
            with pg_migrated_engine.begin() as conn:
                conn.execute(text("UPDATE admin_areas SET parent_id = :x, level = 3 "
                                  "WHERE id = :y"), {"x": x, "y": y})
            outcome["ok"] = True
        except DBAPIError as exc:
            outcome["error"] = exc.orig

    worker = threading.Thread(target=second)
    worker.start()
    try:
        deadline = time.monotonic() + 15
        waited = False
        while time.monotonic() < deadline and not waited:
            with pg_migrated_engine.connect() as probe:
                waited = probe.scalar(text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname = "
                    "current_database() AND cardinality(pg_blocking_pids(pid)) > 0 "
                    "AND query LIKE '%admin_areas%')"))
            time.sleep(0.05)
        assert waited, "the second re-parenting did not wait for the first"
    finally:
        tx.commit()
        t1.close()
        worker.join(15)
    # Whatever the exact error (hierarchy check, or Y's level rule), the loop
    # must not exist.
    assert "ok" not in outcome, "both re-parentings committed"
    with pg_migrated_engine.connect() as conn:
        parents = dict(conn.execute(text(
            "SELECT id, parent_id FROM admin_areas WHERE id IN (:x, :y)"), {"x": x, "y": y}).all())
    assert not (parents[x] == y and parents[y] == x)


def test_a_parent_must_be_in_the_same_country(pg_session, pg_migrated_engine):
    with pg_migrated_engine.begin() as conn:
        _country(conn, "DE")
        top = _area(conn)
    _refused(pg_migrated_engine,
             "INSERT INTO admin_areas (id, country_code, parent_id, level, kind_code, "
             "official_name, created_at, updated_at) VALUES (:id, 'DE', :p, 2, 'DE_KREIS', "
             "'x', now(), now())", {"id": _uid(), "p": top}, "23503",
             "fk_admin_areas_parent_same_country")


def test_kind_codes_carry_a_country_prefix(pg_session, pg_migrated_engine):
    _refused(pg_migrated_engine,
             "INSERT INTO admin_areas (id, country_code, level, kind_code, official_name, "
             "created_at, updated_at) VALUES (:id, 'PL', 1, 'Wojewodztwo', 'x', now(), now())",
             {"id": _uid()}, "23514", "ck_admin_areas_kind_code")


def test_a_locality_must_be_in_its_areas_country(pg_session, pg_migrated_engine):
    with pg_migrated_engine.begin() as conn:
        _country(conn, "DE")
        top = _area(conn)
    _refused(pg_migrated_engine,
             "INSERT INTO localities (id, country_code, admin_area_id, kind, official_name, "
             "created_at, updated_at) VALUES (:id, 'DE', :a, 'CITY', 'x', now(), now())",
             {"id": _uid(), "a": top}, "23503", "fk_localities_area_same_country")


# --- external identifiers ------------------------------------------------------------


def test_external_ids_are_unique_within_their_source_only(pg_session, pg_migrated_engine):
    with pg_migrated_engine.begin() as conn:
        a = _area(conn, name="A")
        b = _area(conn, name="B")
        conn.execute(text("INSERT INTO geo_external_refs (id, source_code, external_id, "
                          "admin_area_id, created_at) VALUES (:i, 'PL_TERYT_TERC', '12', :a, "
                          "now())"), {"i": _uid(), "a": a})
        # The same code in another namespace is a different identifier.
        conn.execute(text("INSERT INTO geo_external_refs (id, source_code, external_id, "
                          "admin_area_id, created_at) VALUES (:i, 'PL_PRG', '12', :a, now())"),
                     {"i": _uid(), "a": a})
    _refused(pg_migrated_engine,
             "INSERT INTO geo_external_refs (id, source_code, external_id, admin_area_id, "
             "created_at) VALUES (:i, 'PL_TERYT_TERC', '12', :b, now())",
             {"i": _uid(), "b": b}, "23505", "uq_geo_external_refs_source_id")
    # One identifier per source per entity.
    _refused(pg_migrated_engine,
             "INSERT INTO geo_external_refs (id, source_code, external_id, admin_area_id, "
             "created_at) VALUES (:i, 'PL_TERYT_TERC', '99', :a, now())",
             {"i": _uid(), "a": a}, "23505", "uq_geo_external_refs_admin_area")


def test_an_external_id_points_at_exactly_one_entity(pg_session, pg_migrated_engine):
    _refused(pg_migrated_engine,
             "INSERT INTO geo_external_refs (id, source_code, external_id, created_at) "
             "VALUES (:i, 'PL_PRG', 'x', now())", {"i": _uid()}, "23514",
             "ck_geo_external_refs_one_target")


# --- addresses and classification ----------------------------------------------------


def test_a_structured_address_needs_a_place(pg_session, pg_migrated_engine):
    _refused(pg_migrated_engine,
             "INSERT INTO addresses (id, country_code, resolution, created_at, updated_at) "
             "VALUES (:i, 'PL', 'STRUCTURED', now(), now())", {"i": _uid()}, "23514",
             "ck_addresses_structured_has_place")


@pytest.mark.parametrize(("category", "subtype", "constraint"), [
    ("ROOM", None, "ck_properties_category"),
    ("HOUSE", "STUDIO", "ck_properties_subtype_in_category"),
    (None, "LOFT", "ck_properties_subtype_needs_category"),
])
def test_the_database_refuses_incoherent_classification(
        pg_session, pg_migrated_engine, category, subtype, constraint):
    with pg_migrated_engine.begin() as conn:
        owner = _uid()
        conn.execute(text("INSERT INTO users (id, email, password_hash, full_name, role, "
                          "created_at) VALUES (:i, :e, 'x', '', 'host', now())"),
                     {"i": owner, "e": f"{owner}@x.example"})
        address = _uid()
        conn.execute(text("INSERT INTO addresses (id, country_code, created_at, updated_at) "
                          "VALUES (:i, 'PL', now(), now())"), {"i": address})
    _refused(pg_migrated_engine,
             "INSERT INTO properties (id, owner_id, city, district, postcode, address, "
             "capacity, bedrooms, bathrooms, has_elevator, furnished, parking, pets_allowed, "
             "attributes, created_at, address_id, category, subtype) VALUES (:i, :o, 'x', '', "
             "'', 'x', 2, 1, 1, false, 'full', 'none', false, '{}', now(), :a, :c, :s)",
             {"i": _uid(), "o": owner, "a": address, "c": category, "s": subtype},
             "23514", constraint)


def test_two_properties_cannot_share_one_address_record(pg_session, pg_migrated_engine):
    with pg_migrated_engine.begin() as conn:
        owner = _uid()
        conn.execute(text("INSERT INTO users (id, email, password_hash, full_name, role, "
                          "created_at) VALUES (:i, :e, 'x', '', 'host', now())"),
                     {"i": owner, "e": f"{owner}@x.example"})
        address = _uid()
        conn.execute(text("INSERT INTO addresses (id, country_code, created_at, updated_at) "
                          "VALUES (:i, 'PL', now(), now())"), {"i": address})
        insert = ("INSERT INTO properties (id, owner_id, city, district, postcode, address, "
                  "capacity, bedrooms, bathrooms, has_elevator, furnished, parking, "
                  "pets_allowed, attributes, created_at, address_id) VALUES (:i, :o, 'x', '', "
                  "'', 'x', 2, 1, 1, false, 'full', 'none', false, '{}', now(), :a)")
        conn.execute(text(insert), {"i": _uid(), "o": owner, "a": address})
    _refused(pg_migrated_engine, insert, {"i": _uid(), "o": owner, "a": address}, "23505",
             "uq_properties_address_id")


def test_spatial_columns_are_postgis_with_gist_indexes(pg_session):
    types = dict(pg_session.execute(text(
        "SELECT c.relname || '.' || a.attname, format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
        "WHERE a.attname IN ('boundary', 'centroid') AND c.relname IN "
        "('admin_areas', 'localities', 'geo_areas')")).all())
    assert types == {
        "admin_areas.boundary": "geography(MultiPolygon,4326)",
        "localities.centroid": "geography(Point,4326)",
        "geo_areas.boundary": "geography(MultiPolygon,4326)",
    }
    indexes = set(pg_session.scalars(text(
        "SELECT indexname FROM pg_indexes WHERE indexdef LIKE '%USING gist%'")))
    assert {"ix_admin_areas_boundary", "ix_localities_centroid", "ix_geo_areas_boundary",
            "ix_properties_exact_geog"} <= indexes


# --- the migration from Foundation Baseline 002 --------------------------------------


def _with_database(url: str, database: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{database}"


@pytest.fixture
def scratch_url(monkeypatch):
    name = f"homies_geo10_{uuid.uuid4().hex[:8]}"
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
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": name})
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


def _migrate(url: str, revision: str, down: bool = False) -> None:
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", url)
    (command.downgrade if down else command.upgrade)(cfg, revision)


LEGACY_ROWS = [
    # property_type, city, district, postcode, address, lat, lon
    ("apartment", "Kraków", "Kazimierz", "31-056", "ul. Józefa 17/12A", 50.051, 19.945),
    ("townhouse", "Wrocław", "", "", "ul. Szeroka 3", None, None),
    ("aparthotel_unit", "Sopot", "", "81-701", "ul. Morska 1/4", 54.44, 18.57),
    ("room", "Łódź", "", "", "ul. Piotrkowska 99/2", None, None),
    (None, "Gdańsk", "", "", "Długa 5", None, None),
]


def test_upgrading_baseline_002_backfills_every_property_without_guessing(scratch_url):
    _migrate(scratch_url, BASELINE_002_HEAD)
    engine = create_engine(scratch_url)
    ids = []
    with engine.begin() as conn:
        owner = _uid()
        conn.execute(text("INSERT INTO users (id, email, password_hash, full_name, role, "
                          "created_at) VALUES (:i, 'o@x.example', 'x', '', 'host', now())"),
                     {"i": owner})
        for ptype, city, district, postcode, address, lat, lon in LEGACY_ROWS:
            pid = _uid()
            ids.append(pid)
            conn.execute(text(
                "INSERT INTO properties (id, owner_id, property_type, city, district, postcode, "
                "municipality, address, latitude, longitude, capacity, bedrooms, bathrooms, "
                "has_elevator, furnished, parking, pets_allowed, attributes, created_at) VALUES "
                "(:i, :o, :t, :c, :d, :pc, 'x', :a, :lat, :lon, 2, 1, 1, false, 'full', 'none', "
                "false, '{}', now())"),
                {"i": pid, "o": owner, "t": ptype, "c": city, "d": district, "pc": postcode,
                 "a": address, "lat": lat, "lon": lon})
        before = conn.execute(text(
            "SELECT id, city, address, latitude, longitude, ST_AsText(exact_geog::geometry) "
            "FROM properties ORDER BY id")).all()

    _migrate(scratch_url, HEAD)

    with engine.connect() as conn:
        rows = {r.id: r for r in conn.execute(text(
            "SELECT p.id, p.property_type, p.category, p.subtype, a.country_code, "
            "a.unstructured_text, a.locality_text, a.district_text, a.postal_code, "
            "a.locality_id, a.resolution, a.source FROM properties p "
            "JOIN addresses a ON a.id = p.address_id")).all()}
        after = conn.execute(text(
            "SELECT id, city, address, latitude, longitude, ST_AsText(exact_geog::geometry) "
            "FROM properties ORDER BY id")).all()
    assert len(rows) == len(LEGACY_ROWS)
    # Legacy location and the exact point are untouched.
    assert before == after
    expected = {
        "apartment": ("APARTMENT", None), "townhouse": ("HOUSE", "TERRACED_HOUSE"),
        "aparthotel_unit": ("APARTMENT", "APARTHOTEL_UNIT"), "room": (None, None),
        None: (None, None),
    }
    for pid, (ptype, city, district, postcode, address, _lat, _lon) in zip(ids, LEGACY_ROWS):
        r = rows[pid]
        assert (r.category, r.subtype) == expected[ptype]
        assert r.property_type == ptype
        assert (r.country_code, r.resolution, r.source) == ("PL", "UNSTRUCTURED",
                                                              "LEGACY_BACKFILL")
        assert (r.unstructured_text, r.locality_text, r.district_text, r.postal_code) == (
            address, city, district, postcode)
        assert r.locality_id is None  # no locality guessed from text

    # The downgrade drops only what this revision added, then upgrade again.
    _migrate(scratch_url, BASELINE_002_HEAD, down=True)
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT id, city, address, latitude, longitude, ST_AsText(exact_geog::geometry) "
            "FROM properties ORDER BY id")).all() == before
        assert conn.scalar(text("SELECT to_regclass('public.addresses')")) is None
    _migrate(scratch_url, HEAD)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM addresses")) == len(LEGACY_ROWS)
    engine.dispose()
