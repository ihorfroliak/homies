"""Card disputes / chargebacks (FIN-03).

Before this, a `charge.dispute.*` webhook was stored, stamped processed and
acknowledged with no effect: the money was gone from the provider balance and
the ledger never knew. Reconciliation could not see it either — a payment with
one capture and no refund is the shape of a *healthy* payment — so the loss was
real, unmodelled and invisible.

## What actually happens at the provider

A dispute withdraws money **immediately**, at creation, not at resolution: the
disputed amount and a non-refundable fee both leave the balance while the
outcome is still unknown. Closing the dispute returns the amount only if it is
won; the fee never comes back. So the ledger entries follow the *money*:
creation moves it, `won` moves it back, and `lost` posts nothing at all —
by then nothing further has moved.

## Who bears the loss

Depends on whether the platform still owed the host for that stay:

* **Not yet paid out** — the obligation is still in `booking_escrow`. The
  dispute discharges it: escrow is debited and cash credited, the same shape as
  a refund. The host is simply never paid, so nobody is chased for anything.
* **Already paid out** — the obligation is gone and the money with it. The
  platform absorbs the amount into `chargeback_loss`.

The platform absorbing it is not a policy preference, it is the only truthful
entry available today: there is no clawback mechanism (FIN-02) and no host
agreement to invoke — the agency contract is still being drafted. If the money
is later recovered from a host, that is a new compensating entry moving it out
of `chargeback_loss`; the ledger is append-only and nothing here is rewritten.

Note the deeper mismatch this exposes, which FIN-02 must eventually resolve:
with Stripe destination charges the host's share leaves at *capture*, so
`payout_sent` is bookkeeping, not a transfer. "Not yet paid out" is therefore
true in our books while the connected account may already hold the money.
Recovering it for real needs a transfer reversal, which this system does not
implement.

## Ordering

Stripe can deliver out of order. A closure for a dispute we never opened is
recorded as `needs_review` with no ledger effect rather than guessed at: no
withdrawal was ever booked, so there is nothing to reverse, and inventing one
would put money in the ledger that never moved.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import business_metrics as metrics
from app.core.audit import audit
from app.modules.booking.models import Booking
from app.modules.ledger import service as ledger
from app.modules.payments.models import Dispute, Payment

OPEN = "open"
WON = "won"
LOST = "lost"
NEEDS_REVIEW = "needs_review"

# Entry kinds. Kept distinct from "refund" so reporting can tell a guest who
# asked for their money back from a guest who went to their bank — the two mean
# very different things about the business, and the card networks only threaten
# processing over the second.
KIND_CHARGEBACK = "chargeback"
KIND_CHARGEBACK_REVERSED = "chargeback_reversed"
KIND_DISPUTE_FEE = "dispute_fee"


def fee_from_event(dispute_object: dict) -> int:
    """The provider's dispute fee, in minor units.

    Stripe reports it inside `balance_transactions[].fee`. Absent (or zero in
    test mode) is normal and must not be an error — a zero fee simply means no
    fee entry is posted, since the ledger rejects zero-amount lines.
    """
    total = 0
    for txn in dispute_object.get("balance_transactions") or []:
        try:
            total += abs(int(txn.get("fee") or 0))
        except (TypeError, ValueError):
            continue
    return total


def process_dispute_created(
    db: Session,
    *,
    provider_dispute_id: str,
    intent_id: str,
    amount: int,
    fee: int = 0,
    currency: str = "",
    reason: str = "",
) -> Dispute:
    """Record the dispute and post the withdrawal. Idempotent per dispute id."""
    existing = db.scalar(
        select(Dispute)
        .where(Dispute.provider_dispute_id == provider_dispute_id)
        .with_for_update()
    )
    if existing is not None:
        return existing  # replay — the withdrawal is already in the ledger

    payment = db.scalar(
        select(Payment).where(Payment.provider_intent_id == intent_id).with_for_update()
    )
    if payment is None:
        # Unknown intent: fail loud. A 5xx leaves processed_at NULL so the
        # event stays dead-lettered and Stripe retries, rather than us
        # acknowledging a money movement we cannot place.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown payment intent for dispute")

    booking = db.get(Booking, payment.booking_id)
    # The decisive question, and the reason it is persisted on the row: was the
    # platform's obligation to the host still outstanding when this landed?
    already_paid_out = booking is not None and booking.payout_status != "none"

    dispute = Dispute(
        provider_dispute_id=provider_dispute_id,
        payment_id=payment.id,
        booking_id=payment.booking_id,
        amount=amount,
        fee=fee,
        currency=currency or payment.currency,
        reason=reason,
        status=OPEN,
        absorbed_by_platform=already_paid_out,
    )
    db.add(dispute)
    db.flush()

    counter_account = ledger.CHARGEBACK_LOSS if already_paid_out else ledger.BOOKING_ESCROW
    ledger.post_entry(
        db,
        kind=KIND_CHARGEBACK,
        lines=[
            # Debit whichever obligation this discharges (escrow) or the loss it
            # creates (chargeback_loss); credit the cash that left the provider.
            (counter_account, amount),
            (ledger.PROVIDER_CASH, -amount),
        ],
        currency=dispute.currency,
        booking_id=payment.booking_id,
        payment_id=payment.id,
        description=f"Dispute {provider_dispute_id} opened ({reason or 'no reason given'})",
    )
    if fee > 0:  # a zero line would violate the ledger's no-zero-lines rule
        ledger.post_entry(
            db,
            kind=KIND_DISPUTE_FEE,
            lines=[(ledger.DISPUTE_FEE_EXPENSE, fee), (ledger.PROVIDER_CASH, -fee)],
            currency=dispute.currency,
            booking_id=payment.booking_id,
            payment_id=payment.id,
            description=f"Provider dispute fee for {provider_dispute_id}",
        )

    payment.status = "charged_back"
    metrics.record_payment(db, "charged_back")
    if booking is not None:
        # A distinct state, not `cancelled` — the same reasoning as D-22 for
        # `expired`. It also removes the booking from the payout query, which
        # selects status == "completed": without this the host could still be
        # paid out of money the platform no longer holds.
        booking.status = "charged_back"
        metrics.record_booking(db, "charged_back")
    audit(
        db,
        actor="system",
        action="payment.disputed",
        entity_type="payment",
        entity_id=payment.id,
        data={
            "dispute_id": provider_dispute_id,
            "amount": amount,
            "fee": fee,
            "absorbed_by_platform": already_paid_out,
        },
    )
    return dispute


def process_dispute_closed(db: Session, *, provider_dispute_id: str, won: bool) -> Dispute:
    """Resolve a dispute. Only a win moves money; a loss confirms what already left."""
    dispute = db.scalar(
        select(Dispute)
        .where(Dispute.provider_dispute_id == provider_dispute_id)
        .with_for_update()
    )
    if dispute is None:
        # Closure without an opening. Nothing was ever withdrawn in our books,
        # so there is nothing to reverse; recording it visibly beats inventing
        # a money movement or silently dropping the event.
        dispute = Dispute(
            provider_dispute_id=provider_dispute_id,
            payment_id="",
            amount=0,
            fee=0,
            currency="",
            status=NEEDS_REVIEW,
            closed_at=datetime.now(timezone.utc),
        )
        db.add(dispute)
        return dispute

    if dispute.status in (WON, LOST):
        return dispute  # replay

    dispute.status = WON if won else LOST
    dispute.closed_at = datetime.now(timezone.utc)

    if won:
        # Reverse into the SAME account that was debited when it opened —
        # `absorbed_by_platform` is read from the row, not recomputed, because
        # the booking's payout state may have moved on in the months between.
        counter_account = (
            ledger.CHARGEBACK_LOSS if dispute.absorbed_by_platform else ledger.BOOKING_ESCROW
        )
        ledger.post_entry(
            db,
            kind=KIND_CHARGEBACK_REVERSED,
            lines=[
                (ledger.PROVIDER_CASH, dispute.amount),
                (counter_account, -dispute.amount),
            ],
            currency=dispute.currency,
            booking_id=dispute.booking_id,
            payment_id=dispute.payment_id or None,
            description=f"Dispute {provider_dispute_id} won; funds reinstated",
        )
        # The fee is deliberately NOT reversed: the provider keeps it whatever
        # the outcome, so winning still costs money.
    # A lost dispute posts nothing. The money left when the dispute opened;
    # closing it confirms the loss rather than causing it.

    audit(
        db,
        actor="system",
        action="payment.dispute_closed",
        entity_type="payment",
        entity_id=dispute.payment_id or provider_dispute_id,
        data={"dispute_id": provider_dispute_id, "outcome": dispute.status},
    )
    return dispute
