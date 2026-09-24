"""Phase-1 admin: users, audit, notifications, property authority.

Short-stay, booking, payment and ledger administration lives in
app/modules/admin/legacy.py (LEGACY_DORMANT) and is not part of the
Phase-1 application.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import AuditLog
from app.core.db import get_db
from app.core.security import require_role
from app.modules.events.models import Notification
from app.modules.identity.models import User
from app.modules.properties import authority as property_authority
from app.modules.properties.models import PropertyAuthority

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
    """Founder delivery audit (OAT-03): status, retry count, channel, last
    error, timestamps. Filter status=dead (or failed) for the dead-letter view."""
    q = select(Notification).order_by(Notification.created_at.desc())
    if status:
        q = q.where(Notification.status == status)
    return [
        {"id": n.id, "type": n.event_type, "role": n.recipient_role, "channel": n.channel,
         "status": n.status, "attempts": n.attempts, "last_error": n.last_error,
         "booking_id": n.correlation_id,
         "created_at": n.created_at.isoformat(),
         "delivered_at": n.delivered_at.isoformat() if n.delivered_at else None,
         "next_attempt_at": n.next_attempt_at.isoformat() if n.next_attempt_at else None}
        for n in db.scalars(q.limit(min(limit, 200)))
    ]


@router.get("/notifications/queue")
def notification_queue(db: Session = Depends(get_db)):
    """Queue depth by delivery state — founder observability without SQL."""
    from app.modules.events import metrics
    return metrics.refresh_queue_depth(db)


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


# --- Property authority (Domain Schema v1 §30, §63) ---------------------------
# Verifying a claim is a human decision against evidence (a land-register
# extract, a notarial deed, a power of attorney). The endpoint records the
# decision; it does not pretend to make it.


def _authority_view(db: Session, a) -> dict:
    return {
        "id": a.id,
        "property_id": a.property_id,
        "holder_legal_party_id": a.holder_legal_party_id,
        "authority_type": a.authority_type,
        "status": a.status,
        "verification_state": a.verification_state,
        "effective_from": a.effective_from.isoformat(),
        "effective_until": a.effective_until.isoformat() if a.effective_until else None,
        "scopes": property_authority.scopes_of(db, a.id),
        "version": a.version,
    }


def _load_authority(db: Session, authority_id: str):
    found = db.get(PropertyAuthority, authority_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Authority not found")
    return found


@router.get("/properties/{property_id}/authorities")
def property_authorities(property_id: str, db: Session = Depends(get_db)):
    return [_authority_view(db, a) for a in property_authority.authorities_of(db, property_id)]


@router.post("/property-authorities/{authority_id}/verify")
def verify_property_authority(
    authority_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_role("admin")),
):
    found = _load_authority(db, authority_id)
    try:
        property_authority.verify(db, found, admin.id)
    except property_authority.AuthorityStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    db.commit()
    return _authority_view(db, found)


@router.post("/property-authorities/{authority_id}/revoke")
def revoke_property_authority(
    authority_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_role("admin")),
):
    found = _load_authority(db, authority_id)
    paused = property_authority.revoke(db, found, admin.id)
    db.commit()
    return {**_authority_view(db, found), "paused_offers": paused}
