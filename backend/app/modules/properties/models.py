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
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
# "room" stays readable for rows created before Spaces existed, but no new
# property may be a room: a room is a space inside a flat (Schema v1 §135).
CREATABLE_PROPERTY_TYPES = tuple(t for t in PROPERTY_TYPES if t != "room")


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    # Nullable at the database level, required by the API. Properties created
    # before the Property/Offer split were derived from listings, which never
    # recorded a type — and inventing "apartment" for them would write a fact
    # nobody established. New properties must supply it (PropertyCreate).
    property_type: Mapped[str | None] = mapped_column(String(24), index=True, nullable=True)

    # Address. `municipality` (gmina) is required and entered by the owner: the
    # Polish tourist tax is set per gmina and charged per night, so a short-stay
    # price cannot be computed without it. It is not derivable from a free-text
    # address, and a TERYT lookup would still need human confirmation.
    city: Mapped[str] = mapped_column(String(80), index=True)
    district: Mapped[str] = mapped_column(String(80), default="", index=True)
    postcode: Mapped[str] = mapped_column(String(12), default="")
    municipality: Mapped[str | None] = mapped_column(String(80), nullable=True)
    address: Mapped[str] = mapped_column(String(255))
    # Plain decimals, not PostGIS: CI runs stock postgres:16 and a geometry
    # column would break the migration there. This is also the shape external
    # pricing APIs ask for.
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    # Hot filters live in real columns with indexes; the long tail lives in
    # `attributes` so a new amenity never needs a migration.
    area_m2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
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
    __table_args__ = (
        # The offer's space must belong to the offer's property. Declared as a
        # composite key rather than checked in code: a listing that points at a
        # room in someone else's flat is exactly the kind of corruption a bug
        # produces quietly, and it would be published under the wrong address.
        ForeignKeyConstraint(
            ["space_id", "property_id"],
            ["spaces.id", "spaces.property_id"],
            name="fk_classified_offers_space_same_property",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), index=True
    )
    space_id: Mapped[str] = mapped_column(String(36), index=True)
    space = relationship(
        "Space",
        primaryjoin="ClassifiedOffer.space_id == Space.id",
        foreign_keys="ClassifiedOffer.space_id",
        lazy="joined",
        viewonly=True,
    )

    @property
    def space_type(self) -> str:
        return self.space.space_type

    @property
    def space_label(self) -> str | None:
        return self.space.label
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(String(4000), default="")
    # draft -> active -> paused | archived
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)

    # Price. The source of truth is `listing_price_components`, one row per
    # component per period, never overwritten (Schema v1 §46). What sits on
    # the offer is a summary recomputed in the same transaction as every
    # change, so search can filter and sort on it with an index (§47). None of
    # this money passes through Homies — it is what the owner tells the tenant
    # they will pay.
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    utilities_included: Mapped[bool] = mapped_column(Boolean, default=False)
    other_costs: Mapped[str] = mapped_column(String(500), default="")
    primary_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    estimated_monthly_total_minor: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    move_in_total_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Optimistic concurrency (§118–§120): a price change names the version it
    # was made against, and loses cleanly if someone else got there first.
    version: Mapped[int] = mapped_column(BigInteger, default=1)

    current_components = relationship(
        "ListingPriceComponent",
        primaryjoin=(
            "and_(ListingPriceComponent.listing_id == ClassifiedOffer.id, "
            "ListingPriceComponent.valid_to.is_(None))"
        ),
        foreign_keys="ListingPriceComponent.listing_id",
        lazy="selectin",
        viewonly=True,
    )

    def _current(self, component_type: str, key: str = "") -> int:
        for c in self.current_components:
            if c.component_type == component_type and c.component_key == key:
                return c.amount_minor
        return 0

    # The owner-facing price fields, read from the current components. Kept on
    # the response so a client sees the same shape it always did.
    @property
    def rent_amount(self) -> int:
        return self._current("BASE_RENT")

    @property
    def admin_fee(self) -> int:
        return self._current("ADMIN_FEE")

    @property
    def utilities_amount(self) -> int:
        return self._current("UTILITIES_ESTIMATE")

    @property
    def parking_fee(self) -> int:
        return self._current("OTHER_MANDATORY", "parking")

    @property
    def deposit_amount(self) -> int:
        return self._current("SECURITY_DEPOSIT")

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
        # The quota query, run before every disclosure: one viewer's rows inside
        # a 24-hour window. Without the time column in the index this degrades
        # into reading a heavy user's whole history on each request.
        Index("ix_contact_reveals_viewer_time", "viewer_id", "revealed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    offer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id"), index=True
    )
    viewer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    revealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# Value types an attribute can carry. Kept small on purpose: every type here
# needs a validator, a filter form and a way to render, so each one is a real
# cost across the web, both apps and the admin.
ATTRIBUTE_TYPES = ("bool", "int", "enum")


class AttributeDefinition(Base):
    """The catalogue that makes the JSONB tail safe to use.

    `Property.attributes` is free-form storage, which is what lets a new amenity
    ship without a migration. Free-form also means `washing_machne` is stored
    happily and then matches no filter for ever — the owner believes the flat
    has a washing machine, the search disagrees, and nothing errors. This table
    is what turns that silent mismatch into a rejected write.

    It is also the single definition the web, both apps and the admin build
    their filter panels from. Hand-written amenity lists per surface are how
    three clients end up disagreeing about what "has a dishwasher" means.

    `external_code` maps onto the vocabularies external pricing APIs already
    use (Wheelhouse's amenity list, for one). Recording it from the start costs
    nothing; discovering later that every code needs translating costs a layer.
    """

    __tablename__ = "attribute_definitions"

    code: Mapped[str] = mapped_column(String(48), primary_key=True)
    value_type: Mapped[str] = mapped_column(String(12))  # bool | int | enum
    unit: Mapped[str] = mapped_column(String(16), default="")
    # Whether it may appear as a search filter, a sort key, or in analytics.
    # A definition that is not filterable is still stored and shown — it simply
    # does not get a filter control.
    filterable: Mapped[bool] = mapped_column(Boolean, default=True)
    sortable: Mapped[bool] = mapped_column(Boolean, default=False)
    analytic: Mapped[bool] = mapped_column(Boolean, default=False)
    # Comma-separated for enums; empty otherwise.
    allowed_values: Mapped[str] = mapped_column(String(500), default="")
    label_pl: Mapped[str] = mapped_column(String(120), default="")
    label_en: Mapped[str] = mapped_column(String(120), default="")
    # The equivalent code at an external pricing provider, where one exists.
    external_code: Mapped[str] = mapped_column(String(48), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# --- Property authority (Domain Schema v1 §30–§32) ----------------------------
#
# The right to act on a specific property, held by a LegalParty. This — not
# `Property.owner_id` — is what every write on a property is authorised against.
#
# Two axes, deliberately separate:
#
# * `status` is whether the right is in force (ACTIVE, REVOKED, EXPIRED...);
# * `verification_state` is whether Homies has checked the claim.
#
# A person who registers a flat holds an ACTIVE, UNVERIFIED authority at once:
# enough to prepare the listing, not enough to publish it. Publishing a flat
# you do not own is the classic scam on a free board, and it is stopped here
# rather than after the first victim wires a deposit.

AUTHORITY_TYPES = (
    "OWNER",
    "CO_OWNER",
    "AUTHORIZED_REPRESENTATIVE",
    "PROPERTY_MANAGER",
    "TENANT_WITH_SUBLET_RIGHT",
    "OTHER_VERIFIED_RIGHT",
)
AUTHORITY_STATUSES = ("PENDING", "ACTIVE", "REVOKED", "EXPIRED")
VERIFICATION_STATES = ("UNVERIFIED", "PENDING", "VERIFIED", "REJECTED")
AUTHORITY_SCOPES = (
    "EDIT_PROPERTY",
    "PUBLISH_LISTING",
    "MANAGE_MEDIA",
    "MANAGE_VIEWINGS",
    "MANAGE_MESSAGES",
    "MANAGE_APPLICATIONS",
    "SIGN_CONTRACT",
    "VIEW_FINANCIALS",
    "MANAGE_SERVICES",
)
# What an owner registering their own flat receives in Phase 1. Contract,
# financial and service scopes wait for the features that would use them.
OWNER_PHASE1_SCOPES = (
    "EDIT_PROPERTY",
    "PUBLISH_LISTING",
    "MANAGE_MEDIA",
    "MANAGE_VIEWINGS",
    "MANAGE_MESSAGES",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class PropertyAuthority(Base):
    __tablename__ = "property_authorities"
    __table_args__ = (
        CheckConstraint(
            _in("authority_type", AUTHORITY_TYPES), name="ck_property_authorities_type"
        ),
        CheckConstraint(_in("status", AUTHORITY_STATUSES), name="ck_property_authorities_status"),
        CheckConstraint(
            _in("verification_state", VERIFICATION_STATES),
            name="ck_property_authorities_verification",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="ck_property_authorities_effective_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="RESTRICT"), index=True
    )
    holder_legal_party_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("legal_parties.id", ondelete="RESTRICT"), index=True
    )
    authority_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    verification_state: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)


class PropertyAuthorityScope(Base):
    __tablename__ = "property_authority_scopes"
    __table_args__ = (
        CheckConstraint(_in("scope", AUTHORITY_SCOPES), name="ck_property_authority_scopes_scope"),
    )

    property_authority_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("property_authorities.id", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String(32), primary_key=True)


# --- Space (Domain Schema v1 §28) ---------------------------------------------
#
# The unit of inventory inside a property: the whole flat, or one room in it.
# A room is not a property — it has no address of its own, no gmina, no owner
# separate from the flat's — so it is modelled as a space, and a listing points
# at a space (§42, §135 "Room is Space, not Property").
#
# Every property gets exactly one active WHOLE_PROPERTY space when it is
# registered. Rooms are added as the owner needs them.

SPACE_TYPES = ("WHOLE_PROPERTY", "ROOM")
SPACE_STATUSES = ("ACTIVE", "ARCHIVED")

_ONE_ACTIVE_WHOLE = "space_type = 'WHOLE_PROPERTY' AND archived_at IS NULL"
_ACTIVE_ROOM = "space_type = 'ROOM' AND archived_at IS NULL"


class Space(Base):
    __tablename__ = "spaces"
    __table_args__ = (
        CheckConstraint(_in("space_type", SPACE_TYPES), name="ck_spaces_space_type"),
        CheckConstraint(_in("status", SPACE_STATUSES), name="ck_spaces_status"),
        CheckConstraint("area_m2 IS NULL OR area_m2 > 0", name="ck_spaces_area_positive"),
        # A label names a room. The whole flat is not "Pokój 1".
        CheckConstraint("space_type = 'ROOM' OR label IS NULL", name="ck_spaces_label_rooms_only"),
        # The target of the listing's composite foreign key: lets the database
        # refuse a listing whose space belongs to a different property.
        UniqueConstraint("id", "property_id", name="uq_spaces_id_property"),
        # At most one active whole-property unit. Two would mean the same flat
        # could be let twice, as a whole, through two different listings.
        Index(
            "uq_spaces_one_active_whole",
            "property_id",
            unique=True,
            postgresql_where=text(_ONE_ACTIVE_WHOLE),
            sqlite_where=text(_ONE_ACTIVE_WHOLE),
        ),
        Index(
            "uq_spaces_active_room_label",
            "property_id",
            "label",
            unique=True,
            postgresql_where=text(_ACTIVE_ROOM),
            sqlite_where=text(_ACTIVE_ROOM),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="RESTRICT"), index=True
    )
    space_type: Mapped[str] = mapped_column(String(16))
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)


# --- Price components (Domain Schema v1 §46–§47) ------------------------------
#
# Each row is one component of the price for one period. A change closes the
# current row (`valid_to`) and opens a new one; nothing is overwritten, so the
# price a tenant was shown last month can always be reconstructed — which is
# what a dispute about "the advert said 2 800" is argued from.

PRICE_COMPONENT_TYPES = (
    "BASE_RENT",
    "ADMIN_FEE",
    "UTILITIES_FIXED",
    "UTILITIES_ESTIMATE",
    "SECURITY_DEPOSIT",
    "AGENCY_FEE",
    "CLEANING_FEE",
    "HOMIES_FEE",
    "OTHER_MANDATORY",
    "SALE_ASKING_PRICE",
)
PRICE_CADENCES = ("ONE_TIME", "MONTHLY", "PER_STAY", "PER_NIGHT")

_CURRENT_COMPONENT = "valid_to IS NULL"


class ListingPriceComponent(Base):
    __tablename__ = "listing_price_components"
    __table_args__ = (
        CheckConstraint(
            _in("component_type", PRICE_COMPONENT_TYPES),
            name="ck_listing_price_components_type",
        ),
        CheckConstraint(_in("cadence", PRICE_CADENCES), name="ck_listing_price_components_cadence"),
        CheckConstraint("amount_minor >= 0", name="ck_listing_price_components_amount"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_listing_price_components_period",
        ),
        # One current row per component. History is unlimited; "now" is not.
        Index(
            "uq_listing_price_components_current",
            "listing_id",
            "component_type",
            "component_key",
            unique=True,
            postgresql_where=text(_CURRENT_COMPONENT),
            sqlite_where=text(_CURRENT_COMPONENT),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id", ondelete="CASCADE"), index=True
    )
    component_type: Mapped[str] = mapped_column(String(32))
    # Distinguishes several components of one type ("parking", "internet").
    component_key: Mapped[str] = mapped_column(String(40), default="")
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    cadence: Mapped[str] = mapped_column(String(16))
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    refundable: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    display_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
