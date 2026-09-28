"""Saved searches & alerts on real PostgreSQL/PostGIS (TASK-014).

Concurrency is proven with database evidence — row locks, pg_blocking_pids,
commit state and uniqueness constraints — never with sleeps alone:

A  two workers on one (listing, generation)          → one SavedSearchMatch
B  two searches of one user, same generation          → one delivery per channel
C  generation N processed while N+1 exists            → N's ack never consumes N+1
D–H queued, then paused / deleted / unsubscribed /
    not public / no longer matching                   → SUPPRESSED at send time
I  concurrent publications / reactivations            → generation +1 exactly once
J  already-public reconfirmation                      → same generation, no alert

Plus: alert matching ≡ live search (structured geography), spatial matching on
the PUBLIC point only, parallel saves, and the migration's backfill/round trip.
"""

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.modules.alerts import matching, worker
from app.modules.alerts.models import AlertDelivery, SavedSearchMatch
from app.modules.properties.models import ClassifiedOffer, ListingPublicGeneration
from tests.conftest import TEST_DATABASE_URL, auth, last_code, register_and_login, verify_ownership
from tests.saved_support import load_geo
from tests.test_geography_pg import _migrate, scratch_url  # noqa: F401 — fixture
from tests.test_listing_freshness_pg import WAIT, _blocked_by, _pid

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

OFFER = {"title": "Alerty PG", "rent_amount": 250000, "min_term_months": 12,
         "contact_mode": "message"}
TASK013_HEAD = "d0f2b4c6e8a1"
HEAD = "f3b5d7e9a1c2"


@pytest.fixture
def sessions(pg_migrated_engine):
    return sessionmaker(bind=pg_migrated_engine, expire_on_commit=False)


@pytest.fixture
def geo(pg_client, sessions):
    return load_geo(sessions)


@pytest.fixture
def owner(pg_client):
    return register_and_login(pg_client, "owner-alerts-pg@example.com", "host")


def _renter(pg_client, email="renter-alerts-pg@example.com", verified=True):
    token = register_and_login(pg_client, email, "guest")
    if verified:
        pg_client.post("/v1/me/verify/email/start", headers=auth(token))
        assert pg_client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                              headers=auth(token)).status_code == 200
    return token


_n = {"i": 0}


def _listing(pg_client, owner, place, *, publish=True, **offer):
    _n["i"] += 1
    made = pg_client.post("/v1/properties", json={
        "category": "APARTMENT", "area_m2": 50, "rooms": 2, "capacity": 2,
        "building_number": str(_n["i"]), **place}, headers=auth(owner))
    assert made.status_code == 201, made.text
    verify_ownership(pg_client, owner, made.json()["id"])
    oid = pg_client.post(f"/v1/properties/{made.json()['id']}/classifieds",
                         json={**OFFER, **offer}, headers=auth(owner)).json()["id"]
    if publish:
        assert pg_client.post(f"/v1/classifieds/{oid}/publish",
                              headers=auth(owner)).status_code == 200
    return oid


def _search(pg_client, token, query, name="S"):
    r = pg_client.post("/v1/me/saved-searches", json={"name": name, "query": query},
                       headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _count(sessions, model, **where):
    with sessions() as db:
        stmt = select(model)
        for k, v in where.items():
            stmt = stmt.where(getattr(model, k) == v)
        return len(list(db.scalars(stmt)))


def _generation(sessions, oid):
    with sessions() as db:
        return db.get(ClassifiedOffer, oid).public_generation


# --- A / B: exactly-once is the database's ------------------------------------------------------


def test_a_two_workers_on_one_episode_make_one_match(pg_client, sessions, geo, owner):
    renter = _renter(pg_client)
    _search(pg_client, renter, f"locality_id={geo['krakow']}")
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"]})
    first = sessions()
    result = {}
    try:
        assert matching.process_generation(first, oid, 1).matches == 1  # not committed
        holder = _pid(first.connection())

        def second():
            with sessions() as db:
                result["outcome"] = matching.process_generation(db, oid, 1)
                db.commit()

        t = threading.Thread(target=second)
        t.start()
        assert _blocked_by(first.get_bind(), holder), "worker 2 did not wait on worker 1's row"
        first.commit()
        t.join(WAIT)
    finally:
        first.close()
    assert result["outcome"].matches == 0  # its insert found worker 1's row
    assert _count(sessions, SavedSearchMatch, listing_id=oid) == 1
    assert _count(sessions, AlertDelivery, listing_id=oid) == 2  # IN_APP + EMAIL, once


def test_b_two_searches_one_user_one_delivery(pg_client, sessions, geo, owner):
    renter = _renter(pg_client)
    _search(pg_client, renter, f"locality_id={geo['krakow']}", name="A")
    _search(pg_client, renter, f"admin_area_id={geo['malopolskie']}", name="B")
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"]})
    threads = [threading.Thread(target=lambda: worker.process_work(sessions)) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(WAIT)
    assert _count(sessions, SavedSearchMatch, listing_id=oid) == 2
    with sessions() as db:
        channels = sorted(d.channel for d in db.scalars(
            select(AlertDelivery).where(AlertDelivery.listing_id == oid)))
        assert channels == ["EMAIL", "IN_APP"]
        user_id = db.scalar(select(AlertDelivery.user_id).where(AlertDelivery.listing_id == oid))
    with pytest.raises(IntegrityError) as caught, sessions.begin() as db:
        db.add(AlertDelivery(user_id=user_id, listing_id=oid, public_generation=1,
                             channel="IN_APP", category="PRODUCT", status="pending"))
    assert caught.value.orig.diag.constraint_name == "uq_alert_deliveries_user_episode_channel"
    # The search-match identity is the table's own key, not a check in code.
    sid = next(iter(_ids_of(sessions, oid)))
    with pytest.raises(IntegrityError) as caught, sessions.begin() as db:
        db.add(SavedSearchMatch(saved_search_id=sid, listing_id=oid, public_generation=1,
                                user_id=user_id))
    assert caught.value.orig.diag.constraint_name == "saved_search_matches_pkey"


def _ids_of(sessions, oid):
    with sessions() as db:
        return {m.saved_search_id for m in db.scalars(
            select(SavedSearchMatch).where(SavedSearchMatch.listing_id == oid))}


# --- C: generation identity -------------------------------------------------------------------


def test_c_acknowledging_n_never_consumes_n_plus_one(pg_client, sessions, geo, owner):
    renter = _renter(pg_client)
    _search(pg_client, renter, f"locality_id={geo['krakow']}")
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"]})
    claimer = sessions()
    try:
        assert matching.claim_work(claimer, 10) == [(oid, 1)]  # gen 1 locked, uncommitted
        # A second worker skips the locked row rather than waiting …
        with sessions() as other:
            assert matching.claim_work(other, 10) == []
        claimer.commit()
    finally:
        claimer.close()
    # … generation 2 appears while generation 1 is still `processing`.
    pg_client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
    pg_client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner))
    with sessions() as db:
        outcome = matching.process_generation(db, oid, 1)
        db.commit()
    assert outcome.outcome == "superseded"
    with sessions() as db:
        rows = {r.public_generation: r.alert_status for r in db.scalars(
            select(ListingPublicGeneration).where(ListingPublicGeneration.listing_id == oid))}
    assert rows == {1: "superseded", 2: "pending"}
    assert worker.process_work(sessions) == {"matched": 1}
    with sessions() as db:
        gens = {m.public_generation for m in db.scalars(
            select(SavedSearchMatch).where(SavedSearchMatch.listing_id == oid))}
    assert gens == {2}


# --- D–H: send-time revalidation on the real engine ------------------------------------------------


def _queued(pg_client, sessions, geo, owner, renter):
    sid = _search(pg_client, renter, f"locality_id={geo['krakow']}&max_rent=300000")
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"]})
    assert worker.process_work(sessions) == {"matched": 1}
    with sessions() as db:
        claimed = worker.delivery.claim_deliveries(db, 10)  # claimed …
        db.commit()
    assert len(claimed) == 2
    return sid, oid, claimed


def _send(sessions, claimed):
    out = set()
    for delivery_id in claimed:
        with sessions() as db:
            out.add((worker.delivery.deliver(db, delivery_id),
                     db.get(AlertDelivery, delivery_id).outcome))
            db.commit()
    return out


@pytest.mark.parametrize("change, reason", [
    ("pause_search", "search_inactive"),
    ("delete_search", "search_deleted"),
    ("unsubscribe", "search_inactive"),
    ("pause_listing", "listing_not_public"),
    ("price_out_of_range", "no_longer_matches"),
])
def test_d_to_h_queued_deliveries_are_revalidated(pg_client, sessions, geo, owner, change,
                                                  reason, monkeypatch):
    renter = _renter(pg_client)
    sid, oid, claimed = _queued(pg_client, sessions, geo, owner, renter)
    # … then, before the send, the world changes:
    if change == "pause_search":
        pg_client.patch(f"/v1/me/saved-searches/{sid}",
                        json={"expected_version": 1, "status": "paused"}, headers=auth(renter))
    elif change == "delete_search":
        pg_client.delete(f"/v1/me/saved-searches/{sid}", headers=auth(renter))
    elif change == "unsubscribe":
        from app.modules.alerts import delivery

        with sessions.begin() as db:
            user_id = db.scalar(select(AlertDelivery.user_id).where(AlertDelivery.id == claimed[0]))
            token = delivery.issue_unsubscribe_token(db, user_id, "SAVED_SEARCH", sid,
                                                     delivery.freshness.db_now(db))
        assert pg_client.post("/v1/notifications/unsubscribe",
                              json={"token": token}).json() == {"status": "ok"}
    elif change == "pause_listing":
        pg_client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
    else:
        version = pg_client.get(f"/v1/classifieds/{oid}").json()["version"]
        assert pg_client.put(f"/v1/classifieds/{oid}/price", json={
            "rent_amount": 400000, "expected_version": version},
            headers=auth(owner)).status_code == 200
    assert _send(sessions, claimed) == {("suppressed", reason)}
    assert _count(sessions, AlertDelivery, status="delivered") == 0


# --- I / J: public generation under concurrency ------------------------------------------------------


@pytest.mark.parametrize("prepare, actions", [
    ("pause", ("publish", "publish", "publish")),
    ("expire", ("publish", "confirm", "confirm")),
])
def test_i_concurrent_publications_open_exactly_one_episode(pg_client, sessions, geo, owner,
                                                            pg_migrated_engine, prepare,
                                                            actions):
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"]})
    if prepare == "pause":
        pg_client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
    else:  # silently expired: still `active`, no longer public
        with pg_migrated_engine.begin() as conn:
            conn.execute(text("UPDATE classified_offers SET last_confirmed_available_at = "
                              "now() - interval '30 days' WHERE id = :o"), {"o": oid})
    holder = pg_migrated_engine.connect()
    tx = holder.begin()
    holder.execute(text("SELECT 1 FROM classified_offers WHERE id = :o FOR UPDATE"), {"o": oid})
    results = []
    threads = [threading.Thread(target=lambda a=a: results.append(pg_client.post(
        f"/v1/classifieds/{oid}/{a}", headers=auth(owner)).status_code)) for a in actions]
    try:
        for t in threads:
            t.start()
        assert _blocked_by(pg_migrated_engine, _pid(holder)), "no transition waited on the row"
    finally:
        tx.rollback()
        holder.close()
        for t in threads:
            t.join(WAIT)
    assert sorted(results) == [200, 200, 200]
    assert _generation(sessions, oid) == 2
    with pg_migrated_engine.connect() as conn:
        assert conn.scalar(text(
            "SELECT count(*) FROM domain_events WHERE event_type = 'ListingBecamePublic' "
            "AND correlation_id = :o"), {"o": oid}) == 2
        assert conn.scalar(text(
            "SELECT count(*) FROM listing_public_generations WHERE listing_id = :o"),
            {"o": oid}) == 2


def test_j_already_public_reconfirmation_keeps_its_episode_and_never_alerts(
        pg_client, sessions, geo, owner):
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"]})
    worker.process_work(sessions)  # episode 1, before any search exists
    renter = _renter(pg_client)
    _search(pg_client, renter, f"locality_id={geo['krakow']}")
    for action in ("confirm", "publish", "confirm"):
        assert pg_client.post(f"/v1/classifieds/{oid}/{action}",
                              headers=auth(owner)).status_code == 200
    assert _generation(sessions, oid) == 1
    assert worker.process_work(sessions) == {}
    assert _count(sessions, AlertDelivery) == 0


# --- matching is the live search -------------------------------------------------------------------


def test_alert_matching_is_exactly_the_live_search(pg_client, sessions, geo, owner):
    """For every saved search: it is alerted about the new listing iff the same
    query on GET /v1/classifieds returns that listing."""
    renter = _renter(pg_client, verified=False)
    queries = {
        "krakow": f"locality_id={geo['krakow']}",
        "warszawa": f"locality_id={geo['warszawa']}",
        "region": f"admin_area_id={geo['malopolskie']}",
        "county_of_balice": f"admin_area_id={geo['zabierzow']}",
        "area": f"geo_area_id={geo['kazimierz']}",
        "country": "country_code=PL&max_rent=260000",
        "country_de": "country_code=DE",
        "anywhere_cheap": "max_rent=100000",
        "anywhere_rooms": "min_rooms=2&category=APARTMENT",
        "legacy_city": "city=Krak%C3%B3w",
        "house": f"locality_id={geo['krakow']}&category=HOUSE",
    }
    ids = {name: _search(pg_client, renter, q, name=name) for name, q in queries.items()}
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"],
                                      "geo_area_id": geo["kazimierz"]})
    worker.process_work(sessions)
    with sessions() as db:
        alerted = {m.saved_search_id for m in db.scalars(
            select(SavedSearchMatch).where(SavedSearchMatch.listing_id == oid))}
    live = set()
    for name, q in queries.items():
        page = pg_client.get(f"/v1/classifieds?{q}&limit=100").json()
        if oid in {i["id"] for i in page["items"]}:
            live.add(ids[name])
    assert alerted == live
    assert {n for n, i in ids.items() if i in alerted} == {
        "krakow", "region", "area", "country", "anywhere_rooms", "legacy_city"}


def test_spatial_matching_uses_the_public_point_only(pg_client, sessions, geo, owner):
    renter = _renter(pg_client, verified=False)
    exact = (50.0612, 19.9371)
    around_exact = "bbox=19.93705%2C50.06115%2C19.93715%2C50.06125"
    near_exact = "near_lat=50.0612&near_lon=19.9371&radius_m=5"
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"], "latitude": exact[0],
                                      "longitude": exact[1]}, publish=False)
    pg_client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner))
    public = pg_client.get(f"/v1/classifieds/{oid}").json()["public_location"]
    assert (public["latitude"], public["longitude"]) != exact
    # Searches saved BEFORE a second, identical listing is published.
    s_exact_box = _search(pg_client, renter, around_exact, name="box on the home")
    s_exact_ring = _search(pg_client, renter, near_exact, name="ring on the home")
    lat, lon = public["latitude"], public["longitude"]
    s_public = _search(pg_client, renter,
                       f"bbox={lon - 0.0005}%2C{lat - 0.0005}%2C{lon + 0.0005}%2C{lat + 0.0005}",
                       name="box on the public cell")
    twin = _listing(pg_client, owner, {"locality_id": geo["krakow"], "latitude": exact[0],
                                       "longitude": exact[1]})
    worker.process_work(sessions)
    with sessions() as db:
        alerted = {m.saved_search_id for m in db.scalars(
            select(SavedSearchMatch).where(SavedSearchMatch.listing_id == twin))}
    assert alerted == {s_public}
    assert s_exact_box not in alerted and s_exact_ring not in alerted


# --- parallel writes -------------------------------------------------------------------------------


def test_parallel_saves_of_one_listing_are_one_save(pg_client, sessions, geo, owner):
    oid = _listing(pg_client, owner, {"locality_id": geo["krakow"]})
    renter = _renter(pg_client, verified=False)
    codes = []
    threads = [threading.Thread(target=lambda: codes.append(pg_client.post(
        f"/v1/me/saved-listings/{oid}", headers=auth(renter)).status_code)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(WAIT)
    assert sorted(codes).count(201) == 1 and set(codes) <= {200, 201}
    with sessions() as db:
        assert db.scalar(text("SELECT count(*) FROM saved_listings")) == 1


def test_parallel_duplicate_saved_searches_are_one_search(pg_client, sessions):
    renter = _renter(pg_client, verified=False)
    codes = []
    threads = [threading.Thread(target=lambda i=i: codes.append(pg_client.post(
        "/v1/me/saved-searches", json={"name": f"n{i}", "query": "min_rooms=2&max_rent=5000"},
        headers=auth(renter)).status_code)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(WAIT)
    assert sorted(codes) == [201, 409, 409, 409, 409, 409]
    with sessions() as db:
        assert db.scalar(text("SELECT count(*) FROM saved_searches")) == 1


# --- migration ------------------------------------------------------------------------------------


def test_migration_backfills_generations_and_round_trips(scratch_url, monkeypatch):  # noqa: F811
    from app.core.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    _migrate(scratch_url, HEAD)
    engine = create_engine(scratch_url)
    local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        db = local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            owner = register_and_login(client, "mig-owner@example.com", "host")
            place = {"city": "Opole", "address": "ul. Migracyjna"}
            live = _listing(client, owner, place)
            draft = _listing(client, owner, {**place, "building_number": "d"}, publish=False)
            paused = _listing(client, owner, {**place, "building_number": "p"})
            client.post(f"/v1/classifieds/{paused}/pause", headers=auth(owner))
            renter = _renter(client, "mig-renter@example.com", verified=False)
            _search(client, renter, "city=Opole")
            client.post(f"/v1/me/saved-listings/{live}", headers=auth(renter))
    finally:
        app.dependency_overrides.clear()

    # Back to the accepted TASK-013 schema: only TASK-014 objects disappear.
    _migrate(scratch_url, TASK013_HEAD, down=True)
    with engine.connect() as conn:
        for table in ("saved_listings", "saved_searches", "listing_public_generations",
                      "alert_deliveries", "user_notifications", "unsubscribe_tokens"):
            assert conn.scalar(text(f"SELECT to_regclass('public.{table}')")) is None
        assert conn.scalar(text("SELECT count(*) FROM information_schema.columns WHERE "
                                "table_name = 'classified_offers' AND column_name IN "
                                "('public_generation', 'public_since')")) == 0
        assert conn.scalar(text("SELECT count(*) FROM classified_offers")) == 3
    # … and forward again from a TASK-013 database with listings in it.
    _migrate(scratch_url, HEAD)
    with engine.connect() as conn:
        rows = {r[0]: (r[1], r[2] is not None and r[2] == r[3]) for r in conn.execute(text(
            "SELECT id, public_generation, public_since, published_at FROM classified_offers"))}
        assert rows == {live: (1, True), paused: (1, True), draft: (0, False)}
        # History is not work: nothing alerts about listings public before TASK-014.
        assert conn.scalar(text("SELECT count(*) FROM listing_public_generations")) == 0
        assert conn.scalar(text("SELECT count(*) FROM alembic_version")) == 1
        with pytest.raises(Exception):
            conn.execute(text("UPDATE classified_offers SET public_generation = -1"))
    engine.dispose()
