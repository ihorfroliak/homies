"""H2 (audit 2026-07-28) — the raw Stripe webhook event must survive a failed
dispatch.

The raw event used to be `flush()`ed in the same transaction as the
ledger-affecting handlers and committed only at the very end, so any handler
failure rolled the audit record back with it: the event disappeared with no
trace while Stripe kept retrying against a permanent error and eventually gave
up. Reproduced before the fix (unknown intent -> 404, zero webhook_events rows).

These tests use the real Stripe signature path (same fixture as FIN-01), not a
mock, so the trust boundary is exercised exactly as in production.
"""

import json
import time
from datetime import date, timedelta

import pytest
from sqlalchemy import select

import app.modules.payments.router as payments_router
from app.modules.payments.models import WebhookEvent
from tests.conftest import TestingSession, auth, register_and_login
from tests.test_fin01_stripe_signature import event_body, sign

# LEGACY_DORMANT runtime (TASK-002 R1): see tests/legacy_runtime.py.
pytestmark = pytest.mark.legacy_runtime

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


def _booking(client):
    host = register_and_login(client, "host@example.com", "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    guest = register_and_login(client, "guest@example.com", "guest")
    return client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                       headers=auth(guest) | {"Idempotency-Key": "h2-000001"}).json()


def _deliver(client, secret, body):
    return client.post("/v1/payments/webhook/stripe", content=body,
                       headers={"Stripe-Signature": sign(body, secret)})


def _events(event_id: str) -> list[WebhookEvent]:
    with TestingSession() as db:
        return list(db.scalars(
            select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id)
        ))


# --- the defect itself ------------------------------------------------------
def test_failed_dispatch_still_persists_the_raw_event(client, admin_token, stripe_webhook):
    """An event for an intent we do not know fails dispatch (404). The audit
    record must survive anyway — this is what silently vanished before."""
    body = event_body("pi_does_not_exist", event_id="evt_h2_unknown")
    resp = _deliver(client, stripe_webhook, body)
    assert resp.status_code == 404, resp.text  # dispatch genuinely failed

    rows = _events("evt_h2_unknown")
    assert len(rows) == 1, "the raw event must be durable even when dispatch fails"
    assert rows[0].processed_at is None, "an unprocessed event is the dead-letter marker"
    assert rows[0].event_type == "payment_intent.succeeded"
    assert rows[0].payload["id"] == "evt_h2_unknown"  # exactly what Stripe sent

    # and no money was invented on the failing path
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True and rec["ledger_grand_total"] == 0


def test_conflicting_state_dispatch_persists_the_raw_event(client, admin_token, stripe_webhook):
    """Second, deterministic failure mode: a success event for a payment that
    already failed. Stripe would retry this forever and still never process it,
    so losing the record used to mean losing it permanently."""
    bk = _booking(client)
    failed = event_body(bk["payment_intent_id"], event_id="evt_h2_fail",
                        etype="payment_intent.payment_failed")
    assert _deliver(client, stripe_webhook, failed).status_code == 200

    body = event_body(bk["payment_intent_id"], event_id="evt_h2_conflict")
    resp = _deliver(client, stripe_webhook, body)
    assert resp.status_code == 409, resp.text

    rows = _events("evt_h2_conflict")
    assert len(rows) == 1 and rows[0].processed_at is None
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True


# --- retry behaviour --------------------------------------------------------
def test_retry_after_a_transient_failure_processes_exactly_once(
    client, admin_token, stripe_webhook, monkeypatch
):
    """Stripe redelivers after a failure. The retry must re-run dispatch (the
    event was never marked processed), confirm the booking, and capture once —
    no duplicate row, no duplicate money."""
    bk = _booking(client)
    body = event_body(bk["payment_intent_id"], event_id="evt_h2_retry")

    real = payments_router.service.process_intent_succeeded
    calls = {"n": 0}

    def flaky(db, intent_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient dispatch failure")
        return real(db, intent_id)

    monkeypatch.setattr(payments_router.service, "process_intent_succeeded", flaky)

    with pytest.raises(RuntimeError):  # first delivery blows up after persistence
        _deliver(client, stripe_webhook, body)

    rows = _events("evt_h2_retry")
    assert len(rows) == 1 and rows[0].processed_at is None
    assert client.get(f"/v1/bookings/{bk['id']}",
                      headers=auth(admin_token)).json()["status"] == "pending"

    # Stripe retries the same event id
    assert _deliver(client, stripe_webhook, body).status_code == 200
    rows = _events("evt_h2_retry")
    assert len(rows) == 1, "a retry must not duplicate the audit row"
    assert rows[0].processed_at is not None
    assert client.get(f"/v1/bookings/{bk['id']}",
                      headers=auth(admin_token)).json()["status"] == "confirmed"

    entries = client.get("/v1/admin/ledger/entries", headers=auth(admin_token)).json()
    captures = [e for e in entries
                if e["kind"] == "payment_captured" and e["booking_id"] == bk["id"]]
    assert len(captures) == 1
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True and rec["double_capture"] == []


# --- success path is unchanged ---------------------------------------------
def test_successful_delivery_marks_processed_and_dedupes(client, admin_token, stripe_webhook):
    bk = _booking(client)
    body = event_body(bk["payment_intent_id"], event_id="evt_h2_ok")

    assert _deliver(client, stripe_webhook, body).status_code == 200
    rows = _events("evt_h2_ok")
    assert len(rows) == 1 and rows[0].processed_at is not None

    second = _deliver(client, stripe_webhook, body)
    assert second.status_code == 200
    assert second.json() == {"received": True, "duplicate": True}
    assert len(_events("evt_h2_ok")) == 1


def test_unknown_event_type_is_persisted_and_marked_processed(client, stripe_webhook):
    """Unknown types are stored for audit and acknowledged — they have no
    handler, so they are 'processed' by definition and must not be replayed."""
    body = json.dumps({
        "id": "evt_h2_other", "object": "event", "type": "customer.subscription.updated",
        "api_version": "2024-06-20", "created": int(time.time()), "livemode": False,
        "data": {"object": {"id": "sub_123", "object": "subscription"}},
    }).encode()
    assert _deliver(client, stripe_webhook, body).status_code == 200
    rows = _events("evt_h2_other")
    assert len(rows) == 1 and rows[0].processed_at is not None
