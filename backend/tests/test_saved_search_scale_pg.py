"""Saved-search matching at a representative synthetic scale (TASK-014).

Proves architecturally and by measurement that a new public listing is NOT
evaluated against every saved search × every listing:

* work exists only for the listing that became public;
* candidates come from the anchor index (a necessary condition), not from all
  saved searches;
* the canonical query is evaluated as boolean columns over the ONE listing
  row — ceil(candidates / EVALUATION_CHUNK) statements;
* validation of all candidate queries reads reference data a fixed number of
  times (QueryContext), not once per search.

Default shape (CI): 2 000 saved searches, 300 listings. TASK014_SCALE=full:
10 000 saved searches, 1 000 listings. Numbers are LOCAL EVIDENCE of this
machine and database, printed for the report — not a production benchmark.
"""

import json
import math
import os
import random
import time
import uuid

import pytest
from sqlalchemy import event, insert, text
from sqlalchemy.orm import sessionmaker

from app.modules.alerts import matching
from app.modules.properties import search
from app.modules.identity.models import User
from app.modules.properties.models import ListingPublicGeneration
from app.modules.saved import service
from app.modules.saved.models import SavedSearch, SavedSearchAnchor
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership
from tests.saved_support import load_geo

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

FULL = os.environ.get("TASK014_SCALE") == "full"
SEARCHES = 10_000 if FULL else 2_000
LISTINGS = 1_000 if FULL else 300
USERS = 500


def _columns(conn, table):
    return [r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t "
        "AND is_generated = 'NEVER' ORDER BY ordinal_position"), {"t": table})]


def _clone(conn, table, source_id, overrides):
    cols = _columns(conn, table)
    exprs = [f":{c}" if c in overrides else c for c in cols]
    conn.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) SELECT {', '.join(exprs)} "
                      f"FROM {table} WHERE id = :_src"), {**overrides, "_src": source_id})


def _seed_listings(engine, templates, n):
    with engine.begin() as conn:
        for i in range(n):
            t = templates[i % len(templates)]
            prop_id, addr_id, space_id, offer_id = (str(uuid.uuid4()) for _ in range(4))
            p = conn.execute(text("SELECT property_id, space_id FROM classified_offers "
                                  "WHERE id = :o"), {"o": t}).one()
            a = conn.scalar(text("SELECT address_id FROM properties WHERE id = :p"),
                            {"p": p.property_id})
            _clone(conn, "addresses", a, {"id": addr_id})
            _clone(conn, "properties", p.property_id, {"id": prop_id, "address_id": addr_id})
            _clone(conn, "spaces", p.space_id, {"id": space_id, "property_id": prop_id})
            _clone(conn, "classified_offers", t, {"id": offer_id, "property_id": prop_id,
                                                  "space_id": space_id})


def _seed_searches(sessions, geo, n):
    rng = random.Random(14)
    places = ([f"locality_id={geo['krakow']}"] * 40 + [f"locality_id={geo['warszawa']}"] * 30
              + [f"admin_area_id={geo['malopolskie']}"] * 10 + ["country_code=PL"] * 10
              + [""] * 10)
    with sessions() as db:
        db.execute(insert(User), [
            {"id": f"00000000-0000-4000-8000-{u:012d}", "email": f"scale{u}@example.com",
             "password_hash": "x", "role": "guest"} for u in range(USERS)])
        ctx = search.QueryContext(db)
        rows, anchors = [], []
        now = db.scalar(text("SELECT now() - interval '1 hour'"))
        taken: set[tuple[int, str]] = set()
        for i in range(n):
            place = rng.choice(places)
            raw = "&".join(filter(None, [place, f"max_rent={rng.randrange(150_000, 400_000, 1000)}",
                                         rng.choice(["", "min_rooms=2", "category=APARTMENT",
                                                     "min_area_m2=40"])]))
            q = search.parse_query_string(db, raw, ctx)
            sid = str(uuid.uuid4())
            canonical = q.canonical()
            # A genuine fingerprint (a forged one makes the search INVALID —
            # TASK-014R F-2); a user who already saved this query gets the
            # next user who has not, as the unique (user, fingerprint) needs.
            user = i % USERS
            while (user, canonical) in taken:
                user = (user + 1) % USERS
            taken.add((user, canonical))
            rows.append({"id": sid, "user_id": f"00000000-0000-4000-8000-{user:012d}",
                         "name": f"s{i}", "market_country_code": "PL",
                         "canonical_query": canonical, "query_schema_version": 1,
                         "query_fingerprint": service.fingerprint(1, canonical),
                         "notifications_enabled": True, "status": "active", "created_at": now,
                         "updated_at": now, "baseline_at": now, "version": 1})
            anchors += [{"saved_search_id": sid, "kind": k, "value": v}
                        for k, v in service.anchors_for(q)]
        db.execute(insert(SavedSearch), rows)
        db.execute(insert(SavedSearchAnchor), anchors)
        db.commit()


def _new_listing(pg_client, owner, place):
    made = pg_client.post("/v1/properties", json={
        "category": "APARTMENT", "area_m2": 50, "rooms": 2, "capacity": 2, **place,
        "building_number": str(uuid.uuid4())[:6]}, headers=auth(owner)).json()
    verify_ownership(pg_client, owner, made["id"])
    oid = pg_client.post(f"/v1/properties/{made['id']}/classifieds", json={
        "title": "Skala", "rent_amount": 250000, "min_term_months": 12,
        "contact_mode": "message"}, headers=auth(owner)).json()["id"]
    assert pg_client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner)).status_code == 200
    return oid


def test_matching_scales_with_candidates_not_with_the_board(pg_client, pg_migrated_engine):
    sessions = sessionmaker(bind=pg_migrated_engine, expire_on_commit=False)
    geo = load_geo(sessions)
    owner = register_and_login(pg_client, "scale-owner@example.com", "host")
    templates = [_new_listing(pg_client, owner, {"locality_id": geo[c]})
                 for c in ("krakow", "warszawa", "balice")]
    with sessions() as db:  # the templates' own work is not what is measured
        db.execute(text("UPDATE listing_public_generations SET alert_status = 'done'"))
        db.commit()
    _seed_listings(pg_migrated_engine, templates, LISTINGS - len(templates))
    _seed_searches(sessions, geo, SEARCHES)
    with pg_migrated_engine.connect() as conn:
        conn.execute(text("ANALYZE saved_searches; ANALYZE saved_search_anchors; "
                          "ANALYZE classified_offers"))
        board = conn.scalar(text("SELECT count(*) FROM classified_offers"))
        total_searches = conn.scalar(text("SELECT count(*) FROM saved_searches"))
    report = {"saved_searches": total_searches, "listings_on_board": board, "cases": {}}

    for label in ("krakow", "warszawa", "balice"):
        oid = _new_listing(pg_client, owner, {"locality_id": geo[label]})
        statements = []

        def count(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(pg_migrated_engine, "before_cursor_execute", count)
        try:
            started = time.perf_counter()
            with sessions() as db:
                outcome = matching.process_generation(db, oid, 1)
                db.commit()
            elapsed = time.perf_counter() - started
        finally:
            event.remove(pg_migrated_engine, "before_cursor_execute", count)
        evaluations = sum(1 for s in statements if "AS m0" in s or " AS m200" in s
                          or ("FROM classified_offers JOIN properties" in s and " AS m" in s))
        report["cases"][label] = {
            "candidates": outcome.candidates, "matches": outcome.matches,
            "deliveries": outcome.deliveries, "sql_statements": len(statements),
            "evaluation_statements": evaluations, "seconds_local": round(elapsed, 3),
            "cartesian_equivalent": total_searches * board,
        }
        # The architecture, asserted:
        assert outcome.candidates < total_searches  # never every saved search
        # One statement per chunk of DISTINCT candidate queries (identical
        # canonical queries are evaluated once).
        assert 1 <= evaluations <= math.ceil(outcome.candidates / search.EVALUATION_CHUNK)
        # A fixed number of statements plus one per evaluation chunk — never
        # one per candidate search and never a scan per listing on the board.
        assert len(statements) <= 40 + evaluations, statements[:50]
        with sessions() as db:
            assert db.get(ListingPublicGeneration, (oid, 1)).alert_status == "done"

    with pg_migrated_engine.connect() as conn:
        keys = "('L', :l), ('C', 'PL'), ('*', '*')"
        plan = conn.execute(text(
            "EXPLAIN (ANALYZE, BUFFERS) SELECT s.id FROM saved_searches s WHERE s.id IN "
            f"(SELECT saved_search_id FROM saved_search_anchors WHERE (kind, value) IN ({keys})) "
            "AND s.status = 'active' AND s.notifications_enabled "
            "AND s.baseline_at < now()"), {"l": geo["balice"]}).scalars().all()
    report["candidate_plan_balice"] = plan
    print("\nTASK014_SCALE_REPORT " + json.dumps(report, indent=2, default=str))
    # Balice (a village) is anchored by no locality search: only the region,
    # country and place-less searches are candidates.
    assert report["cases"]["balice"]["candidates"] < report["cases"]["krakow"]["candidates"]
