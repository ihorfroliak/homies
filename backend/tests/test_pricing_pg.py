"""Price components on real Postgres (Schema v1 §46–§47, §89).

The migration drops the five flat price columns, so its backfill is the only
thing standing between existing listings and losing their price. It is proved
here on a database that has listings — every other test migrates an empty
schema, where the backfill copies nothing and a bug in it is invisible.
"""

import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.schema import alembic_config
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

BEFORE = "c9d3a5e71f28"
AFTER = "d4e8b2c61a95"


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


# (rent, admin, utilities, included, parking, deposit) -> expected (monthly, move_in)
CASES = {
    "everything": ((250000, 50000, 30000, False, 20000, 250000), (350000, 600000)),
    "utilities in the rent": ((200000, 0, 40000, True, 0, 0), (200000, 200000)),
    "rent only": ((180000, 0, 0, False, 0, 0), (180000, 180000)),
}


def _seed(conn) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    user = str(uuid.uuid4())
    conn.execute(
        text("INSERT INTO users (id, email, password_hash, full_name, role, created_at) "
             "VALUES (:id, 'price-mig@example.com', 'x', '', 'host', :now)"),
        {"id": user, "now": now},
    )
    ids = {}
    for n, (label, (flat, _)) in enumerate(CASES.items()):
        prop, space, offer = (str(uuid.uuid4()) for _ in range(3))
        conn.execute(
            text("INSERT INTO properties (id, owner_id, city, district, postcode, municipality, "
                 "address, capacity, bedrooms, bathrooms, has_elevator, furnished, parking, "
                 "pets_allowed, attributes, created_at) VALUES (:id, :u, 'Łódź', '', '', "
                 "'Łódź', :a, 2, 1, 1, false, 'full', 'none', false, '{}', :now)"),
            {"id": prop, "u": user, "a": f"ul. {n}", "now": now},
        )
        conn.execute(
            text("INSERT INTO spaces (id, property_id, space_type, status, created_at, "
                 "updated_at, version) VALUES (:id, :p, 'WHOLE_PROPERTY', 'ACTIVE', now(), "
                 "now(), 1)"),
            {"id": space, "p": prop},
        )
        rent, admin, utilities, included, parking, deposit = flat
        conn.execute(
            text("INSERT INTO classified_offers (id, property_id, space_id, owner_id, title, "
                 "description, status, rent_amount, currency, admin_fee, utilities_amount, "
                 "utilities_included, parking_fee, deposit_amount, other_costs, "
                 "min_term_months, open_ended, contact_phone, contact_mode, created_at) "
                 "VALUES (:id, :p, :s, :u, 'T', '', 'active', :rent, 'PLN', :admin, :util, "
                 ":inc, :park, :dep, '', 12, false, '', 'message', :now)"),
            {"id": offer, "p": prop, "s": space, "u": user, "rent": rent, "admin": admin,
             "util": utilities, "inc": included, "park": parking, "dep": deposit, "now": now},
        )
        ids[label] = offer
    return ids


def test_existing_prices_survive_the_move_to_components(scratch_url):
    _migrate(scratch_url, BEFORE)
    engine = create_engine(scratch_url)
    try:
        with engine.begin() as conn:
            ids = _seed(conn)
        _migrate(scratch_url, AFTER)
        with engine.connect() as conn:
            for label, (flat, (monthly, move_in)) in CASES.items():
                summary = conn.execute(
                    text("SELECT primary_price_minor, estimated_monthly_total_minor, "
                         "move_in_total_minor, version FROM classified_offers WHERE id = :id"),
                    {"id": ids[label]},
                ).one()
                assert summary == (flat[0], monthly, move_in, 1), label

                rent = conn.execute(
                    text("SELECT amount_minor FROM listing_price_components WHERE "
                         "listing_id = :id AND component_type = 'BASE_RENT' "
                         "AND valid_to IS NULL"),
                    {"id": ids[label]},
                ).scalar_one()
                assert rent == flat[0], label

            zero_rows = conn.execute(
                text("SELECT COUNT(*) FROM listing_price_components WHERE amount_minor = 0")
            ).scalar_one()
            flat_left = conn.execute(
                text("SELECT COUNT(*) FROM information_schema.columns WHERE "
                     "table_name = 'classified_offers' AND column_name = 'rent_amount'")
            ).scalar_one()
    finally:
        engine.dispose()

    assert zero_rows == 0, "an absent fee was stored as a zero row"
    assert flat_left == 0, "the flat price columns were left behind as a second truth"


def test_the_downgrade_puts_the_current_price_back(scratch_url):
    _migrate(scratch_url, BEFORE)
    engine = create_engine(scratch_url)
    try:
        with engine.begin() as conn:
            ids = _seed(conn)
        _migrate(scratch_url, AFTER)
        _migrate(scratch_url, BEFORE, down=True)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT rent_amount, admin_fee, utilities_amount, parking_fee, "
                     "deposit_amount FROM classified_offers WHERE id = :id"),
                {"id": ids["everything"]},
            ).one()
    finally:
        engine.dispose()
    assert row == (250000, 50000, 30000, 20000, 250000)


def test_the_database_holds_one_current_row_per_component(pg_session):
    """The partial unique index, on the real engine: history unlimited, "now"
    exactly once."""
    definition = pg_session.scalar(
        text("SELECT indexdef FROM pg_indexes "
             "WHERE indexname = 'uq_listing_price_components_current'")
    )
    assert definition is not None
    assert "UNIQUE" in definition and "valid_to IS NULL" in definition


def test_a_negative_price_never_reaches_a_row(pg_session):
    with pytest.raises(IntegrityError):
        pg_session.execute(
            text("INSERT INTO listing_price_components (id, listing_id, component_type, "
                 "component_key, amount_minor, cadence, mandatory, refundable, estimated, "
                 "valid_from, created_by_user_id, created_at) VALUES ('x', 'nope', "
                 "'BASE_RENT', '', -1, 'MONTHLY', true, false, false, now(), 'u', now())")
        )
        pg_session.commit()
    pg_session.rollback()
