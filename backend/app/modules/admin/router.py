"""Admin visibility: raw system state, no dashboards (D4 scope)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import AuditLog
from app.core.db import get_db
from app.core.security import require_role
from app.modules.booking.models import Booking
from app.modules.identity.models import User
from app.modules.ledger import service as ledger
from app.modules.ledger.models import JournalEntry
from app.modules.payments.models import Payment

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))]
)


def _page(limit: int, offset: int):
    return min(limit, 100), max(offset, 0)


@router.get("/users")
def list_users(limit: int = Query(50), offset: int = 0, db: Session = Depends(get_db)):
    limit, offset = _page(limit, offset)
    users = db.scalars(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
    return [
        {"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name} for u in users
    ]


@router.get("/bookings")
def list_bookings(limit: int = Query(50), offset: int = 0, db: Session = Depends(get_db)):
    limit, offset = _page(limit, offset)
    bookings = db.scalars(
        select(Booking).order_by(Booking.created_at.desc()).limit(limit).offset(offset)
    )
    return [
        {
            "id": b.id,
            "listing_id": b.listing_id,
            "guest_id": b.guest_id,
            "status": b.status,
            "payout_status": b.payout_status,
            "check_in": b.check_in.isoformat(),
            "check_out": b.check_out.isoformat(),
            "total_amount": b.total_amount,
            "currency": b.currency,
        }
        for b in bookings
    ]


@router.get("/payments")
def list_payments(limit: int = Query(50), offset: int = 0, db: Session = Depends(get_db)):
    limit, offset = _page(limit, offset)
    payments = db.scalars(
        select(Payment).order_by(Payment.created_at.desc()).limit(limit).offset(offset)
    )
    return [
        {
            "id": p.id,
            "booking_id": p.booking_id,
            "intent_id": p.provider_intent_id,
            "status": p.status,
            "amount": p.amount,
            "currency": p.currency,
        }
        for p in payments
    ]


@router.get("/ledger/entries")
def list_ledger_entries(
    limit: int = Query(50), offset: int = 0, db: Session = Depends(get_db)
):
    limit, offset = _page(limit, offset)
    entries = db.scalars(
        select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(limit).offset(offset)
    )
    return [
        {
            "id": e.id,
            "kind": e.kind,
            "booking_id": e.booking_id,
            "currency": e.currency,
            "description": e.description,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.get("/ledger/balances")
def ledger_balances(db: Session = Depends(get_db)):
    return ledger.all_balances(db)


@router.get("/ledger/reconciliation")
def ledger_reconciliation(db: Session = Depends(get_db)):
    return ledger.reconcile(db)


@router.get("/payments/reconciliation")
def payments_reconciliation(db: Session = Depends(get_db)):
    """Payment<->ledger consistency + (when Stripe keys are present) a
    Stripe-balance cross-check. Used as the daily reconciliation report."""
    from app.modules.payments import reconciliation
    from app.modules.payments.provider import provider

    report = reconciliation.payment_ledger_consistency(db)
    report["stripe"] = reconciliation.stripe_ledger_reconciliation(db, provider)
    return report


@router.get("/audit")
def list_audit(limit: int = Query(100), offset: int = 0, db: Session = Depends(get_db)):
    limit, offset = _page(limit, offset)
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    return [
        {
            "id": a.id,
            "actor": a.actor,
            "action": a.action,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "data": a.data,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]
