"""Canonical publication rules for Phase-1A listings (founder decisions, 2026-09-24).

LONG_TERM is the non-transactional residential-rental mode. It is not defined
by a minimum term: `min_term_months` is either absent (open-ended) or at least
one month. MONTHLY stays the future transactional product and is not active.

`aparthotel_unit` is, canonically, an APARTMENT with the subtype
APARTHOTEL_UNIT — not a property type of its own and not a door into
hospitality. Whether such a unit may be let as a residential long-term rental
depends on the building's permitted use, and Homies has no policy for that
yet (LEGAL/POLICY REVIEW REQUIRED). Until one exists, publication fails
closed: the unit can be registered and prepared, never made public on the
strength of its type alone.
"""

from fastapi import HTTPException, status

from app.modules.properties.classification import PUBLICATION_POLICY_REQUIRED
from app.modules.properties.models import Property

# Since TASK-010 the subtype is canonical (`properties.subtype`); the legacy
# `property_type` value is checked too, so a row classified either way fails
# closed — neither column alone can open publication.
LEGACY_POLICY_REQUIRED = frozenset({"aparthotel_unit"})

MIN_TERM_MONTHS_FLOOR = 1


def ensure_publishable(prop: Property) -> None:
    if (prop.subtype in PUBLICATION_POLICY_REQUIRED
            or prop.property_type in LEGACY_POLICY_REQUIRED):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Aparthotel units cannot be published yet: residential-use eligibility "
            "needs a policy that does not exist yet.",
        )
