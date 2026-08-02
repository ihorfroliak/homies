"""H3 (audit 2026-07-28) — the Stripe PaymentIntent idempotency key must be
derived from the booking, not generated randomly.

The adapter used to build `pi_{host}_{amount}_{currency}_{uuid4()}`. Because the
key was fresh on every call, Stripe's idempotency protected nothing: if the
booking transaction failed after the intent was created and the flow was
retried, a SECOND intent was created for the same booking — i.e. the guest
could be charged twice. The comment above it claimed the opposite.

These tests drive the real StripeConnectProvider with a fake SDK object, so the
adapter's actual arguments are asserted without any network or credentials.
"""

from datetime import date, timedelta

import pytest

from app.modules.payments.provider import StripeConnectProvider, StripeSimulationProvider
from tests.conftest import auth, register_and_login

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


class _FakeIntents:
    def __init__(self, calls):
        self._calls = calls

    def create(self, **kwargs):
        self._calls.append(kwargs)
        return {"id": f"pi_fake_{len(self._calls)}", "client_secret": "cs_fake"}


class _FakeStripe:
    """Captures what the adapter sends. Only the surface the adapter touches."""

    def __init__(self):
        self.calls = []
        self.PaymentIntent = _FakeIntents(self.calls)


@pytest.fixture()
def adapter(monkeypatch):
    provider = StripeConnectProvider.__new__(StripeConnectProvider)  # skip SDK init
    fake = _FakeStripe()
    provider._stripe = fake
    return provider, fake


def _create(provider, key="bk-123"):
    return provider.create_payment_intent(
        amount=120000, currency="PLN", host_account_id="acct_test_1",
        application_fee=18000, idempotency_key=key,
    )


# --- the defect itself ------------------------------------------------------
def test_idempotency_key_is_derived_from_the_caller_scope(adapter):
    provider, fake = adapter
    _create(provider, key="bk-123")
    assert fake.calls[0]["idempotency_key"] == "pi_bk-123"


def test_repeated_calls_for_the_same_booking_reuse_the_key(adapter):
    """The whole point: a retry must present the SAME key so Stripe returns the
    original intent instead of creating a second charge."""
    provider, fake = adapter
    _create(provider, key="bk-123")
    _create(provider, key="bk-123")
    keys = [c["idempotency_key"] for c in fake.calls]
    assert keys[0] == keys[1] == "pi_bk-123"


def test_different_bookings_get_different_keys(adapter):
    provider, fake = adapter
    _create(provider, key="bk-123")
    _create(provider, key="bk-456")
    keys = [c["idempotency_key"] for c in fake.calls]
    assert keys[0] != keys[1]


def test_key_does_not_depend_on_amount_or_host(adapter):
    """A guest editing nothing but retrying must not slip past idempotency, and
    the key must not silently change when unrelated fields do."""
    provider, fake = adapter
    provider.create_payment_intent(amount=120000, currency="PLN",
                                   host_account_id="acct_a", application_fee=18000,
                                   idempotency_key="bk-123")
    provider.create_payment_intent(amount=999999, currency="PLN",
                                   host_account_id="acct_b", application_fee=1,
                                   idempotency_key="bk-123")
    assert fake.calls[0]["idempotency_key"] == fake.calls[1]["idempotency_key"]


def test_destination_charge_shape_is_unchanged(adapter):
    """Guard the rest of the call so this fix cannot silently alter the money
    shape (ADR-0007 destination charges)."""
    provider, fake = adapter
    _create(provider)
    call = fake.calls[0]
    assert call["amount"] == 120000
    assert call["currency"] == "pln"  # Stripe wants lowercase
    assert call["application_fee_amount"] == 18000
    assert call["transfer_data"] == {"destination": "acct_test_1"}


# --- the seam ---------------------------------------------------------------
def test_simulation_provider_accepts_the_same_signature():
    """Both implementations must satisfy the PaymentProvider protocol, or
    swapping providers breaks at runtime instead of at the seam."""
    intent = StripeSimulationProvider().create_payment_intent(
        amount=1000, currency="PLN", host_account_id="acct_sim",
        application_fee=150, idempotency_key="bk-1",
    )
    assert intent.intent_id.startswith("pi_sim_")


def test_booking_flow_passes_the_booking_id_as_the_key(client, monkeypatch):
    """End to end: the booking that reaches Stripe carries its own id as the
    idempotency scope."""
    import app.modules.payments.service as payments_service

    captured = {}
    real = payments_service.provider.create_payment_intent

    def spy(**kwargs):
        captured.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(payments_service.provider, "create_payment_intent", spy)

    host = register_and_login(client, "host@example.com", "host")
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2,
                      "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    guest = register_and_login(client, "guest@example.com", "guest")
    bk = client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                     headers=auth(guest) | {"Idempotency-Key": "h3-000001"}).json()

    assert captured["idempotency_key"] == bk["id"]
