"""A real backup and restore cycle, executed — not described.

The scripts in `scripts/backup/` have existed since 2026-07-05 and the drill
was run once, by hand, that day. Everything since — the Property/Offer split,
the classifieds board, the attribute catalogue, phone verification, the reveal
quota — landed without that cycle running again. A backup pipeline nobody
exercises is a backup pipeline that is already broken; the only question is
whether you find out during a drill or during an incident.

So this runs the actual thing on every CI build: pg_dump the live schema,
restore it into a fresh database, and prove the copy is one you could really
run the business on.

"Could run on" means more than "the rows came back". A restore that quietly
loses the append-only triggers gives you a ledger that *looks* identical and no
longer resists tampering — the most dangerous possible outcome, because it
passes every check that only counts rows. So the guards are exercised on the
copy, not merely counted.
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from tests.conftest import TEST_DATABASE_URL, auth, register_and_login

# The client tools are not importable Python; they are binaries that must match
# the server's major version. PG_BIN lets a deployment point at a pinned client
# (commonly inside a container) when the host's is older than the server —
# version skew is the usual reason a backup job fails in production.
_PG_BIN = os.environ.get("PG_BIN") or None
PG_DUMP = shutil.which("pg_dump", path=_PG_BIN) or shutil.which("pg_dump")
PG_RESTORE = shutil.which("pg_restore", path=_PG_BIN) or shutil.which("pg_restore")

pytestmark = pytest.mark.skipif(
    not (TEST_DATABASE_URL and PG_DUMP and PG_RESTORE),
    reason="needs TEST_DATABASE_URL and the pg_dump/pg_restore client tools",
)

LISTING = {
    "title": "Apartament przy Wiśle",
    "description": "Dwa pokoje, blisko centrum.",
    "city": "Warszawa",
    "address": "ul. Zapasowa 4",
    "nightly_price_amount": 25000,
    "capacity": 4,
}

PROPERTY = {
    "property_type": "apartment",
    "city": "Kraków",
    "municipality": "Kraków",
    "address": "ul. Kopiowa 7",
    "area_m2": 48,
    "rooms": 2,
    "capacity": 3,
}

CLASSIFIED = {
    "title": "Mieszkanie długoterminowo",
    "rent_amount": 280000,
    "min_term_months": 12,
    "contact_mode": "phone",
    "contact_phone": "+48 500 777 888",
}


def _libpq(url: str) -> str:
    """SQLAlchemy speaks `postgresql+psycopg://`; libpq does not."""
    return url.replace("+psycopg", "", 1)


def _with_database(url: str, database: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{database}"


def _run(argv: list[str], stdin: bytes | None = None) -> bytes:
    """Streams rather than passing --file.

    The artifact goes through stdout and comes back through stdin, so the same
    invocation can be piped into gzip, into an encryptor, or straight at an
    offsite bucket — which is what `backup.sh` already does. A --file path
    would also have to exist wherever the client binary runs, which it does not
    when that client is pinned inside a container.
    """
    proc = subprocess.run(argv, input=stdin, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"{argv[0]} failed ({proc.returncode}):\n"
            f"{proc.stderr.decode(errors='replace') if proc.stderr else ''}"
        )
    return proc.stdout


# --- the cycle ----------------------------------------------------------------


def _seed_a_real_business_day(client):
    """Money, a free-board listing, a verified phone and a disclosure.

    Seeded through the API rather than by INSERT so the dump contains what
    production would actually hold, including the rows the triggers and
    constraints are there to protect.
    """
    from tests.conftest import fire_webhook, last_code

    host = register_and_login(client, "dr-host@example.com", "host")
    guest = register_and_login(client, "dr-guest@example.com", "guest")

    listing = client.post("/v1/listings", json=LISTING, headers=auth(host))
    assert listing.status_code == 201, listing.text
    listing_id = listing.json()["id"]
    client.post(f"/v1/listings/{listing_id}/publish", headers=auth(host))

    booking = client.post(
        "/v1/bookings",
        json={"listing_id": listing_id, "check_in": "2027-03-01", "check_out": "2027-03-05"},
        headers={**auth(guest), "Idempotency-Key": "dr-booking-0001"},
    )
    assert booking.status_code == 201, booking.text
    fire_webhook(client, booking.json()["payment_intent_id"])

    # The free board, so the copy is checked against the whole current schema
    # and not only the tables that existed when the drill was first written.
    prop = client.post("/v1/properties", json=PROPERTY, headers=auth(host))
    offer_id = client.post(
        f"/v1/properties/{prop.json()['id']}/classifieds",
        json=CLASSIFIED,
        headers=auth(host),
    ).json()["id"]
    client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(host))

    client.post(
        "/v1/me/verify/phone/start", json={"phone": "+48600000099"}, headers=auth(guest)
    )
    client.post(
        "/v1/me/verify/phone/confirm", json={"code": last_code()}, headers=auth(guest)
    )
    revealed = client.post(f"/v1/classifieds/{offer_id}/contact", headers=auth(guest))
    assert revealed.status_code == 200, revealed.text


@pytest.fixture
def restored(pg_client, tmp_path):
    """Dump the seeded database, restore it into a fresh one, yield its URL."""
    _seed_a_real_business_day(pg_client)

    artifact = _run([PG_DUMP, "--format=custom", "--no-owner", "--no-privileges",
                     f"--dbname={_libpq(TEST_DATABASE_URL)}"])
    dump = tmp_path / "homies.dump"
    dump.write_bytes(artifact)
    assert artifact, "pg_dump produced an empty artifact"
    # Custom-format dumps start with this magic. An empty or plain-text file
    # would still "restore" into an empty database and look like a success.
    assert artifact[:5] == b"PGDMP", "not a custom-format dump"

    scratch = f"homies_dr_{uuid.uuid4().hex[:8]}"
    admin = create_engine(
        _with_database(TEST_DATABASE_URL, "postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.begin() as conn:
        conn.execute(text(f'CREATE DATABASE "{scratch}"'))
    target = _with_database(TEST_DATABASE_URL, scratch)
    try:
        _run(
            [PG_RESTORE, "--no-owner", "--no-privileges", "--exit-on-error",
             f"--dbname={_libpq(target)}"],
            stdin=artifact,
        )
        yield target
    finally:
        with admin.begin() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :d AND pid <> pg_backend_pid()"
                ),
                {"d": scratch},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
        admin.dispose()


def _connect(url: str):
    engine = create_engine(url)
    return engine, engine.connect()


def _verifier():
    """Load the drill's own verification module, by path.

    `scripts/` is not a package, and the point is to run the SAME rules the
    human-driven drill runs. A second implementation here would drift, and the
    one that drifts is the one nobody executes until the night it is needed.
    """
    import importlib.util

    source = Path(__file__).resolve().parents[1] / "scripts" / "backup" / "verify_restore.py"
    spec = importlib.util.spec_from_file_location("_verify_restore", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the data came back -------------------------------------------------------


def test_every_table_survives_with_the_same_row_count(restored):
    """Compared table by table, read from the database on both sides.

    Nothing is listed by hand: a table added next month is covered by this test
    the day it is created, which is exactly how the previous hand-written list
    came to be missing five tables.
    """
    verify = _verifier()
    source_engine, source = _connect(TEST_DATABASE_URL)
    copy_engine, copy = _connect(restored)
    try:
        before = verify.row_counts(source)
        after = verify.row_counts(copy)
    finally:
        source.close(), source_engine.dispose()
        copy.close(), copy_engine.dispose()

    assert set(after) == set(before), "the restored database has a different set of tables"
    assert after == before, "row counts differ after restore"
    assert before["journal_lines"] > 0, "the fixture proved nothing: no ledger rows to lose"


def test_the_ledger_is_financially_sound_after_restore(restored):
    verify = _verifier()
    report = verify.verify(restored)

    assert report.unbalanced_entries == 0
    assert report.grand_total == 0
    assert report.escrow <= 0
    assert report.paid_without_payout == 0
    assert report.ok


def test_the_copy_is_at_the_same_migration(restored):
    """A copy at a different revision is a copy the application refuses to
    start against — a restore that succeeds and still leaves you down."""
    verify = _verifier()
    source_engine, source = _connect(TEST_DATABASE_URL)
    try:
        expected = source.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        source.close(), source_engine.dispose()

    assert verify.verify(restored).alembic_version == expected


# --- the guards came back, and still bite -------------------------------------


def test_the_append_only_trigger_still_refuses_an_update(restored):
    """The one that matters most, and the one a row count cannot see.

    A ledger restored without its triggers looks byte-identical and silently
    accepts edits. This attempts the edit on the copy.
    """
    engine = create_engine(restored)
    try:
        with engine.begin() as conn, pytest.raises(DBAPIError) as excinfo:
            conn.execute(text("UPDATE journal_lines SET amount = amount + 1"))
        assert "append" in str(excinfo.value).lower() or "immutable" in str(excinfo.value).lower()
    finally:
        engine.dispose()


def test_the_append_only_trigger_still_refuses_a_delete(restored):
    engine = create_engine(restored)
    try:
        with engine.begin() as conn, pytest.raises(DBAPIError):
            conn.execute(text("DELETE FROM journal_entries"))
    finally:
        engine.dispose()


def test_the_phone_uniqueness_still_bites(restored):
    """Verification's whole economic argument is that one SIM backs one
    account. Restored without the unique index, that silently stops holding."""
    engine = create_engine(restored)
    try:
        with engine.begin() as conn:
            ids = list(conn.scalars(text("SELECT id FROM users ORDER BY created_at LIMIT 2")))
        assert len(ids) == 2, "the fixture needs at least two accounts"
        with engine.begin() as conn, pytest.raises(DBAPIError):
            conn.execute(
                text("UPDATE users SET phone = '+48111111111' WHERE id = ANY(:ids)"),
                {"ids": ids},
            )
    finally:
        engine.dispose()


def test_every_constraint_and_index_came_across(restored):
    """The general net under the specific probes above.

    Compared by name and kind, not by definition text. A round trip through
    pg_dump re-renders equivalent expressions differently — this very schema
    comes back with `ARRAY[...]::text[]` written as `ARRAY[...::text]` — so a
    textual comparison reports a loss that did not happen, and an assertion
    that cries wolf gets deleted. Name and kind catch a guard that is actually
    missing; whether the surviving ones still bite is proved by running them.
    """
    def _shape(conn) -> tuple[set, set]:
        constraints = set(
            conn.execute(
                text(
                    "SELECT conrelid::regclass::text, conname, contype "
                    "FROM pg_constraint WHERE connamespace = 'public'::regnamespace"
                )
            ).fetchall()
        )
        indexes = set(
            conn.execute(
                text(
                    "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public'"
                )
            ).fetchall()
        )
        return constraints, indexes

    source_engine, source = _connect(TEST_DATABASE_URL)
    copy_engine, copy = _connect(restored)
    try:
        before_constraints, before_indexes = _shape(source)
        after_constraints, after_indexes = _shape(copy)
    finally:
        source.close(), source_engine.dispose()
        copy.close(), copy_engine.dispose()

    assert after_constraints == before_constraints
    assert after_indexes == before_indexes
    assert ("bookings", "excl_booking_overlap", "x") in after_constraints, (
        "the double-booking guarantee is not in the restored copy"
    )


def test_the_double_booking_guarantee_still_bites(restored):
    """Behaviour, not catalogue text: insert a booking that overlaps one the
    restore brought back, and the copy must refuse it.

    Done by cloning the existing row through a temp table so no column is named
    here — a hand-written INSERT would need updating every time the booking
    table gains a field, and would quietly stop compiling this proof.
    """
    engine = create_engine(restored)
    try:
        with engine.begin() as conn:
            live = conn.execute(
                text("SELECT COUNT(*) FROM bookings WHERE status IN ('pending', 'confirmed')")
            ).scalar_one()
        assert live, "the fixture left no bookable row to collide with"

        with engine.begin() as conn, pytest.raises(DBAPIError) as excinfo:
            conn.execute(
                text(
                    "CREATE TEMP TABLE clash AS SELECT * FROM bookings "
                    "WHERE status IN ('pending', 'confirmed') LIMIT 1"
                )
            )
            conn.execute(text("UPDATE clash SET id = 'dr-overlap-probe'"))
            conn.execute(text("INSERT INTO bookings SELECT * FROM clash"))
        assert "excl_booking_overlap" in str(excinfo.value)
    finally:
        engine.dispose()


def test_the_triggers_are_all_there_by_name(restored):
    source_engine, source = _connect(TEST_DATABASE_URL)
    copy_engine, copy = _connect(restored)
    query = text(
        "SELECT tgrelid::regclass::text, tgname FROM pg_trigger "
        "WHERE NOT tgisinternal ORDER BY 1, 2"
    )
    try:
        before = source.execute(query).fetchall()
        after = copy.execute(query).fetchall()
    finally:
        source.close(), source_engine.dispose()
        copy.close(), copy_engine.dispose()

    assert after == before
    assert len(after) >= 4, "the append-only triggers are missing from both sides"
