# TASK-010R — mutation evidence

Harness: [`task010r_mutants.py`](../../backend/scripts/mutation/task010r_mutants.py)
(new; runner shared with `task002_mutants.py`), plus a regression rerun of
`task010_mutants.py` (G01–G10). Run 2026-09-26 on the TASK-010R working tree,
local disposable PostgreSQL 16.4 / PostGIS 3.4.3 container, Python 3.14.3
venv. Rules as before: green baseline per mutant; killed only when pytest
exits 1 with failures and no errors; original bytes restored and verified by
SHA-256 after each mutant; afterwards `sha256sum -c` over every tracked and
new file under `app/` and `alembic/` matched.

Preconditions (same tree): full SQLite suite 744 passed / 234 skipped; full
PostgreSQL/PostGIS suite 977 passed / 1 skipped.

## TASK-010R mutants — 12 / 12 killed

| Mutant | Invariant | Killed by | How it fails |
|---|---|---|---|
| R01 admin-subtree check for a locality-bound GeoArea removed | GEO-01 | `test_geo01_admin_area_and_a_search_area_of_another_region_are_refused`, SQLite `test_a_search_area_must_lie_inside_the_chosen_admin_area` | assertion: 201 instead of 422 |
| R02 referenced locality name copied into the mirrors again | GEO-02 | `test_geo02_a_valid_locality_name_of_any_allowed_length_works` | the GEO-02 defect itself: SQLSTATE 22001 on `varchar(80)` raised through the request (80-char case still passes) |
| R03 import length check removed | GEO-02 (reference domain) | `test_geo02_names_beyond_the_reference_domain_are_refused_predictably` | expected `GeographyError`, got SQLSTATE 22001 on `varchar(200)` |
| R04 typed `district` unbounded | GEO-02 (free text) | `test_geo02_free_text_beyond_its_column_is_a_422_not_a_500` | 22001 instead of 422 |
| R05 city filter reads the mirror only | GEO-03 | `test_geo03_a_stale_mirror_never_overrides_the_reference`, SQLite rename test | assertion: stale name finds the listing / new name does not |
| R06 district mirror matches structured records | GEO-03 | `test_geo03_a_stale_mirror_never_overrides_the_reference` | assertion |
| R07 display city reads the mirror | GEO-03 | `test_geo03_an_imported_rename_is_what_display_and_filters_follow` | assertion: `'' == 'Renamed locality'` |
| R08 API admits EXACT again | D-58 | `test_exact_cannot_be_chosen_there_is_no_owner_opt_in`, `test_public_exact_is_refused` | assertion: 201 instead of 422 |
| R09 EXACT branch restored in `public_point` | D-58 fail-safe | `test_an_unknown_precision_fails_safe_to_the_grid` | assertion: exact point returned instead of the grid point |
| R10 migration CHECK still admits EXACT | D-58 (database) | `test_the_database_cannot_hold_public_exact` | assertion: no CHECK violation |
| R11 migration leaves stored EXACT | D-58 (migration) | `test_stored_exact_becomes_approximate_and_nothing_private_is_lost` | assertion |
| R12 migration's globe-edge rule (`>=` → `>`) | frozen SQL grid = `location.public_point` | same migration test | the migration refuses the 90° N row (CHECK `…public_coordinates_latitude_range`) |

Kill quality: no mutant was counted on a collection/setup error. R02, R03,
R04 and R12 fail by the database error the invariant exists to prevent,
raised inside the test body (the test client re-raises server exceptions),
not by a Python `assert`; the others fail on explicit assertions. Inspected
individually for R02, R03, R07, R09, R12.

## Regression — TASK-010 G01–G10: 10 / 10 killed

Unchanged from TASK-010 and TASK-011's independent rerun. No harness was
re-pointed.

## Not rerun

Foundation mutation harnesses (TASK-002/004/006/008): no foundation code or
foundation test changed in TASK-010R. The foundation race and privacy tests
ran green inside the full PostgreSQL suite above.

What this does not show: that every alternative implementation would be
caught; anything about production.
