"""Spaces: listings point at the whole flat or a room in it (Schema v1 §28, §42).

The failures this guards against are the ones a flat-per-listing model makes
easy: a room advertised as if it were the flat, a room from one flat attached
to another flat's listing, a room that was taken off the market still on the
board, and a size filter that answers with the building's area when the
tenant asked about the room.
"""

import pytest
from sqlalchemy import select

from app.modules.properties.models import Space
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership

PROPERTY = {
    "property_type": "apartment",
    "city": "Wrocław",
    "municipality": "Wrocław",
    "address": "ul. Pokojowa 1",
    "area_m2": 60,
    "rooms": 3,
    "capacity": 4,
}

OFFER = {
    "title": "Oferta długoterminowa",
    "rent_amount": 180000,
    "min_term_months": 12,
    "contact_mode": "message",
}


@pytest.fixture
def owner(client):
    return register_and_login(client, "spaces-owner@example.com", "host")


def _property(client, token, address="ul. Pokojowa 1", **overrides):
    resp = client.post(
        "/v1/properties",
        json={**PROPERTY, "address": address, **overrides},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    verify_ownership(client, token, resp.json()["id"])
    return resp.json()["id"]


def _room(client, token, property_id, label, area=None):
    body = {"label": label}
    if area is not None:
        body["area_m2"] = area
    return client.post(f"/v1/properties/{property_id}/spaces", json=body, headers=auth(token))


def _offer(client, token, property_id, space_id=None, **overrides):
    body = {**OFFER, **overrides}
    if space_id is not None:
        body["space_id"] = space_id
    return client.post(
        f"/v1/properties/{property_id}/classifieds", json=body, headers=auth(token)
    )


def _publish(client, token, offer_id):
    return client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(token))


def _live(client, token, property_id, space_id=None, **overrides):
    offer = _offer(client, token, property_id, space_id, **overrides)
    assert offer.status_code == 201, offer.text
    assert _publish(client, token, offer.json()["id"]).status_code == 200
    return offer.json()["id"]


# --- every property starts with the whole flat --------------------------------


def test_registering_a_property_creates_its_whole_space(client, owner):
    property_id = _property(client, owner)

    spaces = client.get(f"/v1/properties/{property_id}/spaces", headers=auth(owner)).json()
    assert [s["space_type"] for s in spaces] == ["WHOLE_PROPERTY"]
    assert spaces[0]["label"] is None


def test_a_listing_without_a_space_is_for_the_whole_flat(client, owner):
    property_id = _property(client, owner)
    offer_id = _live(client, owner, property_id)

    public = client.get(f"/v1/classifieds/{offer_id}").json()
    assert public["space_type"] == "WHOLE_PROPERTY"
    assert public["space_label"] is None


def test_the_database_allows_only_one_active_whole_space(client, owner):
    """Two would let the same flat be let twice, as a whole, through two
    listings. Enforced by a partial unique index, so a bug cannot bypass it."""
    property_id = _property(client, owner)
    with TestingSession() as db:
        db.add(Space(property_id=property_id, space_type="WHOLE_PROPERTY", status="ACTIVE"))
        with pytest.raises(Exception):  # noqa: B017 — unique violation, driver-specific type
            db.commit()


# --- rooms --------------------------------------------------------------------


def test_a_room_can_be_listed_on_its_own(client, owner):
    property_id = _property(client, owner)
    room = _room(client, owner, property_id, "Pokój 2", 14.5)
    assert room.status_code == 201, room.text
    assert room.json()["space_type"] == "ROOM"
    assert room.json()["area_m2"] == 14.5

    offer_id = _live(client, owner, property_id, room.json()["id"])
    public = client.get(f"/v1/classifieds/{offer_id}").json()
    assert public["space_type"] == "ROOM"
    assert public["space_label"] == "Pokój 2"


def test_room_labels_are_unique_among_active_rooms(client, owner):
    property_id = _property(client, owner)
    assert _room(client, owner, property_id, "Pokój 1").status_code == 201
    assert _room(client, owner, property_id, "Pokój 1").status_code == 409


def test_an_archived_room_frees_its_label(client, owner):
    """Uniqueness is among active rooms: a room taken off and re-created after
    a renovation must be able to keep its name."""
    property_id = _property(client, owner)
    first = _room(client, owner, property_id, "Pokój 1").json()["id"]
    client.post(f"/v1/spaces/{first}/archive", headers=auth(owner))

    assert _room(client, owner, property_id, "Pokój 1").status_code == 201


def test_the_same_label_is_fine_in_another_flat(client, owner):
    first = _property(client, owner, "ul. Jedna 1")
    second = _property(client, owner, "ul. Druga 2")
    assert _room(client, owner, first, "Pokój 1").status_code == 201
    assert _room(client, owner, second, "Pokój 1").status_code == 201


def test_a_room_from_another_flat_cannot_be_listed_here(client, owner):
    """Otherwise a listing is published under one address for a room that is
    physically somewhere else."""
    here = _property(client, owner, "ul. Tutaj 1")
    there = _property(client, owner, "ul. Tam 2")
    foreign_room = _room(client, owner, there, "Pokój 1").json()["id"]

    assert _offer(client, owner, here, foreign_room).status_code == 404


def test_an_unknown_space_is_not_found(client, owner):
    property_id = _property(client, owner)
    assert _offer(client, owner, property_id, "no-such-space").status_code == 404


def test_a_property_can_no_longer_be_a_room(client, owner):
    """Schema v1 §135. The error says where rooms went, so the client is not
    left guessing."""
    resp = client.post(
        "/v1/properties", json={**PROPERTY, "property_type": "room"}, headers=auth(owner)
    )
    assert resp.status_code == 422
    assert "spaces" in resp.text


def test_a_room_carries_no_label_it_did_not_need_and_the_flat_carries_none(client, owner):
    property_id = _property(client, owner)
    with TestingSession() as db:
        db.add(
            Space(property_id=property_id, space_type="WHOLE_PROPERTY", status="ARCHIVED",
                  label="should not be here")
        )
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation
            db.commit()


# --- archiving ----------------------------------------------------------------


def test_an_archived_space_takes_no_new_listing(client, owner):
    property_id = _property(client, owner)
    room = _room(client, owner, property_id, "Pokój 3").json()["id"]
    client.post(f"/v1/spaces/{room}/archive", headers=auth(owner))

    assert _offer(client, owner, property_id, room).status_code == 409


def test_archiving_takes_down_what_was_live_on_it(client, owner):
    """A room that is no longer available must not stay on the board."""
    property_id = _property(client, owner)
    room = _room(client, owner, property_id, "Pokój 4").json()["id"]
    on_room = _live(client, owner, property_id, room)
    on_flat = _live(client, owner, property_id)

    resp = client.post(f"/v1/spaces/{room}/archive", headers=auth(owner))
    assert resp.status_code == 200, resp.text
    assert resp.json()["paused_offers"] == [on_room]

    board = client.get("/v1/classifieds").text
    assert on_room not in board
    assert on_flat in board, "archiving a room must not touch the flat's own listing"


def test_a_draft_on_a_later_archived_space_cannot_be_published(client, owner):
    property_id = _property(client, owner)
    room = _room(client, owner, property_id, "Pokój 5").json()["id"]
    draft = _offer(client, owner, property_id, room).json()["id"]
    client.post(f"/v1/spaces/{room}/archive", headers=auth(owner))

    resp = _publish(client, owner, draft)
    assert resp.status_code == 409
    assert "archived" in resp.text.lower()


# --- strangers ----------------------------------------------------------------


def test_a_stranger_cannot_add_or_archive_spaces(client, owner):
    property_id = _property(client, owner)
    room = _room(client, owner, property_id, "Pokój 6").json()["id"]
    stranger = register_and_login(client, "space-stranger@example.com", "host")

    assert _room(client, stranger, property_id, "Mój").status_code == 404
    assert client.post(f"/v1/spaces/{room}/archive", headers=auth(stranger)).status_code == 404
    assert client.get(
        f"/v1/properties/{property_id}/spaces", headers=auth(stranger)
    ).status_code == 404


# --- search answers about what is on offer ------------------------------------


def test_the_size_filter_uses_the_rooms_area_not_the_flats(client, owner):
    """A 12 m2 room in a 60 m2 flat is not an answer to "at least 20 m2"."""
    property_id = _property(client, owner)
    small = _room(client, owner, property_id, "Mały", 12).json()["id"]
    big = _room(client, owner, property_id, "Duży", 24).json()["id"]
    small_offer = _live(client, owner, property_id, small)
    big_offer = _live(client, owner, property_id, big)

    found = [o["id"] for o in client.get("/v1/classifieds", params={"min_area_m2": 20}).json()["items"]]
    assert big_offer in found
    assert small_offer not in found


def test_a_room_of_unknown_size_matches_no_minimum(client, owner):
    property_id = _property(client, owner)
    unsized = _room(client, owner, property_id, "Bez metrażu").json()["id"]
    offer_id = _live(client, owner, property_id, unsized)

    found = client.get("/v1/classifieds", params={"min_area_m2": 1}).json()["items"]
    assert offer_id not in [o["id"] for o in found]


def test_search_can_ask_for_rooms_or_whole_flats(client, owner):
    property_id = _property(client, owner)
    room = _room(client, owner, property_id, "Pokój 7", 15).json()["id"]
    room_offer = _live(client, owner, property_id, room)
    flat_offer = _live(client, owner, property_id)

    rooms = [o["id"] for o in client.get("/v1/classifieds", params={"space_type": "ROOM"}).json()["items"]]
    flats = [
        o["id"]
        for o in client.get("/v1/classifieds", params={"space_type": "WHOLE_PROPERTY"}).json()["items"]
    ]
    assert rooms == [room_offer]
    assert flats == [flat_offer]


def test_an_unknown_space_type_filter_fails_loudly(client, owner):
    resp = client.get("/v1/classifieds", params={"space_type": "COUCH"})
    assert resp.status_code == 422


def test_sorting_by_size_uses_the_listed_area(client, owner):
    property_id = _property(client, owner)
    room = _room(client, owner, property_id, "Pokój 8", 10).json()["id"]
    room_offer = _live(client, owner, property_id, room)
    other = _property(client, owner, "ul. Mała 3", area_m2=30)
    flat_offer = _live(client, owner, other)

    order = [o["id"] for o in client.get("/v1/classifieds", params={"sort": "size_desc"}).json()["items"]]
    # 30 m2 flat before the 10 m2 room, although the room's building is 60 m2.
    assert order.index(flat_offer) < order.index(room_offer)


def test_space_writes_are_throttled_as_writes(client):
    from app.core import ratelimit as rl

    assert rl.resolve_policy("POST", "/v1/properties/abc/spaces") is rl.PROPERTY_WRITE
    assert rl.resolve_policy("POST", "/v1/spaces/abc/archive") is rl.PROPERTY_WRITE


def test_the_space_row_matches_the_offer(client, owner):
    property_id = _property(client, owner)
    offer_id = _offer(client, owner, property_id).json()["id"]
    from app.modules.properties.models import ClassifiedOffer

    with TestingSession() as db:
        offer = db.get(ClassifiedOffer, offer_id)
        space = db.scalar(select(Space).where(Space.id == offer.space_id))
    assert space.property_id == property_id
