from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

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
    # pending -> confirmed -> completed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    total_amount: Mapped[int] = mapped_column(Integer)  # minor units, ADR-0002
    currency: Mapped[str] = mapped_column(String(3))
    # none -> paid (payout allocated and sent to host via ledger)
    payout_status: Mapped[str] = mapped_column(String(16), default="none", index=True)
    # operational state (OAT-02): none -> checkin_available -> checked_in -> checked_out
    operational_state: Mapped[str] = mapped_column(String(20), default="none")
    idempotency_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
