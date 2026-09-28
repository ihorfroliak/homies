import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.properties.schemas import ClassifiedOut

NAME_MAX = 80
QUERY_MAX = 16_384  # search.MAX_CANONICAL_LENGTH


def _clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("name must not be empty")
    if any(unicodedata.category(ch) in ("Cc", "Cs") for ch in value):
        raise ValueError("name must not contain control characters")
    return value


class SavedListingOut(BaseModel):
    """A saved Listing. While the listing is public: the normal public shape
    (`listing`). Once it is not: a tombstone — the save's own facts only, no
    cached title, price, media, place or contact (TASK-014)."""

    saved_id: str
    listing_id: str
    saved_at: datetime
    availability_status: Literal["AVAILABLE", "NO_LONGER_AVAILABLE"]
    listing: ClassifiedOut | None = None


class SavedListingPage(BaseModel):
    items: list[SavedListingOut]
    total: int
    limit: int
    offset: int


class SavedSearchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=NAME_MAX)
    # The URL query of a search page, e.g. "category=APARTMENT&max_rent=300000"
    # — the TASK-013 SearchQuery parameters. Stored canonicalised; unknown
    # parameters are refused (limit/offset are page state and are dropped).
    query: str = Field(default="", max_length=QUERY_MAX)
    notifications_enabled: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_name(value)


class SavedSearchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX)
    status: Literal["active", "paused"] | None = None
    notifications_enabled: bool | None = None
    query: str | None = Field(default=None, max_length=QUERY_MAX)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


class SavedSearchOut(BaseModel):
    id: str
    name: str
    # The stored canonical query (TASK-013 D-72): run it as-is against
    # GET /v1/classifieds or /v1/classifieds/map.
    query: str
    query_schema_version: int
    # INVALID: the stored query no longer validates (a place retired, a
    # catalogue value withdrawn, an unsupported schema version). An INVALID
    # search never matches and never alerts — it is not silently broadened.
    query_state: Literal["VALID", "INVALID"]
    invalid_reason: str | None = None
    market_country_code: str | None
    status: Literal["active", "paused"]
    notifications_enabled: bool
    created_at: datetime
    updated_at: datetime
    baseline_at: datetime
    version: int
    # Listings matching right now (only on single-search responses).
    match_count: int | None = None


class SavedSearchList(BaseModel):
    items: list[SavedSearchOut]
    total: int
    limit: int
