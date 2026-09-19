from datetime import date

from pydantic import BaseModel, Field, model_validator


# A Homies booking is capped at 180 nights (docs/PRODUCT_MODEL.md §1). Anything
# longer is long-term rental, which lives on the free classifieds board and is
# never booked or paid through the platform. Enforced here rather than deeper in
# because a 3650-night booking would otherwise multiply cleanly all the way into
# the ledger.
MAX_NIGHTS = 180


class BookingCreate(BaseModel):
    listing_id: str
    check_in: date
    check_out: date  # exclusive
    guests: int = Field(ge=1, default=1)

    @model_validator(mode="after")
    def check_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if (self.check_out - self.check_in).days > MAX_NIGHTS:
            raise ValueError(
                f"A booking may not exceed {MAX_NIGHTS} nights. Longer stays are "
                "long-term rental — see the free listings board."
            )
        return self


class BookingOut(BaseModel):
    id: str
    listing_id: str
    guest_id: str
    check_in: date
    check_out: date
    guests: int
    status: str
    total_amount: int
    currency: str
    payout_status: str
    payment_id: str | None = None
    payment_intent_id: str | None = None

    model_config = {"from_attributes": True}


class DayStatus(BaseModel):
    date: date
    status: str  # available | booked | blocked


class AvailabilityOut(BaseModel):
    listing_id: str
    days: list[DayStatus]
