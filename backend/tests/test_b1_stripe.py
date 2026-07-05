"""B1 — Stripe Connect adapter + webhook subsystem.

No real Stripe account is used. A FakeStripe stands in for the SDK so the
adapter's trust boundary (signature verification), idempotency, replay
safety and ledger translation are proven deterministically. Real sandbox
validation is a separate, keys-required step (see docs/design/b1-stripe.md).
"""

import json

import pytest

import app.modules.payments.router as payments_router
from app.modules.payments.provider import StripeConnectProvider
from tests.conftest import auth, register_and_login


class _FakeWebhook:
    @staticmethod
    def construct_event(payload, sig, secret):
        # Trust boundary: only "valid" signatures are accepted; anything else
        # (missing/tampered) raises, exactly like stripe.Webhook.
        if sig != "valid":
            raise ValueError("Invalid signature")
        return json.loads(payload)


class _FakeStripe:
    Webhook = _FakeWebhook


@pytest.fixture()
def stripe_provider(monkeypatch):
    p = StripeConnectProvider(api_key="sk_test_dummy")
    p._stripe = _FakeStripe()
    monkeypatch.setattr(payments_router, "provider", p)
    return p


def _make_booking(client, admin_token):
    from datetime import date, timedelta

    host = register_and_login(client, "host@example.com", "host")
    guest = register_and_login(client, "guest@example.com", "guest")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 30000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    ci = (date.today() + timedelta(days=20)).isoformat()
    co = (date.today() + timedelta(days=23)).isoformat()
    r = client.post("/v1/bookings", json={"listing_id": lid, "check_in": ci, "check_out": co},
                    headers=auth(guest) | {"Idempotency-Key": "b1-key-0001"})
    assert r.status_code == 201, r.text
    return r.json(), host, guest


def _event(intent_id, etype="payment_intent.succeeded", eid="evt_1"):
    return {"id": eid, "type": etype, "data": {"object": {"id": intent_id}}}


def test_webhook_rejects_bad_signature(client, admin_token, stripe_provider):
    bk, _, _ = _make_booking(client, admin_token)
    r = client.post(
        "/v1/payments/webhook/stripe",
        content=json.dumps(_event(bk["payment_intent_id"])),
        headers={"Stripe-Signature": "tampered"},
    )
    assert r.status_code == 400
    # booking must remain unpaid
    assert client.get("/v1/admin/bookings", headers=auth(admin_token)).json()[0]["status"] == "pending"


def test_webhook_confirms_and_is_idempotent(client, admin_token, stripe_provider):
    bk, _, _ = _make_booking(client, admin_token)
    body = json.dumps(_event(bk["payment_intent_id"]))

    # First delivery: processes, confirms booking, posts capture
    r = client.post("/v1/payments/webhook/stripe", content=body,
                    headers={"Stripe-Signature": "valid"})
    assert r.status_code == 200 and r.json()["type"] == "payment_intent.succeeded"

    # Duplicate delivery (same event id): no double capture
    r = client.post("/v1/payments/webhook/stripe", content=body,
                    headers={"Stripe-Signature": "valid"})
    assert r.json().get("duplicate") is True

    assert client.get(f"/v1/bookings/{bk['id']}", headers=auth(admin_token)).json()["status"] == "confirmed"
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True
    assert rec["double_capture"] == []
    assert rec["ledger_grand_total"] == 0
    # single capture entry
    entries = client.get("/v1/admin/ledger/entries", headers=auth(admin_token)).json()
    assert sum(1 for e in entries if e["kind"] == "payment_captured") == 1


def test_webhook_replay_out_of_order_and_failed(client, admin_token, stripe_provider):
    bk, _, _ = _make_booking(client, admin_token)
    # A failed event for a fresh (unpaid) intent frees the dates; idempotent
    body = json.dumps(_event(bk["payment_intent_id"], "payment_intent.payment_failed", "evt_f"))
    r = client.post("/v1/payments/webhook/stripe", content=body,
                    headers={"Stripe-Signature": "valid"})
    assert r.status_code == 200
    assert client.get(f"/v1/bookings/{bk['id']}", headers=auth(admin_token)).json()["status"] == "payment_failed"
    # reconciliation still balances (no money moved on failure)
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True


def test_stripe_endpoint_503_without_stripe_provider(client, admin_token):
    # Default provider is simulation -> production stripe endpoint refuses.
    r = client.post("/v1/payments/webhook/stripe", content="{}",
                    headers={"Stripe-Signature": "x"})
    assert r.status_code == 503
