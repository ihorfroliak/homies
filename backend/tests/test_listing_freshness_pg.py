"""Listing freshness on real PostgreSQL (TASK-012).

* the thresholds, evaluated by the database at a pinned instant;
* publication and confirmation stamped with the database clock;
* the races: a newer confirmation always beats the sweep, whichever takes the
  row first; archive beats confirm; revoke and space archive beat reactivation.
  Waiting is shown in pg_stat_activity / pg_blocking_pids, never assumed from
  timing;
* the migration from the accepted TASK-010R head, on data.
"""

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.properties import freshness
from app.modules.properties.models import ClassifiedOffer, Space
from tests.conftest import TEST_DATABASE_URL, admin_login, auth, register_and_login
from tests.test_geography_pg import _migrate, scratch_url  # noqa: F401
from tests.test_publication_race_pg import (
    WAIT,
    _authority_id,
    _pause_publication_at,
    _someone_waits_on_a_lock,
    _status,
)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

PROPERTY = {"category": "APARTMENT", "city": "Gdynia", "address": "ul. Aktualna 9",
            "area_m2": 50, "rooms": 2, "capacity": 2}
OFFER = {"title": "Świeże", "rent_amount": 260000, "min_term_months": 12,
         "contact_mode": "message"}
T0 = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
TICK = timedelta(microseconds=1)


def _listing(pg_client, email="fresh-pg@example.com", n=1):
    from tests.conftest import verify_ownership

    owner = register_and_login(pg_client, email, "host")
    offers = []
    for i in range(n):
        prop = pg_client.post("/v1/properties", json={**PROPERTY, "address": f"ul. A {i}"},
                              headers=auth(owner)).json()["id"]
        verify_ownership(pg_client, owner, prop)
        offer = pg_client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                               headers=auth(owner)).json()["id"]
        assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                              headers=auth(owner)).status_code == 200
        offers.append((prop, offer))
    return owner, offers


def _set(engine, offer, **values):
    sets = ", ".join(f"{k} = :{k}" for k in values)
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE classified_offers SET {sets} WHERE id = :id"),
                     {**values, "id": offer})


def _pid(conn) -> int:
    return conn.scalar(text("SELECT pg_backend_pid()"))


def _blocked_by(engine, pid: int) -> bool:
    """Some backend is waiting on a lock held by `pid` — database evidence."""
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            if conn.scalar(text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                    "WHERE :p = ANY(pg_blocking_pids(pid)))"), {"p": pid}):
                return True
        time.sleep(0.05)
    return False


# --- thresholds, decided by the database at a pinned instant -------------------------------

AGES = {
    "fresh_edge": timedelta(days=14) - TICK,
    "due_start": timedelta(days=14),
    "due_edge": timedelta(days=21) - TICK,
    "stale_start": timedelta(days=21),
}


def test_the_thresholds_on_the_database(pg_client, pg_migrated_engine):
    _, offers = _listing(pg_client, n=len(AGES))
    named = dict(zip(AGES, (o for _, o in offers)))
    for name, age in AGES.items():
        _set(pg_migrated_engine, named[name], last_confirmed_available_at=T0 - age)
    with Session(pg_migrated_engine) as db:
        public = set(db.scalars(select(ClassifiedOffer.id).where(
            freshness.public_clause(db, as_of=T0))))
        assert public == {named["fresh_edge"], named["due_start"], named["due_edge"]}
        result = freshness.sweep(db, as_of=T0)
        db.commit()
    assert result.staled == [named["stale_start"]]
    assert set(result.reminded) == {named["due_start"], named["due_edge"]}
    assert _status(pg_migrated_engine, named["stale_start"]) == "stale"
    assert _status(pg_migrated_engine, named["due_edge"]) == "active"


def test_publication_and_confirmation_use_the_database_clock(pg_client, pg_migrated_engine):
    owner, [(_, offer)] = _listing(pg_client)
    with pg_migrated_engine.connect() as conn:
        published, confirmed, now = conn.execute(text(
            "SELECT published_at, last_confirmed_available_at, now() FROM classified_offers "
            "WHERE id = :o"), {"o": offer}).one()
    assert published == confirmed and now - confirmed < timedelta(seconds=30)
    _set(pg_migrated_engine, offer, last_confirmed_available_at=T0)
    assert pg_client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner)).status_code == 200
    with pg_migrated_engine.connect() as conn:
        confirmed, published_after, now = conn.execute(text(
            "SELECT last_confirmed_available_at, published_at, now() FROM classified_offers "
            "WHERE id = :o"), {"o": offer}).one()
    assert now - confirmed < timedelta(seconds=30)
    assert published_after == published  # confirmation does not re-publish


# --- a newer confirmation always beats the sweep ---------------------------------------------


def test_a_confirmation_in_flight_is_skipped_by_the_sweep_and_wins(pg_client, pg_migrated_engine):
    """The owner's confirmation holds the row: the sweep neither waits nor
    pauses it, and the confirmation commits on an active listing."""
    _, [(_, offer)] = _listing(pg_client)
    _set(pg_migrated_engine, offer, last_confirmed_available_at=T0)  # long stale
    confirm = pg_migrated_engine.connect()
    tx = confirm.begin()
    confirm.execute(text("SELECT status FROM classified_offers WHERE id = :o FOR UPDATE"),
                    {"o": offer})
    confirm.execute(text("UPDATE classified_offers SET last_confirmed_available_at = now() "
                         "WHERE id = :o AND status IN ('active', 'stale')"), {"o": offer})
    swept = {}

    def run_sweep():
        with Session(pg_migrated_engine) as db:
            swept["result"] = freshness.sweep(db)
            db.commit()

    sweeper = threading.Thread(target=run_sweep)
    try:
        sweeper.start()
        sweeper.join(5)
        # Skipped, not waited for: the sweep finished while the confirmation
        # still held the row, and did not touch it.
        assert not sweeper.is_alive(), "the sweep waited on the confirmation's row lock"
        assert swept["result"].staled == []
    finally:
        tx.commit()
        confirm.close()
        sweeper.join(WAIT)
    assert _status(pg_migrated_engine, offer) == "active"
    with Session(pg_migrated_engine) as db:
        assert freshness.sweep(db).staled == []
        db.commit()
    assert pg_client.get(f"/v1/classifieds/{offer}").status_code == 200


def test_a_confirmation_waiting_behind_the_sweep_reactivates_the_listing(
        pg_client, pg_migrated_engine):
    """The sweep took the row first and made it stale. The owner's
    confirmation waits for exactly that transaction, then — reading the
    committed `stale` — goes through reactivation and wins."""
    owner, [(_, offer)] = _listing(pg_client)
    _set(pg_migrated_engine, offer, last_confirmed_available_at=T0)
    sweeper = Session(pg_migrated_engine)
    result = {}
    try:
        swept = freshness.sweep(sweeper)
        assert swept.staled == [offer]
        sweeper_pid = _pid(sweeper.connection())
        worker = threading.Thread(target=lambda: result.update(
            confirm=pg_client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))))
        worker.start()
        assert _blocked_by(pg_migrated_engine, sweeper_pid), "confirm did not wait on the sweep"
        assert "confirm" not in result
        sweeper.commit()
        worker.join(WAIT)
    finally:
        sweeper.close()
    assert result["confirm"].status_code == 200, result["confirm"].text
    assert _status(pg_migrated_engine, offer) == "active"
    with pg_migrated_engine.connect() as conn:
        events = conn.execute(text(
            "SELECT event_type FROM domain_events WHERE correlation_id = :o "
            "AND event_type <> 'ListingBecamePublic' ORDER BY occurred_at"),
            {"o": offer}).scalars().all()
        episodes = conn.execute(text(
            "SELECT dedup_key FROM domain_events WHERE correlation_id = :o "
            "AND event_type = 'ListingBecamePublic' ORDER BY occurred_at"),
            {"o": offer}).scalars().all()
    assert events == [freshness.LISTING_AUTO_PAUSED_STALE, freshness.LISTING_REACTIVATED]
    # TASK-014: publication opened episode 1; the reactivation of the stale
    # listing opened episode 2 — exactly once, behind the sweep's lock.
    assert episodes == [f"ListingBecamePublic:{offer}:1", f"ListingBecamePublic:{offer}:2"]


# --- nothing resurrects an archived listing -------------------------------------------------


def test_archive_committed_while_confirm_waits_wins(pg_client, pg_migrated_engine):
    owner, [(_, offer)] = _listing(pg_client)
    archiver = pg_migrated_engine.connect()
    tx = archiver.begin()
    archiver.execute(text("UPDATE classified_offers SET status = 'archived' WHERE id = :o"),
                     {"o": offer})
    result = {}
    worker = threading.Thread(target=lambda: result.update(
        confirm=pg_client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))))
    try:
        worker.start()
        assert _blocked_by(pg_migrated_engine, _pid(archiver)), "confirm did not wait"
    finally:
        tx.commit()
        archiver.close()
        worker.join(WAIT)
    assert result["confirm"].status_code == 409, result["confirm"].text
    assert _status(pg_migrated_engine, offer) == "archived"
    with Session(pg_migrated_engine) as db:
        _set(pg_migrated_engine, offer, last_confirmed_available_at=T0)
        assert freshness.sweep(db).staled == []
        db.commit()
    assert _status(pg_migrated_engine, offer) == "archived"


# --- invalidation vs reactivation --------------------------------------------------------------


def _stale(pg_client, pg_migrated_engine, email):
    owner, [(prop, offer)] = _listing(pg_client, email)
    _set(pg_migrated_engine, offer, last_confirmed_available_at=T0)
    with Session(pg_migrated_engine) as db:
        freshness.sweep(db)
        db.commit()
    assert _status(pg_migrated_engine, offer) == "stale"
    return owner, prop, offer


def test_a_revoke_committed_before_the_decision_keeps_it_stale(
        pg_client, pg_migrated_engine, monkeypatch):
    owner, prop, offer = _stale(pg_client, pg_migrated_engine, "revoke-first@example.com")
    admin = admin_login(pg_client)
    aid = _authority_id(pg_migrated_engine, prop)
    reached, resume = _pause_publication_at(monkeypatch, "precheck")
    result = {}
    worker = threading.Thread(target=lambda: result.update(
        confirm=pg_client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))))
    worker.start()
    try:
        assert reached.wait(WAIT)
        revoked = pg_client.post(f"/v1/admin/property-authorities/{aid}/revoke",
                                 headers=auth(admin))
        assert revoked.status_code == 200, revoked.text
    finally:
        resume.set()
        worker.join(WAIT)
    assert result["confirm"].status_code in (403, 404), result["confirm"].text
    assert _status(pg_migrated_engine, offer) == "stale"
    assert pg_client.get(f"/v1/classifieds/{offer}").status_code == 404


def test_a_revoke_arriving_during_reactivation_waits_and_takes_it_down(
        pg_client, pg_migrated_engine, monkeypatch):
    owner, prop, offer = _stale(pg_client, pg_migrated_engine, "revoke-during@example.com")
    admin = admin_login(pg_client)
    aid = _authority_id(pg_migrated_engine, prop)
    reached, resume = _pause_publication_at(monkeypatch, "protected")
    result = {}
    confirmer = threading.Thread(target=lambda: result.update(
        confirm=pg_client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))))
    revoker = threading.Thread(target=lambda: result.update(
        revoke=pg_client.post(f"/v1/admin/property-authorities/{aid}/revoke",
                              headers=auth(admin))))
    confirmer.start()
    try:
        assert reached.wait(WAIT)
        revoker.start()
        assert _blocked_by(pg_migrated_engine, reached.pid), "revoke did not wait"
        assert "revoke" not in result
    finally:
        resume.set()
        confirmer.join(WAIT)
        if revoker.ident:
            revoker.join(WAIT)
    assert result["confirm"].status_code == 200, result["confirm"].text
    assert result["revoke"].json()["paused_offers"] == [offer]
    assert _status(pg_migrated_engine, offer) == "paused"
    assert pg_client.get(f"/v1/classifieds/{offer}").status_code == 404


def test_archiving_the_space_during_reactivation_waits_and_takes_it_down(
        pg_client, pg_migrated_engine, monkeypatch):
    owner, prop, offer = _stale(pg_client, pg_migrated_engine, "space-during@example.com")
    with pg_migrated_engine.connect() as conn:
        space = conn.scalar(select(Space.id).where(Space.property_id == prop))
    reached, resume = _pause_publication_at(monkeypatch, "protected")
    result = {}
    confirmer = threading.Thread(target=lambda: result.update(
        confirm=pg_client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))))
    archiver = threading.Thread(target=lambda: result.update(
        archive=pg_client.post(f"/v1/spaces/{space}/archive", headers=auth(owner))))
    confirmer.start()
    try:
        assert reached.wait(WAIT)
        archiver.start()
        assert _someone_waits_on_a_lock(pg_migrated_engine), "archive did not wait"
    finally:
        resume.set()
        confirmer.join(WAIT)
        if archiver.ident:
            archiver.join(WAIT)
    assert result["confirm"].status_code == 200, result["confirm"].text
    assert result["archive"].status_code == 200, result["archive"].text
    assert _status(pg_migrated_engine, offer) == "paused"


def test_the_database_refuses_an_unknown_status(pg_client, pg_migrated_engine):
    from sqlalchemy.exc import IntegrityError

    _, [(_, offer)] = _listing(pg_client)
    with pytest.raises(IntegrityError) as caught, pg_migrated_engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET status = 'published' WHERE id = :o"),
                     {"o": offer})
    assert caught.value.orig.diag.constraint_name == "ck_classified_offers_status"


# --- migration: TASK-010R head → TASK-012, on data -----------------------------------------------

TASK_010R_HEAD = "a7c9e1f3b5d7"
TASK_012_HEAD = "b8d0f2a4c6e8"


def _seed(conn, statuses_published):
    owner = str(uuid.uuid4())
    conn.execute(text("INSERT INTO users (id, email, password_hash, full_name, role, created_at) "
                      "VALUES (:i, :e, 'x', '', 'host', now())"),
                 {"i": owner, "e": f"{owner}@x.example"})
    ids = {}
    for n, (status, published) in enumerate(statuses_published):
        address = conn.scalar(text(
            "INSERT INTO addresses (id, country_code, postal_code, unstructured_text, "
            "locality_text, district_text, resolution, source, verification, created_at, "
            "updated_at) VALUES (gen_random_uuid()::text, 'PL', '', :t, 'Gdynia', '', "
            "'UNSTRUCTURED', 'USER_INPUT', 'UNVERIFIED', now(), now()) RETURNING id"),
            {"t": f"ul. M {n}"})
        pid = conn.scalar(text(
            "INSERT INTO properties (id, owner_id, address_id, city, district, postcode, address, "
            "latitude, longitude, capacity, bedrooms, bathrooms, has_elevator, furnished, "
            "parking, pets_allowed, attributes, created_at) VALUES (gen_random_uuid()::text, "
            ":o, :a, 'Gdynia', '', '', :t, 54.5, 18.5, 2, 1, 1, false, 'full', 'none', false, "
            "'{}', now()) RETURNING id"), {"o": owner, "a": address, "t": f"ul. M {n}"})
        space = conn.scalar(text(
            "INSERT INTO spaces (id, property_id, space_type, status, version, created_at, "
            "updated_at) VALUES (gen_random_uuid()::text, :p, 'WHOLE_PROPERTY', 'ACTIVE', 1, "
            "now(), now()) RETURNING id"), {"p": pid})
        ids[status + str(n)] = conn.scalar(text(
            "INSERT INTO classified_offers (id, property_id, space_id, owner_id, title, "
            "description, status, currency, utilities_included, other_costs, contact_mode, "
            "contact_phone, open_ended, public_location_precision, public_latitude, "
            "public_longitude, primary_price_minor, estimated_monthly_total_minor, version, "
            "created_at, published_at) VALUES (gen_random_uuid()::text, :p, :s, :o, 't', '', "
            ":st, 'PLN', false, '', 'message', '', true, 'APPROXIMATE', 54.5025, 18.5, "
            "260000, 300000, 3, now(), :pub) RETURNING id"),
            {"p": pid, "s": space, "o": owner, "st": status, "pub": published})
    return ids


def test_upgrading_the_accepted_task_010r_schema_backfills_from_publication_only(
        scratch_url):  # noqa: F811
    _migrate(scratch_url, TASK_010R_HEAD)
    engine = create_engine(scratch_url)
    long_ago = datetime(2025, 5, 1, 9, 30, tzinfo=timezone.utc)
    recent = datetime.now(timezone.utc) - timedelta(days=2)
    with engine.begin() as conn:
        ids = _seed(conn, [("active", long_ago), ("active", recent), ("paused", long_ago),
                           ("archived", long_ago), ("draft", None)])
    with engine.connect() as conn:
        before = {r["id"]: dict(r) for r in conn.execute(text(
            "SELECT * FROM classified_offers")).mappings()}

    _migrate(scratch_url, TASK_012_HEAD)
    with engine.connect() as conn:
        after = {r["id"]: dict(r) for r in conn.execute(text(
            "SELECT * FROM classified_offers")).mappings()}
    assert set(after) == set(before)
    for oid, row in after.items():
        confirmed = row.pop("last_confirmed_available_at")
        assert row == before[oid]  # ids, links, status, prices, version, location unchanged
        assert confirmed == before[oid]["published_at"]  # evidence only, never invented
    assert after[ids["draft4"]].get("status") == "draft"
    # No lifecycle transition in the migration: the year-old active listing is
    # still `active` — only the read-time rule keeps it off the board.
    assert after[ids["active0"]]["status"] == "active"
    with Session(engine) as db:
        rows = freshness.preflight(db)
    assert [r["listing_id"] for r in rows] == [ids["active0"]]

    # Downgrade: a stale listing becomes paused (still not public), then back up.
    with engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET status = 'stale' WHERE id = :i"),
                     {"i": ids["active0"]})
    _migrate(scratch_url, TASK_010R_HEAD, down=True)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT status FROM classified_offers WHERE id = :i"),
                           {"i": ids["active0"]}) == "paused"
    _migrate(scratch_url, TASK_012_HEAD)
    engine.dispose()


def test_the_migration_refuses_an_unknown_status_instead_of_guessing(scratch_url):  # noqa: F811
    _migrate(scratch_url, TASK_010R_HEAD)
    engine = create_engine(scratch_url)
    with engine.begin() as conn:
        _seed(conn, [("published", None)])
    with pytest.raises(RuntimeError, match="will not guess"):
        _migrate(scratch_url, TASK_012_HEAD)
    engine.dispose()
