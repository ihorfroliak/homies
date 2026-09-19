"""FIN-03: chargebacks in the ledger.

The defect this closes was not a crash. A `charge.dispute.*` webhook was
stored, stamped processed and acknowledged with no effect, so the money left
the provider and the ledger never knew — and reconciliation could not tell,
because a payment with one capture and no refund is the shape of a *healthy*
payment. Every test here is about a number being wrong while everything still
returns 200.
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.modules.admin import kpi as kpi_service
from app.modules.booking.models import Booking
from app.modules.ledger import service as ledger
from app.modules.payments import disputes, reconciliation
from app.modules.payments.models import Dispute, Payment

AMOUNT = 100_000
FEE = 6_000


@pytest.fixture
def db(client):  # noqa: ARG001 — client builds the schema and session factory
    from tests.conftest import TestingSession

    with TestingSession() as session:
        yield session


def _paid_booking(db, *, payout_status="none", total=AMOUNT):
    booking = Booking(
        guest_id="g1", listing_id="l1",
        # Availability is keyed on the property; these fixtures never go
        # through the booking endpoint, so the link is supplied directly.
        property_id="p1",
        check_in=date(2026, 3, 1), check_out=date(2026, 3, 5),
        total_amount=total, currency="PLN", status="completed",
        payout_status=payout_status, idempotency_key=f"k-{payout_status}-{total}",
    )
    db.add(booking)
    db.flush()
    payment = Payment(
        booking_id=booking.id, provider_intent_id=f"pi_{booking.id}",
        status="succeeded", amount=total, currency="PLN",
    )
    db.add(payment)
    db.flush()
    # The capture that put the money in escrow.
    ledger.post_entry(
        db, kind="payment_captured",
        lines=[(ledger.PROVIDER_CASH, total), (ledger.BOOKING_ESCROW, -total)],
        currency="PLN", booking_id=booking.id, payment_id=payment.id,
    )
    db.commit()
    return booking, payment


def _open_dispute(db, payment, *, fee=FEE, dispute_id="dp_1"):
    d = disputes.process_dispute_created(
        db, provider_dispute_id=dispute_id, intent_id=payment.provider_intent_id,
        amount=AMOUNT, fee=fee, currency="PLN", reason="fraudulent",
    )
    db.commit()
    return d


# --- the money, before payout -------------------------------------------------


def test_dispute_before_payout_discharges_escrow_and_removes_the_cash(db):
    """Concrete numbers, end to end.

    Capture put +100000 in provider_cash and -100000 in escrow. The dispute
    takes the cash back and releases the obligation, so both return to zero —
    the platform is square and the host is simply never paid.
    """
    _, payment = _paid_booking(db)
    assert ledger.account_balance(db, ledger.PROVIDER_CASH) == AMOUNT
    assert ledger.account_balance(db, ledger.BOOKING_ESCROW) == -AMOUNT

    _open_dispute(db, payment, fee=0)

    assert ledger.account_balance(db, ledger.PROVIDER_CASH) == 0
    assert ledger.account_balance(db, ledger.BOOKING_ESCROW) == 0
    assert ledger.account_balance(db, ledger.CHARGEBACK_LOSS) == 0, (
        "nobody absorbed a loss: the obligation was still ours to cancel"
    )
    assert ledger.reconcile(db)["ok"] is True


def test_dispute_after_payout_lands_in_chargeback_loss(db):
    """The case the old code refused with a 409 and then dropped.

    The obligation is already discharged, so there is no escrow to release —
    the money is simply gone, and the ledger has to say whose it was.
    """
    _, payment = _paid_booking(db, payout_status="paid")
    _open_dispute(db, payment, fee=0)

    assert ledger.account_balance(db, ledger.CHARGEBACK_LOSS) == AMOUNT
    assert ledger.account_balance(db, ledger.BOOKING_ESCROW) == -AMOUNT, (
        "escrow must be untouched: this booking's obligation was already settled"
    )
    assert ledger.reconcile(db)["ok"] is True


def test_dispute_fee_is_a_separate_expense(db):
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=FEE)

    assert ledger.account_balance(db, ledger.DISPUTE_FEE_EXPENSE) == FEE
    assert ledger.account_balance(db, ledger.PROVIDER_CASH) == -FEE, (
        "the fee leaves the balance on top of the disputed amount"
    )
    assert ledger.reconcile(db)["ok"] is True


def test_zero_fee_posts_no_entry(db):
    """The ledger rejects zero-amount lines; a free dispute must not crash."""
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=0)

    entries = db.scalars(select(kpi_service.JournalEntry.kind)).all()
    assert "dispute_fee" not in entries
    assert ledger.reconcile(db)["ok"] is True


# --- outcomes -----------------------------------------------------------------


def test_won_dispute_reinstates_the_amount_but_never_the_fee(db):
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=FEE)

    disputes.process_dispute_closed(db, provider_dispute_id="dp_1", won=True)
    db.commit()

    assert ledger.account_balance(db, ledger.PROVIDER_CASH) == AMOUNT - FEE, (
        "winning returns the disputed amount; the provider keeps the fee"
    )
    assert ledger.account_balance(db, ledger.DISPUTE_FEE_EXPENSE) == FEE
    assert ledger.reconcile(db)["ok"] is True


def test_lost_dispute_posts_no_further_entry(db):
    """The money left when the dispute opened. Closing confirms, it does not move."""
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=0)
    before = len(db.scalars(select(kpi_service.JournalEntry.id)).all())

    disputes.process_dispute_closed(db, provider_dispute_id="dp_1", won=False)
    db.commit()

    after = db.scalars(select(kpi_service.JournalEntry.id)).all()
    assert len(after) == before, "a lost dispute must not double-count the loss"
    assert ledger.account_balance(db, ledger.PROVIDER_CASH) == 0


def test_win_reverses_the_account_that_was_actually_debited(db):
    """Reversal follows the stored decision, not a recomputed one.

    A dispute can close months later. If the reversal recomputed "was it paid
    out?" at closing time it could credit escrow for money that was taken from
    chargeback_loss, quietly inventing an obligation.
    """
    booking, payment = _paid_booking(db, payout_status="paid")
    _open_dispute(db, payment, fee=0)
    assert ledger.account_balance(db, ledger.CHARGEBACK_LOSS) == AMOUNT

    booking.payout_status = "none"  # state moved on in the meantime
    db.commit()

    disputes.process_dispute_closed(db, provider_dispute_id="dp_1", won=True)
    db.commit()

    assert ledger.account_balance(db, ledger.CHARGEBACK_LOSS) == 0
    assert ledger.account_balance(db, ledger.BOOKING_ESCROW) == -AMOUNT, (
        "escrow must be untouched by a reversal that never debited it"
    )
    assert ledger.reconcile(db)["ok"] is True


# --- idempotency and ordering -------------------------------------------------


def test_duplicate_delivery_withdraws_once(db):
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=FEE)
    _open_dispute(db, payment, fee=FEE)  # same dispute id — Stripe retry

    assert ledger.account_balance(db, ledger.PROVIDER_CASH) == -FEE
    assert len(db.scalars(select(Dispute.id)).all()) == 1


def test_replayed_closure_reinstates_once(db):
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=0)
    for _ in range(3):
        disputes.process_dispute_closed(db, provider_dispute_id="dp_1", won=True)
        db.commit()

    assert ledger.account_balance(db, ledger.PROVIDER_CASH) == AMOUNT


def test_closure_without_an_opening_is_recorded_not_guessed(db):
    """Out-of-order delivery must not invent a money movement."""
    d = disputes.process_dispute_closed(db, provider_dispute_id="dp_unknown", won=True)
    db.commit()

    assert d.status == "needs_review"
    assert db.scalars(select(kpi_service.JournalEntry.id)).all() == []
    assert reconciliation.payment_ledger_consistency(db)["ok"] is False, (
        "an unplaceable dispute must not stay invisible"
    )


def test_dispute_for_an_unknown_intent_fails_loud(db):
    """A 5xx leaves processed_at NULL so the event dead-letters and retries,
    rather than acknowledging a movement we cannot place."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        disputes.process_dispute_created(
            db, provider_dispute_id="dp_x", intent_id="pi_nope",
            amount=AMOUNT, fee=0, currency="PLN",
        )


# --- state --------------------------------------------------------------------


def test_disputed_booking_cannot_be_paid_out(db):
    """The hole this closes: paying a host from money the platform lost.

    The payout query selects status == "completed"; a charged-back booking must
    leave that set.
    """
    booking, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=0)

    db.refresh(booking)
    assert booking.status == "charged_back"
    payable = db.scalars(
        select(Booking).where(Booking.status == "completed", Booking.payout_status == "none")
    ).all()
    assert booking.id not in [b.id for b in payable]


def test_chargeback_is_not_recorded_as_a_refund(db):
    """A guest who asked for their money back and a guest who went to their
    bank mean different things; only the second threatens card processing."""
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=0)

    db.refresh(payment)
    assert payment.status == "charged_back"
    kinds = set(db.scalars(select(kpi_service.JournalEntry.kind)).all())
    assert "chargeback" in kinds
    assert "refund" not in kinds


# --- reporting ----------------------------------------------------------------


WINDOW = kpi_service.Window(start=date(2026, 1, 1), end=date(2030, 1, 1))


def test_kpi_reports_chargebacks_separately_from_refunds(db):
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=FEE)

    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.money["charged_back"] == AMOUNT
    assert report.money["refunded"] == 0
    assert report.money["dispute_fees"] == FEE
    assert report.money["gmv_net"] == 0, "disputed money is not net revenue"
    assert report.ratios_bps["chargeback_rate"] == 10_000


def test_won_dispute_does_not_count_against_the_chargeback_rate(db):
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=0)
    disputes.process_dispute_closed(db, provider_dispute_id="dp_1", won=True)
    db.commit()

    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.ratios_bps["chargeback_rate"] == 0
    assert report.money["gmv_net"] == AMOUNT


def test_kpi_no_longer_claims_disputes_are_unanswerable(db):
    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    payload = kpi_service.as_payload(report)
    assert not any("hargeback" in u["kpi"] for u in payload["unavailable"]), (
        "the endpoint must stop advertising a gap it has closed"
    )


def test_unknown_entry_kinds_are_surfaced_not_swallowed(db):
    """N-13: every other ledger reader is kind-agnostic or fails loud; this one
    returned HTTP 200 with a smaller number and no indication of the omission."""
    ledger.post_entry(
        db, kind="some_future_kind",
        lines=[(ledger.PROVIDER_CASH, 5_000), (ledger.BOOKING_ESCROW, -5_000)],
        currency="PLN",
    )
    db.commit()

    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.unknown_kinds == ["some_future_kind"]
    assert kpi_service.as_payload(report)["unreadable_entry_kinds"] == ["some_future_kind"]


def test_known_kinds_do_not_trip_the_probe(db):
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=FEE)
    disputes.process_dispute_closed(db, provider_dispute_id="dp_1", won=True)
    db.commit()

    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.unknown_kinds == []


def test_reconciliation_flags_a_chargeback_the_ledger_missed(db):
    """Exactly the state the old 409-then-drop path left behind."""
    _, payment = _paid_booking(db)
    payment.status = "charged_back"  # provider took it; no ledger entry posted
    db.commit()

    report = reconciliation.payment_ledger_consistency(db)
    assert payment.id in report["charged_back_without_entry"]
    assert report["ok"] is False


def test_reconciliation_is_clean_on_a_properly_recorded_dispute(db):
    _, payment = _paid_booking(db)
    _open_dispute(db, payment, fee=FEE)

    report = reconciliation.payment_ledger_consistency(db)
    assert report["charged_back_without_entry"] == []
    assert report["ok"] is True


# --- webhook path -------------------------------------------------------------


def _dispute_event(kind: str, *, dispute_id="dp_evt", intent_id="pi_x", status_="warning_needs_response"):
    return {
        "id": f"evt_{kind}_{dispute_id}",
        "type": kind,
        "data": {
            "object": {
                "id": dispute_id,
                "payment_intent": intent_id,
                "amount": AMOUNT,
                "currency": "pln",
                "reason": "fraudulent",
                "status": status_,
                "balance_transactions": [{"fee": FEE, "amount": -AMOUNT}],
            }
        },
    }


def test_intent_is_extracted_from_a_dispute_event():
    from app.modules.payments.router import _intent_id_of

    assert _intent_id_of(_dispute_event("charge.dispute.created")) == "pi_x"
    assert _intent_id_of(_dispute_event("charge.dispute.closed")) == "pi_x"


def test_fee_is_read_from_balance_transactions():
    obj = _dispute_event("charge.dispute.created")["data"]["object"]
    assert disputes.fee_from_event(obj) == FEE
    assert disputes.fee_from_event({}) == 0
    assert disputes.fee_from_event({"balance_transactions": [{"fee": None}]}) == 0
