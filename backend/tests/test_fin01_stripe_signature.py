"""FIN-01 (part 1) — webhook trust boundary against the REAL Stripe library.

These tests do not mock Stripe. They build genuine `Stripe-Signature` headers
with the same HMAC-SHA256 scheme Stripe uses and let
`stripe.Webhook.construct_event` verify them, so the signature path, replay
tolerance and payload-tampering detection are validated by the real
implementation. No Stripe API key and no network access are required — signing
secrets are generated locally per test.

The parts that genuinely need a Stripe account (PaymentIntent creation, test
cards, 3DS/SCA, refunds, transfers, payouts, disputes) live in
tests/stripe_live/ and are skipped unless credentials are supplied.
"""

import hashlib
import hmac
import json
import secrets
import time
from datetime import date, timedelta

import pytest

import app.modules.payments.router as payments_router
from app.core.config import settings
from app.modules.payments.provider import StripeConnectProvider
from tests.conftest import auth, register_and_login

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


def sign(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Build a real Stripe-Signature header (scheme v1)."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.".encode() + payload
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={signature}"


@pytest.fixture()
def stripe_webhook(monkeypatch):
    """Real StripeConnectProvider wired to a locally generated signing secret."""
    secret = "whsec_" + secrets.token_hex(24)
    monkeypatch.setattr(settings, "stripe_webhook_secret", secret)
    provider = StripeConnectProvider(api_key="sk_test_" + secrets.token_hex(12))
    monkeypatch.setattr(payments_router, "provider", provider)
    return secret


def _paid_booking(client):
    host = register_and_login(client, "host@example.com", "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    guest = register_and_login(client, "guest@example.com", "guest")
    return client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                       headers=auth(guest) | {"Idempotency-Key": "fin01-0001"}).json()


def event_body(intent_id: str, event_id: str = "evt_real_1",
               etype: str = "payment_intent.succeeded") -> bytes:
    """Shaped like a genuine Stripe event — note the top-level `"object":
    "event"`, which the SDK requires and which our earlier mocked tests
    omitted."""
    return json.dumps({
        "id": event_id, "object": "event", "type": etype,
        "api_version": "2024-06-20", "created": int(time.time()),
        "livemode": False,
        "data": {"object": {"id": intent_id, "object": "payment_intent"}},
    }).encode()


# --- signature verification (real library) ----------------------------------
def test_valid_signature_is_accepted_and_processed(client, admin_token, stripe_webhook):
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"])
    r = client.post("/v1/payments/webhook/stripe", content=body,
                    headers={"Stripe-Signature": sign(body, stripe_webhook)})
    assert r.status_code == 200, r.text
    assert client.get(f"/v1/bookings/{bk['id']}",
                      headers=auth(admin_token)).json()["status"] == "confirmed"


def test_missing_signature_is_rejected(client, stripe_webhook):
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"])
    assert client.post("/v1/payments/webhook/stripe", content=body).status_code == 400


def test_signature_from_a_different_secret_is_rejected(client, stripe_webhook):
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"])
    attacker_secret = "whsec_" + secrets.token_hex(24)
    r = client.post("/v1/payments/webhook/stripe", content=body,
                    headers={"Stripe-Signature": sign(body, attacker_secret)})
    assert r.status_code == 400


def test_tampered_payload_is_rejected(client, stripe_webhook):
    """Signature is computed over the original body; changing a byte must fail."""
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"])
    header = sign(body, stripe_webhook)
    tampered = body.replace(b"payment_intent.succeeded", b"payment_intent.canceled")
    assert client.post("/v1/payments/webhook/stripe", content=tampered,
                       headers={"Stripe-Signature": header}).status_code == 400


def test_replayed_old_timestamp_is_rejected(client, stripe_webhook):
    """Stripe's default tolerance is 300s — an old capture cannot be replayed."""
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"])
    stale = sign(body, stripe_webhook, timestamp=int(time.time()) - 3600)
    assert client.post("/v1/payments/webhook/stripe", content=stale,
                       headers={"Stripe-Signature": stale and stale}).status_code == 400


def test_malformed_signature_header_is_rejected(client, stripe_webhook):
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"])
    for header in ("", "garbage", "t=,v1=", "v1=deadbeef", "t=abc,v1=xyz"):
        assert client.post("/v1/payments/webhook/stripe", content=body,
                           headers={"Stripe-Signature": header}).status_code == 400


def test_malformed_json_with_valid_signature_fails_safely(client, stripe_webhook):
    body = b"{not json"
    r = client.post("/v1/payments/webhook/stripe", content=body,
                    headers={"Stripe-Signature": sign(body, stripe_webhook)})
    assert r.status_code == 400  # rejected, no crash, no state change


# --- at-least-once delivery -------------------------------------------------
def test_duplicate_signed_delivery_does_not_duplicate_money(client, admin_token, stripe_webhook):
    """Stripe guarantees at-least-once. The same signed event delivered many
    times must capture exactly once."""
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"])
    for _ in range(5):
        header = sign(body, stripe_webhook)  # fresh timestamp, same event id
        assert client.post("/v1/payments/webhook/stripe", content=body,
                           headers={"Stripe-Signature": header}).status_code == 200

    entries = client.get("/v1/admin/ledger/entries", headers=auth(admin_token)).json()
    captures = [e for e in entries
                if e["kind"] == "payment_captured" and e["booking_id"] == bk["id"]]
    assert len(captures) == 1
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True and rec["double_capture"] == []


def test_unknown_event_type_is_recorded_but_not_acted_on(client, admin_token, stripe_webhook):
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"], event_id="evt_unknown",
                      etype="customer.subscription.updated")
    r = client.post("/v1/payments/webhook/stripe", content=body,
                    headers={"Stripe-Signature": sign(body, stripe_webhook)})
    assert r.status_code == 200
    # booking untouched, ledger untouched
    assert client.get(f"/v1/bookings/{bk['id']}",
                      headers=auth(admin_token)).json()["status"] == "pending"
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True


def test_failed_payment_event_does_not_confirm_booking(client, admin_token, stripe_webhook):
    bk = _paid_booking(client)
    body = event_body(bk["payment_intent_id"], event_id="evt_failed",
                      etype="payment_intent.payment_failed")
    r = client.post("/v1/payments/webhook/stripe", content=body,
                    headers={"Stripe-Signature": sign(body, stripe_webhook)})
    assert r.status_code == 200
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(admin_token)).json()
    assert state["lifecycle_state"] == "payment_failed"
    assert state["financial"]["payment_status"] == "failed"
    # no money was created or destroyed
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True and rec["ledger_grand_total"] == 0
