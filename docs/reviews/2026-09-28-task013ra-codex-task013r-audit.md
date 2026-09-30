# TASK-013RA — Narrow independent re-audit

**TASK_013_ACCEPTED_WITH_NONBLOCKING_NOTES**

Audited SHA: `3f324b6ddff6c7557894eb5f65736729d956f7eb`.
Direct parent: `56567d24bd764563bc21707c0c027e637a206e16`.

F13A-01 and F13A-02 are closed. All requested affected gates are accepted. No new P0/P1/P2/P3 defect was established. Two nonblocking notes are recorded below. Acceptance is for continued Phase-1A development; production readiness was not assessed.

## Independence and provenance

The managed detached checkout was `C:\Users\ihorf\.codex\worktrees\task-013ra-audit\homies`. Initial and final HEAD exactly matched the requested SHA; final porcelain status was empty, including untracked files. Direct parent and ancestry were verified; the requested Claude repair branch contains this commit. No repository files were edited, and no commit, push, PR, deployment, production-data operation, or paid-provider activation occurred.

The repository was mounted read-only in test containers. Bytecode and pytest caches were disabled; mypy and evidence files were external. Mutations ran only in a separate external copy. A newly created network-isolated PostgreSQL/PostGIS container, `homies-task013ra-3f324b6-db`, held disposable databases; no existing database was used.

Authority consulted: 00, Constitution/Business Logic/Architecture 01–03, Governance 05, relevant 04a §§16–21, D-76, TASK-013 contract, and IMPLEMENTATION-CONVERGENCE dispositions. Previously accepted areas were checked only for the requested bounded regressions.

The archived TASK-013A report equals the available original **byte-for-byte**, 34,785 bytes each. SHA-256, also matching the original recorded hash:

`73ea10c964301e3123877c175b8bb0c837d82bf49534c9982e5c7e9cffa3f220`

Original: `C:\Users\ihorf\AppData\Local\Temp\homies-task013a-56567d2\TASK-013A-audit.md`. Archive: `docs/reviews/2026-09-28-task013a-codex-task013-audit.md`. Evidence: `archive.json`.

## Gate evidence

| Gate | Independent evidence and result |
|---|---|
| Numeric validation | Both endpoints exercised with 10**100, 2**63, negative values, each money maximum and maximum+1, huge rooms/area/term, NaN/Inf, and malformed bbox/radius. A 268-request matrix passed. Invalid structural values were refused before discovery SQL; no invalid bound or NUL reached PostgreSQL adaptation. A real matching listing at money 10**12, rooms 100, area 100,000 and term 1,200 matched both endpoints; ceilings one below excluded it. Valid unmatched queries remained 200. Inspection found parameter bounds and explicit validation, not arbitrary database-error translation. |
| Text / identifiers | NUL tested in city, district, all three place IDs, attributes, country, category/subtype/space type, furnished/parking, sort, bbox and date input. Controlled 422 responses; no SQL/internal error leak. Length 200/201 for city/district and 36/37 for IDs tested. Real structured locality/search-area names of exactly 200 Unicode characters matched on list and map. Unicode and whitespace were preserved. |
| Controlled vocabulary | Unknown furnished/parking, category, subtype, space type, sort and attribute values returned 422. Valid catalogue examples returned 200. |
| Input budgets | Repeated dimensions accepted 25 values and refused 26, including duplicates before deduplication; attributes accepted 20 and refused 21. A synthetic filterable catalogue code of exactly 48 characters was accepted; 49 was rejected. Long individual inputs were refused. Three ID dimensions simultaneously at 25 values were used to construct an actual normalized 16,384-character query: both endpoints accepted it; 16,385 returned 422. This establishes the API/canonical-storage budget, not external URL ingress capacity. |
| Normalization | Empty supported optional text/choice/ID values disappear; repeated IDs collapse and sort; parameter order does not change identity; negative zero becomes 0.0; Unicode remains unchanged. List/map canonical strings agree and round-trip identically. |
| Map aggregate | `search.py:515` builds count(*) and count(*) FILTER on the same FROM/WHERE, through one invocation of filters/public eligibility. PostgreSQL statement_timestamp supplies a single decision instant. `router.py:874` subtracts with_point directly; no clamp. Captured production aggregate is in `aggregate.sql`. |
| Concurrency | Repaired publication-between-statements test passed. V05 restored the two original count calls and deterministically returned total=0, with_point=1, without_point=-1, failing the partition assertion. Aggregate/marker drift under READ COMMITTED remains accepted; no transaction-wide snapshot requirement was introduced. |
| Cap / partition / ordering | The 499, 500 and 501 cases passed with a without-point listing: correct counts, cap, truncation and map/list order. Mixed five-listing case produced (5,3,2). Ordinary query-order and public projection tests also passed. |
| Spatial privacy | Anonymous bbox and radius predicates still reference public_geog. Aggregate reuses those filters. Exact-only viewports did not reveal listings; public-point viewports did. No exact coordinates appeared in map output. S02/S09 detected intentional exact-point regressions. |
| Public eligibility | Independent pinned-UTC probe excluded exactly 21×24h and included the listing one microsecond before the boundary on list/map/count. Existing freshness and timezone suites passed. |
| Performance | S10 query-count baseline passed: list count remains bounded for 1/10/24 structured listings and map remains within its <=4-statement guard. Repair reduces two aggregate statements to one. Removing preload made list query counts rise to 40/82 for 10/24 rows and was caught. No new benchmark was needed. |
| Migration | No migration file added or changed. d0f2b4c6e8a1 file has identical Git blob `e5dbda93c4e393aa9f66bf86b1a839b68a5d186d` in parent and repair. Alembic reports one head, d0f2b4c6e8a1. TASK-013 upgrade/downgrade/index/data-preservation regression and all 13 migration tests passed. |

## Tests actually run

Runtime: Python 3.12.14; PostgreSQL 16.4; PostGIS 3.4.3; UTC database/session environment. Runtime versions are recorded in `environment.json`.

| Execution | Result |
|---|---|
| Full SQLite invocation | **902 passed, 1 failed, 343 skipped** |
| Unchanged SQLite failure rerun | **1 passed** |
| Full PostgreSQL-enabled invocation | **1,235 passed, 1 failed, 10 skipped** |
| Unchanged PostgreSQL failure rerun | **1 passed** |
| Independent external probes | **4 passed**, including the 268-request matrix and exact-boundary probes |
| Ruff: app, tests, alembic, scripts | Passed |
| Mypy: app | Passed, 87 source files |
| OpenAPI export --check | Up to date |
| Alembic heads | Single head d0f2b4c6e8a1 |

The PostgreSQL-enabled run includes these entirely passing subsets: validation 101; PostgreSQL validation/map consistency 42; TASK-013 search 22; PostgreSQL search/privacy/performance/index migration 10; geography repair 27; freshness 36; PostgreSQL freshness 11; timezone freshness 46; migration suite 13; OpenAPI contract 5. These counts overlap the full-run totals and must not be added to them.

PostgreSQL skips: nine backup/restore cases because this runner lacked pg_dump/pg_restore client tools, plus the live Stripe collection. SQLite skips include PostgreSQL-gated tests. CI, external ingress limits, production performance and production readiness were not tested.

These were **not two clean full-suite runs**. Original failures and reruns are preserved in their separate logs/XML. No JWT/time validation was weakened. The first independent long-query probe had an auditor fixture error: generated IDs became duplicates and correctly collapsed. The generator was corrected to retain unique prefixes; the original harness failure is preserved and is not a product finding.

## Mutation review

All **11/11** requested mutants were independently executed and meaningfully killed, each after its own green baseline; no survivors, collection errors or setup-only failures are counted. Failure details were inspected.

| Mutant | Meaningful failure |
|---|---|
| V01 bounds removed | PostgreSQL bigint NumericValueOutOfRange |
| V02 NUL checks removed | PostgreSQL NUL text DataError |
| V03 choices unchecked | Invalid furnished value returned 200 rather than 422 |
| V04 repetition budget removed | 26 values returned 200 rather than 422 |
| V05 old two-count implementation | Partition 0/1/-1 |
| V06 wrong point predicate | (5,5,0) rather than (5,3,2) |
| S01 eligibility weakened | Extra nonpublic listings appeared |
| S02 exact-point spatial predicate | Exact-home viewport revealed the listing |
| S08 map filters removed | Map included a listing excluded by the price filter |
| S09 exact map projection | Exact-coordinate sentinel appeared in output |
| S10 preload removed | Query count grew with page size |

Restoration hashes matched for all **355 files** of the external copy (`changed=[]`). Evidence: `mutation-results.json`, individual baseline/mutant logs and XML, `mutation-restoration.json`. The audit checkout itself was never mutated.

## Findings

**Canonical violations / blocking defects: none established in this bounded re-audit.** P0 0; P1 0; P2 0; P3 0.

**F13RA-N01 — NOTE — canonical backstop test/documentation overstates the per-field guarantee.**

- Location: `backend/tests/test_search_validation.py:74` and `:87`; `backend/app/modules/properties/search.py:369`; D-76 wording.
- Rule involved: D-76's enforced canonical input budget and meaningful regression evidence. The production rule is satisfied; this is a test/documentation improvement.
- Evidence: the alleged worst-case test uses ASCII IDs and constructs attribute codes longer than 48 characters. Accepted per-field Unicode ID strings percent-encode enough to reach the canonical backstop. Independent HTTP probes accepted exactly 16,384 and rejected 16,385 while individual dimensions stayed within their budgets.
- Expected: distinguish individual-field bounds from the independently necessary canonical bound; test the actual API boundary.
- Suggested repair: replace the worst-case claim with endpoint boundary tests using unique percent-encoded IDs and valid individual lengths, and adjust the comment/documentation. No change to the working production guard is requested.
- CANONICAL DECISION REQUIRED: **No**.

**F13RA-N02 — NOTE — unstable audit-host wall clock limits full-suite certification.**

- Location/evidence: `clock-watch.json`; `tests/test_oat02_notifications.py:154`; `tests/test_organizations.py:75` during `test_publication_authority_race_pg.py:290` setup; original full-run logs/XML.
- Rule involved: report only observed test results; preserve temporal/security validation. This is an environment qualification, not an established repair regression.
- Evidence: 57,876 samples over 600 seconds recorded 25 backward steps, largest approximately 0.615 seconds. SQLite's legacy event timeline put PayoutExecuted before BookingCreated; that path orders wall-clock occurred_at (`events/service.py:89`). PostgreSQL's organization-test setup rejected a newly issued token: iat=1790610048, adjacent to a recorded rollback to 1790610047.9776416. Both unchanged tests passed on isolated reruns. These failures are consistent with the measured clock instability; the original failures did not capture decoder-level diagnostics, so causation is not claimed as conclusively proven.
- Expected: a stable runtime clock for unqualified full-suite certification.
- Suggested repair: stabilize the host/VM clock and rerun both full suites before claiming clean-run certification. Do not relax JWT or freshness validation. The independent exact-boundary probe pinned the business decision instant, and the requested temporal subset passed.
- CANONICAL DECISION REQUIRED: **No**.

## Required verdicts

```text
F13A_01_NUMERIC = CLOSED
F13A_01_TEXT = CLOSED
CONTROLLED_VOCABULARY = ACCEPTED
INPUT_BUDGETS = ACCEPTED
QUERY_NORMALIZATION = ACCEPTED
F13A_02_MAP_COUNT = CLOSED
MAP_COUNT_CONCURRENCY = ACCEPTED
SPATIAL_PRIVACY = ACCEPTED
PUBLIC_ELIGIBILITY = ACCEPTED
PERFORMANCE_REGRESSION = ACCEPTED
MIGRATION_REGRESSION = ACCEPTED

TASK_013_ACCEPTED_WITH_NONBLOCKING_NOTES

TASK_013_PHASE_1A_SLICE_ACCEPTED

SHA:
3f324b6ddff6c7557894eb5f65736729d956f7eb

PRODUCTION READINESS:
NOT ASSESSED / NOT READY

DEPLOYMENT:
NOT DEPLOYED
```

Evidence directory: `C:\Users\ihorf\AppData\Local\Temp\homies-task013ra-3f324b6`.

CHATGPT HANDOFF: Please adjudicate acceptance of this exact SHA for continued Phase-1A development, closure of F13A-01/F13A-02 and the bounded F13A-03 gates, with the two nonblocking notes retained. This audit does not authorize deployment or certify production readiness.

