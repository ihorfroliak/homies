"""Schemas for properties and the free classifieds board.

The important one is `ClassifiedOut`: it has no phone field at all. Protecting
the number by remembering to strip it would fail the first time someone adds a
convenience endpoint — this way the public shape cannot carry it, and a leak
would require deliberately adding the field back.
"""

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.modules.properties.models import MIN_CLASSIFIED_TERM_MONTHS, PROPERTY_TYPES

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
    property_type: str
    city: str = Field(min_length=1, max_length=80)
    district: str = ""
    postcode: str = ""
    # Required, entered by the owner: the Polish tourist tax is set per gmina.
    municipality: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=255)
    latitude: float | None = None
    longitude: float | None = None
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
        if self.property_type not in PROPERTY_TYPES:
            raise ValueError(f"property_type must be one of {', '.join(PROPERTY_TYPES)}")
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


class PropertyOut(BaseModel):
    id: str
    owner_id: str
    property_type: str
    city: str
    district: str
    postcode: str
    municipality: str
    address: str
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
        # The board is for long-term rental only. A shorter term is a Homies
        # booking — paid and commissioned — and must not arrive here by
        # mislabelling a 3-month let as a free classified.
        if self.open_ended:
            if self.min_term_months is not None:
                raise ValueError("an open-ended offer cannot also set min_term_months")
            return self
        if self.min_term_months is None:
            raise ValueError("set min_term_months or mark the offer open_ended")
        if self.min_term_months < MIN_CLASSIFIED_TERM_MONTHS:
            raise ValueError(
                f"the free board starts at {MIN_CLASSIFIED_TERM_MONTHS} months. "
                "Shorter stays are booked through Homies."
            )
        return self


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
    # What the tenant will actually pay per month, so offers can be compared
    # without doing arithmetic in their head. Not stored: derived on read, so it
    # can never drift from its parts.
    monthly_total_estimate: int

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
