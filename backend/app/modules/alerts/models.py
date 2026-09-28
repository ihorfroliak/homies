"""Saved-search alert state (TASK-014).

    listing_public_generations (properties)   work identity (listing, generation)
        → saved_search_matches                one row per (search, listing, generation)
        → alert_deliveries                    one row per (user, listing, generation, channel)
        → user_notifications                  the in-app inbox entry of a delivery

Search-match identity and delivery identity are separate on purpose: two
saved searches of one user matching the same listing episode are two matches
and ONE delivery per channel. Every "exactly once" here is a database
uniqueness constraint, not a check in code.

Category: PRODUCT — user-requested, optional, unsubscribable. Homies product
policy (04a §22), not a legal conclusion, and not marketing consent.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

PRODUCT = "PRODUCT"
CATEGORIES = (PRODUCT,)
IN_APP = "IN_APP"
EMAIL = "EMAIL"
CHANNELS = (IN_APP, EMAIL)
SAVED_SEARCH_MATCH = "SAVED_SEARCH_MATCH"

DELIVERY_STATUSES = ("pending", "processing", "delivered", "suppressed", "failed", "dead")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SavedSearchMatch(Base):
    __tablename__ = "saved_search_matches"
    __table_args__ = (
        Index("ix_saved_search_matches_episode", "listing_id", "public_generation", "user_id"),
    )

    saved_search_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saved_searches.id", ondelete="CASCADE"), primary_key=True
    )
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id"), primary_key=True
    )
    public_generation: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AlertDelivery(Base):
    """One user-facing notification of one listing episode on one channel.
    Queued is not authorised: the worker revalidates everything at send time
    and ends in `suppressed` when anything no longer holds."""

    __tablename__ = "alert_deliveries"
    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", "public_generation", "channel",
                         name="uq_alert_deliveries_user_episode_channel"),
        CheckConstraint("channel IN ('IN_APP', 'EMAIL')", name="ck_alert_deliveries_channel"),
        CheckConstraint("category IN ('PRODUCT')", name="ck_alert_deliveries_category"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'delivered', 'suppressed', 'failed', 'dead')",
            name="ck_alert_deliveries_status",
        ),
        Index("ix_alert_deliveries_due", "status", "next_attempt_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    listing_id: Mapped[str] = mapped_column(String(36), ForeignKey("classified_offers.id"))
    public_generation: Mapped[int] = mapped_column(BigInteger)
    channel: Mapped[str] = mapped_column(String(8))
    category: Mapped[str] = mapped_column(String(16), default=PRODUCT)
    status: Mapped[str] = mapped_column(String(12), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # A short machine reason (suppression / failure class). Never a message
    # body, an address or anything a provider echoed back.
    outcome: Mapped[str] = mapped_column(String(48), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserNotification(Base):
    """The user's in-app inbox (canonical user-facing notification). Separate
    from the booking-era `notifications` table, which is a delivery queue.
    Carries localisation keys and safe identifiers — never a listing snapshot,
    an address, a price, an email or a contact detail."""

    __tablename__ = "user_notifications"
    __table_args__ = (
        CheckConstraint("category IN ('PRODUCT')", name="ck_user_notifications_category"),
        Index("ix_user_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(16))
    notification_type: Mapped[str] = mapped_column(String(48))
    title_key: Mapped[str] = mapped_column(String(96))
    body_key: Mapped[str] = mapped_column(String(96))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    # One inbox entry per in-app delivery, however often it is retried.
    delivery_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("alert_deliveries.id"), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationPreference(Base):
    """Schema v1 §71. No row = the default (PRODUCT: enabled on both channels —
    the user asked for these alerts by saving a search). Disabling never
    deletes a saved search."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint("category IN ('PRODUCT')", name="ck_notification_preferences_category"),
        CheckConstraint("channel IN ('IN_APP', 'EMAIL')", name="ck_notification_preferences_channel"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    category: Mapped[str] = mapped_column(String(16), primary_key=True)
    channel: Mapped[str] = mapped_column(String(8), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


UNSUBSCRIBE_SCOPES = ("SAVED_SEARCH", "PRODUCT_EMAIL")


class UnsubscribeToken(Base):
    """A bearer capability for one-click unsubscribe. Only the SHA-256 of the
    token is stored; the raw 256-bit token exists in the email alone and says
    nothing about the user, the address or the search."""

    __tablename__ = "unsubscribe_tokens"
    __table_args__ = (
        CheckConstraint("scope IN ('SAVED_SEARCH', 'PRODUCT_EMAIL')",
                        name="ck_unsubscribe_tokens_scope"),
        CheckConstraint("length(token_hash) = 64", name="ck_unsubscribe_tokens_hash_length"),
    )

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(16))
    saved_search_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("saved_searches.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
