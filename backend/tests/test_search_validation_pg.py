"""TASK-013R on real PostgreSQL/PostGIS: input that used to reach the database
as a 500, and the map partition under a concurrent publication.

* F13A-01: huge integers and NUL-bearing text/ids are refused before SQL on
  both surfaces (the candidate raised `NumericValueOutOfRange` /
  "text fields cannot contain NUL" from PostgreSQL);
* F13A-02: total / with_point / without_point come from one aggregate, so a
  publication committed between statements cannot make the partition
  impossible;
* the map cap at 499 / 500 / 501 markers;
* the public-eligibility cutoff (21×24h) and spatial privacy still hold for
  the counts, not only for the rows.
"""

import pytest
from sqlalchemy import event, text

from app.modules.properties import search
from tests.conftest import TEST_DATABASE_URL
from tests.test_search_pg import _listing, owner  # noqa: F401 — fixture

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

SURFACES = ("/v1/classifieds", "/v1/classifieds/map")
POINT = {"latitude": 50.0614, "longitude": 19.9366}


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("name, value", [
    ("max_rent", str(10**100)), ("min_rent", str(2**63)), ("max_monthly_total", str(10**100)),
    ("min_monthly_total", str(10**100)), ("max_move_in_total", str(10**100)),
    ("min_rooms", str(2**31)), ("min_area_m2", str(10**100)), ("max_term_months", str(2**31)),
    ("city", "Kra\x00ków"), ("district", "Kazi\x00mierz"), ("locality_id", "abc\x00def"),
    ("admin_area_id", "abc\x00def"), ("geo_area_id", "abc\x00def"), ("has", "bal\x00cony"),
    ("furnished", "INVALID"), ("parking", "INVALID"),
])
def test_input_that_reached_postgres_as_a_500_is_now_422(pg_client, surface, name, value):
    # raise_server_exceptions is on: a database error would raise here.
    response = pg_client.get(surface, params={name: value})
    assert response.status_code == 422, (name, response.status_code, response.text)


def test_bounds_themselves_are_valid_queries_on_postgres(pg_client, owner):  # noqa: F811
    _listing(pg_client, owner, prop=POINT)
    for surface in SURFACES:
        response = pg_client.get(surface, params={
            "max_rent": search.MAX_MONEY_MINOR, "min_rooms": 0, "min_area_m2": 0,
            "max_term_months": search.MAX_TERM_MONTHS, "max_monthly_total": search.MAX_MONEY_MINOR,
            "max_move_in_total": search.MAX_MONEY_MINOR})
        assert response.status_code == 200 and response.json()["total"] == 1, response.text


@pytest.mark.parametrize("surface", SURFACES)
def test_negative_zero_coordinates_have_one_canonical_form(pg_client, surface):
    def canonical(params):
        response = pg_client.get(surface, params=params)
        assert response.status_code == 200, response.text
        return response.json()["query"]

    zero = canonical({"near_lat": "0.0", "near_lon": "0.0", "radius_m": 1000, "bbox": "0,0,1,1"})
    negative = canonical({"near_lat": "-0.0", "near_lon": "-0.0", "radius_m": 1000,
                          "bbox": "-0.0,-0.0,1,1"})
    assert zero == negative and "-0.0" not in negative
    params = [("near_lat", "-0.0"), ("near_lon", "19.9"), ("radius_m", "1500"),
              ("bbox", "19.8,49.9,20.1,50.2"), ("city", "Kraków")]
    first = canonical(params)
    from urllib.parse import parse_qsl
    assert canonical(parse_qsl(first)) == first


# --- F13A-02: the map partition ----------------------------------------------------------


def _partition(body):
    total, with_point, without = body["total"], body["with_point"], body["without_point"]
    assert without >= 0 and with_point >= 0, body
    assert total == with_point + without, body
    return total, with_point, without


def test_the_partition_counts_listings_with_and_without_a_point(pg_client, owner):  # noqa: F811
    with_point = [_listing(pg_client, owner, prop=POINT) for _ in range(3)]
    _listing(pg_client, owner)  # no coordinates: listed, no marker
    _listing(pg_client, owner, prop=POINT, offer={"public_location_precision": "DISTRICT"})
    body = pg_client.get("/v1/classifieds/map").json()
    assert _partition(body) == (5, 3, 2)
    assert {p["id"] for p in body["points"]} == set(with_point)
    assert body["truncated"] is False


def test_a_publication_between_statements_cannot_break_the_partition(
        pg_client, pg_migrated_engine, owner):  # noqa: F811
    """The F13A-02 interleaving, made deterministic: right after the map's first
    COUNT statement, another connection publishes a pointed listing. Two
    separate counts would read total=0 then with_point=1 (without_point=-1);
    one aggregate cannot."""
    offer_id = _listing(pg_client, owner, prop=POINT)
    with pg_migrated_engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET status = 'draft' WHERE id = :id"),
                      {"id": offer_id})
    assert pg_client.get("/v1/classifieds/map").json()["total"] == 0

    fired = {"done": False}

    def publish_after_first_count(conn, cursor, statement, parameters, context, executemany):
        if fired["done"] or "count(" not in statement.lower():
            return
        fired["done"] = True
        with pg_migrated_engine.connect() as other:
            other.execute(text("UPDATE classified_offers SET status = 'active', "
                               "last_confirmed_available_at = now() WHERE id = :id"),
                          {"id": offer_id})
            other.commit()

    event.listen(pg_migrated_engine, "after_cursor_execute", publish_after_first_count)
    try:
        body = pg_client.get("/v1/classifieds/map").json()
    finally:
        event.remove(pg_migrated_engine, "after_cursor_execute", publish_after_first_count)
    assert fired["done"]
    total, with_point, _ = _partition(body)
    assert with_point <= total
    # Drift between the aggregate and the marker rows is accepted (READ
    # COMMITTED); impossible counts inside one response are not.
    assert pg_client.get("/v1/classifieds/map").json()["total"] == 1


def _clone(pg_migrated_engine, seed_id: str, copies: int) -> None:
    """copies more rows of one published listing (generated columns omitted)."""
    with pg_migrated_engine.begin() as conn:
        columns = [r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'classified_offers' AND is_generated = 'NEVER' "
            "ORDER BY ordinal_position"))]
        values = ["gen_random_uuid()::text" if c == "id" else c for c in columns]
        conn.execute(text(
            f"INSERT INTO classified_offers ({', '.join(columns)}) "  # noqa: S608
            f"SELECT {', '.join(values)} FROM classified_offers, generate_series(1, :n) "
            "WHERE id = :seed"), {"n": copies, "seed": seed_id})


@pytest.mark.parametrize("markers, truncated", [(499, False), (500, False), (501, True)])
def test_the_map_cap_at_499_500_501(pg_client, pg_migrated_engine, owner, markers, truncated):  # noqa: F811
    seed = _listing(pg_client, owner, prop=POINT)
    _clone(pg_migrated_engine, seed, markers - 1)
    _listing(pg_client, owner)  # one without a point, never a marker
    body = pg_client.get("/v1/classifieds/map", params={"sort": "price_asc"}).json()
    assert _partition(body) == (markers + 1, markers, 1)
    assert body["cap"] == search.MAP_CAP
    assert len(body["points"]) == min(markers, search.MAP_CAP)
    assert body["truncated"] is truncated
    listed = pg_client.get("/v1/classifieds", params={"sort": "price_asc", "limit": 100}).json()
    pointed = [o["id"] for o in listed["items"] if o["id"] in {p["id"] for p in body["points"]}]
    assert [p["id"] for p in body["points"]][:len(pointed)] == pointed, "map keeps list order"


# --- eligibility and privacy still hold for the counts -----------------------------------


def test_the_21_day_cutoff_applies_to_the_map_counts(pg_client, pg_migrated_engine, owner):  # noqa: F811
    fresh = _listing(pg_client, owner, prop=POINT)
    edge = _listing(pg_client, owner, prop=POINT)
    expired = _listing(pg_client, owner)
    with pg_migrated_engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET last_confirmed_available_at = "
                          "now() - interval '21 days' + interval '1 minute' WHERE id = :id"),
                     {"id": edge})
        conn.execute(text("UPDATE classified_offers SET last_confirmed_available_at = "
                          "now() - interval '21 days' WHERE id = :id"), {"id": expired})
    body = pg_client.get("/v1/classifieds/map").json()
    assert _partition(body) == (2, 2, 0)
    assert {p["id"] for p in body["points"]} == {fresh, edge}
    assert pg_client.get("/v1/classifieds").json()["total"] == 2


def test_map_counts_follow_the_public_point_not_the_exact_one(
        pg_client, pg_migrated_engine, owner):  # noqa: F811
    """A viewport around the exact home but outside its public grid cell
    counts nothing — the aggregate uses public_geog like the rows (D-70)."""
    offer = _listing(pg_client, owner, prop=POINT)
    with pg_migrated_engine.connect() as conn:
        pub = conn.execute(text("SELECT public_latitude, public_longitude FROM "
                                "classified_offers WHERE id = :id"), {"id": offer}).one()
    lat, lon = POINT["latitude"], POINT["longitude"]
    assert (float(pub[0]), float(pub[1])) != (lat, lon)
    around_exact = f"{lon - 0.0002},{lat - 0.0002},{lon + 0.0002},{lat + 0.0002}"
    around_public = f"{float(pub[1]) - 0.0002},{float(pub[0]) - 0.0002}," \
                    f"{float(pub[1]) + 0.0002},{float(pub[0]) + 0.0002}"
    exact = pg_client.get("/v1/classifieds/map", params={"bbox": around_exact}).json()
    public = pg_client.get("/v1/classifieds/map", params={"bbox": around_public}).json()
    assert _partition(exact) == (0, 0, 0)
    assert _partition(public) == (1, 1, 0)
