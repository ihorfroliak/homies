from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
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
    # requires_payment -> succeeded -> refunded | voided (never paid) | failed
    status: Mapped[str] = mapped_column(String(24), default="requires_payment", index=True)
    amount: Mapped[int] = mapped_column(Integer)  # minor units, ADR-0002
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
