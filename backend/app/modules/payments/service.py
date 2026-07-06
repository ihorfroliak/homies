"""Payments application service: intent creation, webhook processing,
refunds and host payouts. Every money movement posts a ledger entry —
the ledger is the source of truth (docs/strategy/00-DECISIONS.md D2)."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.modules.booking.models import Booking
from app.modules.events import service as events
from app.modules.ledger import service as ledger
from app.modules.payments.models import Payment
from app.modules.payments.provider import provider


def platform_fee(amount: int) -> int:
    return amount * settings.platform_fee_bps // 10_000


def create_payment_for_booking(db: Session, booking: Booking, host_id: str) -> Payment:
    from app.modules.identity.models import HostProfile

    host_profile = db.get(HostProfile, host_id)
    host_account = host_profile.stripe_account_id if host_profile else ""
    intent = provider.create_payment_intent(
        amount=booking.total_amount,
        currency=booking.currency,
        host_account_id=host_account,
        application_fee=platform_fee(booking.total_amount),
    )
    payment = Payment(
        booking_id=booking.id,
        provider_intent_id=intent.intent_id,
        amount=booking.total_amount,
        currency=booking.currency,
    )
    db.add(payment)
    db.flush()
    return payment


def process_intent_succeeded(db: Session, intent_id: str) -> Payment:
    """Webhook handler body. Idempotent AND concurrency-safe: the payment row
    is locked FOR UPDATE so two simultaneous deliveries of the same event
    serialize — the second sees 'succeeded' and no-ops (no double capture)."""
    payment = db.scalar(
        select(Payment).where(Payment.provider_intent_id == intent_id).with_for_update()
    )
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown payment intent")
    if payment.status == "succeeded":
        return payment  # replay — already processed
    if payment.status != "requires_payment":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Payment is {payment.status}")

    booking = db.get(Booking, payment.booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Booking is gone")

    if booking.status == "cancelled":
        # D5 RC-2: late success after cancellation. Stripe already captured
        # the money — record the capture AND refund it immediately so a
        # cancelled booking never holds escrow (invariant I6).
        payment.status = "succeeded"
        ledger.post_entry(
            db,
            kind="payment_captured",
            lines=[
                (ledger.PROVIDER_CASH, payment.amount),
                (ledger.BOOKING_ESCROW, -payment.amount),
            ],
            currency=payment.currency,
            booking_id=booking.id,
            payment_id=payment.id,
            description=f"Late capture after cancellation, booking {booking.id}",
        )
        provider.refund(payment.provider_intent_id, payment.amount)
        payment.status = "refunded"
        ledger.post_entry(
            db,
            kind="refund",
            lines=[
                (ledger.BOOKING_ESCROW, payment.amount),
                (ledger.PROVIDER_CASH, -payment.amount),
            ],
            currency=payment.currency,
            booking_id=booking.id,
            payment_id=payment.id,
            description=f"Auto-refund of late capture, booking {booking.id}",
        )
        audit(
            db,
            actor="system",
            action="payment.late_success_refunded",
            entity_type="payment",
            entity_id=payment.id,
            data={"intent_id": intent_id, "amount": payment.amount},
        )
        return payment

    if booking.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Booking is not awaiting payment")

    payment.status = "succeeded"
    booking.status = "confirmed"
    booking.operational_state = "checkin_available"
    ledger.post_entry(
        db,
        kind="payment_captured",
        lines=[
            (ledger.PROVIDER_CASH, payment.amount),  # debit: cash at provider grows
            (ledger.BOOKING_ESCROW, -payment.amount),  # credit: we owe this stay
        ],
        currency=payment.currency,
        booking_id=booking.id,
        payment_id=payment.id,
        description=f"Capture for booking {booking.id}",
    )
    audit(
        db,
        actor="system",
        action="payment.succeeded",
        entity_type="payment",
        entity_id=payment.id,
        data={"intent_id": intent_id, "amount": payment.amount},
    )
    events.emit(
        db, events.BOOKING_CONFIRMED, correlation_id=booking.id,
        payload={"amount": payment.amount, "currency": payment.currency},
        dedup_key=f"{events.BOOKING_CONFIRMED}:{booking.id}",
    )
    # Managed pilot: check-in instructions become available at confirmation
    # (no scheduler yet; a T-24h timer is a later refinement).
    events.emit(
        db, events.CHECKIN_AVAILABLE, correlation_id=booking.id,
        payload={"check_in": booking.check_in.isoformat()},
        dedup_key=f"{events.CHECKIN_AVAILABLE}:{booking.id}",
    )
    return payment


def process_intent_failed(db: Session, intent_id: str) -> Payment | None:
    """payment_intent.payment_failed: mark the payment failed and free the
    dates. Idempotent; never touches the ledger (no money moved)."""
    payment = db.scalar(select(Payment).where(Payment.provider_intent_id == intent_id))
    if payment is None:
        return None
    if payment.status in ("failed", "refunded"):
        return payment
    if payment.status == "succeeded":
        # A failure after success is contradictory — do not unwind money here;
        # surface for reconciliation instead.
        audit(
            db, actor="system", action="payment.failed_after_success",
            entity_type="payment", entity_id=payment.id, data={"intent_id": intent_id},
        )
        return payment
    payment.status = "failed"
    booking = db.get(Booking, payment.booking_id)
    if booking is not None and booking.status == "pending":
        booking.status = "payment_failed"
    audit(
        db, actor="system", action="payment.failed",
        entity_type="payment", entity_id=payment.id, data={"intent_id": intent_id},
    )
    return payment


def process_charge_refunded(db: Session, intent_id: str) -> Payment | None:
    """charge.refunded from Stripe (e.g. an out-of-band or dispute refund).
    Reconciles the ledger if we have not already recorded the refund.
    Idempotent."""
    payment = db.scalar(select(Payment).where(Payment.provider_intent_id == intent_id))
    if payment is None or payment.status != "succeeded":
        return payment
    booking = db.get(Booking, payment.booking_id)
    if booking is not None and booking.payout_status != "none":
        raise HTTPException(status.HTTP_409_CONFLICT, "Refund after payout needs clawback flow")
    payment.status = "refunded"
    ledger.post_entry(
        db,
        kind="refund",
        lines=[
            (ledger.BOOKING_ESCROW, payment.amount),
            (ledger.PROVIDER_CASH, -payment.amount),
        ],
        currency=payment.currency,
        booking_id=payment.booking_id,
        payment_id=payment.id,
        description=f"Stripe charge.refunded for booking {payment.booking_id}",
    )
    if booking is not None and booking.status in ("pending", "confirmed"):
        booking.status = "cancelled"
    audit(
        db, actor="system", action="payment.refunded_via_stripe",
        entity_type="payment", entity_id=payment.id, data={"intent_id": intent_id},
    )
    return payment


def refund_booking(db: Session, booking: Booking, actor: str) -> Payment | None:
    """Full refund (D4 policy simplification). Reverses escrow."""
    payment = db.scalar(select(Payment).where(Payment.booking_id == booking.id))
    if payment is None:
        return None
    if payment.status == "requires_payment":
        payment.status = "voided"  # nothing was captured
        return payment
    if payment.status != "succeeded":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot refund payment in {payment.status}")
    if booking.payout_status != "none":
        # Post-payout refunds need a host clawback flow — explicitly out of D4 scope.
        raise HTTPException(status.HTTP_409_CONFLICT, "Refund after payout is not supported yet")

    provider.refund(payment.provider_intent_id, payment.amount)
    payment.status = "refunded"
    ledger.post_entry(
        db,
        kind="refund",
        lines=[
            (ledger.BOOKING_ESCROW, payment.amount),  # debit: obligation released
            (ledger.PROVIDER_CASH, -payment.amount),  # credit: cash returned to guest
        ],
        currency=payment.currency,
        booking_id=booking.id,
        payment_id=payment.id,
        description=f"Full refund for booking {booking.id}",
    )
    audit(
        db,
        actor=actor,
        action="payment.refunded",
        entity_type="payment",
        entity_id=payment.id,
        data={"amount": payment.amount},
    )
    return payment


def run_host_payout(db: Session, host_id: str, actor: str) -> dict:
    """Allocate earnings and simulate the transfer for every completed,
    paid, not-yet-paid-out booking of this host. Idempotent: bookings are
    selected by payout_status='none' and flipped in the same transaction."""
    from app.modules.identity.models import HostProfile
    from app.modules.listings.models import Listing

    profile = db.get(HostProfile, host_id)
    if profile is None or profile.onboarding_state != "payout_ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Host is not payout-ready")

    listing_ids = db.scalars(select(Listing.id).where(Listing.host_id == host_id)).all()
    bookings = list(
        db.scalars(
            select(Booking)
            .where(
                Booking.listing_id.in_(listing_ids),
                Booking.status == "completed",
                Booking.payout_status == "none",
            )
            .with_for_update()
        )
    )
    paid_total = 0
    fee_total = 0
    payable = ledger.host_payable_code(host_id)
    for booking in bookings:
        payment = db.scalar(
            select(Payment).where(
                Payment.booking_id == booking.id, Payment.status == "succeeded"
            )
        )
        if payment is None:
            continue  # unpaid or refunded booking never pays out
        fee = platform_fee(booking.total_amount)
        net = booking.total_amount - fee
        allocation_lines = [
            (ledger.BOOKING_ESCROW, booking.total_amount),
            (payable, -net),
        ]
        if fee > 0:  # a zero line would violate the ledger's no-zero-lines rule
            allocation_lines.append((ledger.PLATFORM_REVENUE, -fee))
        ledger.post_entry(
            db,
            kind="payout_allocated",
            lines=allocation_lines,
            currency=booking.currency,
            booking_id=booking.id,
            description=f"Earnings allocation, fee {settings.platform_fee_bps} bps",
        )
        ledger.post_entry(
            db,
            kind="payout_sent",
            lines=[
                (payable, net),
                (ledger.PROVIDER_CASH, -net),  # money leaves the provider to host's bank
            ],
            currency=booking.currency,
            booking_id=booking.id,
            description=f"Payout to host {host_id} (simulated transfer)",
        )
        booking.payout_status = "paid"
        if booking.operational_state in ("none", "checkin_available", "checked_in"):
            booking.operational_state = "checked_out"
        events.emit(
            db, events.PAYOUT_EXECUTED, correlation_id=booking.id,
            payload={"net": net, "fee": fee, "currency": booking.currency, "host_id": host_id},
            dedup_key=f"{events.PAYOUT_EXECUTED}:{booking.id}",
        )
        paid_total += net
        fee_total += fee
    # Invariant I5 (D5): escrow may never go negative. A violation means an
    # over-allocation bug — abort the whole run rather than move money.
    if ledger.account_balance(db, ledger.BOOKING_ESCROW) > 0:
        db.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Ledger invariant violated: booking_escrow over-released; payout run aborted",
        )
    audit(
        db,
        actor=actor,
        action="payout.run",
        entity_type="host",
        entity_id=host_id,
        data={"bookings": len(bookings), "paid_total": paid_total, "fee_total": fee_total},
    )
    return {"host_id": host_id, "bookings_paid": len(bookings), "paid_total": paid_total, "fee_total": fee_total}
