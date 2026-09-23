"""The free long-term board: Property/Offer split, term floor, phone protection.

The security-relevant assertions here are the phone ones. A leak on this board
is not a bug that annoys someone — it is somebody's personal number handed to a
scraper, and the whole reason owners would trust the platform with it.
"""

from datetime import date

import pytest

from app.modules.properties.models import MIN_CLASSIFIED_TERM_MONTHS
from tests.conftest import auth, register_and_login, verify_phone

PROPERTY = {
    "property_type": "apartment",
    "city": "Warszawa",
    "district": "Mokotów",
    "postcode": "02-676",
    "municipality": "Warszawa",
    "address": "ul. Testowa 5/3",
    "area_m2": 52,
    "rooms": 3,
    "bedrooms": 2,
    "bathrooms": 1,
    "capacity": 4,
    "furnished": "full",
    "parking": "spot",
    "attributes": {"washing_machine": True, "wifi_mbps": 300},
}

OFFER = {
    "title": "M3 Mokotów, długoterminowo",
    "description": "Cicha okolica, blisko metra.",
    "rent_amount": 350000,
    "admin_fee": 60000,
    "utilities_amount": 40000,
    "utilities_included": False,
    "parking_fee": 20000,
    "deposit_amount": 350000,
    "min_term_months": 12,
    "contact_phone": "+48 500 111 222",
    "contact_mode": "phone",
}

PHONE = OFFER["contact_phone"]


def _owner(client, email="owner@example.com"):
    return register_and_login(client, email, "host")


def _property(client, token, **overrides):
    resp = client.post("/v1/properties", json={**PROPERTY, **overrides}, headers=auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _classified(client, token, property_id, **overrides):
    return client.post(
        f"/v1/properties/{property_id}/classifieds",
        json={**OFFER, **overrides},
        headers=auth(token),
    )


def _published(client, token, **overrides):
    property_id = _property(client, token)
    offer = _classified(client, token, property_id, **overrides).json()
    client.post(f"/v1/classifieds/{offer['id']}/publish", headers=auth(token))
    return offer["id"]


# --- the Property/Offer split -------------------------------------------------


def test_a_classified_hangs_off_a_property(client):
    """Not a free-floating listing: the flat exists as an object in its own right.

    A standalone classified means the same flat can never also carry a paid
    offer, which is exactly what the split exists to prevent.
    """
    token = _owner(client)
    property_id = _property(client, token)

    resp = _classified(client, token, property_id)
    assert resp.status_code == 201, resp.text
    assert resp.json()["property_id"] == property_id


def test_one_property_can_carry_several_offers(client):
    token = _owner(client)
    property_id = _property(client, token)

    first = _classified(client, token, property_id, title="Wariant A")
    second = _classified(client, token, property_id, title="Wariant B")
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["property_id"] == second.json()["property_id"] == property_id


def test_municipality_is_required(client):
    """Without the gmina the tourist tax cannot be computed for paid modes."""
    token = _owner(client)
    body = {k: v for k, v in PROPERTY.items() if k != "municipality"}
    assert client.post("/v1/properties", json=body, headers=auth(token)).status_code == 422


def test_property_type_must_be_known(client):
    token = _owner(client)
    resp = client.post(
        "/v1/properties", json={**PROPERTY, "property_type": "castle"}, headers=auth(token)
    )
    assert resp.status_code == 422


def test_attributes_survive_the_round_trip(client):
    """The long tail is stored as-is so a new amenity needs no migration."""
    token = _owner(client)
    property_id = _property(client, token, attributes={"sauna": True, "wifi_mbps": 1000})

    mine = client.get("/v1/properties", headers=auth(token)).json()
    stored = next(p for p in mine if p["id"] == property_id)
    assert stored["attributes"] == {"sauna": True, "wifi_mbps": 1000}


# --- the board is long-term only ----------------------------------------------


@pytest.mark.parametrize("months", [MIN_CLASSIFIED_TERM_MONTHS, 12, 24])
def test_terms_from_six_months_are_accepted(client, months):
    token = _owner(client, f"owner{months}@example.com")
    property_id = _property(client, token)
    assert _classified(client, token, property_id, min_term_months=months).status_code == 201


@pytest.mark.parametrize("months", [1, 3, 5])
def test_shorter_terms_belong_to_the_paid_modes(client, months):
    """A 3-month let is a Homies booking. Letting it in free would be a way to
    dodge the commission by mislabelling the offer."""
    token = _owner(client, f"short{months}@example.com")
    property_id = _property(client, token)

    resp = _classified(client, token, property_id, min_term_months=months)
    assert resp.status_code == 422, resp.text
    assert str(MIN_CLASSIFIED_TERM_MONTHS) in resp.text


def test_open_ended_offers_need_no_term(client):
    token = _owner(client)
    property_id = _property(client, token)
    resp = _classified(client, token, property_id, min_term_months=None, open_ended=True)
    assert resp.status_code == 201
    assert resp.json()["open_ended"] is True


def test_an_offer_cannot_be_both_open_ended_and_fixed(client):
    token = _owner(client)
    property_id = _property(client, token)
    resp = _classified(client, token, property_id, min_term_months=12, open_ended=True)
    assert resp.status_code == 422


def test_monthly_total_is_derived_not_stored(client):
    """Tenants compare offers without doing arithmetic; the deposit is excluded
    because it comes back."""
    token = _owner(client)
    property_id = _property(client, token)
    body = _classified(client, token, property_id).json()

    assert body["monthly_total_estimate"] == 350000 + 60000 + 40000 + 20000


def test_included_utilities_are_not_added_twice(client):
    token = _owner(client)
    property_id = _property(client, token)
    body = _classified(
        client, token, property_id, utilities_included=True, utilities_amount=40000
    ).json()

    assert body["monthly_total_estimate"] == 350000 + 60000 + 20000


# --- phone protection ---------------------------------------------------------


def test_phone_is_absent_from_the_public_listing(client):
    """The public shape has no phone field at all, so a leak needs someone to
    deliberately add one back."""
    token = _owner(client)
    offer_id = _published(client, token)

    board = client.get("/v1/classifieds").text
    detail = client.get(f"/v1/classifieds/{offer_id}").text

    assert PHONE not in board and PHONE not in detail
    assert "500 111 222" not in board and "500 111 222" not in detail
    assert "contact_phone" not in board and "contact_phone" not in detail


def test_anonymous_visitors_cannot_reveal_a_number(client):
    token = _owner(client)
    offer_id = _published(client, token)

    resp = client.post(f"/v1/classifieds/{offer_id}/contact")
    assert resp.status_code == 401, resp.text
    assert PHONE not in resp.text


def test_a_user_without_a_verified_phone_is_refused(client):
    """Sign-in alone is free. The gate is a proven number, because that is what
    costs a bulk collector something per account."""
    owner = _owner(client)
    offer_id = _published(client, owner)
    seeker = register_and_login(client, "unverified@example.com", "guest")

    resp = client.post(f"/v1/classifieds/{offer_id}/contact", headers=auth(seeker))
    assert resp.status_code == 403, resp.text
    assert PHONE not in resp.text


def test_a_verified_user_gets_the_number(client):
    owner = _owner(client)
    offer_id = _published(client, owner)
    seeker = register_and_login(client, "seeker@example.com", "guest")
    verify_phone(client, seeker, "+48500000001")

    resp = client.post(f"/v1/classifieds/{offer_id}/contact", headers=auth(seeker))
    assert resp.status_code == 200, resp.text
    assert resp.json()["contact_phone"] == PHONE


def test_every_disclosure_is_recorded(client):
    """The log is what makes a quota and a scraping signal possible later."""
    from app.modules.properties.models import ContactReveal
    from tests.conftest import TestingSession

    owner = _owner(client)
    offer_id = _published(client, owner)
    seeker = register_and_login(client, "logged@example.com", "guest")
    verify_phone(client, seeker, "+48500000002")

    client.post(f"/v1/classifieds/{offer_id}/contact", headers=auth(seeker))

    with TestingSession() as db:
        from sqlalchemy import select

        reveals = list(db.scalars(select(ContactReveal).where(ContactReveal.offer_id == offer_id)))
    assert len(reveals) == 1
    assert reveals[0].viewer_id is not None


def test_asking_twice_is_one_disclosure(client):
    """A repeat view is not a repeat disclosure — they already have the number.
    Counting it would overstate both the quota and the risk signal."""
    from sqlalchemy import select

    from app.modules.properties.models import ContactReveal
    from tests.conftest import TestingSession

    owner = _owner(client)
    offer_id = _published(client, owner)
    seeker = register_and_login(client, "twice@example.com", "guest")
    verify_phone(client, seeker, "+48500000003")

    for _ in range(3):
        resp = client.post(f"/v1/classifieds/{offer_id}/contact", headers=auth(seeker))
        assert resp.status_code == 200

    with TestingSession() as db:
        rows = list(db.scalars(select(ContactReveal).where(ContactReveal.offer_id == offer_id)))
    assert len(rows) == 1


def test_message_only_owners_never_disclose_a_number(client):
    owner = _owner(client)
    offer_id = _published(client, owner, contact_mode="message", contact_phone="")
    seeker = register_and_login(client, "msg@example.com", "guest")
    verify_phone(client, seeker, "+48500000004")

    resp = client.post(f"/v1/classifieds/{offer_id}/contact", headers=auth(seeker))
    assert resp.status_code == 409
    assert "message" in resp.text.lower()


def test_phone_mode_requires_a_number(client):
    token = _owner(client)
    property_id = _property(client, token)
    resp = _classified(client, token, property_id, contact_mode="phone", contact_phone="")
    assert resp.status_code == 422


# --- visibility and ownership -------------------------------------------------


def test_unpublished_offers_are_not_public(client):
    token = _owner(client)
    property_id = _property(client, token)
    offer_id = _classified(client, token, property_id).json()["id"]

    assert client.get(f"/v1/classifieds/{offer_id}").status_code == 404
    assert offer_id not in client.get("/v1/classifieds").text


def test_a_paused_offer_leaves_the_board(client):
    token = _owner(client)
    offer_id = _published(client, token)
    assert offer_id in client.get("/v1/classifieds").text

    client.post(f"/v1/classifieds/{offer_id}/pause", headers=auth(token))
    assert offer_id not in client.get("/v1/classifieds").text


def test_a_stranger_cannot_post_against_someone_elses_property(client):
    owner = _owner(client, "real-owner@example.com")
    property_id = _property(client, owner)
    intruder = register_and_login(client, "intruder@example.com", "host")

    resp = _classified(client, intruder, property_id)
    # 404, not 403: telling a stranger the property exists is an enumeration oracle.
    assert resp.status_code == 404


def test_a_stranger_cannot_publish_someone_elses_offer(client):
    owner = _owner(client, "owner-pub@example.com")
    property_id = _property(client, owner)
    offer_id = _classified(client, owner, property_id).json()["id"]
    intruder = register_and_login(client, "intruder2@example.com", "host")

    assert client.post(
        f"/v1/classifieds/{offer_id}/publish", headers=auth(intruder)
    ).status_code == 404


def test_the_board_can_be_filtered_by_city(client):
    token = _owner(client, "multi-city@example.com")
    warsaw = _property(client, token, city="Warszawa")
    krakow = _property(client, token, city="Kraków")
    for pid in (warsaw, krakow):
        offer = _classified(client, token, pid).json()
        client.post(f"/v1/classifieds/{offer['id']}/publish", headers=auth(token))

    only_krakow = client.get("/v1/classifieds", params={"city": "Kraków"}).json()
    assert only_krakow["total"] == 1
    assert only_krakow["items"][0]["property_id"] == krakow


# --- rate limiting ------------------------------------------------------------


def test_new_write_paths_are_throttled_not_treated_as_reads(client):
    """A write route that forgets to register a policy silently inherits the
    generous public-read budget. Asserted rather than trusted."""
    from app.core import ratelimit as rl

    assert rl.resolve_policy("POST", "/v1/properties") is rl.PROPERTY_WRITE
    assert rl.resolve_policy("POST", "/v1/properties/abc/classifieds") is rl.PROPERTY_WRITE
    assert rl.resolve_policy("POST", "/v1/classifieds/abc/publish") is rl.PROPERTY_WRITE
    # The endpoint that hands out personal data gets its own, tighter budget.
    assert rl.resolve_policy("POST", "/v1/classifieds/abc/contact") is rl.CONTACT_REVEAL
    assert rl.CONTACT_REVEAL.capacity < rl.PROPERTY_WRITE.capacity


def test_available_from_is_optional_and_preserved(client):
    token = _owner(client)
    property_id = _property(client, token)
    body = _classified(client, token, property_id, available_from=date(2027, 1, 15).isoformat())
    assert body.json()["available_from"] == "2027-01-15"


def test_the_public_listing_carries_no_owner_id(client):
    """A stable account id on every public listing lets anyone join one
    person's whole portfolio together without signing in."""
    token = _owner(client, "portfolio@example.com")
    offer_id = _published(client, token)
    owner_id = client.get("/v1/me", headers=auth(token)).json()["id"]

    board = client.get("/v1/classifieds").text
    detail = client.get(f"/v1/classifieds/{offer_id}").text
    search = client.get("/v1/classifieds", params={"city": "Warszawa"}).text

    for body in (board, detail, search):
        assert owner_id not in body
        assert "owner_id" not in body
