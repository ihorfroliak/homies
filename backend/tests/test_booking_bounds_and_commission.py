"""Booking length cap (PRODUCT_MODEL §1) and the commission stamp.

Both are small changes guarding expensive mistakes:

* A booking longer than 180 nights is long-term rental. It belongs on the free
  classifieds board, not in the paid booking path — and until now nothing
  stopped a 3650-night booking multiplying cleanly into the ledger.
* The commission used to be read from settings at PAYOUT time, so an admin
  changing the rate re-priced every booking not yet paid out. The rate is now
  stamped when the booking is created, and the payout must honour that stamp
  however the setting has moved since.
"""

from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.modules.booking.schemas import MAX_NIGHTS
from tests.conftest import auth, fire_webhook, register_and_login

# LEGACY_DORMANT runtime (TASK-002 R1): see tests/legacy_runtime.py.
pytestmark = pytest.mark.legacy_runtime

NIGHTLY = 30000


def _listing(client, host_token):
    r = client.post(
        "/v1/listings",
        json={
            "title": "Bounds test",
            "city": "Warszawa",
            "address": "Testowa 1",
            "capacity": 4,
            "nightly_price_amount": NIGHTLY,
        },
        headers=auth(host_token),
    )
    assert r.status_code == 201, r.text
    listing_id = r.json()["id"]
    client.post(f"/v1/listings/{listing_id}/publish", headers=auth(host_token))
    return listing_id


def _book(client, guest_token, listing_id, nights, *, start_offset=10, key="key"):
    check_in = date.today() + timedelta(days=start_offset)
    return client.post(
        "/v1/bookings",
        json={
            "listing_id": listing_id,
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=nights)).isoformat(),
            "guests": 1,
        },
        headers={**auth(guest_token), "Idempotency-Key": f"idem-{key}-0001"},
    )


# --- booking length cap -------------------------------------------------------


@pytest.mark.parametrize("nights", [1, MAX_NIGHTS])
def test_stays_up_to_the_cap_are_accepted(client, nights):
    host = register_and_login(client, f"host{nights}@example.com", "host")
    guest = register_and_login(client, f"guest{nights}@example.com", "guest")
    listing_id = _listing(client, host)

    resp = _book(client, guest, listing_id, nights, key=f"ok-{nights}")
    assert resp.status_code == 201, resp.text
    assert resp.json()["total_amount"] == nights * NIGHTLY


def test_a_stay_one_night_over_the_cap_is_rejected(client):
    """181 nights is long-term rental, and long-term rental is not booked here."""
    host = register_and_login(client, "host181@example.com", "host")
    guest = register_and_login(client, "guest181@example.com", "guest")
    listing_id = _listing(client, host)

    resp = _book(client, guest, listing_id, MAX_NIGHTS + 1, key="too-long")
    assert resp.status_code == 422, resp.text
    assert "180" in resp.text


def test_zero_night_booking_still_rejected(client):
    """Kept from the original rules: check_out must be after check_in."""
    host = register_and_login(client, "host0@example.com", "host")
    guest = register_and_login(client, "guest0@example.com", "guest")
    listing_id = _listing(client, host)

    assert _book(client, guest, listing_id, 0, key="zero").status_code == 422


# --- commission stamp ---------------------------------------------------------


def test_booking_records_the_rate_in_force_when_it_was_created(client):
    from app.modules.booking.models import Booking
    from tests.conftest import TestingSession

    host = register_and_login(client, "host-rate@example.com", "host")
    guest = register_and_login(client, "guest-rate@example.com", "guest")
    listing_id = _listing(client, host)

    original = settings.platform_fee_bps
    try:
        settings.platform_fee_bps = 800
        booking_id = _book(client, guest, listing_id, 3, key="rate-1").json()["id"]
    finally:
        settings.platform_fee_bps = original

    with TestingSession() as db:
        assert db.get(Booking, booking_id).commission_bps == 800


def test_changing_the_rate_does_not_reprice_an_existing_booking(client, admin_token):
    """The defect this closes.

    Book at 8%, then have an admin move the platform rate to 15% before the
    payout runs. The host agreed to 8% and must be paid at 8% — the ledger entry
    and the payout total must both reflect the stamped rate, not the new one.
    """
    host = register_and_login(client, "host-repr@example.com", "host")
    guest = register_and_login(client, "guest-repr@example.com", "guest")
    listing_id = _listing(client, host)

    original = settings.platform_fee_bps
    try:
        settings.platform_fee_bps = 800
        booking = _book(client, guest, listing_id, 4, key="repr-1").json()
    finally:
        settings.platform_fee_bps = original

    total = booking["total_amount"]
    fee_at_booking = total * 800 // 10_000

    # Pay, complete, and make the host payout-ready through the real endpoints.
    fire_webhook(client, booking["payment_intent_id"])
    client.post(f"/v1/bookings/{booking['id']}/complete", headers=auth(admin_token))
    onboarding = client.post(
        "/v1/hosts/onboarding",
        json={"payout_iban": "PL61109010140000071219812874"},
        headers=auth(host),
    )
    assert onboarding.json()["onboarding_state"] == "payout_ready"
    host_id = client.get("/v1/me", headers=auth(host)).json()["id"]

    # The rate moves AFTER the booking exists — the classic way this used to bite.
    try:
        settings.platform_fee_bps = 1500
        payout = client.post(f"/v1/hosts/{host_id}/payouts/run", headers=auth(admin_token))
    finally:
        settings.platform_fee_bps = original

    assert payout.status_code == 200, payout.text
    body = payout.json()
    assert body["fee_total"] == fee_at_booking, (
        f"host was paid at the new rate: fee {body['fee_total']} != {fee_at_booking}"
    )
    assert body["paid_total"] == total - fee_at_booking
