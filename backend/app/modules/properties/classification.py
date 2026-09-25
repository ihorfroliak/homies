"""Property classification (04a §7, §13; TASK-010 decision D-55).

Five dimensions, kept apart on purpose:

* **category** — what the object is: APARTMENT | HOUSE. The canonical
  PropertyType. ROOM is never one: a room is a Space.
* **subtype** — a refinement with real product or policy value, valid only
  under its category.
* **space_type** — WHOLE_PROPERTY | ROOM, on Space (spaces.py).
* **listing intent** — RENT | SALE, on the listing (future).
* **rental mode** — LONG_TERM (Phase 1A) | MONTHLY | SHORT_STAY, on the listing.

`property_type` is the pre-canon vocabulary (apartment, studio, loft, house,
townhouse, aparthotel_unit, and unreadable-for-new "room"). It stays readable
and writable for existing clients and maps onto category + subtype; nothing is
lost. A legacy "room" property has no category: it is not reinterpreted.
"""

CATEGORIES = ("APARTMENT", "HOUSE")

SUBTYPES: dict[str, tuple[str, ...]] = {
    # STUDIO and LOFT carry search value today; APARTHOTEL_UNIT carries policy
    # (publication fails closed, listing_rules.py).
    "APARTMENT": ("STUDIO", "LOFT", "APARTHOTEL_UNIT"),
    "HOUSE": ("DETACHED_HOUSE", "SEMI_DETACHED_HOUSE", "TERRACED_HOUSE"),
}
ALL_SUBTYPES = tuple(s for group in SUBTYPES.values() for s in group)

# legacy property_type -> (category, subtype)
LEGACY_MAP: dict[str, tuple[str | None, str | None]] = {
    "apartment": ("APARTMENT", None),
    "studio": ("APARTMENT", "STUDIO"),
    "loft": ("APARTMENT", "LOFT"),
    "aparthotel_unit": ("APARTMENT", "APARTHOTEL_UNIT"),
    "house": ("HOUSE", None),
    # A townhouse (dom szeregowy) is a terraced house.
    "townhouse": ("HOUSE", "TERRACED_HOUSE"),
    # Readable legacy value only; a room is a Space, so no category.
    "room": (None, None),
}

# category/subtype -> the legacy value older clients read.
_REVERSE: dict[tuple[str, str | None], str] = {
    ("APARTMENT", None): "apartment",
    ("APARTMENT", "STUDIO"): "studio",
    ("APARTMENT", "LOFT"): "loft",
    ("APARTMENT", "APARTHOTEL_UNIT"): "aparthotel_unit",
    ("HOUSE", None): "house",
    ("HOUSE", "TERRACED_HOUSE"): "townhouse",
    ("HOUSE", "DETACHED_HOUSE"): "house",
    ("HOUSE", "SEMI_DETACHED_HOUSE"): "house",
}

# Subtypes whose publication needs a policy that does not exist yet.
PUBLICATION_POLICY_REQUIRED = frozenset({"APARTHOTEL_UNIT"})


class ClassificationError(ValueError):
    pass


def subtype_check_sql() -> str:
    """The CHECK that keeps subtype under its category (used by the migration)."""
    parts = [
        f"(category = '{cat}' AND subtype IN ({', '.join(repr(s) for s in subs)}))"
        for cat, subs in SUBTYPES.items()
    ]
    return "subtype IS NULL OR " + " OR ".join(parts)


def resolve(property_type: str | None, category: str | None,
            subtype: str | None) -> tuple[str, str, str | None]:
    """(legacy property_type, category, subtype) for a new property.

    Accepts the legacy value, the canonical pair, or both when they agree.
    """
    if property_type == "room" or category == "ROOM" or subtype == "ROOM":
        raise ClassificationError(
            "a room is not a property: register the flat, then add the room with "
            "POST /v1/properties/{id}/spaces"
        )
    if category is None and subtype is not None:
        raise ClassificationError("a subtype needs its category")
    if category is not None:
        if category not in CATEGORIES:
            raise ClassificationError(f"category must be one of {', '.join(CATEGORIES)}")
        if subtype is not None and subtype not in SUBTYPES[category]:
            raise ClassificationError(
                f"subtype for {category} must be one of {', '.join(SUBTYPES[category])}"
            )
    if property_type is not None:
        if property_type not in LEGACY_MAP:
            raise ClassificationError(
                "property_type must be one of "
                + ", ".join(t for t in LEGACY_MAP if t != "room")
            )
        mapped_category, mapped_subtype = LEGACY_MAP[property_type]
        if category is None:
            assert mapped_category is not None
            return property_type, mapped_category, mapped_subtype
        if (category, subtype) != (mapped_category, mapped_subtype) and not (
            category == mapped_category and subtype is not None
            and _REVERSE.get((category, subtype)) == property_type
        ):
            raise ClassificationError(
                f"property_type {property_type!r} does not match {category}/{subtype}"
            )
        return property_type, category, subtype
    if category is None:
        raise ClassificationError("give category (APARTMENT or HOUSE) or property_type")
    return _REVERSE[(category, subtype)], category, subtype
