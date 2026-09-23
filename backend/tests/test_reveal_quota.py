"""The ceiling on how much of the board one account can take.

The rate limiter bounds *speed*. At CONTACT_REVEAL's sustained refill one
verified account could still collect thousands of numbers in a day — the whole
board — without ever tripping it. A SIM is bought once; the board leaks
continuously. This quota bounds the *total*, which is the part that matters to
an owner who handed over their personal number.

The tests below are mostly about the ways a quota is usually got wrong: it
resets at midnight, it counts repeat views, it blocks people from re-opening
what they already have, it is enforced in one handler and forgotten in another,
or it is kept in a counter that a restart wipes.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.properties.models import ContactReveal
from tests.conftest import (
    TestingSession,
    auth,
    register_and_login,
    verify_ownership,
    verify_phone,
)

PROPERTY = {
    "property_type": "apartment",
    "city": "Warszawa",
    "municipality": "Warszawa",
    "address": "ul. Limitowa 1",
    "area_m2": 50,
    "rooms": 2,
    "capacity": 4,
}

OFFER = {
    "title": "Mieszkanie długoterminowo",
    "rent_amount": 300000,
    "min_term_months": 12,
    "contact_mode": "phone",
    "contact_phone": "+48 500 111 222",
}


@pytest.fixture
def owner(client):
    return register_and_login(client, "quota-owner@example.com", "host")


@pytest.fixture
def seeker(client):
    token = register_and_login(client, "quota-seeker@example.com", "guest")
    verify_phone(client, token, "+48600000001")
    return token


@pytest.fixture
def small_quota():
    """Three, so a test can cross the line without publishing twenty flats."""
    original = settings.contact_reveal_daily_quota
    settings.contact_reveal_daily_quota = 3
    yield 3
    settings.contact_reveal_daily_quota = original


def _publish(client, token, address):
    prop = client.post(
        "/v1/properties", json={**PROPERTY, "address": address}, headers=auth(token)
    )
    assert prop.status_code == 201, prop.text
    verify_ownership(client, token, prop.json()["id"])
    offer = client.post(
        f"/v1/properties/{prop.json()['id']}/classifieds", json=OFFER, headers=auth(token)
    )
    offer_id = offer.json()["id"]
    client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(token))
    return offer_id


def _board(client, owner_token, count):
    return [_publish(client, owner_token, f"ul. Limitowa {i}") for i in range(count)]


def _reveal(client, token, offer_id):
    return client.post(f"/v1/classifieds/{offer_id}/contact", headers=auth(token))


def _backdate(viewer_email: str, offer_id: str, age: timedelta):
    """Move one reveal into the past. The window is what is being tested, and
    waiting 24 hours is not a test strategy."""
    from app.modules.identity.models import User

    with TestingSession() as db:
        viewer = db.scalar(select(User).where(User.email == viewer_email))
        row = db.scalar(
            select(ContactReveal).where(
                ContactReveal.offer_id == offer_id, ContactReveal.viewer_id == viewer.id
            )
        )
        row.revealed_at = datetime.now(timezone.utc) - age
        db.commit()


# --- the ceiling holds --------------------------------------------------------


def test_reveals_are_allowed_up_to_the_quota(client, owner, seeker, small_quota):
    for offer_id in _board(client, owner, small_quota):
        assert _reveal(client, seeker, offer_id).status_code == 200


def test_the_next_one_is_refused(client, owner, seeker, small_quota):
    offers = _board(client, owner, small_quota + 1)
    for offer_id in offers[:small_quota]:
        assert _reveal(client, seeker, offer_id).status_code == 200

    blocked = _reveal(client, seeker, offers[-1])
    assert blocked.status_code == 429, blocked.text
    assert "500 111 222" not in blocked.text, "the number leaked in the refusal"


def test_the_refusal_says_when_to_come_back(client, owner, seeker, small_quota):
    """A 429 with no Retry-After is indistinguishable from a broken endpoint."""
    offers = _board(client, owner, small_quota + 1)
    for offer_id in offers[:small_quota]:
        _reveal(client, seeker, offer_id)

    blocked = _reveal(client, seeker, offers[-1])
    retry_after = int(blocked.headers["Retry-After"])
    assert 0 < retry_after <= 24 * 3600


def test_no_row_is_written_for_a_blocked_attempt(client, owner, seeker, small_quota):
    """A blocked attempt is not a disclosure. Recording it would push the
    window forward on every retry and turn a day's block into a permanent one."""
    offers = _board(client, owner, small_quota + 1)
    for offer_id in offers[:small_quota]:
        _reveal(client, seeker, offer_id)
    _reveal(client, seeker, offers[-1])

    with TestingSession() as db:
        rows = list(db.scalars(select(ContactReveal)))
    assert len(rows) == small_quota


# --- the window rolls, it does not reset --------------------------------------


def test_an_aged_out_reveal_frees_a_slot(client, owner, seeker, small_quota):
    offers = _board(client, owner, small_quota + 1)
    for offer_id in offers[:small_quota]:
        _reveal(client, seeker, offer_id)
    assert _reveal(client, seeker, offers[-1]).status_code == 429

    _backdate("quota-seeker@example.com", offers[0], timedelta(hours=24, minutes=1))
    assert _reveal(client, seeker, offers[-1]).status_code == 200


def test_a_reveal_just_inside_the_window_still_counts(client, owner, seeker, small_quota):
    """23h59m is not yesterday. An off-by-one here is a free extra quota every
    day, compounding for anyone patient enough to notice."""
    offers = _board(client, owner, small_quota + 1)
    for offer_id in offers[:small_quota]:
        _reveal(client, seeker, offer_id)

    _backdate("quota-seeker@example.com", offers[0], timedelta(hours=23, minutes=59))
    assert _reveal(client, seeker, offers[-1]).status_code == 429


def test_the_window_is_not_a_calendar_day(client, owner, seeker, small_quota):
    """Midnight resets hand a double quota to anything that waits for them —
    which is exactly what an unattended collector does."""
    offers = _board(client, owner, small_quota + 1)
    for offer_id in offers[:small_quota]:
        _reveal(client, seeker, offer_id)

    # Every view is hours old but all within one rolling day; a calendar-day
    # implementation that had ticked over midnight would let this through.
    for hours, offer_id in enumerate(offers[:small_quota], start=1):
        _backdate("quota-seeker@example.com", offer_id, timedelta(hours=hours * 5))

    assert _reveal(client, seeker, offers[-1]).status_code == 429


# --- what must not consume quota ----------------------------------------------


def test_a_number_you_already_have_stays_available_at_the_ceiling(
    client, owner, seeker, small_quota
):
    """The case that matters, and the one an implementation gets wrong: the
    budget is spent, and the tenant re-opens the number they were given this
    morning to call about a viewing. Refusing that is the product punishing its
    own users to no security benefit — they already hold the number."""
    offers = _board(client, owner, small_quota + 1)
    for offer_id in offers[:small_quota]:
        assert _reveal(client, seeker, offer_id).status_code == 200
    assert _reveal(client, seeker, offers[-1]).status_code == 429, "quota not actually full"

    for _ in range(3):
        again = _reveal(client, seeker, offers[0])
        assert again.status_code == 200, again.text
        assert again.json()["contact_phone"] == OFFER["contact_phone"]


def test_repeat_views_do_not_eat_the_budget(client, owner, seeker, small_quota):
    offers = _board(client, owner, small_quota + 1)
    for _ in range(5):
        assert _reveal(client, seeker, offers[0]).status_code == 200

    # One number taken, so the rest of the budget must still be there.
    for offer_id in offers[1:small_quota]:
        assert _reveal(client, seeker, offer_id).status_code == 200
    assert _reveal(client, seeker, offers[-1]).status_code == 429


def test_a_repeat_view_adds_no_row(client, owner, seeker):
    offer_id = _publish(client, owner, "ul. Powtorka 9")
    for _ in range(3):
        _reveal(client, seeker, offer_id)

    with TestingSession() as db:
        assert len(list(db.scalars(select(ContactReveal)))) == 1


def test_a_message_only_offer_does_not_spend_quota(client, owner, seeker, small_quota):
    """Nothing was disclosed, so nothing should be charged."""
    prop = client.post(
        "/v1/properties", json={**PROPERTY, "address": "ul. Wiadomosc 8"}, headers=auth(owner)
    ).json()["id"]
    verify_ownership(client, owner, prop)
    offer = client.post(
        f"/v1/properties/{prop}/classifieds",
        json={**OFFER, "contact_mode": "message", "contact_phone": ""},
        headers=auth(owner),
    ).json()["id"]
    client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))

    for _ in range(small_quota + 2):
        assert _reveal(client, seeker, offer).status_code == 409

    assert client.get("/v1/me/reveal-quota", headers=auth(seeker)).json()["used"] == 0


# --- the quota is per account -------------------------------------------------


def test_each_account_has_its_own_budget(client, owner, small_quota):
    """Stated rather than assumed: a global counter would let one collector
    lock every tenant out of the board."""
    offers = _board(client, owner, small_quota + 1)
    first = register_and_login(client, "budget-one@example.com", "guest")
    verify_phone(client, first, "+48600000011")
    second = register_and_login(client, "budget-two@example.com", "guest")
    verify_phone(client, second, "+48600000012")

    for offer_id in offers[:small_quota]:
        assert _reveal(client, first, offer_id).status_code == 200
    assert _reveal(client, first, offers[-1]).status_code == 429

    assert _reveal(client, second, offers[-1]).status_code == 200


def test_the_count_is_read_from_the_rows_not_from_a_counter(client, owner, seeker, small_quota):
    """Reconstructible after a restart, and the same evidence a dispute would
    be argued from. A counter on the user row would be neither."""
    offers = _board(client, owner, small_quota)
    for offer_id in offers:
        _reveal(client, seeker, offer_id)

    with TestingSession() as db:
        rows = list(db.scalars(select(ContactReveal)))
    assert len(rows) == small_quota

    # Delete the evidence and the budget comes back — proving the rows are the
    # source, not a cached number somewhere else.
    with TestingSession() as db:
        for row in db.scalars(select(ContactReveal)):
            db.delete(row)
        db.commit()

    assert client.get("/v1/me/reveal-quota", headers=auth(seeker)).json()["used"] == 0


# --- the budget is visible ----------------------------------------------------


def test_a_fresh_account_sees_a_full_budget(client, seeker):
    body = client.get("/v1/me/reveal-quota", headers=auth(seeker)).json()
    assert body["limit"] == settings.contact_reveal_daily_quota
    assert body["used"] == 0
    assert body["remaining"] == settings.contact_reveal_daily_quota
    assert body["resets_in"] == 0


def test_the_budget_goes_down_as_it_is_spent(client, owner, seeker, small_quota):
    for i, offer_id in enumerate(_board(client, owner, small_quota), start=1):
        _reveal(client, seeker, offer_id)
        body = client.get("/v1/me/reveal-quota", headers=auth(seeker)).json()
        assert body["used"] == i
        assert body["remaining"] == small_quota - i

    assert client.get("/v1/me/reveal-quota", headers=auth(seeker)).json()["resets_in"] > 0


def test_the_budget_never_reads_negative(client, owner, seeker, small_quota):
    """If the quota is lowered while people hold more than the new ceiling, the
    number on the screen must still make sense."""
    for offer_id in _board(client, owner, small_quota):
        _reveal(client, seeker, offer_id)
    settings.contact_reveal_daily_quota = 1

    body = client.get("/v1/me/reveal-quota", headers=auth(seeker)).json()
    assert body["remaining"] == 0
    assert body["used"] == 1  # clamped to the ceiling rather than reported as 3 of 1


def test_the_quota_view_carries_no_personal_data(client, owner, seeker):
    """It is a budget, not a history. Offer ids would rebuild the search
    someone ran; a phone number would defeat the entire module."""
    offer_id = _publish(client, owner, "ul. Prywatna 7")
    _reveal(client, seeker, offer_id)

    body = client.get("/v1/me/reveal-quota", headers=auth(seeker))
    assert offer_id not in body.text
    assert "500 111 222" not in body.text


def test_the_quota_view_needs_an_account(client):
    assert client.get("/v1/me/reveal-quota").status_code == 401


# --- configuration ------------------------------------------------------------


def test_the_quota_cannot_be_configured_to_zero(client):
    """Zero would silently disable the board rather than the quota, and the
    mistake would look like a platform outage."""
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(contact_reveal_daily_quota=0)
