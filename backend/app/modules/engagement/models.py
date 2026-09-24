"""Conversations and messages (Domain Schema v1 §53–§55).

A conversation belongs to a listing and has two sides. The tenant side is the
account that started it. The provider side is not a fixed person: it is
whoever currently holds MANAGE_MESSAGES over the listing's property — the
owner, an agent of the agency that manages it, someone the owner mandated.
Access is decided by that authority at the moment of reading, so an agent who
leaves the agency stops seeing the conversation the same instant, and the one
who replaces them sees it without anyone copying anything.

Participants are still recorded (§54): the tenant as a USER, and the provider
as an ORGANIZATION when an organisation holds the right, or as the USER who
listed it otherwise. That record says who the conversation was with; it is not
what decides who may read it.
"""

from datetime import date, datetime, time, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


CONVERSATION_STATUSES = ("ACTIVE", "ARCHIVED", "CLOSED")
PROVIDER_STAGES = (
    "NEW", "REPLIED", "VIEWING", "APPLICATION", "SHORTLISTED", "ACCEPTED", "REJECTED",
    "ARCHIVED",
)
PARTICIPANT_TYPES = ("USER", "ORGANIZATION")
MESSAGE_TYPES = ("USER", "SYSTEM")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(_in("status", CONVERSATION_STATUSES), name="ck_conversations_status"),
        CheckConstraint(
            f"provider_stage IS NULL OR {_in('provider_stage', PROVIDER_STAGES)}",
            name="ck_conversations_provider_stage",
        ),
        # §53: a conversation has a context. Phase 1 always has the listing.
        CheckConstraint(
            "listing_id IS NOT NULL OR viewing_id IS NOT NULL",
            name="ck_conversations_has_context",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    listing_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classified_offers.id", ondelete="RESTRICT"), index=True,
        nullable=True,
    )
    viewing_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # The tenant who started it. Not in §53, added deliberately: without it a
    # personal owner and the tenant are both just USER participants, and an
    # owner who has since sold the flat would still count as a party able to
    # write. With it, the tenant is fixed and the provider side is always
    # "whoever holds MANAGE_MESSAGES now".
    requester_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    # The provider's own pipeline stage for this lead — the seam for a lead
    # inbox, without building a CRM.
    provider_stage: Mapped[str | None] = mapped_column(String(16), default="NEW", nullable=True)
    assigned_to_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (
        CheckConstraint(_in("participant_type", PARTICIPANT_TYPES),
                        name="ck_conversation_participants_type"),
        # Exactly one identity, and the one the type names (§54).
        CheckConstraint(
            "(participant_type = 'USER' AND user_id IS NOT NULL AND organization_id IS NULL) "
            "OR (participant_type = 'ORGANIZATION' AND organization_id IS NOT NULL "
            "AND user_id IS NULL)",
            name="ck_conversation_participants_one_identity",
        ),
        Index("uq_conversation_participants_user", "conversation_id", "user_id", unique=True,
              postgresql_where=text("user_id IS NOT NULL"),
              sqlite_where=text("user_id IS NOT NULL")),
        Index("uq_conversation_participants_organization", "conversation_id",
              "organization_id", unique=True,
              postgresql_where=text("organization_id IS NOT NULL"),
              sqlite_where=text("organization_id IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    participant_type: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(_in("message_type", MESSAGE_TYPES), name="ck_messages_type"),
        # A person's message names the person, even when sent for an
        # organisation (§55): "the agency said" is not an answer to "who said".
        CheckConstraint(
            "message_type = 'SYSTEM' OR sender_user_id IS NOT NULL",
            name="ck_messages_user_message_has_sender",
        ),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="RESTRICT")
    )
    sender_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    sender_organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True
    )
    message_type: Mapped[str] = mapped_column(String(16), default="USER")
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redaction_reason_code: Mapped[str | None] = mapped_column(String(40), nullable=True)


# --- Viewings (Domain Schema v1 §57–§60) --------------------------------------
#
# The provider publishes when the flat can be seen — weekly windows and one-off
# dates, in the listing's local time — and blocks out times it cannot. A tenant
# picks one of the slots that produces; the provider confirms it, unless the
# listing takes bookings instantly.
#
# Weekdays follow Python: Monday is 0, Sunday is 6.

BOOKING_MODES = ("INSTANT_BOOKING", "REQUEST_APPROVAL")
WINDOW_TYPES = ("WEEKLY", "ONE_OFF")
VIEWING_STATUSES = ("REQUESTED", "CONFIRMED", "DECLINED", "CANCELLED", "COMPLETED", "NO_SHOW")


class ViewingSettings(Base):
    __tablename__ = "viewing_settings"
    __table_args__ = (
        CheckConstraint(_in("booking_mode", BOOKING_MODES), name="ck_viewing_settings_mode"),
        CheckConstraint("duration_minutes > 0", name="ck_viewing_settings_duration"),
        CheckConstraint("minimum_notice_minutes >= 0", name="ck_viewing_settings_notice"),
        CheckConstraint("buffer_before_minutes >= 0 AND buffer_after_minutes >= 0",
                        name="ck_viewing_settings_buffers"),
        CheckConstraint("max_concurrent_bookings >= 1", name="ck_viewing_settings_capacity"),
    )

    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id", ondelete="CASCADE"), primary_key=True
    )
    # Approval by default (§57): a stranger booking a time in someone's home
    # without the owner saying yes is a choice the owner makes, not a default.
    booking_mode: Mapped[str] = mapped_column(String(20), default="REQUEST_APPROVAL")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Warsaw")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    minimum_notice_minutes: Mapped[int] = mapped_column(Integer, default=120)
    buffer_before_minutes: Mapped[int] = mapped_column(Integer, default=0)
    buffer_after_minutes: Mapped[int] = mapped_column(Integer, default=0)
    max_concurrent_bookings: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    version: Mapped[int] = mapped_column(BigInteger, default=1)


class ViewingWindow(Base):
    __tablename__ = "viewing_windows"
    __table_args__ = (
        CheckConstraint(_in("window_type", WINDOW_TYPES), name="ck_viewing_windows_type"),
        CheckConstraint("local_end_time > local_start_time", name="ck_viewing_windows_order"),
        CheckConstraint(
            "(window_type = 'WEEKLY' AND weekday BETWEEN 0 AND 6 AND local_date IS NULL) "
            "OR (window_type = 'ONE_OFF' AND local_date IS NOT NULL AND weekday IS NULL)",
            name="ck_viewing_windows_shape",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_viewing_windows_validity",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id", ondelete="CASCADE"), index=True
    )
    window_type: Mapped[str] = mapped_column(String(10))
    weekday: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    local_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    local_start_time: Mapped[time] = mapped_column(Time)
    local_end_time: Mapped[time] = mapped_column(Time)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ViewingBlackout(Base):
    __tablename__ = "viewing_blackouts"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_viewing_blackouts_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Viewing(Base):
    __tablename__ = "viewings"
    __table_args__ = (
        CheckConstraint(_in("status", VIEWING_STATUSES), name="ck_viewings_status"),
        CheckConstraint("ends_at > starts_at", name="ck_viewings_order"),
        CheckConstraint("attendee_count > 0", name="ck_viewings_attendees"),
        Index("ix_viewings_listing_starts", "listing_id", "starts_at"),
        Index("ix_viewings_requester_starts", "requester_user_id", "starts_at"),
        Index("ix_viewings_status_starts", "status", "starts_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id", ondelete="RESTRICT")
    )
    requester_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="REQUESTED")
    attendee_count: Mapped[int] = mapped_column(SmallInteger, default=1)
    requester_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    confirmed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
