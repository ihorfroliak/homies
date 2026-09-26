"""Schemas for properties and the free classifieds board.

The important one is `ClassifiedOut`: it has no phone field at all. Protecting
the number by remembering to strip it would fail the first time someone adds a
convenience endpoint — this way the public shape cannot carry it, and a leak
would require deliberately adding the field back.
"""

from decimal import Decimal
from typing import Literal
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.modules.properties import classification
from app.modules.properties.models import (
    MIN_CLASSIFIED_TERM_MONTHS,
)

FURNISHED = ("full", "partial", "none")
PARKING = ("none", "street", "spot", "garage")
CONTACT_MODES = ("message", "phone")


class AttributeOut(BaseModel):
    code: str
    value_type: str
    unit: str
    filterable: bool
    sortable: bool
    allowed_values: str
    label_pl: str
    label_en: str

    model_config = {"from_attributes": True}


class PropertyCreate(BaseModel):
    # Register for an organisation you belong to, rather than for yourself.
    # The claim is then held by the organisation's legal party.
    organization_id: str | None = None
    # What the registrant claims to be. A claim, not a fact: it is what the
    # verification checks the evidence against.
    authority_type: Literal[
        "OWNER", "CO_OWNER", "AUTHORIZED_REPRESENTATIVE", "PROPERTY_MANAGER",
        "TENANT_WITH_SUBLET_RIGHT", "OTHER_VERIFIED_RIGHT",
    ] = "OWNER"
    # Classification (classification.py): the canonical pair, or the legacy
    # value, or both when they agree.
    property_type: str | None = None
    category: str | None = None
    subtype: str | None = None

    # Location (TASK-010). Structured: a reference locality (or, when no
    # locality fits, an administrative area) from /v1/geo, plus street,
    # building and unit. Free text is still accepted and kept as typed, but
    # an address made only of text is UNSTRUCTURED and says so.
    # country_code defaults to the current market for existing clients; new
    # clients send it. It is a request default, not a model assumption.
    country_code: str = Field(default="PL", pattern="^[A-Z]{2}$")
    locality_id: str | None = None
    admin_area_id: str | None = None
    geo_area_id: str | None = None
    thoroughfare: str | None = Field(default=None, max_length=200)
    building_number: str | None = Field(default=None, max_length=20)
    unit_number: str | None = Field(default=None, max_length=32)
    # Legacy free-text fields. `city` is required only when no locality or
    # area is given; `municipality` (a Polish gmina) is optional since
    # TASK-010 — it only ever served the dormant short-stay tourist tax.
    city: str | None = Field(default=None, min_length=1, max_length=80)
    district: str = Field(default="", max_length=80)
    postcode: str = Field(default="", max_length=12)
    municipality: str | None = Field(default=None, max_length=80)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    # Finite and on the globe; both or neither (TASK-001 F-07). The database
    # enforces the same with CHECK constraints.
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    area_m2: int = Field(gt=0)
    rooms: int = Field(ge=0)
    bedrooms: int = Field(ge=0, default=0)
    bathrooms: int = Field(ge=0, default=1)
    capacity: int = Field(ge=1, default=2)
    floor: int | None = None
    floors_total: int | None = None
    has_elevator: bool = False
    furnished: str = "full"
    parking: str = "none"
    pets_allowed: bool = False
    attributes: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_enums(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude go together: give both or neither")
        try:
            classification.resolve(self.property_type, self.category, self.subtype)
        except classification.ClassificationError as exc:
            raise ValueError(str(exc)) from None
        if self.locality_id and self.admin_area_id:
            raise ValueError("give locality_id or admin_area_id, not both")
        if not (self.locality_id or self.admin_area_id or self.city):
            raise ValueError("give locality_id (from /v1/geo/localities) or city")
        if not (self.address or self.building_number):
            raise ValueError("give the street and number (address), or building_number")
        if self.furnished not in FURNISHED:
            raise ValueError(f"furnished must be one of {', '.join(FURNISHED)}")
        if self.parking not in PARKING:
            raise ValueError(f"parking must be one of {', '.join(PARKING)}")
        return self


class AuthorityOut(BaseModel):
    """Owner-facing summary of one right over the property. The holder's legal
    identity is not included: this is what the owner needs to act, not a
    record of who else may."""

    id: str
    authority_type: str
    status: str
    verification_state: str
    scopes: list[str]


class NamedRef(BaseModel):
    id: str
    name: str
    slug: str | None = None


class AreaRef(NamedRef):
    level: int
    kind_code: str


class PropertyLocationOut(BaseModel):
    """The full structured address. PRIVATE: owner/provider/admin only."""

    country_code: str
    areas: list[AreaRef] = []
    locality: NamedRef | None = None
    geo_area: NamedRef | None = None
    postal_code: str
    thoroughfare: str | None = None
    building_number: str | None = None
    unit_number: str | None = None
    unstructured_text: str
    resolution: str
    source: str
    verification: str


class PublicPlace(BaseModel):
    """Where a listing is, as far as the public may know: country, official
    areas, locality, search area. Never a street, building, unit, postal code,
    exact point or an identifier that pinpoints a building (D-54)."""

    country_code: str
    areas: list[AreaRef] = []
    locality: NamedRef | None = None
    geo_area: NamedRef | None = None


class PropertyOut(BaseModel):
    """Owner-facing only. It carries the exact address and coordinates, which
    no public response may (Schema v1 §80, §116)."""

    id: str
    owner_id: str
    property_type: str | None = None
    category: str | None = None
    subtype: str | None = None
    unit_number: str | None = None
    location: PropertyLocationOut | None = None
    city: str
    district: str
    postcode: str
    municipality: str | None = None
    address: str
    latitude: float | None = None
    longitude: float | None = None
    area_m2: int
    rooms: int
    bedrooms: int
    bathrooms: int
    capacity: int
    floor: int | None = None
    floors_total: int | None = None
    has_elevator: bool
    furnished: str
    parking: str
    pets_allowed: bool
    attributes: dict
    authorities: list[AuthorityOut] = []

    model_config = {"from_attributes": True}


class ClassifiedCreate(BaseModel):
    # Which part of the property is on offer. Omitted means the whole flat.
    space_id: str | None = None
    # How coarsely the listing is placed on the public map. The flat's own
    # coordinates are never public — there is no EXACT (D-58); asking for it
    # is a 422.
    public_location_precision: Literal["APPROXIMATE", "DISTRICT"] = "APPROXIMATE"
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(default="", max_length=4000)
    rent_amount: int = Field(gt=0)  # minor units, ADR-0002
    admin_fee: int = Field(ge=0, default=0)
    utilities_amount: int = Field(ge=0, default=0)
    utilities_included: bool = False
    parking_fee: int = Field(ge=0, default=0)
    deposit_amount: int = Field(ge=0, default=0)
    other_costs: str = Field(default="", max_length=500)
    min_term_months: int | None = None
    open_ended: bool = False
    available_from: date | None = None
    contact_phone: str = Field(default="", max_length=32)
    contact_mode: str = "message"

    @model_validator(mode="after")
    def check_term_and_contact(self):
        if self.contact_mode not in CONTACT_MODES:
            raise ValueError(f"contact_mode must be one of {', '.join(CONTACT_MODES)}")
        if self.contact_mode == "phone" and not self.contact_phone:
            raise ValueError("contact_phone is required when contact_mode is 'phone'")
        # LONG_TERM is the non-transactional residential-rental mode. It is not
        # defined by a six-month floor (founder decision 2026-09-24): the offer
        # is open-ended or states a minimum of at least one month.
        if self.open_ended:
            if self.min_term_months is not None:
                raise ValueError("an open-ended offer cannot also set min_term_months")
            return self
        if self.min_term_months is None:
            raise ValueError("set min_term_months or mark the offer open_ended")
        if self.min_term_months < MIN_CLASSIFIED_TERM_MONTHS:
            raise ValueError(
                f"min_term_months must be at least {MIN_CLASSIFIED_TERM_MONTHS}, "
                "or mark the offer open_ended"
            )
        return self


class PublicMedia(BaseModel):
    id: str
    url: str
    is_cover: bool
    media_type: str
    width_px: int | None = None
    height_px: int | None = None


class PublicLocation(BaseModel):
    latitude: float
    longitude: float
    precision: str


class ClassifiedOut(BaseModel):
    """Public shape. Deliberately has no phone field — see the module docstring.

    Nor an owner id. A stable account identifier on every public listing lets
    anyone join all of one person's listings together — their whole portfolio,
    their addresses by district — without an account. Built field by field
    rather than from the row, so a new column never goes public by default
    (Schema v1 §80).
    """

    id: str
    property_id: str
    space_id: str
    # WHOLE_PROPERTY or ROOM, so a tenant can tell a flat from a room in one
    # before opening the listing (Schema v1 §115).
    space_type: str
    space_label: str | None = None
    # Where, as far as the public may know: the city and district, and a map
    # point whose precision the owner chose. Never the street address and
    # never the flat's own coordinates unless the owner asked for that.
    city: str
    district: str
    public_location: PublicLocation | None = None
    place: PublicPlace | None = None
    media: list[PublicMedia] = []
    title: str
    description: str
    status: str
    rent_amount: int
    currency: str
    admin_fee: int
    utilities_amount: int
    utilities_included: bool
    parking_fee: int
    deposit_amount: int
    other_costs: str
    min_term_months: int | None = None
    open_ended: bool
    available_from: date | None = None
    contact_mode: str
    # What the tenant pays each month, so offers compare without arithmetic;
    # and what they need on the day they move in, deposit included. Both are
    # summaries of the current price components, kept in step with them in the
    # same transaction as every change.
    monthly_total_estimate: int
    move_in_total: int
    # For optimistic concurrency: a price change names the version it saw.
    version: int

    model_config = {"from_attributes": True}


class ClassifiedPage(BaseModel):
    """A page of the board plus the count the UI needs to say "Show 124 places".

    `total` is the size of the whole result set, not of this page: a filter
    panel that cannot show how many places match forces people to paginate to
    find out whether a filter did anything.
    """

    items: list["ClassifiedOut"]
    total: int
    limit: int
    offset: int


class ContactRevealOut(BaseModel):
    offer_id: str
    contact_phone: str


class RevealQuotaOut(BaseModel):
    """What the app shows next to the "show number" button.

    Carries no phone numbers and no offer ids — it is a budget, not a history.
    """

    limit: int
    used: int
    remaining: int
    resets_in: int  # seconds until the oldest view ages out; 0 when nothing is used


class SpaceIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    area_m2: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)


class SpaceOut(BaseModel):
    id: str
    property_id: str
    space_type: str
    label: str | None = None
    # Serialised as a number. Decimal would go out as a JSON string, and every
    # client would have to remember to parse it.
    area_m2: float | None = None
    status: str

    model_config = {"from_attributes": True}


class SpaceArchiveOut(SpaceOut):
    paused_offers: list[str]


class PriceUpdate(BaseModel):
    """A new price, stated the same way as when the offer was created, plus
    the version the owner was looking at when they edited it."""

    rent_amount: int = Field(gt=0)
    admin_fee: int = Field(ge=0, default=0)
    utilities_amount: int = Field(ge=0, default=0)
    utilities_included: bool = False
    parking_fee: int = Field(ge=0, default=0)
    deposit_amount: int = Field(ge=0, default=0)
    expected_version: int = Field(ge=1)


class PriceComponentOut(BaseModel):
    component_type: str
    component_key: str
    amount_minor: int
    cadence: str
    mandatory: bool
    refundable: bool
    estimated: bool
    valid_from: datetime
    valid_to: datetime | None = None

    model_config = {"from_attributes": True}
