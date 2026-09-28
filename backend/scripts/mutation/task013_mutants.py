"""TASK-013 mutation harness — discovery invariants.

Same rules and runner as task002_mutants.py: green baseline first; killed
only on test failures with no errors; original bytes restored and SHA-256
verified. Usage from backend/:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task013_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

API = "tests/test_search.py"
PG = "tests/test_search_pg.py"
REPAIR = "tests/test_geography_repair_pg.py"
SEARCH = "app/modules/properties/search.py"
ROUTER = "app/modules/properties/router.py"

harness.MUTANTS = [
    {
        "id": "S01-search-without-public-eligibility",
        "invariant": "search never resurrects stale/paused/draft listings",
        "file": SEARCH,
        "old": "    out: list[ColumnElement[bool]] = [freshness.public_clause(db)]\n",
        "new": ("    out: list[ColumnElement[bool]] = "
                "[ClassifiedOffer.status.in_(('active', 'paused', 'stale'))]\n"),
        "tests": [API + "::test_stale_paused_and_draft_never_appear_in_list_or_map"],
    },
    {
        "id": "S02-viewport-on-the-exact-point",
        "invariant": "anonymous spatial inclusion uses the public point only",
        "file": SEARCH,
        "old": "        out.append(func.ST_Intersects(_PUBLIC_GEOG, func.geography(envelope)))\n",
        "new": ("        out.append(func.ST_Intersects(literal_column('properties.exact_geog'), "
                "func.geography(envelope)))\n"),
        "tests": [PG + "::test_spatial_search_is_no_oracle_for_the_exact_home"],
    },
    {
        "id": "S03-admin-descendants-ignored",
        "invariant": "a region matches everything beneath it",
        "file": SEARCH,
        "old": "        within = geography.descendant_area_ids(q.admin_area_ids)\n",
        "new": "        within = list(q.admin_area_ids)\n",
        "tests": [PG + "::test_structured_geography_composes"],
    },
    {
        "id": "S04-unknown-availability-matches-available-by",
        "invariant": "UNKNOWN move-in never matches an explicit date",
        "file": SEARCH,
        "old": "        out.append(ClassifiedOffer.available_from <= q.available_by)  # NULL never matches\n",
        "new": ("        out.append(or_(ClassifiedOffer.available_from.is_(None),\n"
                "                       ClassifiedOffer.available_from <= q.available_by))\n"),
        "tests": [API + "::test_available_by_matches_stated_dates_only"],
    },
    {
        "id": "S05-rent-ceiling-exclusive",
        "invariant": "price boundaries are inclusive",
        "file": SEARCH,
        "old": "        out.append(ClassifiedOffer.primary_price_minor <= q.max_rent)\n",
        "new": "        out.append(ClassifiedOffer.primary_price_minor < q.max_rent)\n",
        "tests": [API + "::test_rent_monthly_total_and_move_in_are_different_filters"],
    },
    {
        "id": "S06-city-filter-trusts-the-mirror",
        "invariant": "structured geography beats a stale legacy mirror",
        "file": SEARCH,
        "old": ("            and_(Property.city == q.city,\n"
                "                 _addresses_where(Address.locality_id.is_(None))),\n"),
        "new": "            Property.city == q.city,\n",
        "tests": [REPAIR + "::test_geo03_a_stale_mirror_never_overrides_the_reference"],
    },
    {
        "id": "S07-no-sort-tie-breaker",
        "invariant": "equal sort keys page deterministically",
        "file": SEARCH,
        "old": "    return [key, ClassifiedOffer.id.asc()]\n",
        "new": "    return [key]\n",
        "tests": [API + "::test_equal_sort_keys_page_deterministically_by_id"],
    },
    {
        "id": "S08-map-ignores-the-filters",
        "invariant": "the map is the list's universe",
        "file": ROUTER,
        "old": "        search.select_matching(\n            db, q,\n",
        "new": "        search.select_matching(\n            db, search.SearchQuery(),\n",
        "tests": [API + "::test_map_is_the_same_universe_as_the_list"],
    },
    {
        "id": "S09-map-serves-the-exact-point",
        "invariant": "the map projects the public point only",
        "file": ROUTER,
        "old": ("            ClassifiedOffer.id, ClassifiedOffer.public_latitude, "
                "ClassifiedOffer.public_longitude,\n"),
        "new": "            ClassifiedOffer.id, Property.latitude, Property.longitude,\n",
        "tests": [API + "::test_the_map_is_a_light_projection_without_private_data"],
    },
    {
        "id": "S10-place-preload-removed",
        "invariant": "rendering places costs a fixed number of queries",
        "file": ROUTER,
        "old": "        .options(selectinload(Address.locality), selectinload(Address.geo_area))\n",
        "new": "",
        "extra": [("    areas = _preload_places(db, rows)  # noqa: F841 — keeps the preloaded "
                   "areas alive\n", "")],
        "tests": [PG + "::test_a_page_of_structured_listings_costs_a_fixed_number_of_queries"],
    },
    {
        "id": "S11-cross-country-contradiction-accepted",
        "invariant": "a place outside country_code is a 422",
        "file": SEARCH,
        "old": ('                _refuse(f"a {model.__tablename__} id given is not in '
                '{country_code}")\n'),
        "new": "                pass\n",
        "tests": [PG + "::test_a_place_in_another_country_than_asked_is_422"],
    },
    {
        "id": "S12-subtype-outside-category-accepted",
        "invariant": "contradictory classification is a 422",
        "file": SEARCH,
        "old": ('            _refuse(f"subtype {\', \'.join(outside)} is not a kind of '
                '{\', \'.join(categories)}")\n'),
        "new": "            pass\n",
        "tests": [API + "::test_contradictory_or_invalid_queries_are_422_not_500"],
    },
]


if __name__ == "__main__":
    harness.main()
