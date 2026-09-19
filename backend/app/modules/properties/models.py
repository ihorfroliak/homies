"""Property and the free long-term classifieds board (PRODUCT_MODEL §1–§3).

Two concepts that must not be merged:

* **Property** is the physical object. It exists once, whatever is done with it.
* **Offer** is that property published in one rental mode. One property can carry
  several offers at once.

`ClassifiedOffer` is the first offer type to land. It is deliberately the one
that touches no money: Homies does not book it, take payment for it, hold a
deposit or resolve its disputes. That makes it the cheapest way to prove the
Property/Offer split in code without going anywhere near the ledger.

It hangs off a `Property` rather than standing alone. The earlier design had it
free-floating with its own `owner_id`, which means a flat on the board has no
physical record and the same flat can never also carry a paid offer — the exact
thing this split exists to prevent.

The owner's phone number is the sensitive part of this table. It is never
serialised into any public response; see `router.py` and the tests that assert
it. `ContactReveal` records every disclosure, which is what makes a quota and a
scraping signal possible later.
"""

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# JSONB where it exists so the long tail can carry a GIN index once filters are
# built; plain JSON on SQLite so the fast unit suite still runs.
ATTRIBUTE_JSON = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# The physical kinds of object that can be rented. Kept as data rather than
# subclasses: an apartment and a house differ by which fields are filled in, not
# by behaviour, so seven tables would buy nothing.
PROPERTY_TYPES = (
    "apartment",
    "studio",
    "room",
    "house",
    "townhouse",
    "loft",
    "aparthotel_unit",
)


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    property_type: Mapped[str] = mapped_column(String(24), index=True)

    # Address. `municipality` (gmina) is required and entered by the owner: the
    # Polish tourist tax is set per gmina and charged per night, so a short-stay
    # price cannot be computed without it. It is not derivable from a free-text
    # address, and a TERYT lookup would still need human confirmation.
    city: Mapped[str] = mapped_column(String(80), index=True)
    district: Mapped[str] = mapped_column(String(80), default="", index=True)
    postcode: Mapped[str] = mapped_column(String(12), default="")
    municipality: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(255))
    # Plain decimals, not PostGIS: CI runs stock postgres:16 and a geometry
    # column would break the migration there. This is also the shape external
    # pricing APIs ask for.
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    # Hot filters live in real columns with indexes; the long tail lives in
    # `attributes` so a new amenity never needs a migration.
    area_m2: Mapped[int] = mapped_column(Integer)
    rooms: Mapped[int] = mapped_column(Integer, index=True)
    bedrooms: Mapped[int] = mapped_column(Integer, default=0)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1)
    capacity: Mapped[int] = mapped_column(Integer, default=2)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floors_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_elevator: Mapped[bool] = mapped_column(Boolean, default=False)
    furnished: Mapped[str] = mapped_column(String(12), default="full")  # full|partial|none
    parking: Mapped[str] = mapped_column(String(12), default="none")  # none|street|spot|garage
    pets_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Free-form amenities keyed by the attribute catalogue. Mapped onto the
    # vocabularies external pricing APIs already use, so no translation layer is
    # needed later.
    attributes: Mapped[dict] = mapped_column(ATTRIBUTE_JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# 6 months is the floor for the free board. Shorter than that is a Homies
# booking (paid, commissioned) and belongs to a different offer type.
MIN_CLASSIFIED_TERM_MONTHS = 6


class ClassifiedOffer(Base):
    """A free long-term listing. Homies is not a party to anything here."""

    __tablename__ = "classified_offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), index=True
    )
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(String(4000), default="")
    # draft -> active -> paused | archived
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)

    # Money, in integer minor units (ADR-0002). None of this passes through
    # Homies — it is what the owner tells the tenant they will pay.
    rent_amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    # Structured so tenants can compare offers instead of parsing prose.
    admin_fee: Mapped[int] = mapped_column(Integer, default=0)  # czynsz administracyjny
    utilities_amount: Mapped[int] = mapped_column(Integer, default=0)
    utilities_included: Mapped[bool] = mapped_column(Boolean, default=False)
    parking_fee: Mapped[int] = mapped_column(Integer, default=0)
    deposit_amount: Mapped[int] = mapped_column(Integer, default=0)
    other_costs: Mapped[str] = mapped_column(String(500), default="")

    # Term. Either a minimum in months (>= 6) or explicitly open-ended.
    min_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_ended: Mapped[bool] = mapped_column(Boolean, default=False)
    available_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    # NEVER serialised into a public response. Disclosed only through the
    # reveal endpoint, to an authenticated account, and every disclosure is
    # logged in ContactReveal.
    contact_phone: Mapped[str] = mapped_column(String(32), default="")
    # message | phone — what the owner is willing to be contacted by.
    contact_mode: Mapped[str] = mapped_column(String(12), default="message")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContactReveal(Base):
    """One row per disclosure of an owner's phone number.

    This is the evidence behind three things that do not exist yet but will
    need it: a per-user daily quota, the owner's own "who asked for my number"
    view, and a scraping signal for trust & safety. Recording from the first
    day costs nothing; reconstructing it later is impossible.
    """

    __tablename__ = "contact_reveals"
    __table_args__ = (
        # One row per (viewer, offer): repeat views are not repeat disclosures,
        # and counting them would overstate both the quota and the risk signal.
        UniqueConstraint("offer_id", "viewer_id", name="uq_contact_reveal_viewer"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    offer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id"), index=True
    )
    viewer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    revealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
