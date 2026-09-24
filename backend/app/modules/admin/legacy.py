"""LEGACY_DORMANT — DO NOT EXTEND FOR PHASE 1.

Administration of the short-stay, booking, payment and ledger runtime: booking
and payment lists, ledger entries/balances/reconciliation, ledger-backed KPIs,
payment reconciliation and booking incidents. Not registered by the Phase-1
application (app/composition.py); the legacy test harness
(tests/legacy_runtime.py) still exercises it.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.security import require_role
from app.modules.admin import kpi as kpi_service
from app.modules.booking.models import Booking
from app.modules.events import service as events
from app.modules.events.models import Incident
from app.modules.ledger import service as ledger
from app.modules.ledger.models import JournalEntry
from app.modules.payments.models import Payment

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))]
)


def _page(limit: int, offset: int):
    return min(limit, 100), max(offset, 0)


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


@router.get("/kpi")
def kpi(
    date_from: date = Query(..., alias="from", description="Inclusive start (UTC date)"),
    date_to: date = Query(..., alias="to", description="EXCLUSIVE end (UTC date)"),
    currency: str | None = Query(None, description="Defaults to the platform currency"),
    db: Session = Depends(get_db),
):
    """Monetary KPIs, answered from the ledger (OBS-07).

    The window is half-open [from, to) so consecutive periods never
    double-count a boundary day. Money is in integer minor units and ratios in
    basis points — see app/modules/admin/kpi.py for why neither is a float.
    """
    if date_to <= date_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "'to' must be after 'from'")
    report = kpi_service.compute(
        db,
        currency=(currency or settings.default_currency).upper(),
        window=kpi_service.Window(start=date_from, end=date_to),
    )
    return kpi_service.as_payload(report)


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
