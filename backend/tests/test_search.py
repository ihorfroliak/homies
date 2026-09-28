"""Marketplace discovery — one query model for list and map (TASK-013).

API/domain level on SQLite. Spatial (PostGIS), structured-geography,
privacy-probe and query-count guarantees are proved on PostgreSQL in
test_search_pg.py.
"""

from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl

import pytest
from sqlalchemy import update

from app.modules.properties import search
from app.modules.properties.models import ClassifiedOffer
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership

BASE_PROPERTY = {"city": "Lublin", "area_m2": 50, "rooms": 2, "capacity": 2}
BASE_OFFER = {"title": "Szukane", "rent_amount": 200000, "min_term_months": 12,
              "contact_mode": "message"}


@pytest.fixture
def owner(client):
    return register_and_login(client, "search-owner@example.com", "host")


_n = {"i": 0}


def _listing(client, token, prop=None, offer=None, room=False, publish=True):
    _n["i"] += 1
    body = {**BASE_PROPERTY, "category": "APARTMENT", "address": f"ul. Szukana {_n['i']}",
            **(prop or {})}
    made = client.post("/v1/properties", json=body, headers=auth(token))
    assert made.status_code == 201, made.text
    pid = made.json()["id"]
    verify_ownership(client, token, pid)
    extra = {}
    if room:
        space = client.post(f"/v1/properties/{pid}/spaces",
                            json={"label": "Pokój A", "area_m2": 12}, headers=auth(token))
        assert space.status_code == 201, space.text
        extra["space_id"] = space.json()["id"]
    created = client.post(f"/v1/properties/{pid}/classifieds",
                          json={**BASE_OFFER, **extra, **(offer or {})}, headers=auth(token))
    assert created.status_code == 201, created.text
    oid = created.json()["id"]
    if publish:
        assert client.post(f"/v1/classifieds/{oid}/publish", headers=auth(token)).status_code == 200
    return oid


def _ids(client, **params):
    response = client.get("/v1/classifieds", params=params)
    assert response.status_code == 200, response.text
    return [o["id"] for o in response.json()["items"]]


def _map(client, **params):
    response = client.get("/v1/classifieds/map", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --- property / space ------------------------------------------------------------------------


def test_category_subtype_and_space_type_compose(client, owner):
    flat = _listing(client, owner)
    studio = _listing(client, owner, prop={"subtype": "STUDIO"})
    house = _listing(client, owner, prop={"category": "HOUSE", "subtype": "DETACHED_HOUSE"})
    room = _listing(client, owner, room=True)
    assert set(_ids(client, category="APARTMENT")) == {flat, studio, room}
    assert set(_ids(client, category=["APARTMENT", "HOUSE"])) == {flat, studio, house, room}
    assert _ids(client, subtype="STUDIO") == [studio]
    assert _ids(client, space_type="ROOM") == [room]
    assert set(_ids(client, space_type="WHOLE_PROPERTY", category="APARTMENT")) == {flat, studio}
    assert _ids(client, category="HOUSE", space_type="ROOM") == []  # unlikely, not invalid


@pytest.mark.parametrize("params, message", [
    ({"category": "ROOM"}, "category must be one of"),
    ({"subtype": "CASTLE"}, "subtype must be one of"),
    ({"category": "HOUSE", "subtype": "STUDIO"}, "is not a kind of"),
    ({"space_type": "BED"}, "space_type must be one of"),
    ({"min_rent": 300000, "max_rent": 200000}, "min_rent is above max_rent"),
    ({"min_monthly_total": 5, "max_monthly_total": 4}, "min_monthly_total is above"),
    ({"sort": "relevance"}, "sort must be one of"),
    ({"has": "not_an_attribute"}, "not a filterable attribute"),
    ({"offset": 10_001}, ""),
])
def test_contradictory_or_invalid_queries_are_422_not_500(client, params, message):
    for path in ("/v1/classifieds", "/v1/classifieds/map"):
        if path.endswith("map") and "offset" in params:
            continue
        response = client.get(path, params=params)
        assert response.status_code == 422, (path, response.text)
        assert message in response.text


# --- price and costs -------------------------------------------------------------------------


def test_rent_monthly_total_and_move_in_are_different_filters(client, owner):
    plain = _listing(client, owner, offer={"rent_amount": 200000})
    fees = _listing(client, owner, offer={"rent_amount": 180000, "admin_fee": 50000})
    deposit = _listing(client, owner, offer={"rent_amount": 190000, "deposit_amount": 400000})
    # rent: the base rent alone — boundaries inclusive
    assert set(_ids(client, max_rent=190000)) == {fees, deposit}
    assert set(_ids(client, min_rent=190000, max_rent=190000)) == {deposit}
    # monthly total: every mandatory monthly charge stated
    assert set(_ids(client, max_monthly_total=200000)) == {plain, deposit}
    assert _ids(client, min_monthly_total=230000) == [fees]
    # move-in: first month + mandatory one-offs (deposit included)
    assert set(_ids(client, max_move_in_total=230000)) == {plain, fees}


def test_utilities_basis_says_how_honest_the_total_is(client, owner):
    stated = _listing(client, owner, offer={"utilities_amount": 30000})
    included = _listing(client, owner, offer={"utilities_amount": 30000,
                                              "utilities_included": True})
    unknown = _listing(client, owner)
    items = {o["id"]: o for o in client.get("/v1/classifieds").json()["items"]}
    assert items[stated]["utilities_basis"] == "ESTIMATED"
    assert items[stated]["monthly_total_estimate"] == 230000
    assert items[included]["utilities_basis"] == "INCLUDED"
    assert items[included]["monthly_total_estimate"] == 200000
    assert items[unknown]["utilities_basis"] == "NOT_STATED"


# --- availability ----------------------------------------------------------------------------


def test_available_by_matches_stated_dates_only(client, owner):
    soon = _listing(client, owner, offer={"available_from": "2026-10-01"})
    later = _listing(client, owner, offer={"available_from": "2027-02-01"})
    unknown = _listing(client, owner)
    assert _ids(client, available_by="2026-12-31") == [soon]
    assert set(_ids(client)) == {soon, later, unknown}  # UNKNOWN stays in general search
    assert _ids(client, sort="available_soonest") == [soon, later, unknown]  # unknown last


# --- freshness: search never resurrects ---------------------------------------------------


def test_stale_paused_and_draft_never_appear_in_list_or_map(client, owner):
    fresh = _listing(client, owner)
    stale = _listing(client, owner)
    paused = _listing(client, owner)
    draft = _listing(client, owner, publish=False)
    with TestingSession() as db:
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == stale).values(
            last_confirmed_available_at=datetime.now(timezone.utc) - timedelta(days=21)))
        db.commit()
    assert client.post(f"/v1/classifieds/{paused}/pause", headers=auth(owner)).status_code == 200
    assert _ids(client) == [fresh]
    assert _map(client)["total"] == 1
    assert {p["id"] for p in _map(client)["points"]} <= {fresh}
    assert draft not in _ids(client)


# --- sorting and paging -----------------------------------------------------------------------


def test_equal_sort_keys_page_deterministically_by_id(client, owner):
    offers = [_listing(client, owner, offer={"rent_amount": 150000}) for _ in range(5)]
    for sort in ("price_asc", "price_desc", "size_desc"):
        pages = [_ids(client, sort=sort, limit=2, offset=o) for o in (0, 2, 4)]
        flat = [i for page in pages for i in page]
        assert flat == sorted(offers), sort  # ties broken by id, no gaps, no repeats


def test_newest_is_publication_order_and_confirmation_does_not_bump(client, owner):
    first = _listing(client, owner)
    second = _listing(client, owner)
    assert _ids(client)[:2] == [second, first]
    assert client.post(f"/v1/classifieds/{first}/confirm", headers=auth(owner)).status_code == 200
    assert _ids(client)[:2] == [second, first]  # reconfirming is not a way to the top


# --- URL state -----------------------------------------------------------------------------


def test_the_applied_query_is_canonical_and_round_trips(client, owner):
    _listing(client, owner)
    params = [("space_type", "WHOLE_PROPERTY"), ("category", "HOUSE"), ("category", "APARTMENT"),
              ("max_rent", "250000"), ("sort", "newest"), ("available_by", "2027-01-01")]
    page = client.get("/v1/classifieds", params=params).json()
    assert page["query"] == ("available_by=2027-01-01&category=APARTMENT&category=HOUSE"
                             "&max_rent=250000&space_type=WHOLE_PROPERTY")
    again = client.get("/v1/classifieds", params=parse_qsl(page["query"])).json()
    assert again["query"] == page["query"] and again["total"] == page["total"]
    assert _map(client, **dict(params[:1]))["query"] == "space_type=WHOLE_PROPERTY"


def test_zero_results_is_an_answer_with_its_query(client, owner):
    _listing(client, owner)
    page = client.get("/v1/classifieds", params={"max_rent": 1}).json()
    assert page["total"] == 0 and page["items"] == [] and page["query"] == "max_rent=1"


# --- list and map are one universe ----------------------------------------------------------


def test_map_is_the_same_universe_as_the_list(client, owner):
    pointed = [_listing(client, owner, prop={"latitude": 51.25 + i / 100, "longitude": 22.57})
               for i in range(3)]
    unplaced = _listing(client, owner)  # no coordinates: no public point
    district = _listing(client, owner, prop={"latitude": 51.3, "longitude": 22.6},
                        offer={"public_location_precision": "DISTRICT"})
    dear = _listing(client, owner, prop={"latitude": 51.4, "longitude": 22.7},
                    offer={"rent_amount": 350000})
    house = _listing(client, owner, prop={"category": "HOUSE", "latitude": 51.5,
                                          "longitude": 22.8})
    cases = [({}, set(pointed) | {dear, house}, 2),
             ({"max_rent": 200000}, set(pointed) | {house}, 2),
             ({"category": "APARTMENT", "sort": "price_asc"}, set(pointed) | {dear}, 2),
             ({"min_rent": 300000}, {dear}, 0)]
    for params, expected_points, without in cases:
        listed = set(_ids(client, limit=100, **params))
        mapped = _map(client, **params)
        assert {p["id"] for p in mapped["points"]} == expected_points, params
        assert mapped["total"] == len(listed) == len(expected_points) + without, params
        assert expected_points <= listed and mapped["without_point"] == without, params
        assert mapped["truncated"] is False
    assert {unplaced, district} <= set(_ids(client, limit=100))


def test_the_map_is_a_light_projection_without_private_data(client, owner):
    _listing(client, owner, prop={"latitude": 51.248811, "longitude": 22.568821,
                                  "thoroughfare": "ul. Prywatna", "building_number": "77",
                                  "unit_number": "5", "postcode": "20-001"},
             offer={"contact_mode": "phone", "contact_phone": "+48 700 800 900"})
    body = client.get("/v1/classifieds/map").text
    for private in ("51.248811", "22.568821", "Prywatna", "20-001", "700 800", "owner_id",
                    "address", "unit_number"):
        assert private not in body
    (point,) = _map(client)["points"]
    assert set(point) == {"id", "latitude", "longitude", "precision", "rent_amount",
                          "monthly_total_estimate", "currency", "space_type", "category",
                          "freshness"}


def test_the_map_cap_truncates_in_query_order(client, owner):
    pointed = [_listing(client, owner, prop={"latitude": 51.2, "longitude": 22.5},
                        offer={"rent_amount": 100000 + i}) for i in range(4)]
    mapped = _map(client, limit=2, sort="price_asc")
    assert [p["id"] for p in mapped["points"]] == pointed[:2]
    assert mapped["truncated"] is True and mapped["with_point"] == 4


def test_search_metrics_record_filter_names_not_values(client, owner):
    before = search.FILTER_USE.labels(filter="max_rent")._value.get()
    client.get("/v1/classifieds", params={"max_rent": 123456})
    assert search.FILTER_USE.labels(filter="max_rent")._value.get() == before + 1
    q = search.SearchQuery(max_rent=123456, available_by=date(2027, 1, 1))
    assert q.used_filters() == ["available_by", "max_rent"]
