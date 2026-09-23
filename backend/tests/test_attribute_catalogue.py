"""The attribute catalogue: what makes the free-form JSONB tail safe to use.

The failure this closes is quiet, not loud. `{"washing_machne": true}` used to
be stored happily; the owner believed the flat had a washing machine, every
search disagreed, and nothing anywhere raised. A typo in an amenity code is not
a crash — it is a listing that silently stops matching the filters that would
have rented it.
"""

import pytest

from tests.conftest import auth, register_and_login, verify_ownership

PROPERTY = {
    "property_type": "apartment",
    "city": "Warszawa",
    "municipality": "Warszawa",
    "address": "ul. Atrybutowa 1",
    "area_m2": 50,
    "rooms": 2,
    "capacity": 4,
}

OFFER = {"title": "Do wynajęcia", "rent_amount": 300000, "min_term_months": 12}


@pytest.fixture
def owner(client):
    return register_and_login(client, "attr-owner@example.com", "host")


def _property(client, token, attributes, address="ul. Atrybutowa 1"):
    return client.post(
        "/v1/properties",
        json={**PROPERTY, "address": address, "attributes": attributes},
        headers=auth(token),
    )


def _publish(client, token, attributes, address):
    prop = _property(client, token, attributes, address)
    assert prop.status_code == 201, prop.text
    verify_ownership(client, token, prop.json()["id"])
    offer = client.post(
        f"/v1/properties/{prop.json()['id']}/classifieds",
        json=OFFER,
        headers=auth(token),
    )
    offer_id = offer.json()["id"]
    client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(token))
    return offer_id


# --- the catalogue exists and is public ---------------------------------------


def test_the_catalogue_is_published(client):
    """Every surface builds its filters from this one definition."""
    resp = client.get("/v1/attributes")
    assert resp.status_code == 200
    codes = {a["code"] for a in resp.json()}
    assert {"wifi", "dishwasher", "washing_machine", "balcony"} <= codes


def test_every_definition_carries_both_languages(client):
    """A filter panel with half its labels missing is a filter panel nobody
    can use in one of the two languages the product ships in."""
    for definition in client.get("/v1/attributes").json():
        assert definition["label_pl"], definition["code"]
        assert definition["label_en"], definition["code"]


def test_types_are_from_the_known_set(client):
    from app.modules.properties.models import ATTRIBUTE_TYPES

    for definition in client.get("/v1/attributes").json():
        assert definition["value_type"] in ATTRIBUTE_TYPES, definition


def test_enums_declare_their_allowed_values(client):
    """An enum with no values is a free-text field wearing a label."""
    for definition in client.get("/v1/attributes").json():
        if definition["value_type"] == "enum":
            assert definition["allowed_values"], definition["code"]


def test_codes_are_mapped_to_the_external_vocabulary(client):
    """Recording the mapping now costs nothing; discovering later that all of
    them need translating costs a layer."""
    from tests.conftest import TestingSession

    from app.modules.properties.models import AttributeDefinition

    with TestingSession() as db:
        mapped = [
            a for a in db.query(AttributeDefinition).all() if a.external_code
        ]
    assert len(mapped) >= 15, "the amenity vocabulary is barely mapped"


# --- writes are validated against it ------------------------------------------


def test_a_typo_is_rejected_rather_than_stored(client, owner):
    """The whole point. Stored silently, this would match no filter for ever."""
    resp = _property(client, owner, {"washing_machne": True})
    assert resp.status_code == 422, resp.text
    assert "washing_machne" in resp.text


def test_a_known_code_is_accepted(client, owner):
    assert _property(client, owner, {"washing_machine": True}).status_code == 201


def test_a_boolean_attribute_rejects_a_number(client, owner):
    resp = _property(client, owner, {"dishwasher": 1})
    assert resp.status_code == 422
    assert "true or false" in resp.text


def test_a_numeric_attribute_rejects_a_boolean(client, owner):
    """`"wifi_mbps": true` is a mistake that reads as plausible."""
    resp = _property(client, owner, {"wifi_mbps": True})
    assert resp.status_code == 422
    assert "whole number" in resp.text


def test_a_numeric_attribute_rejects_a_negative(client, owner):
    assert _property(client, owner, {"wifi_mbps": -5}).status_code == 422


def test_an_enum_rejects_a_value_outside_its_set(client, owner):
    resp = _property(client, owner, {"window_view": "volcano"})
    assert resp.status_code == 422
    assert "must be one of" in resp.text


def test_an_enum_accepts_a_declared_value(client, owner):
    assert _property(client, owner, {"window_view": "park"}).status_code == 201


def test_every_problem_is_reported_not_just_the_first(client, owner):
    """Fixing one typo only to be told about the next is a bad way to spend an
    afternoon."""
    resp = _property(client, owner, {"washing_machne": True, "dishwashr": True})
    assert resp.status_code == 422
    assert "washing_machne" in resp.text and "dishwashr" in resp.text


def test_empty_attributes_are_fine(client, owner):
    assert _property(client, owner, {}).status_code == 201


# --- filtering by amenity -----------------------------------------------------


def test_the_board_filters_on_amenities(client, owner):
    with_dishwasher = _publish(client, owner, {"dishwasher": True}, "ul. Ze zmywarka 2")
    without = _publish(client, owner, {"dishwasher": False}, "ul. Bez zmywarki 3")
    unspecified = _publish(client, owner, {}, "ul. Nieokreslona 4")

    found = client.get("/v1/classifieds", params={"has": "dishwasher"}).json()
    ids = [o["id"] for o in found["items"]]
    assert with_dishwasher in ids
    assert without not in ids, "an explicit false must not match"
    assert unspecified not in ids, "a missing attribute is not a yes"


def test_several_amenities_narrow_rather_than_widen(client, owner):
    both = _publish(client, owner, {"dishwasher": True, "balcony": True}, "ul. Oba 5")
    only_one = _publish(client, owner, {"dishwasher": True}, "ul. Jeden 6")

    resp = client.get(
        "/v1/classifieds", params=[("has", "dishwasher"), ("has", "balcony")]
    ).json()
    ids = [o["id"] for o in resp["items"]]
    assert both in ids
    assert only_one not in ids


def test_an_unknown_filter_code_fails_loudly(client, owner):
    """Silently matching nothing would look like "no flats have dishwashers"."""
    _publish(client, owner, {"dishwasher": True}, "ul. Glosno 7")

    resp = client.get("/v1/classifieds", params={"has": "dishwashr"})
    assert resp.status_code == 422, resp.text
    assert "not a filterable attribute" in resp.text


def test_amenity_filters_combine_with_the_budget(client, owner):
    wanted = _publish(client, owner, {"dishwasher": True}, "ul. Tania 8")
    pricey_prop = _property(client, owner, {"dishwasher": True}, "ul. Droga 9")
    verify_ownership(client, owner, pricey_prop.json()["id"])
    offer = client.post(
        f"/v1/properties/{pricey_prop.json()['id']}/classifieds",
        json={**OFFER, "rent_amount": 900000},
        headers=auth(owner),
    ).json()["id"]
    client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))

    found = client.get(
        "/v1/classifieds", params={"has": "dishwasher", "max_monthly_total": 400000}
    ).json()
    ids = [o["id"] for o in found["items"]]
    assert ids == [wanted]
