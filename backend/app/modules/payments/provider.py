"""Payment provider abstraction — the Stripe Connect seam.

D4 ships the simulation implementation. The real StripeConnectProvider
replaces it behind the same interface: create_payment_intent maps to
PaymentIntent with transfer_data[destination] + application_fee_amount
(destination charge on the host's connected account), refund maps to
Refund, payout is handled by Stripe's payout schedule. Webhook signature
verification is a must in the real implementation.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4


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


provider: PaymentProvider = StripeSimulationProvider()
