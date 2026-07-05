from datetime import date

from pydantic import BaseModel, Field, model_validator


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    city: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=3, max_length=255)
    capacity: int = Field(ge=1, le=20, default=2)
    nightly_price_amount: int = Field(gt=0, description="Minor units (grosz), ADR-0002")
    currency: str = Field(default="PLN", min_length=3, max_length=3)


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
