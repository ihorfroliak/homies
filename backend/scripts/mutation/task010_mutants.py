"""TASK-010 mutation harness — geography, address privacy, classification.

Same rules and runner as task002_mutants.py: green baseline first; killed
only on test failures with no errors; original bytes restored and SHA-256
verified. Migration mutants take effect because the PostgreSQL test session
rebuilds its schema from the migrations. Usage from backend/:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task010_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

API = "tests/test_geography.py"
DB = "tests/test_geography_pg.py"
MIGRATION = "alembic/versions/e4f6a8b0c2d4_geography_address_classification.py"

harness.MUTANTS = [
    {
        "id": "G01-postal-code-in-public-place",
        "invariant": "public place schema carries no private address component",
        "file": "app/modules/properties/schemas.py",
        "old": ("    country_code: str\n    areas: list[AreaRef] = []\n"
                "    locality: NamedRef | None = None\n    geo_area: NamedRef | None = None\n\n\n"
                "class PropertyOut(BaseModel):"),
        "new": ("    country_code: str\n    areas: list[AreaRef] = []\n"
                "    locality: NamedRef | None = None\n    geo_area: NamedRef | None = None\n"
                "    postal_code: str = \"\"\n\n\nclass PropertyOut(BaseModel):"),
        "tests": [API + "::test_the_public_listing_shows_the_place_and_nothing_private",
                  API + "::test_public_schemas_cannot_carry_private_address_fields"],
    },
    {
        "id": "G02-trigger-reads-parent-without-lock",
        "invariant": "no hierarchy cycle under concurrent re-parenting",
        "file": MIGRATION,
        "old": "                 WHERE id = NEW.parent_id FOR SHARE;\n",
        "new": "                 WHERE id = NEW.parent_id;\n",
        "tests": [DB + "::test_two_concurrent_reparentings_cannot_close_a_loop"],
    },
    {
        "id": "G03-trigger-level-rule-removed",
        "invariant": "levels follow the parent (cycle-proof hierarchy)",
        "file": MIGRATION,
        "old": ("                IF parent_level IS NULL OR NEW.level <> parent_level + 1 THEN\n"),
        "new": ("                IF parent_level IS NULL THEN\n"),
        "tests": [DB + "::test_levels_must_follow_the_parent",
                  DB + "::test_a_cycle_cannot_be_written"],
    },
    {
        "id": "G04-room-accepted-as-property-type",
        "invariant": "ROOM is a Space, never a property classification (API)",
        "file": "app/modules/properties/classification.py",
        "old": ('    if property_type == "room" or category == "ROOM" or subtype == "ROOM":\n'),
        "new": ('    if False:\n'),
        "extra": [(
            '    "room": (None, None),\n',
            '    "room": ("APARTMENT", None),\n',
        )],
        "tests": [API + "::test_room_and_incoherent_classifications_are_refused"],
    },
    {
        "id": "G05-db-category-check-admits-room",
        "invariant": "ROOM is never a category (database)",
        "file": MIGRATION,
        "old": ("                               \"category IS NULL OR category IN "
                "('APARTMENT', 'HOUSE')\")\n"),
        "new": ("                               \"category IS NULL OR category IN "
                "('APARTMENT', 'HOUSE', 'ROOM')\")\n"),
        "tests": [DB + "::test_the_database_refuses_incoherent_classification"],
    },
    {
        "id": "G06-external-id-not-unique-in-source",
        "invariant": "external identifiers unique within their source namespace",
        "file": MIGRATION,
        "old": ("        sa.UniqueConstraint(\"source_code\", \"external_id\", "
                "name=\"uq_geo_external_refs_source_id\"),\n"),
        "new": "",
        "tests": [DB + "::test_external_ids_are_unique_within_their_source_only"],
    },
    {
        "id": "G07-locality-country-not-checked",
        "invariant": "an address's places are in its country (API)",
        "file": "app/modules/geography/service.py",
        "old": ("        if locality.country_code != loc.country_code:\n"
                "            raise GeographyError(\"locality is in another country\")\n"),
        "new": "",
        "tests": [API + "::test_a_locality_in_another_country_is_refused"],
    },
    {
        "id": "G08-backfill-guesses-structured",
        "invariant": "brownfield backfill keeps text, never guesses a place",
        "file": MIGRATION,
        "old": "                   left(district, 120), 'UNSTRUCTURED', 'LEGACY_BACKFILL', 'UNVERIFIED',\n",
        "new": "                   left(district, 120), 'UNSTRUCTURED', 'USER_INPUT', 'UNVERIFIED',\n",
        "tests": [DB + "::test_upgrading_baseline_002_backfills_every_property_without_guessing"],
    },
    {
        "id": "G09-aparthotel-subtype-publishes",
        "invariant": "aparthotel units fail closed however they are classified",
        "file": "app/modules/properties/listing_rules.py",
        "old": ("    if (prop.subtype in PUBLICATION_POLICY_REQUIRED\n"
                "            or prop.property_type in LEGACY_POLICY_REQUIRED):\n"),
        "new": "    if prop.property_type in LEGACY_POLICY_REQUIRED and prop.subtype is None:\n",
        "tests": [API + "::test_an_aparthotel_unit_classified_canonically_still_fails_closed"],
    },
    {
        "id": "G10-region-search-direct-children-only",
        "invariant": "a region filter covers every area beneath it, at any depth",
        "file": "app/modules/properties/router.py",
        "old": "        within = geography.descendant_area_ids(admin_area_id)\n",
        "new": "        within = [admin_area_id]\n",
        "tests": [API + "::test_search_by_country_region_locality_and_area"],
    },
]


if __name__ == "__main__":
    harness.main()
