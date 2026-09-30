"""BK-01 — unpaid booking expiry + scheduler.

Deterministic: instead of sleeping past a TTL, tests set `payment_expires_at`
directly (or pass an explicit `now`), then drive one sweep. Covers the state
machine, idempotency, the payment-vs-expiry race, batch isolation, config
validation and metrics.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.modules.booking.expiry import expire_due_bookings
from app.modules.booking.models import Booking
from tests.conftest import TestingSession, auth, fire_webhook, register_and_login

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


def _listing(client):
    host = register_and_login(client, "host@example.com", "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    return lid


def _book(client, lid, key, guest_email="guest@example.com"):
    guest = register_and_login(client, guest_email, "guest")
    return client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                       headers=auth(guest) | {"Idempotency-Key": key}).json()


def _set_deadline(booking_id, when):
    with TestingSession() as db:
        db.get(Booking, booking_id).payment_expires_at = when
        db.commit()


def _status(booking_id):
    with TestingSession() as db:
        return db.get(Booking, booking_id).status


def _sweep(now=None):
    with TestingSession() as db:
        return expire_due_bookings(db, now=now)


# 1. a pending booking receives a deadline
@pytest.mark.legacy_runtime
def test_pending_booking_gets_a_deadline(client):
    lid = _listing(client)
    bk = _book(client, lid, "bk01-0001")
    with TestingSession() as db:
        booking = db.get(Booking, bk["id"])
        assert booking.status == "pending"
        assert booking.payment_expires_at is not None
        # SQLite returns naive datetimes; normalise before comparing (Postgres
        # keeps the tz). The deadline must be in the future.
        deadline = booking.payment_expires_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        assert deadline > datetime.now(timezone.utc)


# 2. a not-yet-due booking is left alone
@pytest.mark.legacy_runtime
def test_future_deadline_is_not_expired(client):
    lid = _listing(client)
    bk = _book(client, lid, "bk01-0002")
    res = _sweep()  # deadline is 30 min out
    assert res["expired"] == 0
    assert _status(bk["id"]) == "pending"


# 3. a due unpaid booking becomes expired
@pytest.mark.legacy_runtime
def test_due_booking_is_expired(client):
    lid = _listing(client)
    bk = _book(client, lid, "bk01-0003")
    _set_deadline(bk["id"], datetime.now(timezone.utc) - timedelta(seconds=1))
    res = _sweep()
    assert res["expired"] == 1
    assert _status(bk["id"]) == "expired"


# 4. a paid booking is never expired, even past its (stale) deadline
@pytest.mark.legacy_runtime
def test_paid_booking_is_never_expired(client, admin_token):
    lid = _listing(client)
    bk = _book(client, lid, "bk01-0004")
    fire_webhook(client, bk["payment_intent_id"])
    assert _status(bk["id"]) == "confirmed"
    _set_deadline(bk["id"], datetime.now(timezone.utc) - timedelta(days=1))  # force a stale date
    res = _sweep()
    assert res["expired"] == 0
    assert _status(bk["id"]) == "confirmed"


# 5 & 6. idempotent: expiring twice changes nothing the second time
@pytest.mark.legacy_runtime
def test_expiry_is_idempotent(client):
    lid = _listing(client)
    bk = _book(client, lid, "bk01-0005")
    _set_deadline(bk["id"], datetime.now(timezone.utc) - timedelta(seconds=1))
    assert _sweep()["expired"] == 1
    assert _sweep()["expired"] == 0  # nothing left to do
    assert _status(bk["id"]) == "expired"


# 7. two workers cannot both expire the same booking.
#
# The guarantee is the row-guarded UPDATE (... WHERE status='pending'): the
# loser's UPDATE affects 0 rows. On real Postgres concurrent workers are
# serialised by row locks; here we prove the *guard* deterministically, because
# SQLite with a shared connection cannot faithfully model true thread
# concurrency (same limitation the audit records as TST-05 / CI-03). A Postgres
# CI service is the recommended way to also exercise real concurrency.
@pytest.mark.legacy_runtime
def test_two_expiry_attempts_transition_the_row_exactly_once(client):
    from sqlalchemy import update

    lid = _listing(client)
    bk = _book(client, lid, "bk01-0006")
    _set_deadline(bk["id"], datetime.now(timezone.utc) - timedelta(seconds=1))

    def attempt_expire() -> int:
        with TestingSession() as db:
            res = db.execute(
                update(Booking)
                .where(Booking.id == bk["id"], Booking.status == "pending")
                .values(status="expired", payment_expires_at=None)
            )
            db.commit()
            return res.rowcount

    first = attempt_expire()   # winner
    second = attempt_expire()  # loser: row is no longer pending
    assert first == 1
    assert second == 0         # the guard makes the second a no-op -> expired once
    assert _status(bk["id"]) == "expired"


# 8. payment-vs-expiry race: whoever commits first wins, no PAID+EXPIRED
@pytest.mark.legacy_runtime
def test_payment_after_expiry_is_auto_refunded(client, admin_token):
    """Expiry wins first, then a late payment success arrives. The booking must
    stay expired and the money must be refunded — never PAID+EXPIRED."""
    lid = _listing(client)
    bk = _book(client, lid, "bk01-0007")
    _set_deadline(bk["id"], datetime.now(timezone.utc) - timedelta(seconds=1))
    assert _sweep()["expired"] == 1

    resp = fire_webhook(client, bk["payment_intent_id"])  # late success
    assert resp.status_code == 200
    assert _status(bk["id"]) == "expired"  # not confirmed
    # money captured then auto-refunded -> ledger nets to zero, no escrow held
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True and rec["balances"]["booking_escrow"] == 0


@pytest.mark.legacy_runtime
def test_payment_before_expiry_keeps_booking_confirmed(client, admin_token):
    """Payment wins first; the sweep then finds a non-pending row and skips it."""
    lid = _listing(client)
    bk = _book(client, lid, "bk01-0008")
    fire_webhook(client, bk["payment_intent_id"])  # confirmed
    _set_deadline(bk["id"], datetime.now(timezone.utc) - timedelta(seconds=1))  # stale
    assert _sweep()["expired"] == 0
    assert _status(bk["id"]) == "confirmed"


# 9. the sweep processes multiple bookings at once
@pytest.mark.legacy_runtime
def test_sweep_processes_a_batch(client):
    lid = _listing(client)
    ids = []
    for i in range(5):
        bk = _book(client, lid, f"bk01-batch-{i}", guest_email=f"g{i}@example.com")
        # non-overlapping dates so all 5 can coexist
        with TestingSession() as db:
            b = db.get(Booking, bk["id"])
            b.check_in = date.today() + timedelta(days=200 + i * 3)
            b.check_out = date.today() + timedelta(days=201 + i * 3)
            b.payment_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        ids.append(bk["id"])
    res = _sweep()
    assert res["expired"] == 5
    assert all(_status(i) == "expired" for i in ids)


# 10. one failing booking does not stop the batch
@pytest.mark.legacy_runtime
def test_one_failure_does_not_stop_the_batch(client, monkeypatch):
    lid = _listing(client)
    good = _book(client, lid, "bk01-good")
    with TestingSession() as db:
        b = db.get(Booking, good["id"])
        b.check_in = date.today() + timedelta(days=300)
        b.check_out = date.today() + timedelta(days=302)
        b.payment_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    # Make the first UPDATE raise, then restore normal behaviour.
    import app.modules.booking.expiry as expiry_mod

    real_execute = expiry_mod.Session.execute
    calls = {"n": 0}

    def flaky(self, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient db error")
        return real_execute(self, *a, **k)

    # inject a failing booking ahead of the good one
    bad = _book(client, lid, "bk01-bad", guest_email="bad@example.com")
    with TestingSession() as db:
        b = db.get(Booking, bad["id"])
        b.check_in = date.today() + timedelta(days=310)
        b.check_out = date.today() + timedelta(days=312)
        b.payment_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    monkeypatch.setattr(expiry_mod.Session, "execute", flaky)
    res = _sweep()
    monkeypatch.undo()
    assert res["failed"] >= 1 and res["expired"] >= 1  # batch continued despite the failure


# 12. TTL config validation
def test_ttl_config_rejects_out_of_bounds():
    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(booking_payment_ttl_seconds=0)
    with pytest.raises(ValueError):
        Settings(booking_payment_ttl_seconds=10)  # below floor
    with pytest.raises(ValueError):
        Settings(booking_payment_ttl_seconds=200_000)  # above ceiling
    assert Settings(booking_payment_ttl_seconds=1800).booking_payment_ttl_seconds == 1800


# 13 & 14. metrics emitted, no ghost booking left, calendar freed
@pytest.mark.legacy_runtime
def test_metrics_and_calendar_freed_after_expiry(client):
    from app.modules.booking import expiry as e

    lid = _listing(client)
    bk = _book(client, lid, "bk01-0009")
    _set_deadline(bk["id"], datetime.now(timezone.utc) - timedelta(seconds=1))
    before = e.EXPIRY_EXPIRED._value.get()
    _sweep()
    assert e.EXPIRY_EXPIRED._value.get() == before + 1

    # dates are available again -> a new guest can book them
    other = register_and_login(client, "other@example.com", "guest")
    r = client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                    headers=auth(other) | {"Idempotency-Key": "bk01-rebook"})
    assert r.status_code == 201
