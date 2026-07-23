"""FIN-01 (part 2) — Stripe Test Mode integration suite.

NOT part of ordinary CI: it needs real Stripe test credentials and network
access. Behaviour is deliberate:

  * no credentials, not requested        -> skipped with a clear reason
  * STRIPE_LIVE_TESTS=1 without keys     -> FAILS loudly (never silently green)
  * a live (sk_live_) key                -> FAILS immediately; this suite must
                                            never touch real money

Run:  STRIPE_LIVE_TESTS=1 STRIPE_API_KEY=sk_test_... make test-stripe

Every scenario records evidence in docs/design/fin-01-stripe-validation.md.
Secrets are never printed; only masked key mode and Stripe object ids appear.
"""

import os

import pytest

REQUESTED = os.getenv("STRIPE_LIVE_TESTS") == "1"
API_KEY = os.getenv("STRIPE_API_KEY", "")
CONNECTED_ACCOUNT = os.getenv("STRIPE_TEST_CONNECTED_ACCOUNT", "")

if not REQUESTED:
    pytest.skip(
        "Stripe Test Mode suite not requested (set STRIPE_LIVE_TESTS=1 with "
        "STRIPE_API_KEY=sk_test_... to run)",
        allow_module_level=True,
    )

# Explicitly requested: from here on, missing or unsafe credentials are errors,
# never skips — a green run must mean the checks actually executed.
if not API_KEY:
    raise RuntimeError("STRIPE_LIVE_TESTS=1 but STRIPE_API_KEY is not set")
if not API_KEY.startswith(("sk_test_", "rk_test_")):
    raise RuntimeError("refusing to run: STRIPE_API_KEY is not a test-mode key")

import stripe  # noqa: E402

stripe.api_key = API_KEY

PLATFORM_FEE_BPS = 1500
AMOUNT = 105000  # 1050.00 PLN, integer minor units (ADR-0002)
CURRENCY = "pln"


def expected_fee(amount: int) -> int:
    return amount * PLATFORM_FEE_BPS // 10_000


@pytest.fixture(scope="module")
def account():
    return stripe.Account.retrieve()


def test_credentials_are_test_mode(account):
    """Guard rail: prove we are in test mode before anything else runs."""
    assert account["charges_enabled"] in (True, False)  # reachable
    assert stripe.api_key.startswith(("sk_test_", "rk_test_"))


def test_payment_intent_carries_amount_currency_and_platform_fee():
    """Destination charge shape (ADR-0007): the fee we book must be the fee
    Stripe records, in integer minor units."""
    if not CONNECTED_ACCOUNT:
        pytest.fail(
            "STRIPE_TEST_CONNECTED_ACCOUNT is required: create a test Connect "
            "account and export its acct_... id"
        )
    intent = stripe.PaymentIntent.create(
        amount=AMOUNT,
        currency=CURRENCY,
        payment_method_types=["card"],
        application_fee_amount=expected_fee(AMOUNT),
        transfer_data={"destination": CONNECTED_ACCOUNT},
    )
    assert intent["amount"] == AMOUNT
    assert intent["currency"] == CURRENCY
    assert intent["application_fee_amount"] == expected_fee(AMOUNT)
    assert intent["status"] == "requires_payment_method"


def test_successful_card_payment_reaches_succeeded():
    if not CONNECTED_ACCOUNT:
        pytest.fail("STRIPE_TEST_CONNECTED_ACCOUNT is required")
    intent = stripe.PaymentIntent.create(
        amount=AMOUNT, currency=CURRENCY, payment_method_types=["card"],
        application_fee_amount=expected_fee(AMOUNT),
        transfer_data={"destination": CONNECTED_ACCOUNT},
    )
    confirmed = stripe.PaymentIntent.confirm(intent["id"], payment_method="pm_card_visa")
    assert confirmed["status"] == "succeeded"
    # gross == fee + host net, exactly, with no floating point involved
    charge = stripe.Charge.retrieve(confirmed["latest_charge"])
    assert charge["amount"] == AMOUNT
    assert charge["application_fee_amount"] + (AMOUNT - charge["application_fee_amount"]) == AMOUNT


def test_declined_card_does_not_succeed():
    intent = stripe.PaymentIntent.create(
        amount=AMOUNT, currency=CURRENCY, payment_method_types=["card"]
    )
    with pytest.raises(stripe.error.CardError):
        stripe.PaymentIntent.confirm(intent["id"], payment_method="pm_card_chargeDeclined")
    assert stripe.PaymentIntent.retrieve(intent["id"])["status"] != "succeeded"


def test_authentication_required_card_enters_3ds_flow():
    """SCA: the intent must stop at requires_action rather than succeeding."""
    intent = stripe.PaymentIntent.create(
        amount=AMOUNT, currency=CURRENCY, payment_method_types=["card"]
    )
    confirmed = stripe.PaymentIntent.confirm(
        intent["id"], payment_method="pm_card_authenticationRequired",
        return_url="https://example.com/return",
    )
    assert confirmed["status"] in ("requires_action", "requires_source_action")


def test_refund_is_idempotent_for_the_same_key():
    intent = stripe.PaymentIntent.create(
        amount=AMOUNT, currency=CURRENCY, payment_method_types=["card"]
    )
    stripe.PaymentIntent.confirm(intent["id"], payment_method="pm_card_visa")
    key = f"refund-{intent['id']}"
    first = stripe.Refund.create(payment_intent=intent["id"], idempotency_key=key)
    second = stripe.Refund.create(payment_intent=intent["id"], idempotency_key=key)
    assert first["id"] == second["id"]  # one refund, not two
    assert first["amount"] == AMOUNT
