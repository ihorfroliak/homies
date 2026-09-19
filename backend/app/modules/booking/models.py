from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.db import Base


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        # Idempotency: retry with the same key returns the original booking
        UniqueConstraint("guest_id", "idempotency_key", name="uq_booking_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    listing_id: Mapped[str] = mapped_column(String(36), ForeignKey("listings.id"), index=True)
    guest_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)  # exclusive
    guests: Mapped[int] = mapped_column(Integer, default=1)
    # pending -> confirmed -> completed | cancelled | expired (BK-01)
    #   expired = unpaid past its deadline; distinct from a user cancellation
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    total_amount: Mapped[int] = mapped_column(Integer)  # minor units, ADR-0002
    currency: Mapped[str] = mapped_column(String(3))
    # The commission rate agreed AT BOOKING TIME, in basis points. Stamped here
    # rather than read from settings at payout: the rate is an admin-editable
    # setting, and reading it later silently re-prices every booking that has
    # not been paid out yet — a host who agreed to 8% would be paid as if they
    # had agreed to whatever the rate is on payout day.
    commission_bps: Mapped[int] = mapped_column(
        Integer, default=lambda: settings.platform_fee_bps
    )
    # none -> paid (payout allocated and sent to host via ledger)
    payout_status: Mapped[str] = mapped_column(String(16), default="none", index=True)
    # operational state (OAT-02): none -> checkin_available -> checked_in -> checked_out
    operational_state: Mapped[str] = mapped_column(String(20), default="none")
    idempotency_key: Mapped[str] = mapped_column(String(64))
    # BK-01: durable deadline for a pending (unpaid) booking. Persisted so the
    # sweep does not depend on `created_at + N` arithmetic and survives a TTL
    # config change. Null once the booking leaves 'pending'.
    payment_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
