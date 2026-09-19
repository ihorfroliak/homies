"""Validation of the free-form attribute tail against the catalogue.

Without this, `{"washing_machne": true}` is stored happily. The owner believes
the flat has a washing machine, every search disagrees, and nothing anywhere
raises. A typo in an amenity code is not a crash — it is a listing that quietly
stops matching the filters that would have rented it.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.properties.models import AttributeDefinition


class AttributeError_(ValueError):
    """Raised with a message meant for the owner, not for a log."""


def load_catalogue(db: Session) -> dict[str, AttributeDefinition]:
    return {d.code: d for d in db.scalars(select(AttributeDefinition))}


def validate(db: Session, attributes: dict) -> dict:
    """Return the attributes unchanged, or raise with what is wrong and why.

    Unknown codes are rejected rather than dropped. Silently discarding them
    would leave the owner believing they had recorded something.
    """
    if not attributes:
        return attributes

    catalogue = load_catalogue(db)
    if not catalogue:
        # An empty catalogue means the seed never ran. Rejecting every write
        # would be worse than accepting them, and accepting silently would hide
        # a broken deployment — so accept and let the seeding test fail loudly.
        return attributes

    problems: list[str] = []
    for code, value in attributes.items():
        definition = catalogue.get(code)
        if definition is None:
            problems.append(f"unknown attribute '{code}'")
            continue
        if definition.value_type == "bool" and not isinstance(value, bool):
            problems.append(f"'{code}' must be true or false")
        elif definition.value_type == "int":
            # bool is an int in Python, and "wifi_mbps": true is a mistake.
            if isinstance(value, bool) or not isinstance(value, int):
                problems.append(f"'{code}' must be a whole number")
            elif value < 0:
                problems.append(f"'{code}' cannot be negative")
        elif definition.value_type == "enum":
            allowed = [v for v in definition.allowed_values.split(",") if v]
            if value not in allowed:
                problems.append(f"'{code}' must be one of {', '.join(allowed)}")

    if problems:
        raise AttributeError_("; ".join(problems))
    return attributes
