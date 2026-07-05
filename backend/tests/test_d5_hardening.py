"""D5 hardening: webhook trust boundary, late-success auto-refund,
ledger immutability."""

import pytest

from tests.conftest import TestingSession, auth, fire_webhook
from tests.test_e2e_flow import full_flow


def test_webhook_rejects_wrong_secret(client, admin_token):
    _, booking, _, _ = full_flow(client, admin_token)
    resp = fire_webhook(client, booking["payment_intent_id"], secret="wrong-secret")
    assert resp.status_code == 401
    # Booking must remain unpaid
    bookings = client.get("/v1/admin/bookings", headers=auth(admin_token)).json()
    assert bookings[0]["status"] == "pending"


def test_late_payment_success_after_cancel_is_auto_refunded(client, admin_token):
    _, booking, _, guest_token = full_flow(client, admin_token)

    # Guest cancels while payment is still in flight
    resp = client.post(f"/v1/bookings/{booking['id']}/cancel", headers=auth(guest_token))
    assert resp.status_code == 200

    # Void happened; simulate the provider capturing anyway (late webhook)
    # by resetting the payment state as if capture raced the cancellation.
    from app.modules.payments.models import Payment

    with TestingSession() as db:
        payment = db.query(Payment).filter_by(booking_id=booking["id"]).one()
        payment.status = "requires_payment"
        db.commit()

    resp = fire_webhook(client, booking["payment_intent_id"])
    assert resp.status_code == 200
    assert resp.json()["status"] == "refunded"

    # Invariant I6: cancelled booking holds no escrow; system nets to zero
    balances = client.get("/v1/admin/ledger/balances", headers=auth(admin_token)).json()
    assert balances["booking_escrow"] == 0
    assert balances["provider_cash"] == 0
    recon = client.get("/v1/admin/ledger/reconciliation", headers=auth(admin_token)).json()
    assert recon["ok"] is True

    # Both capture and refund are in the ledger trace
    entries = client.get("/v1/admin/ledger/entries", headers=auth(admin_token)).json()
    kinds = [e["kind"] for e in entries]
    assert "payment_captured" in kinds
    assert "refund" in kinds


def test_ledger_is_append_only(client, admin_token):
    _, booking, _, _ = full_flow(client, admin_token)
    resp = fire_webhook(client, booking["payment_intent_id"])
    assert resp.status_code == 200

    from app.modules.ledger.models import JournalLine, LedgerImmutabilityError

    with TestingSession() as db:
        line = db.query(JournalLine).first()
        line.amount += 1
        with pytest.raises(LedgerImmutabilityError):
            db.commit()
        db.rollback()

    with TestingSession() as db:
        line = db.query(JournalLine).first()
        db.delete(line)
        with pytest.raises(LedgerImmutabilityError):
            db.commit()
        db.rollback()
