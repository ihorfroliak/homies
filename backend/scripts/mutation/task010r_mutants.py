"""TASK-010R mutation harness — GEO-01/02/03 and the public-EXACT prohibition.

Same rules and runner as task002_mutants.py: green baseline first; killed
only on test failures with no errors; original bytes restored and SHA-256
verified. Migration mutants take effect because the PostgreSQL test session
rebuilds its schema from the migrations. Usage from backend/:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task010r_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

API = "tests/test_geography.py"
LOC = "tests/test_location.py"
PG = "tests/test_geography_repair_pg.py"
SERVICE = "app/modules/geography/service.py"
ROUTER = "app/modules/properties/router.py"
MIGRATION = "alembic/versions/a7c9e1f3b5d7_no_public_exact_location.py"

harness.MUTANTS = [
    {
        "id": "R01-no-admin-ancestry-check-for-search-area",
        "invariant": "GEO-01: a locality-bound search area lies inside the chosen admin area",
        "file": SERVICE,
        "old": "                if bound is None or bound.admin_area_id not in within:\n",
        "new": "                if bound is None:\n",
        "tests": [PG + "::test_geo01_admin_area_and_a_search_area_of_another_region_are_refused",
                  API + "::test_a_search_area_must_lie_inside_the_chosen_admin_area"],
    },
    {
        "id": "R02-reference-names-copied-into-narrow-mirrors",
        "invariant": "GEO-02: a valid reference name never reaches a narrower column",
        "file": SERVICE,
        "old": '        locality_text="" if locality is not None else loc.locality_text.strip(),\n',
        "new": ("        locality_text=(locality.official_name if locality is not None\n"
                "                       else loc.locality_text).strip(),\n"),
        "tests": [PG + "::test_geo02_a_valid_locality_name_of_any_allowed_length_works"],
    },
    {
        "id": "R03-import-length-check-removed",
        "invariant": "GEO-02: names beyond the reference domain are refused by name",
        "file": SERVICE,
        "old": "        if value is not None and len(value) > limit:\n",
        "new": "        if False:\n",
        "tests": [PG + "::test_geo02_names_beyond_the_reference_domain_are_refused_predictably"],
    },
    {
        "id": "R04-district-length-unbounded",
        "invariant": "GEO-02: free text beyond its column is a 422, not a 500",
        "file": "app/modules/properties/schemas.py",
        "old": '    district: str = Field(default="", max_length=80)\n',
        "new": '    district: str = ""\n',
        "tests": [PG + "::test_geo02_free_text_beyond_its_column_is_a_422_not_a_500"],
    },
    {
        "id": "R05-city-filter-reads-the-stale-mirror",
        "invariant": "GEO-03: structured search follows the reference, not the mirror",
        "file": ROUTER,
        "old": ("            Property.address_id.in_(\n"
                "                select(Address.id).join(Locality, Locality.id == Address.locality_id)\n"
                "                .where(Locality.official_name == city)),\n"
                "            and_(Property.city == city, Property.address_id.in_(\n"
                "                select(Address.id).where(Address.locality_id.is_(None)))),\n"),
        "new": "            Property.city == city,\n",
        "tests": [PG + "::test_geo03_a_stale_mirror_never_overrides_the_reference",
                  API + "::test_a_rename_is_what_display_and_the_city_filter_follow"],
    },
    {
        "id": "R06-district-filter-mirror-wins",
        "invariant": "GEO-03: a stale district mirror never matches a structured record",
        "file": ROUTER,
        "old": ("            and_(Property.district == district, Property.address_id.in_(\n"
                "                select(Address.id).where(Address.geo_area_id.is_(None)))),\n"),
        "new": "            Property.district == district,\n",
        "tests": [PG + "::test_geo03_a_stale_mirror_never_overrides_the_reference"],
    },
    {
        "id": "R07-display-city-reads-the-mirror",
        "invariant": "GEO-03: public display follows the reference after a rename",
        "file": "app/modules/properties/models.py",
        "old": ("        if record is not None and record.locality is not None:\n"
                "            return record.locality.official_name\n"),
        "new": "",
        "tests": [PG + "::test_geo03_an_imported_rename_is_what_display_and_filters_follow"],
    },
    {
        "id": "R08-api-admits-public-exact",
        "invariant": "D-58: a new request for public EXACT is refused",
        "file": "app/modules/properties/schemas.py",
        "old": '    public_location_precision: Literal["APPROXIMATE", "DISTRICT"] = "APPROXIMATE"\n',
        "new": ('    public_location_precision: Literal["EXACT", "APPROXIMATE", "DISTRICT"] = '
                '"APPROXIMATE"\n'),
        "tests": [LOC + "::test_exact_cannot_be_chosen_there_is_no_owner_opt_in",
                  PG + "::test_public_exact_is_refused"],
    },
    {
        "id": "R09-exact-serialisation-restored",
        "invariant": "D-58: no stored or stale precision value ever yields the exact point",
        "file": "app/modules/properties/location.py",
        "old": "    lon = Decimal(str(longitude))\n    return",
        "new": ("    lon = Decimal(str(longitude))\n"
                "    if precision == \"EXACT\":\n"
                "        return lat.quantize(_SIX), lon.quantize(_SIX)\n"
                "    return"),
        "tests": [LOC + "::test_an_unknown_precision_fails_safe_to_the_grid"],
    },
    {
        "id": "R10-database-still-admits-exact",
        "invariant": "D-58: the database cannot hold public EXACT",
        "file": MIGRATION,
        "old": ('        CHECK, "classified_offers", "public_location_precision IN '
                "('APPROXIMATE', 'DISTRICT')\"\n"),
        "new": ('        CHECK, "classified_offers", "public_location_precision IN '
                "('EXACT', 'APPROXIMATE', 'DISTRICT')\"\n"),
        "tests": [PG + "::test_the_database_cannot_hold_public_exact"],
    },
    {
        "id": "R11-migration-keeps-stored-exact",
        "invariant": "D-58: stored EXACT is converted, its public point recomputed",
        "file": MIGRATION,
        "old": "           AND o.public_location_precision = 'EXACT'\n",
        "new": "           AND o.public_location_precision = 'NONE'\n",
        "tests": [PG + "::test_stored_exact_becomes_approximate_and_nothing_private_is_lost"],
    },
    {
        "id": "R12-migration-grid-edge-rule-dropped",
        "invariant": "D-58: the frozen SQL grid equals location.public_point, globe edge included",
        "file": MIGRATION,
        "old": ('    return (f"round(({index} - CASE WHEN {index} * {step} >= {upper} THEN 1 ELSE 0 END)"\n'),
        "new": ('    return (f"round(({index} - CASE WHEN {index} * {step} > {upper} THEN 1 ELSE 0 END)"\n'),
        "tests": [PG + "::test_stored_exact_becomes_approximate_and_nothing_private_is_lost"],
    },
]


if __name__ == "__main__":
    harness.main()
