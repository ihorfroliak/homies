"""H4 (audit 2026-07-28) — the payment provider call must not run inside the
booking's row-locked transaction.

`create_booking` used to hold `SELECT listing ... FOR UPDATE` across a network
round-trip to Stripe, so concurrent bookings of the same listing queued behind
it and a pooled DB connection stayed pinned for the whole call. The provider
call now happens after the commit.

That moves the failure mode: the booking can exist for a moment without a
payment. These tests pin the resulting contract — the booking survives as
`pending`, and a replay with the same Idempotency-Key heals it rather than
returning something unpayable.

The proof that the lock is genuinely released lives in test_ci03_concurrency.py
(real Postgres — SQLite has no row locks to hold).
"""

from datetime import date, timedelta

import pytest

import app.modules.payments.service as payments_service
from app.modules.booking.models import Booking
from app.modules.payments.models import Payment
from tests.conftest import TestingSession, auth, register_and_login

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


def _listing(client):
    host = register_and_login(client, "host@example.com", "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2,
                      "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    return lid


def _book(client, token, lid, key):
    return client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                       headers=auth(token) | {"Idempotency-Key": key})


# --- happy path is unchanged ------------------------------------------------
def test_booking_still_returns_a_payable_intent(client):
    lid = _listing(client)
    guest = register_and_login(client, "guest@example.com", "guest")
    resp = _book(client, guest, lid, "h4-happy-01")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["payment_id"] and body["payment_intent_id"]
    assert body["status"] == "pending"


# --- the new failure mode ---------------------------------------------------
def test_provider_failure_leaves_a_pending_booking_and_no_payment(client, monkeypatch):
    """Stripe is down. The booking must still be committed — the dates are held
    and its TTL will free them — but no payment row may be invented."""
    lid = _listing(client)
    guest = register_and_login(client, "guest@example.com", "guest")

    def boom(**kwargs):
        raise RuntimeError("stripe unreachable")

    monkeypatch.setattr(payments_service.provider, "create_payment_intent", boom)

    with pytest.raises(RuntimeError):
        _book(client, guest, lid, "h4-down-01")

    with TestingSession() as db:
        bookings = list(db.scalars(select_bookings()))
        payments = list(db.scalars(select_payments()))
    assert len(bookings) == 1
    assert bookings[0].status == "pending"
    assert bookings[0].payment_expires_at is not None  # the TTL still protects inventory
    assert payments == []


def test_replay_after_a_provider_failure_heals_the_booking(client, monkeypatch):
    """Stripe recovers and the guest retries with the same Idempotency-Key. The
    replay must return the ORIGINAL booking, now with a payable intent — not a
    second booking and not an unpayable one."""
    lid = _listing(client)
    guest = register_and_login(client, "guest@example.com", "guest")

    real = payments_service.provider.create_payment_intent

    def boom(**kwargs):
        raise RuntimeError("stripe unreachable")

    monkeypatch.setattr(payments_service.provider, "create_payment_intent", boom)
    with pytest.raises(RuntimeError):
        _book(client, guest, lid, "h4-heal-01")

    monkeypatch.setattr(payments_service.provider, "create_payment_intent", real)
    resp = _book(client, guest, lid, "h4-heal-01")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["payment_intent_id"], "the replay must produce a payable intent"

    with TestingSession() as db:
        bookings = list(db.scalars(select_bookings()))
        payments = list(db.scalars(select_payments()))
    assert len(bookings) == 1 and bookings[0].id == body["id"]
    assert len(payments) == 1, "healing must not create a second payment"


def test_replay_of_a_healthy_booking_does_not_create_a_second_intent(client, monkeypatch):
    """The ordinary replay path must not call the provider again at all."""
    lid = _listing(client)
    guest = register_and_login(client, "guest@example.com", "guest")
    first = _book(client, guest, lid, "h4-replay-01").json()

    calls = {"n": 0}
    real = payments_service.provider.create_payment_intent

    def counting(**kwargs):
        calls["n"] += 1
        return real(**kwargs)

    monkeypatch.setattr(payments_service.provider, "create_payment_intent", counting)
    second = _book(client, guest, lid, "h4-replay-01").json()

    assert second["id"] == first["id"]
    assert second["payment_intent_id"] == first["payment_intent_id"]
    assert calls["n"] == 0, "a replay with an existing payment must not touch the provider"


def test_expired_booking_replay_is_not_healed(client, monkeypatch):
    """Only a still-pending booking is worth a payment intent. A booking that
    already expired must not acquire one on replay."""
    lid = _listing(client)
    guest = register_and_login(client, "guest@example.com", "guest")

    def boom(**kwargs):
        raise RuntimeError("stripe unreachable")

    monkeypatch.setattr(payments_service.provider, "create_payment_intent", boom)
    with pytest.raises(RuntimeError):
        _book(client, guest, lid, "h4-expired-01")

    with TestingSession() as db:
        booking = db.scalars(select_bookings()).one()
        booking.status = "expired"
        booking.payment_expires_at = None
        db.commit()

    resp = _book(client, guest, lid, "h4-expired-01")
    assert resp.status_code == 201
    assert resp.json()["payment_intent_id"] is None
    with TestingSession() as db:
        assert list(db.scalars(select_payments())) == []


# small helpers so the selects read cleanly above
def select_bookings():
    from sqlalchemy import select

    return select(Booking)


def select_payments():
    from sqlalchemy import select

    return select(Payment)
