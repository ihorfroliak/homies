"""Admin visibility: raw system state, no dashboards (D4 scope)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.core.audit import AuditLog, audit
from app.core.db import get_db
from app.core.security import require_role
from app.modules.booking.models import Booking
from app.modules.events import service as events
from app.modules.events.models import Incident, Notification
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


class IncidentCreate(BaseModel):
    booking_id: str
    kind: str = "other"  # checkin_problem | damage | other
    note: str = ""


@router.post("/incidents", status_code=201)
def open_incident(body: IncidentCreate, user=Depends(require_role("admin")),
                  db: Session = Depends(get_db)):
    booking = db.get(Booking, body.booking_id)
    if booking is None:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    inc = Incident(booking_id=body.booking_id, kind=body.kind, note=body.note, opened_by=user.id)
    db.add(inc)
    db.flush()
    events.emit(
        db, events.INCIDENT_OPENED, correlation_id=body.booking_id,
        payload={"incident_id": inc.id, "kind": body.kind, "note": body.note},
        dedup_key=f"{events.INCIDENT_OPENED}:{inc.id}",
    )
    audit(db, actor=user.id, action="incident.opened", entity_type="incident", entity_id=inc.id)
    db.commit()
    return {"id": inc.id, "status": inc.status}


@router.get("/incidents")
def list_incidents(status: str | None = None, db: Session = Depends(get_db)):
    q = select(Incident).order_by(Incident.created_at.desc())
    if status:
        q = q.where(Incident.status == status)
    return [
        {"id": i.id, "booking_id": i.booking_id, "kind": i.kind, "note": i.note,
         "status": i.status, "created_at": i.created_at.isoformat()}
        for i in db.scalars(q.limit(100))
    ]


@router.get("/founder-feed")
def founder_feed(limit: int = Query(50), db: Session = Depends(get_db)):
    """Founder operational visibility: in-app notifications routed to the
    founder role, newest first."""
    rows = db.scalars(
        select(Notification)
        .where(Notification.recipient_role == "founder")
        .order_by(Notification.created_at.desc()).limit(min(limit, 100))
    )
    return [
        {"type": n.event_type, "booking_id": n.correlation_id, "payload": n.payload,
         "status": n.status, "at": n.created_at.isoformat()}
        for n in rows
    ]


@router.get("/notifications")
def list_notifications(status: str | None = None, limit: int = Query(100),
                       db: Session = Depends(get_db)):
    """All notifications; filter status=failed for the dead-letter view."""
    q = select(Notification).order_by(Notification.created_at.desc())
    if status:
        q = q.where(Notification.status == status)
    return [
        {"id": n.id, "type": n.event_type, "role": n.recipient_role, "channel": n.channel,
         "status": n.status, "error": n.error, "booking_id": n.correlation_id}
        for n in db.scalars(q.limit(min(limit, 200)))
    ]


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
