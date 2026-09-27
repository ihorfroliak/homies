"""Listing completeness guidance for owners (TASK-012, D-63).

Deterministic, documented, the same for everyone — not a score the public
ever sees and not an input to ranking. It tells the owner two different
things and never mixes them up:

* **required** — what publication itself demands (the rules publish enforces:
  a verified claim, a listable space, a publishable property type, a rent).
  A missing required item blocks publishing; it is enforced there, not here.
* **recommended** — what makes the listing more useful to a renter. Missing
  one never blocks anything.

`completeness_percent` = passed ÷ applicable, over both kinds, rounded down.
A check that does not apply (e.g. freshness on a draft) is left out rather
than counted as passed or failed. Thresholds below are policy, kept here.
"""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.properties import authority, freshness, spaces
from app.modules.properties.classification import PUBLICATION_POLICY_REQUIRED
from app.modules.properties.listing_rules import LEGACY_POLICY_REQUIRED
from app.modules.properties.models import ClassifiedOffer, Property

RECOMMENDED_PHOTOS = 3
RECOMMENDED_DESCRIPTION_CHARS = 200
RECOMMENDED_AMENITIES = 3


@dataclass(frozen=True)
class Check:
    code: str
    required: bool
    passed: bool


@dataclass
class Assessment:
    checks: list[Check] = field(default_factory=list)

    @property
    def completeness_percent(self) -> int:
        if not self.checks:
            return 100
        return (100 * sum(c.passed for c in self.checks)) // len(self.checks)

    @property
    def missing_required(self) -> list[str]:
        return [c.code for c in self.checks if c.required and not c.passed]

    @property
    def recommended_improvements(self) -> list[str]:
        return [c.code for c in self.checks if not c.required and not c.passed]


def assess(db: Session, user_id: str, offer: ClassifiedOffer, prop: Property,
           now: datetime) -> Assessment:
    """Every check, in a fixed order. Codes are stable API values."""
    a = Assessment()

    def add(code: str, required: bool, passed: bool) -> None:
        a.checks.append(Check(code, required, bool(passed)))

    # Required — mirrors of the publication rules, read without locks.
    add("verify_property_authority", True,
        authority.can_act(db, user_id, prop.id, "PUBLISH_LISTING", verified=True))
    space = offer.space
    listable = True
    try:
        spaces.ensure_listable(space)
    except spaces.SpaceArchived:
        listable = False
    add("use_an_active_space", True, listable)
    add("publishable_property_type", True,
        prop.subtype not in PUBLICATION_POLICY_REQUIRED
        and prop.property_type not in LEGACY_POLICY_REQUIRED)
    add("set_rent", True, offer.rent_amount > 0)

    # Recommended — each one a concrete thing the owner can do.
    add("add_photos", False, len(offer.media) >= RECOMMENDED_PHOTOS)
    add("add_description", False,
        len((offer.description or "").strip()) >= RECOMMENDED_DESCRIPTION_CHARS)
    record = prop.address_record
    add("choose_place_from_list", False,
        record is not None and record.resolution == "STRUCTURED")
    add("set_property_category", False, prop.category is not None)
    add("set_move_in_date", False, offer.available_from is not None)
    add("state_utilities", False, offer.utilities_included or offer.utilities_amount > 0)
    add("add_amenities", False,
        sum(1 for v in (prop.attributes or {}).values() if v not in (None, False, "", 0))
        >= RECOMMENDED_AMENITIES)
    if offer.status in ("active", "stale"):
        add("confirm_still_current", False,
            freshness.state(offer.last_confirmed_available_at, now) == freshness.FRESH)
    return a
