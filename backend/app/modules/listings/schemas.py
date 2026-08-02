from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    city: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=3, max_length=255)
    capacity: int = Field(ge=1, le=20, default=2)
    nightly_price_amount: int = Field(gt=0, description="Minor units (grosz), ADR-0002")
    currency: str = Field(default=settings.default_currency, min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def _single_supported_currency(cls, v: str) -> str:
        # H1 (audit 2026-07-28): the ledger sums account balances across ALL
        # currencies without scoping (journal_lines has no currency column), so
        # a non-default currency would silently corrupt booking_escrow math and
        # make the I5 escrow invariant meaningless. Listing creation is the sole
        # entry point for currency (booking/payment/ledger inherit it), so this
        # is the single choke point. Until currency-scoped ledger accounts exist
        # (long-term), only the configured default currency is accepted.
        normalized = v.upper()
        if normalized != settings.default_currency.upper():
            raise ValueError(
                f"currency must be {settings.default_currency} "
                "(multi-currency is not supported yet)"
            )
        return normalized


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=140)
    address: str | None = Field(default=None, min_length=3, max_length=255)
    capacity: int | None = Field(default=None, ge=1, le=20)
    nightly_price_amount: int | None = Field(default=None, gt=0)


class ListingOut(BaseModel):
    id: str
    host_id: str
    title: str
    city: str
    address: str
    capacity: int
    nightly_price_amount: int
    currency: str
    status: str

    model_config = {"from_attributes": True}


class BlockCreate(BaseModel):
    start_date: date
    end_date: date  # exclusive

    @model_validator(mode="after")
    def check_range(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
