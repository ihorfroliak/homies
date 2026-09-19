"""Availability belongs to the property, not to one way of offering it.

The scenario this exists for: a flat is listed twice — say a short-stay offer
and a monthly one. While the calendar was keyed on `listing_id`, both listings
had their own calendar, so the same nights could be sold twice and every check
in the system would have passed.

The concurrency case needs real Postgres: SQLite has neither row locks nor the
exclusion constraint, so it cannot model the race at all. It is skipped without
TEST_DATABASE_URL and runs in CI.
"""

import os
from datetime import date, timedelta

import pytest
from app.modules.booking.availability import is_available
from app.modules.booking.models import Booking
from tests.conftest import auth, register_and_login

pytestmark = pytest.mark.usefixtures("client")

NIGHTLY = 30000
CHECK_IN = date.today() + timedelta(days=21)
CHECK_OUT = CHECK_IN + timedelta(days=3)


def _property(client, token, address="ul. Wspólna 7/2"):
    resp = client.post(
        "/v1/properties",
        json={
            "property_type": "apartment",
            "city": "Warszawa",
            "municipality": "Warszawa",
            "address": address,
            "area_m2": 48,
            "rooms": 2,
            "capacity": 4,
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _listing(client, token, property_id, title="Offer"):
    resp = client.post(
        "/v1/listings",
        json={
            "property_id": property_id,
            "title": title,
            "city": "Warszawa",
            "address": "ul. Wspólna 7/2",
            "capacity": 4,
            "nightly_price_amount": NIGHTLY,
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    listing_id = resp.json()["id"]
    client.post(f"/v1/listings/{listing_id}/publish", headers=auth(token))
    return listing_id


def _book(client, token, listing_id, key, check_in=CHECK_IN, check_out=CHECK_OUT):
    return client.post(
        "/v1/bookings",
        json={
            "listing_id": listing_id,
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "guests": 1,
        },
        headers={**auth(token), "Idempotency-Key": f"idem-{key}-0001"},
    )


# --- the defect this change closes --------------------------------------------


def test_two_listings_of_one_flat_cannot_sell_the_same_nights(client):
    """The whole reason the calendar moved.

    Both listings are legitimate — the same flat offered two ways. Booking the
    second must fail on availability, because the flat is already occupied.
    """
    host = register_and_login(client, "host-two@example.com", "host")
    guest = register_and_login(client, "guest-two@example.com", "guest")
    property_id = _property(client, host)
    first = _listing(client, host, property_id, title="Na doby")
    second = _listing(client, host, property_id, title="Na miesiące")

    assert _book(client, guest, first, "one").status_code == 201
    clash = _book(client, guest, second, "two")
    assert clash.status_code == 409, clash.text
    assert "not available" in clash.text.lower()


def test_different_flats_of_one_host_stay_independent(client):
    """The guard must not over-reach: two properties are two calendars."""
    host = register_and_login(client, "host-sep@example.com", "host")
    guest = register_and_login(client, "guest-sep@example.com", "guest")
    flat_a = _listing(client, host, _property(client, host, "ul. A 1"), title="Flat A")
    flat_b = _listing(client, host, _property(client, host, "ul. B 2"), title="Flat B")

    assert _book(client, guest, flat_a, "sep-a").status_code == 201
    assert _book(client, guest, flat_b, "sep-b").status_code == 201


def test_a_host_block_closes_every_offer_of_that_flat(client):
    """A flat closed for renovation is unavailable in every mode it is offered."""
    host = register_and_login(client, "host-block@example.com", "host")
    guest = register_and_login(client, "guest-block@example.com", "guest")
    property_id = _property(client, host)
    first = _listing(client, host, property_id, title="Na doby")
    second = _listing(client, host, property_id, title="Na miesiące")

    blocked = client.post(
        f"/v1/listings/{first}/blocks",
        json={"start_date": CHECK_IN.isoformat(), "end_date": CHECK_OUT.isoformat()},
        headers=auth(host),
    )
    assert blocked.status_code in (200, 201), blocked.text

    clash = _book(client, guest, second, "blocked")
    assert clash.status_code == 409, clash.text


def test_availability_endpoint_reports_the_property_calendar(client):
    """Otherwise it would show a night as free while the flat's other listing
    has it booked — the guest finds out only at checkout."""
    host = register_and_login(client, "host-avail@example.com", "host")
    guest = register_and_login(client, "guest-avail@example.com", "guest")
    property_id = _property(client, host)
    first = _listing(client, host, property_id, title="Na doby")
    second = _listing(client, host, property_id, title="Na miesiące")

    _book(client, guest, first, "avail")

    window = client.get(
        f"/v1/listings/{second}/availability",
        params={"from": CHECK_IN.isoformat(), "to": CHECK_OUT.isoformat()},
    ).json()
    assert all(d["status"] == "booked" for d in window["days"]), window


def test_bookings_carry_the_property_key(client):
    from tests.conftest import TestingSession

    host = register_and_login(client, "host-key@example.com", "host")
    guest = register_and_login(client, "guest-key@example.com", "guest")
    property_id = _property(client, host)
    listing_id = _listing(client, host, property_id)

    booking_id = _book(client, guest, listing_id, "key").json()["id"]
    with TestingSession() as db:
        assert db.get(Booking, booking_id).property_id == property_id


def test_availability_helper_is_keyed_on_the_property(client):
    """Guards the signature itself: passing a listing id must not answer."""
    from tests.conftest import TestingSession

    host = register_and_login(client, "host-helper@example.com", "host")
    guest = register_and_login(client, "guest-helper@example.com", "guest")
    property_id = _property(client, host)
    listing_id = _listing(client, host, property_id)
    _book(client, guest, listing_id, "helper")

    with TestingSession() as db:
        assert is_available(db, property_id, CHECK_IN, CHECK_OUT) is False
        # A listing id is not a property id, so it must find nothing blocked.
        assert is_available(db, listing_id, CHECK_IN, CHECK_OUT) is True


# --- listings still get a property even without one being supplied ------------


def test_a_listing_created_without_a_property_gets_one(client):
    """Transitional shim: existing clients do not send property_id yet."""
    from tests.conftest import TestingSession

    from app.modules.listings.models import Listing

    host = register_and_login(client, "host-shim@example.com", "host")
    resp = client.post(
        "/v1/listings",
        json={
            "title": "No property supplied",
            "city": "Kraków",
            "address": "ul. Stara 3",
            "capacity": 2,
            "nightly_price_amount": 20000,
        },
        headers=auth(host),
    )
    assert resp.status_code == 201, resp.text

    with TestingSession() as db:
        listing = db.get(Listing, resp.json()["id"])
        assert listing.property_id, "every listing must offer a physical object"


def test_a_host_cannot_list_against_someone_elses_property(client):
    owner = register_and_login(client, "real-owner2@example.com", "host")
    property_id = _property(client, owner)
    intruder = register_and_login(client, "intruder3@example.com", "host")

    resp = client.post(
        "/v1/listings",
        json={
            "property_id": property_id,
            "title": "Not mine",
            "city": "Warszawa",
            "address": "ul. Wspólna 7/2",
            "capacity": 2,
            "nightly_price_amount": 20000,
        },
        headers=auth(intruder),
    )
    assert resp.status_code == 404, resp.text


# --- the race, on the real engine ---------------------------------------------


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="needs real Postgres: SQLite has no exclusion constraint",
)
def test_the_database_itself_rejects_a_second_booking_of_the_same_flat(pg_session):
    """The backstop, proven by going around the application check.

    The endpoint already refuses this (see the first test in this file), but an
    application check only holds while every write goes through it. This inserts
    straight into the table, through two different listings of one property, and
    asserts the database refuses on its own.

    Note what this does NOT claim. The row lock in the booking endpoint is not
    what makes the system safe here — the exclusion constraint is. The lock
    serialises the common path so a loser gets a clean "dates are not available"
    instead of a caught constraint violation. Removing either one alone still
    yields one booking; removing both is what breaks it, which is exactly the
    defence-in-depth this is meant to have.
    """
    from sqlalchemy.exc import IntegrityError

    from app.core.security import hash_password
    from app.modules.identity.models import User
    from app.modules.listings.models import Listing
    from app.modules.properties.models import Property

    owner = User(email="db-owner@example.com", password_hash=hash_password("x" * 12), role="host")
    guest = User(email="db-guest@example.com", password_hash=hash_password("x" * 12), role="guest")
    pg_session.add_all([owner, guest])
    pg_session.flush()

    prop = Property(owner_id=owner.id, city="Warszawa", address="ul. Race 1", capacity=2)
    pg_session.add(prop)
    pg_session.flush()

    offers = []
    for title in ("nightly", "monthly"):
        listing = Listing(
            host_id=owner.id,
            property_id=prop.id,
            title=title,
            city="Warszawa",
            address="ul. Race 1",
            capacity=2,
            nightly_price_amount=NIGHTLY,
            currency="PLN",
            status="active",
        )
        pg_session.add(listing)
        offers.append(listing)
    pg_session.flush()

    def booking(listing_id: str, key: str) -> Booking:
        return Booking(
            listing_id=listing_id,
            property_id=prop.id,
            guest_id=guest.id,
            check_in=CHECK_IN,
            check_out=CHECK_OUT,
            guests=1,
            total_amount=3 * NIGHTLY,
            currency="PLN",
            idempotency_key=key,
            status="pending",
        )

    pg_session.add(booking(offers[0].id, "db-race-a"))
    pg_session.commit()

    pg_session.add(booking(offers[1].id, "db-race-b"))
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="needs real Postgres",
)
def test_the_constraint_is_keyed_on_the_property(pg_session):
    """Reads the live constraint rather than trusting the migration ran as written.

    The name is load-bearing: test_td01_migrations and the DR restore check both
    look for `excl_booking_overlap`, so a rename would pass here and break there.
    """
    from sqlalchemy import text

    definition = pg_session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'excl_booking_overlap'"
        )
    ).scalar_one()
    assert "property_id WITH =" in definition, definition
    assert "listing_id" not in definition, definition
