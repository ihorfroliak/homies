"""Backup → destroy → restore drill for the Phase-1A data (PR-001).

tests/test_dr_restore_pg.py proves the cycle for the ledger and bookings,
seeded through the dormant booking routes. This drill seeds what the deployable
Phase-1A application actually holds — reference geography, structured
addresses, properties with exact (private) and public points, spaces,
listings with price components and freshness, authorities — then:

1. dumps it with pg_dump (custom format, streamed),
2. restores it into a brand-new database with pg_restore,
3. proves the copy is one the business could run on: same migration head,
   same rows, same generated PostGIS columns, the same public search answer,
   and the database invariants still refusing what they must refuse.

Disposable databases only. What this does NOT prove: offsite storage,
encryption at rest, point-in-time recovery, restore time at production volume,
or that a real production backup job runs — see docs/production/BACKUP-RESTORE.md.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.schema import alembic_config
from app.modules.geography import service
from app.modules.geography.models import GeoArea, GeoSource
from app.modules.properties import freshness
from app.modules.properties.models import ClassifiedOffer
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership
# Importing it also applies its HOMIES_REQUIRE_RESTORE_DRILL check (PR-001R F7).
from tests.test_dr_restore_pg import (
    DRILL_AVAILABLE,
    DRILL_SKIP_REASON,
    PG_DUMP,
    PG_RESTORE,
    _libpq,
    _run,
    _with_database,
)
from tests.test_geography import PL_AREAS, PL_LOCALITIES, SOURCE

pytestmark = pytest.mark.skipif(not DRILL_AVAILABLE, reason=DRILL_SKIP_REASON)

# Tables whose every row must come back identical.
TABLES = ("countries", "geo_sources", "admin_areas", "localities", "geo_areas",
          "geo_external_refs", "addresses", "properties", "spaces", "classified_offers",
          "listing_price_components", "legal_parties", "person_legal_parties",
          "property_authorities", "property_authority_scopes", "attribute_definitions")


def _seed(pg_client, pg_session):
    db = pg_session
    db.add(GeoSource(code=SOURCE, name="Test fixture (not an official register)"))
    db.flush()
    service.import_areas(db, "PL", SOURCE, PL_AREAS)
    service.import_localities(db, "PL", SOURCE, PL_LOCALITIES)
    db.commit()
    krakow = service._by_ref(db, SOURCE, "L-KRK", "locality_id")
    kazimierz = GeoArea(country_code="PL", locality_id=krakow, kind="NEIGHBOURHOOD",
                        name="Kazimierz")
    db.add(kazimierz)
    db.commit()

    owner = register_and_login(pg_client, "dr-phase1@example.com", "host")
    offers = []
    for i, extra in enumerate(({}, {"admin_fee": 45000, "utilities_amount": 30000,
                                     "deposit_amount": 500000}, {})):
        prop = pg_client.post("/v1/properties", json={
            "category": "APARTMENT", "locality_id": krakow, "geo_area_id": kazimierz.id,
            "thoroughfare": "ul. Odtworzona", "building_number": str(10 + i),
            "unit_number": str(i), "postcode": "31-000", "latitude": 50.051 + i / 1000,
            "longitude": 19.945, "area_m2": 40 + i, "rooms": 2, "capacity": 2,
        }, headers=auth(owner))
        assert prop.status_code == 201, prop.text
        verify_ownership(pg_client, owner, prop.json()["id"])
        offer = pg_client.post(f"/v1/properties/{prop.json()['id']}/classifieds", json={
            "title": f"Przywrócone {i}", "rent_amount": 260000 + i, "min_term_months": 12,
            "contact_mode": "message", **extra}, headers=auth(owner)).json()["id"]
        assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                              headers=auth(owner)).status_code == 200
        offers.append(offer)
    # One listing past its freshness window: it must stay non-public after restore.
    db.execute(text("UPDATE classified_offers SET last_confirmed_available_at = :t "
                    "WHERE id = :o"),
               {"t": datetime.now(timezone.utc) - timedelta(days=30), "o": offers[2]})
    db.commit()
    return offers


def _rows(conn, table):
    # Sorted on the whole row, not on the first column: tables with a
    # composite key (property_authority_scopes) tie on column 1, and tied rows
    # come back in no defined order — the comparison was order-flaky (PR-001R).
    return sorted(conn.execute(text(f"SELECT * FROM {table}")).all(), key=repr)  # noqa: S608


def _public_ids(url):
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            return set(db.scalars(select(ClassifiedOffer.id).where(freshness.public_clause(db))))
    finally:
        engine.dispose()


def test_phase1_data_survives_backup_destroy_restore(pg_client, pg_session,
                                                     pg_migrated_engine):
    offers = _seed(pg_client, pg_session)
    with pg_migrated_engine.connect() as conn:
        before = {t: _rows(conn, t) for t in TABLES}
        geogs_before = conn.execute(text(
            "SELECT p.id, ST_AsText(p.exact_geog::geometry), ST_AsText(o.public_geog::geometry) "
            "FROM properties p JOIN classified_offers o ON o.property_id = p.id ORDER BY 1")).all()
        head = conn.scalar(text("SELECT version_num FROM alembic_version"))
    public_before = _public_ids(TEST_DATABASE_URL)
    assert public_before == {offers[0], offers[1]}

    # 1. backup
    artifact = _run([PG_DUMP, "--format=custom", "--no-owner", "--no-privileges",
                     f"--dbname={_libpq(TEST_DATABASE_URL)}"])
    assert artifact[:5] == b"PGDMP", "not a custom-format dump"

    # 2. restore into a database that never saw the data
    scratch = f"homies_dr1_{uuid.uuid4().hex[:8]}"
    admin = create_engine(_with_database(TEST_DATABASE_URL, "postgres"),
                          isolation_level="AUTOCOMMIT")
    with admin.begin() as conn:
        conn.execute(text(f'CREATE DATABASE "{scratch}"'))
    target = _with_database(TEST_DATABASE_URL, scratch)
    restored = create_engine(target)
    try:
        _run([PG_RESTORE, "--no-owner", "--no-privileges", "--exit-on-error",
              f"--dbname={_libpq(target)}"], stdin=artifact)

        # 3. the copy is the same business
        with restored.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == head
            from alembic.script import ScriptDirectory

            assert head == ScriptDirectory.from_config(alembic_config()).get_current_head()
            for table in TABLES:
                assert _rows(conn, table) == before[table], table
            assert conn.execute(text(
                "SELECT p.id, ST_AsText(p.exact_geog::geometry), "
                "ST_AsText(o.public_geog::geometry) FROM properties p "
                "JOIN classified_offers o ON o.property_id = p.id ORDER BY 1")).all() \
                == geogs_before
            assert conn.scalar(text(
                "SELECT count(*) FROM pg_indexes WHERE indexname = "
                "'ix_classified_offers_public_geog'")) == 1
        assert _public_ids(target) == public_before  # same public answer, stale stays hidden

        # ...and the guards still refuse on the copy.
        with pytest.raises(IntegrityError) as caught, restored.begin() as conn:
            conn.execute(text("UPDATE classified_offers SET public_location_precision = "
                              "'EXACT' WHERE id = :o"), {"o": offers[0]})
        assert caught.value.orig.diag.constraint_name == "ck_classified_offers_location_precision"
        with pytest.raises(IntegrityError), restored.begin() as conn:
            conn.execute(text("UPDATE classified_offers SET status = 'published' "
                              "WHERE id = :o"), {"o": offers[0]})
        with pytest.raises(DBAPIError), restored.begin() as conn:  # hierarchy trigger
            top = conn.scalar(text("SELECT id FROM admin_areas WHERE parent_id IS NULL "
                                   "ORDER BY id LIMIT 1"))
            child = conn.scalar(text("SELECT id FROM admin_areas WHERE parent_id = :p "
                                     "LIMIT 1"), {"p": top})
            conn.execute(text("UPDATE admin_areas SET parent_id = :c, level = 3 "
                              "WHERE id = :t"), {"c": child, "t": top})
        with pytest.raises(IntegrityError), restored.begin() as conn:  # one address, one property
            conn.execute(text("UPDATE properties SET address_id = "
                              "(SELECT address_id FROM properties ORDER BY id LIMIT 1) "
                              "WHERE id = (SELECT id FROM properties ORDER BY id DESC LIMIT 1)"))
    finally:
        restored.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": scratch})
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
        admin.dispose()
