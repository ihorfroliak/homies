"""Search on the free board.

The assertion that matters most is the budget one. A tenant who types "up to
3 000 zł" means what leaves their account each month, not the rent line. Two
offers at the same rent are different prices when one adds building fees, and a
search that hides that difference misleads people on the one number they came
to compare.
"""

from datetime import date

import pytest

from tests.conftest import auth, register_and_login, verify_ownership

BASE_PROPERTY = {
    "property_type": "apartment",
    "city": "Warszawa",
    "district": "Mokotów",
    "municipality": "Warszawa",
    "address": "ul. Testowa 1",
    "area_m2": 50,
    "rooms": 2,
    "capacity": 4,
    "furnished": "full",
    "parking": "none",
}

BASE_OFFER = {
    "title": "Mieszkanie długoterminowo",
    "rent_amount": 300000,
    "min_term_months": 12,
    "contact_mode": "message",
}


@pytest.fixture
def owner(client):
    return register_and_login(client, "search-owner@example.com", "host")


def _publish(client, token, *, property_overrides=None, offer_overrides=None):
    prop = client.post(
        "/v1/properties",
        json={**BASE_PROPERTY, **(property_overrides or {})},
        headers=auth(token),
    )
    assert prop.status_code == 201, prop.text
    verify_ownership(client, token, prop.json()["id"])
    offer = client.post(
        f"/v1/properties/{prop.json()['id']}/classifieds",
        json={**BASE_OFFER, **(offer_overrides or {})},
        headers=auth(token),
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]
    client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(token))
    return offer_id


def _search(client, **params):
    resp = client.get("/v1/classifieds", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- budget is the total, not the rent ----------------------------------------


def test_budget_filters_on_what_the_tenant_actually_pays(client, owner):
    """Both offers charge 3 000 zł rent. Only one of them costs 3 000 zł."""
    cheap = _publish(client, owner, offer_overrides={"rent_amount": 300000})
    expensive = _publish(
        client,
        owner,
        property_overrides={"address": "ul. Droga 2"},
        offer_overrides={"rent_amount": 300000, "admin_fee": 60000},
    )

    found = _search(client, max_monthly_total=300000)
    ids = [o["id"] for o in found["items"]]
    assert cheap in ids
    assert expensive not in ids, "a 3 600 zł flat was shown to a 3 000 zł budget"


def test_included_utilities_lower_the_total(client, owner):
    """Same rent, same utilities figure — but one owner already covers them."""
    included = _publish(
        client,
        owner,
        offer_overrides={"utilities_amount": 50000, "utilities_included": True},
    )
    excluded = _publish(
        client,
        owner,
        property_overrides={"address": "ul. Osobna 3"},
        offer_overrides={"utilities_amount": 50000, "utilities_included": False},
    )

    ids = [o["id"] for o in _search(client, max_monthly_total=300000)["items"]]
    assert included in ids
    assert excluded not in ids


def test_the_deposit_is_not_part_of_the_monthly_budget(client, owner):
    """It comes back, so it is not a monthly cost."""
    offer_id = _publish(client, owner, offer_overrides={"deposit_amount": 900000})
    assert offer_id in [o["id"] for o in _search(client, max_monthly_total=300000)["items"]]


def test_sorting_by_price_uses_the_total_too(client, owner):
    low_rent_high_fees = _publish(
        client, owner, offer_overrides={"rent_amount": 280000, "admin_fee": 90000}
    )
    high_rent_no_fees = _publish(
        client,
        owner,
        property_overrides={"address": "ul. Inna 4"},
        offer_overrides={"rent_amount": 300000},
    )

    order = [o["id"] for o in _search(client, sort="price_asc")["items"]]
    assert order.index(high_rent_no_fees) < order.index(low_rent_high_fees)


# --- structured filters -------------------------------------------------------


def test_filters_narrow_on_the_property_facts(client, owner):
    small = _publish(client, owner, property_overrides={"rooms": 1, "area_m2": 28})
    large = _publish(
        client,
        owner,
        property_overrides={"address": "ul. Duza 5", "rooms": 4, "area_m2": 95},
    )

    found = [o["id"] for o in _search(client, min_rooms=3, min_area_m2=80)["items"]]
    assert found == [large]
    assert small not in found


def test_pets_and_elevator_are_exact_not_merely_truthy(client, owner):
    with_pets = _publish(client, owner, property_overrides={"pets_allowed": True})
    without = _publish(
        client, owner, property_overrides={"address": "ul. Bez 6", "pets_allowed": False}
    )

    assert [o["id"] for o in _search(client, pets_allowed=True)["items"]] == [with_pets]
    assert [o["id"] for o in _search(client, pets_allowed=False)["items"]] == [without]


def test_an_offer_with_no_start_date_counts_as_available_now(client, owner):
    """A missing date means "available now"; filtering it out would hide the
    offers most ready to rent."""
    undated = _publish(client, owner, offer_overrides={"available_from": None})
    later = _publish(
        client,
        owner,
        property_overrides={"address": "ul. Pozniej 7"},
        offer_overrides={"available_from": date(2027, 6, 1).isoformat()},
    )

    ids = [o["id"] for o in _search(client, available_by=date(2027, 1, 1).isoformat())["items"]]
    assert undated in ids
    assert later not in ids


def test_open_ended_offers_satisfy_any_maximum_term(client, owner):
    """Open-ended commits the tenant to nothing, so it fits any "at most N"."""
    open_ended = _publish(
        client, owner, offer_overrides={"min_term_months": None, "open_ended": True}
    )
    long_only = _publish(
        client,
        owner,
        property_overrides={"address": "ul. Dluga 8"},
        offer_overrides={"min_term_months": 24},
    )

    ids = [o["id"] for o in _search(client, max_term_months=12)["items"]]
    assert open_ended in ids
    assert long_only not in ids


def test_filters_combine_rather_than_replace(client, owner):
    wanted = _publish(
        client,
        owner,
        property_overrides={"rooms": 3, "pets_allowed": True},
        offer_overrides={"rent_amount": 250000},
    )
    wrong_rooms = _publish(
        client,
        owner,
        property_overrides={"address": "ul. Malo 9", "rooms": 1, "pets_allowed": True},
        offer_overrides={"rent_amount": 250000},
    )
    too_pricey = _publish(
        client,
        owner,
        property_overrides={"address": "ul. Drogo 10", "rooms": 3, "pets_allowed": True},
        offer_overrides={"rent_amount": 900000},
    )

    found = [
        o["id"]
        for o in _search(client, min_rooms=2, pets_allowed=True, max_monthly_total=300000)["items"]
    ]
    assert found == [wanted]
    assert wrong_rooms not in found and too_pricey not in found


# --- counts, paging, safety ---------------------------------------------------


def test_total_counts_the_whole_result_not_the_page(client, owner):
    """A filter panel that cannot say how many places match forces people to
    paginate just to learn whether a filter did anything."""
    for i in range(5):
        _publish(client, owner, property_overrides={"address": f"ul. Wiele {i}"})

    page = _search(client, limit=2)
    assert len(page["items"]) == 2
    assert page["total"] == 5
    assert page["limit"] == 2 and page["offset"] == 0


def test_paging_walks_the_whole_set_without_repeats(client, owner):
    for i in range(5):
        _publish(client, owner, property_overrides={"address": f"ul. Strona {i}"})

    seen = []
    for offset in (0, 2, 4):
        seen += [o["id"] for o in _search(client, limit=2, offset=offset)["items"]]
    assert len(seen) == 5
    assert len(set(seen)) == 5


def test_sort_is_an_allowlist(client, owner):
    """A column name from the query string would expose every column in the
    table to ordering, and in a string-built query far worse."""
    _publish(client, owner)

    resp = client.get("/v1/classifieds", params={"sort": "contact_phone"})
    assert resp.status_code == 422, resp.text
    assert "sort must be one of" in resp.text


def test_only_active_offers_are_searchable(client, owner):
    published = _publish(client, owner)
    draft_property = client.post(
        "/v1/properties",
        json={**BASE_PROPERTY, "address": "ul. Szkic 11"},
        headers=auth(owner),
    ).json()["id"]
    draft = client.post(
        f"/v1/properties/{draft_property}/classifieds",
        json=BASE_OFFER,
        headers=auth(owner),
    ).json()["id"]

    ids = [o["id"] for o in _search(client)["items"]]
    assert published in ids
    assert draft not in ids


def test_search_results_still_carry_no_phone_number(client, owner):
    """The filter path is a second way out of the database; it must protect the
    number exactly as the plain listing does."""
    _publish(
        client,
        owner,
        offer_overrides={"contact_mode": "phone", "contact_phone": "+48 500 999 888"},
    )

    body = client.get("/v1/classifieds", params={"city": "Warszawa"}).text
    assert "500 999 888" not in body
    assert "contact_phone" not in body
