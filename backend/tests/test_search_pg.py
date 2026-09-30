"""Marketplace discovery on real PostgreSQL/PostGIS (TASK-013).

* structured geography composes (country, admin descendants, localities,
  search areas; multi-value OR inside a dimension, AND across);
* list and map are one universe, also inside a viewport;
* spatial privacy: anonymous spatial inclusion follows the PUBLIC point only,
  so boxes and circles around the exact home reveal nothing (D-70);
* no private sentinel reaches list, map, filters or detail;
* rendering structured places costs a fixed number of queries per page.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text

from app.modules.geography import service
from app.modules.geography.models import GeoArea, GeoExternalRef, GeoSource
from app.modules.properties import location
from app.modules.properties.models import Property
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership
from tests.test_geography import PL_AREAS, PL_LOCALITIES, SOURCE
from tests.test_geography_pg import _migrate, scratch_url  # noqa: F401

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

OFFER = {"title": "Odkrywanie", "rent_amount": 250000, "min_term_months": 12,
         "contact_mode": "message"}


def _ref(db, external_id, column):
    return service._by_ref(db, SOURCE, external_id, column)


@pytest.fixture
def geo(pg_client, pg_session):
    db = pg_session
    if db.get(GeoSource, SOURCE) is None:
        db.add(GeoSource(code=SOURCE, name="Test fixture (not an official register)"))
        db.flush()
    service.import_areas(db, "PL", SOURCE, PL_AREAS)
    service.import_localities(db, "PL", SOURCE, PL_LOCALITIES)
    db.commit()
    ids = {name: _ref(db, ext, "locality_id")
           for name, ext in (("krakow", "L-KRK"), ("warszawa", "L-WAW"), ("balice", "L-BAL"))}
    ids.update({name: _ref(db, ext, "admin_area_id")
                for name, ext in (("malopolskie", "12"), ("mazowieckie", "14"),
                                  ("zabierzow", "1206152"))})
    kazimierz = GeoArea(country_code="PL", locality_id=ids["krakow"], kind="NEIGHBOURHOOD",
                        name="Kazimierz", slug="kazimierz")
    db.add(kazimierz)
    db.commit()
    ids["kazimierz"] = kazimierz.id
    return ids


@pytest.fixture
def owner(pg_client):
    return register_and_login(pg_client, "discover@example.com", "host")


_n = {"i": 0}


def _listing(pg_client, owner, place=None, prop=None, offer=None, room=False):
    _n["i"] += 1
    body = {"category": "APARTMENT", "area_m2": 48, "rooms": 2, "capacity": 2,
            "building_number": str(_n["i"]), **(place or {"city": "Kielce",
                                                      "address": f"ul. A {_n['i']}"}),
            **(prop or {})}
    made = pg_client.post("/v1/properties", json=body, headers=auth(owner))
    assert made.status_code == 201, made.text
    pid = made.json()["id"]
    verify_ownership(pg_client, owner, pid)
    extra = {}
    if room:
        space = pg_client.post(f"/v1/properties/{pid}/spaces",
                               json={"label": "Pokój", "area_m2": 11}, headers=auth(owner))
        extra["space_id"] = space.json()["id"]
    oid = pg_client.post(f"/v1/properties/{pid}/classifieds", json={**OFFER, **extra,
                         **(offer or {})}, headers=auth(owner)).json()["id"]
    assert pg_client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner)).status_code == 200
    return oid


def _ids(pg_client, **params):
    response = pg_client.get("/v1/classifieds", params={"limit": 100, **params})
    assert response.status_code == 200, response.text
    return set(o["id"] for o in response.json()["items"])


def _map_ids(pg_client, **params):
    response = pg_client.get("/v1/classifieds/map", params=params)
    assert response.status_code == 200, response.text
    return {p["id"] for p in response.json()["points"]}, response.json()


# --- geography ----------------------------------------------------------------------------


def test_structured_geography_composes(pg_client, geo, owner):
    krakow = _listing(pg_client, owner, {"locality_id": geo["krakow"],
                                         "geo_area_id": geo["kazimierz"]})
    balice = _listing(pg_client, owner, {"locality_id": geo["balice"]})
    warsaw = _listing(pg_client, owner, {"locality_id": geo["warszawa"]})
    typed = _listing(pg_client, owner)  # unstructured: country known, no reference place
    # The country is known for every address (unstructured ones too); the
    # finer structured filters match only what an address references.
    assert _ids(pg_client, country_code="PL") == {krakow, balice, warsaw, typed}
    assert _ids(pg_client, admin_area_id=geo["malopolskie"]) == {krakow, balice}  # descendants
    assert _ids(pg_client, admin_area_id=geo["zabierzow"]) == {balice}
    assert _ids(pg_client, admin_area_id=[geo["zabierzow"], geo["mazowieckie"]]) == {balice,
                                                                                    warsaw}
    assert _ids(pg_client, locality_id=[geo["krakow"], geo["warszawa"]]) == {krakow, warsaw}
    assert _ids(pg_client, geo_area_id=geo["kazimierz"]) == {krakow}
    assert _ids(pg_client, admin_area_id=geo["malopolskie"], locality_id=geo["warszawa"]) == set()
    assert typed not in _ids(pg_client, admin_area_id=geo["malopolskie"]) | _ids(
        pg_client, locality_id=[geo["krakow"], geo["warszawa"], geo["balice"]])


def test_a_place_in_another_country_than_asked_is_422(pg_client, pg_session, geo):
    for param in ("admin_area_id", "locality_id", "geo_area_id"):
        value = geo["malopolskie"] if param == "admin_area_id" else (
            geo["krakow"] if param == "locality_id" else geo["kazimierz"])
        for path in ("/v1/classifieds", "/v1/classifieds/map"):
            response = pg_client.get(path, params={"country_code": "DE", param: value})
            assert response.status_code == 422, (param, path, response.text)


def test_compound_queries_return_exactly_the_expected_listings(pg_client, geo, owner):
    target = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                      offer={"rent_amount": 240000, "available_from": "2026-11-01"})
    too_dear = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                        offer={"rent_amount": 260000, "available_from": "2026-11-01"})
    too_late = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                        offer={"rent_amount": 240000, "available_from": "2027-03-01"})
    undated = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                       offer={"rent_amount": 240000})
    house = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                     prop={"category": "HOUSE"},
                     offer={"rent_amount": 240000, "available_from": "2026-11-01"})
    room = _listing(pg_client, owner, {"locality_id": geo["krakow"]}, room=True,
                    offer={"rent_amount": 120000, "available_from": "2026-11-01"})
    region_room = _listing(pg_client, owner, {"locality_id": geo["balice"]}, room=True,
                           offer={"rent_amount": 90000})
    compound = {"locality_id": geo["krakow"], "category": "APARTMENT",
                "space_type": "WHOLE_PROPERTY", "max_rent": 250000, "available_by": "2026-12-01"}
    assert _ids(pg_client, **compound) == {target}
    assert _map_ids(pg_client, **compound)[1]["total"] == 1
    assert _ids(pg_client, admin_area_id=geo["malopolskie"], space_type="ROOM") == {
        room, region_room}
    assert not {too_dear, too_late, undated, house} & _ids(pg_client, **compound)


# --- the map is the list's universe, also in a viewport ------------------------------------

KRAKOW_BOX = "19.90,50.03,19.99,50.09"


def test_list_and_map_agree_inside_a_viewport(pg_client, geo, owner):
    inside = [_listing(pg_client, owner, {"locality_id": geo["krakow"]},
                       prop={"latitude": 50.05 + i / 200, "longitude": 19.93})
              for i in range(3)]
    outside = _listing(pg_client, owner, {"locality_id": geo["warszawa"]},
                       prop={"latitude": 52.23, "longitude": 21.01})
    district = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                        prop={"latitude": 50.06, "longitude": 19.94},
                        offer={"public_location_precision": "DISTRICT"})
    for params in ({"bbox": KRAKOW_BOX}, {"bbox": KRAKOW_BOX, "max_rent": 250000},
                   {"bbox": KRAKOW_BOX, "sort": "price_desc"}):
        listed = _ids(pg_client, **params)
        mapped, page = _map_ids(pg_client, **params)
        assert listed == mapped == set(inside), params
        assert page["without_point"] == 0 and page["total"] == len(listed)
    assert outside not in _ids(pg_client, bbox=KRAKOW_BOX)
    assert district not in _ids(pg_client, bbox=KRAKOW_BOX)  # no point, no viewport match


# --- spatial privacy probe (D-70) ----------------------------------------------------------

EXACT = (50.061237, 19.937681)


def _box(lat, lon, half=0.0004):
    return f"{lon - half},{lat - half},{lon + half},{lat + half}"


def test_spatial_search_is_no_oracle_for_the_exact_home(pg_client, geo, owner):
    offer = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                     prop={"latitude": EXACT[0], "longitude": EXACT[1]})
    public = tuple(float(v) for v in location.public_point(*EXACT, "APPROXIMATE"))
    assert public != EXACT
    # Boxes and circles around the exact home that miss the public cell centre:
    # the listing is never found — the exact point is not what is searched.
    for dlat, dlon in ((0, 0), (0.0002, 0), (0, 0.0002), (-0.0002, -0.0002)):
        box = _box(EXACT[0] + dlat, EXACT[1] + dlon)
        assert offer not in _ids(pg_client, bbox=box), box
        assert offer not in _map_ids(pg_client, bbox=box)[0], box
    assert offer not in _ids(pg_client, near_lat=EXACT[0], near_lon=EXACT[1], radius_m=20)
    # Around the public point it is found — the only thing the map ever shows.
    assert offer in _ids(pg_client, bbox=_box(*public))
    assert offer in _ids(pg_client, near_lat=public[0], near_lon=public[1], radius_m=20)
    # Shrinking boxes converge on the public point, never on the exact one.
    for half in (0.01, 0.003, 0.001, 0.0002):
        found = offer in _ids(pg_client, bbox=_box(*public, half=half))
        assert found, half


def test_the_database_never_filters_public_search_by_the_exact_point(pg_client, pg_session,
                                                                      geo, owner):
    """Belt and braces: move the exact point far away without touching the
    public point — spatial search results do not change."""
    offer = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                     prop={"latitude": EXACT[0], "longitude": EXACT[1]})
    public = tuple(float(v) for v in location.public_point(*EXACT, "APPROXIMATE"))
    before = _ids(pg_client, bbox=_box(*public))
    pid = pg_session.scalar(text("SELECT property_id FROM classified_offers WHERE id = :o"),
                            {"o": offer})
    pg_session.execute(text("UPDATE properties SET latitude = -33.9, longitude = 151.2 "
                            "WHERE id = :p"), {"p": pid})
    pg_session.commit()
    assert _ids(pg_client, bbox=_box(*public)) == before == {offer}
    assert offer not in _ids(pg_client, bbox="151.1,-34.0,151.3,-33.8")


# --- private sentinels ----------------------------------------------------------------------

SENTINELS = ("ul. Odkryta-Tajna", "913Q", "U-7070", "88-777", "RAW-SENTINEL-4242",
             "PRG-DISCOVER-9191", "50.061237", "19.937681", "+48 777 666 555", "Kowalski")


def test_no_private_sentinel_reaches_discovery(pg_client, pg_session, geo, owner):
    offer = _listing(pg_client, owner, {"locality_id": geo["krakow"],
                                        "geo_area_id": geo["kazimierz"]},
                     prop={"thoroughfare": "ul. Odkryta-Tajna", "building_number": "913Q",
                           "unit_number": "U-7070", "postcode": "88-777",
                           "address": "RAW-SENTINEL-4242",
                           "latitude": EXACT[0], "longitude": EXACT[1]},
                     offer={"contact_mode": "phone", "contact_phone": "+48 777 666 555"})
    pid = pg_session.scalar(text("SELECT property_id FROM classified_offers WHERE id = :o"),
                            {"o": offer})
    prop = pg_session.get(Property, pid)
    pg_session.add(GeoExternalRef(source_code="PL_PRG_ADDRESS", external_id="PRG-DISCOVER-9191",
                                  address_id=prop.address_id))
    pg_session.commit()
    public = tuple(float(v) for v in location.public_point(*EXACT, "APPROXIMATE"))
    probes = [
        ("/v1/classifieds", {}),
        ("/v1/classifieds", {"locality_id": geo["krakow"], "geo_area_id": geo["kazimierz"]}),
        ("/v1/classifieds", {"admin_area_id": geo["malopolskie"], "country_code": "PL"}),
        ("/v1/classifieds", {"bbox": _box(*public, half=0.01)}),
        ("/v1/classifieds", {"near_lat": public[0], "near_lon": public[1], "radius_m": 500}),
        ("/v1/classifieds", {"city": "Kraków", "district": "Kazimierz", "sort": "price_asc"}),
        ("/v1/classifieds/map", {}),
        ("/v1/classifieds/map", {"bbox": _box(*public, half=0.01)}),
        (f"/v1/classifieds/{offer}", {}),
    ]
    for path, params in probes:
        response = pg_client.get(path, params=params)
        assert response.status_code == 200, (path, params, response.text)
        assert offer in response.text, (path, params)  # the probe is not vacuous
        for sentinel in (*SENTINELS, prop.address_id):
            assert sentinel not in response.text, (sentinel, path, params)


# --- query count: rendering places costs a fixed number of queries ---------------------------


def test_a_page_of_structured_listings_costs_a_fixed_number_of_queries(
        pg_client, pg_migrated_engine, geo, owner):
    places = [{"locality_id": geo["krakow"], "geo_area_id": geo["kazimierz"]},
              {"locality_id": geo["balice"]}, {"locality_id": geo["warszawa"]},
              {"admin_area_id": geo["zabierzow"]}]
    for i in range(24):
        _listing(pg_client, owner, places[i % len(places)])
    seen: list[str] = []

    def count(conn, cursor, statement, *args):
        seen.append(statement)

    counts = {}
    event.listen(pg_migrated_engine, "before_cursor_execute", count)
    try:
        for limit in (1, 10, 24):
            seen.clear()
            response = pg_client.get("/v1/classifieds", params={"limit": limit})
            assert response.status_code == 200 and len(response.json()["items"]) == limit
            assert all(o["place"] is not None for o in response.json()["items"])
            counts[limit] = len(seen)
        seen.clear()
        assert pg_client.get("/v1/classifieds/map").status_code == 200
        counts["map"] = len(seen)
    finally:
        event.remove(pg_migrated_engine, "before_cursor_execute", count)
    # Bounded, not per row: a relation's one selectin query appears once a
    # page contains it (a single row may need fewer), then never grows.
    assert counts[10] == counts[24] and counts[1] <= counts[10] <= 10, counts
    assert counts["map"] <= 4, counts


def test_stale_listings_are_absent_from_viewport_and_map(pg_client, pg_migrated_engine, geo,
                                                         owner):
    offer = _listing(pg_client, owner, {"locality_id": geo["krakow"]},
                     prop={"latitude": 50.06, "longitude": 19.94})
    with pg_migrated_engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET last_confirmed_available_at = :t "
                          "WHERE id = :o"),
                     {"t": datetime.now(timezone.utc) - timedelta(days=21, seconds=1),
                      "o": offer})
    assert offer not in _ids(pg_client, bbox=KRAKOW_BOX)
    assert offer not in _map_ids(pg_client, bbox=KRAKOW_BOX)[0]
    assert _map_ids(pg_client)[1]["total"] == 0


# --- migration: discovery indexes, from the accepted TASK-012 head --------------------------

TASK_012_HEAD = "b8d0f2a4c6e8"
TASK_013_HEAD = "d0f2b4c6e8a1"


def test_the_index_migration_changes_no_data(scratch_url):  # noqa: F811
    from sqlalchemy import create_engine

    from tests.test_listing_freshness_pg import _seed

    _migrate(scratch_url, TASK_012_HEAD)
    engine = create_engine(scratch_url)
    with engine.begin() as conn:
        _seed(conn, [("active", datetime.now(timezone.utc)), ("draft", None)])

    def snapshot():
        with engine.connect() as conn:
            return (conn.execute(text("SELECT * FROM classified_offers ORDER BY id")).all(),
                    conn.execute(text("SELECT * FROM addresses ORDER BY id")).all())

    def indexes():
        with engine.connect() as conn:
            return set(conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE indexname IN "
                "('ix_addresses_geo_area', 'ix_classified_offers_primary_price_minor')"))
                .scalars())

    before = snapshot()
    _migrate(scratch_url, TASK_013_HEAD)
    assert snapshot() == before
    assert indexes() == {"ix_addresses_geo_area", "ix_classified_offers_primary_price_minor"}
    _migrate(scratch_url, TASK_012_HEAD, down=True)
    assert indexes() == set() and snapshot() == before
    _migrate(scratch_url, TASK_013_HEAD)
    engine.dispose()
