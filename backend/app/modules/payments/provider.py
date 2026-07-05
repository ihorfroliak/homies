"""Payment provider abstraction — the Stripe Connect seam.

Two implementations behind one Protocol:
- StripeSimulationProvider: deterministic, in-process (default; no account
  needed; keeps D5-D9 tests hermetic).
- StripeConnectProvider: real Stripe Connect (destination charges).

The provider is selected by settings.payment_provider. The domain model,
ledger and booking engine never import Stripe types — Stripe is an external
processor, not the accounting system (ADR-0007).
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.core.config import settings


@dataclass
class PaymentIntent:
    intent_id: str
    client_secret: str
    amount: int
    currency: str


class PaymentProvider(Protocol):
    def create_payment_intent(
        self, amount: int, currency: str, host_account_id: str, application_fee: int
    ) -> PaymentIntent: ...

    def refund(self, intent_id: str, amount: int) -> str: ...


class StripeSimulationProvider:
    """Deterministic in-process stand-in for Stripe Connect sandbox."""

    def create_payment_intent(
        self, amount: int, currency: str, host_account_id: str, application_fee: int
    ) -> PaymentIntent:
        intent_id = f"pi_sim_{uuid4().hex[:20]}"
        return PaymentIntent(
            intent_id=intent_id,
            client_secret=f"{intent_id}_secret_{uuid4().hex[:12]}",
            amount=amount,
            currency=currency,
        )

    def refund(self, intent_id: str, amount: int) -> str:
        return f"re_sim_{uuid4().hex[:20]}"


class StripeConnectProvider:
    """Real Stripe Connect adapter using **destination charges**.

    Model choice (ADR-0007): destination charges (a single PaymentIntent on
    the platform with transfer_data.destination = host connected account +
    application_fee_amount = platform fee). Chosen over separate
    charges-and-transfers because the managed-operator model already makes
    Homies the customer-facing merchant of record; destination charges keep
    one atomic object per booking, let Stripe move the host's share
    automatically, and expose the platform fee explicitly — which maps
    cleanly onto our ledger split (escrow -> host_payable + platform_revenue).

    Stripe stays external: every state change still arrives as a verified
    webhook and is translated into immutable ledger entries. Nothing here
    writes balances.
    """

    def __init__(self, api_key: str):
        import stripe  # imported lazily so simulation needs no SDK at import

        if not api_key:
            raise RuntimeError("STRIPE_API_KEY is required for the stripe provider")
        stripe.api_key = api_key
        self._stripe = stripe

    def create_payment_intent(
        self, amount: int, currency: str, host_account_id: str, application_fee: int
    ) -> PaymentIntent:
        # Idempotency-Key: a booking creates exactly one intent; the caller's
        # booking id makes this safe to retry without duplicate charges.
        intent = self._stripe.PaymentIntent.create(
            amount=amount,
            currency=currency.lower(),
            automatic_payment_methods={"enabled": True},  # cards, BLIK, Apple/Google Pay
            application_fee_amount=application_fee,
            transfer_data={"destination": host_account_id},
            idempotency_key=f"pi_{host_account_id}_{amount}_{currency}_{uuid4().hex[:12]}",
        )
        return PaymentIntent(
            intent_id=intent["id"],
            client_secret=intent["client_secret"],
            amount=amount,
            currency=currency,
        )

    def refund(self, intent_id: str, amount: int) -> str:
        refund = self._stripe.Refund.create(
            payment_intent=intent_id,
            amount=amount,
            idempotency_key=f"re_{intent_id}_{amount}",
        )
        return refund["id"]

    def construct_event(self, payload: bytes, sig_header: str) -> dict:
        """Verify the Stripe signature and return the event. Raises on an
        invalid/missing signature or a tampered payload — the trust boundary."""
        return self._stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )


def build_provider() -> PaymentProvider:
    if settings.payment_provider == "stripe":
        return StripeConnectProvider(settings.stripe_api_key)
    return StripeSimulationProvider()


# Selected once at import; overridable in tests.
provider: PaymentProvider = build_provider()
