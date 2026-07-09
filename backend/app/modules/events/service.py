"""Operational notification layer (OAT-02) — pilot-grade, brutally minimal.

emit() appends an immutable domain event (idempotent by dedup_key) and fans
it out to recipients per a static routing table. Delivery is best-effort:
a channel failure marks the notification 'failed' (dead-letter = query
failed rows) and NEVER raises into the money path. Notifications never block
a booking or a ledger write.

No external message bus. Channels are log-based; in-app notifications are the
stored rows a user reads. Real email/SMS providers slot in behind Channel
later without touching callers.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.events.models import DomainEvent, Notification
from app.modules.events.templates import template_id_for

log = logging.getLogger("homies.notifications")

# Stable domain event set (OAT-02 requirement 1).
BOOKING_CREATED = "BookingCreated"
BOOKING_CONFIRMED = "BookingConfirmed"
CHECKIN_AVAILABLE = "CheckInAvailable"
CHECKIN_COMPLETED = "CheckInCompleted"
CANCELLATION_PROCESSED = "CancellationProcessed"
PAYOUT_EXECUTED = "PayoutExecuted"
INCIDENT_OPENED = "IncidentOpened"

# event_type -> [(recipient_role, channel)]
ROUTING: dict[str, list[tuple[str, str]]] = {
    BOOKING_CREATED: [("guest", "email"), ("founder", "in_app")],
    BOOKING_CONFIRMED: [("guest", "email"), ("host", "email"), ("founder", "in_app")],
    CHECKIN_AVAILABLE: [("guest", "email")],
    CHECKIN_COMPLETED: [("host", "email"), ("founder", "in_app")],
    CANCELLATION_PROCESSED: [("guest", "email"), ("host", "email"), ("founder", "in_app")],
    PAYOUT_EXECUTED: [("host", "email"), ("founder", "in_app")],
    INCIDENT_OPENED: [("founder", "in_app"), ("host", "email")],
}


def _resolve_recipient(db: Session, role: str, booking_id: str) -> str | None:
    from app.modules.booking.models import Booking
    from app.modules.listings.models import Listing

    booking = db.get(Booking, booking_id)
    if booking is None:
        return None
    if role == "guest":
        return booking.guest_id
    if role == "host":
        listing = db.get(Listing, booking.listing_id)
        return listing.host_id if listing else None
    return None  # founder = role-level feed, no specific user


def emit(db: Session, event_type: str, correlation_id: str, payload: dict, dedup_key: str) -> bool:
    """Append the event and route notifications. Idempotent: a repeated
    dedup_key is a no-op (returns False). Returns True when newly emitted."""
    if db.scalar(select(DomainEvent).where(DomainEvent.dedup_key == dedup_key)):
        return False
    ev = DomainEvent(
        event_type=event_type, correlation_id=correlation_id,
        dedup_key=dedup_key, payload=payload,
    )
    db.add(ev)
    db.flush()
    # Transactional outbox (OAT-03): notifications are written PENDING in the
    # SAME transaction as the event + business mutation. Delivery is the
    # worker's job — business logic never publishes directly.
    for role, channel in ROUTING.get(event_type, []):
        db.add(Notification(
            event_id=ev.id, event_type=event_type, correlation_id=correlation_id,
            recipient_role=role, recipient_user_id=_resolve_recipient(db, role, correlation_id),
            channel=channel, template_id=template_id_for(event_type), payload=payload,
            status="pending",
        ))
    db.flush()
    return True


def booking_timeline(db: Session, booking_id: str) -> list[dict]:
    events = db.scalars(
        select(DomainEvent)
        .where(DomainEvent.correlation_id == booking_id)
        .order_by(DomainEvent.occurred_at)
    )
    return [
        {"type": e.event_type, "at": e.occurred_at.isoformat(), "payload": e.payload}
        for e in events
    ]
