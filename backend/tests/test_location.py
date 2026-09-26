"""The flat's own position stays private (Domain Schema v1 §80, §106, §115).

A public listing says where, as far as the public may know: city, district and
a map point at the precision the owner chose. It never carries the street
address, and never the flat's own coordinates — there is no EXACT and no owner
opt-in (D-58, TASK-010R). The tests plant distinctive coordinates and then look for them in every
public response — the way a leak would actually be found.
"""

from decimal import Decimal

import pytest

from app.modules.properties import location
from tests.conftest import auth, register_and_login, verify_ownership

# Distinctive, so a leak is findable by searching the response text.
EXACT_LAT = 52.229676
EXACT_LON = 21.012229
ADDRESS = "ul. Tajna 17/4"

PROPERTY = {
    "property_type": "apartment",
    "city": "Warszawa",
    "district": "Śródmieście",
    "municipality": "Warszawa",
    "address": ADDRESS,
    "latitude": EXACT_LAT,
    "longitude": EXACT_LON,
    "area_m2": 50,
    "rooms": 2,
    "capacity": 3,
}

OFFER = {
    "title": "Mieszkanie w centrum",
    "rent_amount": 320000,
    "min_term_months": 12,
    "contact_mode": "message",
}


@pytest.fixture
def owner(client):
    return register_and_login(client, "location-owner@example.com", "host")


def _listed(client, token, precision=None, **property_overrides):
    prop = client.post(
        "/v1/properties", json={**PROPERTY, **property_overrides}, headers=auth(token)
    )
    assert prop.status_code == 201, prop.text
    verify_ownership(client, token, prop.json()["id"])
    body = dict(OFFER)
    if precision is not None:
        body["public_location_precision"] = precision
    offer = client.post(
        f"/v1/properties/{prop.json()['id']}/classifieds", json=body, headers=auth(token)
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]
    assert client.post(
        f"/v1/classifieds/{offer_id}/publish", headers=auth(token)
    ).status_code == 200
    return offer_id


def _all_public_text(client, offer_id) -> str:
    return "\n".join([
        client.get(f"/v1/classifieds/{offer_id}").text,
        client.get("/v1/classifieds").text,
        client.get("/v1/classifieds", params={"city": "Warszawa"}).text,
    ])


# --- what the public never sees -----------------------------------------------


def test_the_street_address_is_never_public(client, owner):
    offer_id = _listed(client, owner)
    text = _all_public_text(client, offer_id)
    assert ADDRESS not in text
    assert "Tajna" not in text


def test_the_exact_coordinates_are_never_public_by_default(client, owner):
    offer_id = _listed(client, owner)
    text = _all_public_text(client, offer_id)
    assert "52.229676" not in text
    assert "21.012229" not in text


def test_district_precision_shows_no_point_at_all(client, owner):
    offer_id = _listed(client, owner, precision="DISTRICT")
    public = client.get(f"/v1/classifieds/{offer_id}").json()
    assert public["public_location"] is None
    assert public["district"] == "Śródmieście"
    assert "52.2" not in _all_public_text(client, offer_id)


def test_exact_cannot_be_chosen_there_is_no_owner_opt_in(client, owner):
    """D-58: public exact residential coordinates are prohibited."""
    prop = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()
    verify_ownership(client, owner, prop["id"])
    refused = client.post(f"/v1/properties/{prop['id']}/classifieds",
                          json={**OFFER, "public_location_precision": "EXACT"},
                          headers=auth(owner))
    assert refused.status_code == 422, refused.text


def test_an_unknown_precision_fails_safe_to_the_grid():
    """A stale or unexpected stored value must never mean "exact"."""
    assert location.public_point(EXACT_LAT, EXACT_LON, "EXACT") == location.public_point(
        EXACT_LAT, EXACT_LON, "APPROXIMATE")
    assert location.PRECISIONS == ("APPROXIMATE", "DISTRICT")


def test_the_owner_still_sees_their_own_coordinates(client, owner):
    """Private is not lost: the owner-facing property carries them."""
    _listed(client, owner)
    mine = client.get("/v1/properties", headers=auth(owner)).json()[0]
    assert float(mine["latitude"]) == EXACT_LAT


# --- the approximate point ----------------------------------------------------


def test_the_approximate_point_is_not_the_flat(client, owner):
    offer_id = _listed(client, owner)
    point = client.get(f"/v1/classifieds/{offer_id}").json()["public_location"]
    assert point["precision"] == "APPROXIMATE"
    assert (point["latitude"], point["longitude"]) != (EXACT_LAT, EXACT_LON)


def test_the_approximate_point_stays_within_its_grid_cell(client, owner):
    """Close enough to be useful on a map: within half a cell of the flat."""
    offer_id = _listed(client, owner)
    point = client.get(f"/v1/classifieds/{offer_id}").json()["public_location"]
    assert abs(point["latitude"] - EXACT_LAT) <= float(location.GRID_LAT) / 2
    assert abs(point["longitude"] - EXACT_LON) <= float(location.GRID_LON) / 2


def test_republishing_gives_the_same_point(client, owner):
    """A fresh random offset on each publish could be averaged back to the
    flat. A grid cell is the same answer every time — nothing to average."""
    offer_id = _listed(client, owner)
    first = client.get(f"/v1/classifieds/{offer_id}").json()["public_location"]
    client.post(f"/v1/classifieds/{offer_id}/pause", headers=auth(owner))
    client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(owner))
    again = client.get(f"/v1/classifieds/{offer_id}").json()["public_location"]
    assert first == again


def test_two_flats_in_one_cell_share_a_point(client, owner):
    """Which is what makes the point anonymous rather than merely shifted."""
    a = _listed(client, owner, address="ul. A 1", latitude=52.2301, longitude=21.0121)
    b = _listed(client, owner, address="ul. B 2", latitude=52.2309, longitude=21.0149)
    pa = client.get(f"/v1/classifieds/{a}").json()["public_location"]
    pb = client.get(f"/v1/classifieds/{b}").json()["public_location"]
    assert pa == pb


def test_a_flat_without_coordinates_has_no_point(client, owner):
    offer_id = _listed(client, owner, latitude=None, longitude=None)
    assert client.get(f"/v1/classifieds/{offer_id}").json()["public_location"] is None


@pytest.mark.parametrize(
    ("value", "step"),
    [(Decimal("52.229676"), location.GRID_LAT), (Decimal("-33.868820"), location.GRID_LAT),
     (Decimal("21.012229"), location.GRID_LON), (Decimal("-0.000001"), location.GRID_LON)],
)
def test_the_cell_centre_contains_the_value(value, step):
    """Including negative coordinates, where naive truncation rounds toward
    zero and puts the point in the neighbouring cell."""
    centre = location._cell_centre(value, step)
    assert centre - step / 2 <= value < centre + step / 2


def test_an_unknown_precision_is_refused(client, owner):
    prop = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    resp = client.post(
        f"/v1/properties/{prop}/classifieds",
        json={**OFFER, "public_location_precision": "STREET"},
        headers=auth(owner),
    )
    assert resp.status_code == 422


# --- the public shape ---------------------------------------------------------


def test_the_listing_says_which_city_and_district(client, owner):
    public = client.get(f"/v1/classifieds/{_listed(client, owner)}").json()
    assert (public["city"], public["district"]) == ("Warszawa", "Śródmieście")


@pytest.mark.parametrize(
    "params",
    [{"bbox": "21,52,21"}, {"bbox": "a,b,c,d"}, {"bbox": "22,52,21,53"},
     {"near_lat": 52.2}, {"near_lat": 52.2, "near_lon": 21.0}],
)
def test_malformed_map_searches_fail_loudly(client, params):
    assert client.get("/v1/classifieds", params=params).status_code == 422


def test_the_radius_is_capped(client):
    """An unbounded radius is a full-table scan wearing a filter's clothes."""
    resp = client.get(
        "/v1/classifieds", params={"near_lat": 52.2, "near_lon": 21.0, "radius_m": 500_000}
    )
    assert resp.status_code == 422
