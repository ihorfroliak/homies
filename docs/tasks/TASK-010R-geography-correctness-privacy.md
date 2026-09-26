# TASK-010R — Geography correctness & public location privacy reconciliation

| Field | Value |
|---|---|
| Status | IN_REVIEW — builder complete; narrow independent re-audit required (05 §9: exact location / private data, data-transforming migration) |
| Owner (writer) | Claude Code |
| Starting SHA | TASK-010 candidate `e87352a9862408e76e7ebee08b846dab728d4dac` |
| Foundation | Baseline 002 `36231840ee52d6185e73fda07e54eab33ffe41f3` (accepted, untouched) |
| Branch | `claude/TASK-010R-geography-correctness-privacy` |
| Audit | TASK-011 (Codex) — `TASK_010_REQUIRES_TARGETED_FIXES`, P0 0 / P1 0 / P2 3 / P3 0; [archived verbatim](../reviews/2026-09-26-task011-codex-task010-audit.md) |

## Scope

A targeted repair. The accepted parts of TASK-010 (migration/backfill,
country model, generic hierarchy, classification, ROOM separation,
APARTHOTEL fail-closed, doctrine, audit archive, PostGIS, external ids) are
not redesigned.

| Finding | Repair |
|---|---|
| **GEO-01** (P2) contradictory admin area + locality-bound GeoArea accepted and published | `build_address`: a locality-bound GeoArea must be the given locality's, or its locality must lie in the chosen admin area's subtree (recursive CTE); otherwise 422, nothing written. A GeoArea bound to no locality stays usable anywhere in its country |
| **GEO-02** (P2) 200-char reference names overflowed 80/120-char mirrors → HTTP 500 | Referenced names are no longer copied into `properties.city/district` or `addresses.locality_text/district_text` (they hold `""` for a referenced part); display reads the reference. Import rows beyond the reference model's own limits are refused by name (`GeographyError`). Typed `district` is bounded (80) like `city` — 422, not 500 |
| **GEO-03** (P2) rename left public `city` and the city filter stale | Display (`Property.display_city/display_district`, used by public and owner DTOs) and the city/district filters read the referenced Locality/GeoArea's current name for structured records; the typed mirror only where nothing is referenced. No fan-out updates on rename |
| **Public EXACT** (canonical decision required → D-58) | Prohibited, no owner opt-in. API: `public_location_precision` accepts APPROXIMATE / DISTRICT only (EXACT → 422). `location.public_point`: no EXACT branch; anything not DISTRICT yields the grid point (fail-safe). DB: CHECK admits APPROXIMATE / DISTRICT only. Migration `a7c9e1f3b5d7`: stored EXACT → APPROXIMATE, public point recomputed by the same grid in SQL; the private exact point untouched |

Chosen EXACT strategy: **A** (reject new EXACT, convert stored EXACT by
migration) plus B's fail-safe in `public_point` — the smallest change that
makes a public exact point impossible at every layer. Downgrade widens the
CHECK back; converted rows stay APPROXIMATE (which were EXACT is not kept).

## Authority rule (D-57, 04a §17)

```text
STRUCTURED record:            authoritative geography reference wins
UNSTRUCTURED / LEGACY_BACKFILL
  (or a part not referenced): legacy free-text mirror is the fallback
```

## Out of scope

Old-name alias search; address update endpoint; mirror removal; public
`place` N+1 (still nonblocking debt); Building; reference ingestion; any
foundation change.

## Acceptance tests

`tests/test_geography_repair_pg.py` (PostgreSQL/PostGIS, 27 cases: GEO-01 ×8,
GEO-02 ×9, GEO-03 ×5, privacy sentinels ×2, EXACT ×2, migration ×1),
`tests/test_geography.py` (SQLite GEO-01/GEO-03), `tests/test_location.py`
(EXACT refused, fail-safe), `tests/test_location_pg.py` (search on public
points), full suites, OpenAPI drift. Mutation:
`scripts/mutation/task010r_mutants.py`.

Reproduction on the candidate before any production change: the new
PostgreSQL file against `e87352a` failed exactly on GEO-01 (201 instead of
422), GEO-02 (SQLSTATE 22001 on `varchar(80)` for 81/120-char names and a
long typed district, on `varchar(120)` for 121/200-char names and a long
search-area name, on `varchar(200)` for a 201-char import row), GEO-03 (stale `city`, stale
filter), EXACT (201, no CHECK) — 15 failed / 11 passed. Two of the 15 (the
sentinel probes) failed on a bug in the probe itself — a missing `country`
query parameter — not on a leak; fixed before the repair.

## Evidence (2026-09-26, local; Python 3.14.3 venv, PostgreSQL 16.4 / PostGIS 3.4.3 container)

Python 3.12 was not available with test dependencies locally (the
`homies-api:latest` image has 3.12.14 but no pytest); CI did not run.

| Check | Result |
|---|---|
| Full suite, SQLite | 744 passed, 234 skipped (PostgreSQL-only tests) |
| Full suite, PostgreSQL/PostGIS | 977 passed, 1 skipped (Stripe Test Mode suite, not requested) |
| `tests/test_geography_repair_pg.py` | 27 passed (included above) |
| ruff · mypy · OpenAPI `--check` | clean · no issues (82 files) · up to date (regenerated) |
| Migration | Foundation Baseline 002 → TASK-010 (`e4f6a8b0c2d4`, with EXACT rows) → TASK-010R (`a7c9e1f3b5d7`) → down to TASK-010 → up again; fresh → head in every PG session |
| Mutation — TASK-010R | 12 / 12 killed ([report](../reviews/2026-09-26-task010r-mutation.md)) |
| Mutation — TASK-010 regression | G01–G10 10 / 10 killed |

A first full PostgreSQL run had 1 failure — a test-isolation bug in the new
file (it inserted country DE, which another test had already seeded;
countries survive truncation). Fixed; the rerun above is complete and green.

## Known debt

* Public `place` N+1 (unchanged, nonblocking); display_city/district add the
  same lazy loads per row.
* City/district filters now match on exact reference names (as before on
  the mirror): case-sensitive, no alias/old-name search.
* Rows created by the TASK-010 candidate may still hold copied names in the
  mirrors; never read while a reference exists, not cleaned (no data
  migration needed for correctness).
* Downgrade of `a7c9e1f3b5d7` does not restore which offers were EXACT.
* Python 3.12 run and CI still to do.
