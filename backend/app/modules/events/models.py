from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DomainEvent(Base):
    """Immutable, append-only domain events (OAT-02). correlation_id ties an
    event to its booking so a full timeline is reconstructable from events
    alone. dedup_key makes emission idempotent."""

    __tablename__ = "domain_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)  # booking_id
    dedup_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Notification(Base):
    """Transactional outbox row (OAT-03). Written in the same DB transaction as
    the event + business mutation, then delivered by the worker. Delivery
    state machine: pending -> processing -> delivered | failed -> dead.
    In-app notifications are the rows a user reads; email/sms go through the
    provider abstraction."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    recipient_role: Mapped[str] = mapped_column(String(16))  # guest | host | founder
    recipient_user_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    channel: Mapped[str] = mapped_column(String(16))  # email | sms | in_app
    template_id: Mapped[str] = mapped_column(String(48), default="")
    locale: Mapped[str] = mapped_column(String(8), default="en")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # template variables
    # delivery state machine
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Incident(Base):
    """Minimal operational incident hook (OAT-02). Not a full dispute engine —
    just enough for 'incident opened -> founder visibility'."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    booking_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # checkin_problem | damage | other
    note: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open|resolved
    opened_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# Domain events are append-only (same guard pattern as the ledger).
def _forbid(mapper, connection, target):  # noqa: ARG001
    raise RuntimeError("domain_events is append-only")


event.listen(DomainEvent, "before_update", _forbid)
event.listen(DomainEvent, "before_delete", _forbid)
