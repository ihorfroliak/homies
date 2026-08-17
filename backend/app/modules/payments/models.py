from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    booking_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bookings.id"), unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="stripe_sim")
    provider_intent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # requires_payment -> succeeded -> refunded | charged_back | voided (never paid) | failed
    status: Mapped[str] = mapped_column(String(24), default="requires_payment", index=True)
    amount: Mapped[int] = mapped_column(Integer)  # minor units, ADR-0002
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class WebhookEvent(Base):
    """Raw Stripe webhook events, persisted for audit and idempotency (B1).
    stripe_event_id is unique => duplicate deliveries are no-ops; processed_at
    marks completion so retries after a crash re-run safely."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    stripe_event_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Dispute(Base):
    """A card dispute (chargeback) — FIN-03.

    Separate from Payment because a dispute has its own lifecycle, its own
    money and its own identity at the provider, and because the chargeback-rate
    KPI needs a countable record. The ledger records what money *moved*; this
    table records what is *open*.
    """

    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # Stripe `dp_...`. Unique => duplicate deliveries of the same dispute event
    # cannot post the withdrawal twice.
    provider_dispute_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    payment_id: Mapped[str] = mapped_column(String(36), ForeignKey("payments.id"), index=True)
    booking_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    amount: Mapped[int] = mapped_column(Integer)  # disputed, minor units
    # The provider's non-refundable dispute fee. Kept separate from `amount`
    # because winning returns the amount but never the fee.
    fee: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3))
    reason: Mapped[str] = mapped_column(String(64), default="")
    # open -> won | lost. `needs_review` marks a closure we saw without ever
    # seeing the opening, so no money was ever withdrawn in our books.
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    # Whether the booking had already been paid out when the dispute landed.
    # Persisted rather than recomputed: it decides which account was debited,
    # and a reversal months later must credit back the SAME account even if the
    # booking's payout state has moved on since.
    absorbed_by_platform: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
