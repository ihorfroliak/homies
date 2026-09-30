# ARCHIVE — TASK-011R Codex narrow independent re-audit of TASK-010R

| Provenance | Value |
|---|---|
| Audit task | TASK-011R — Narrow Independent Re-audit of TASK-010R |
| Auditor | Codex (OpenAI Codex Desktop), independent of the builder (also audited TASK-011) |
| Audited SHA | `ed9cf1b49f70716bd214a3212b2e7497ca5078ec` (branch `claude/TASK-010R-geography-correctness-privacy`) |
| Date | 2026-09-27 (report file written 2026-09-27 19:39 local) |
| Verdict | **TASK_010R_ACCEPTED_WITH_NONBLOCKING_NOTES** — P0 0 / P1 0 / P2 0 / P3 0, NOTE 2 (N11R-01, N11R-02); **TASK_010_PHASE_1A_SLICE_ACCEPTED** at `ed9cf1b` |
| Source file | `%TEMP%\homies-task011r-ed9cf1b\TASK-011R-audit.md` (auditor's evidence directory, outside the repository) |
| Source SHA-256 | `c71c21645461dcf0a3a7fe46a790be7a5134f155181aaef135e069d240f03e7d` |
| Codex session | thread `01a09879-13f3-7382-bd99-6b9c006a0ff4` (Codex Desktop) |
| Archived by | Claude Code (builder) at the start of TASK-012, 2026-09-27 |

Everything below the rule is the auditor's report **byte-for-byte as written**
(not rewritten, sanitised or reconstructed). Links inside it point at the
auditor's detached worktree and evidence directory on the founder's machine;
they are kept as written. The two notes are handled in TASK-012 as
documentation maintenance (see its contract).

---

# TASK-011R FINAL NARROW INDEPENDENT RE-AUDIT

## EXECUTIVE VERDICT

**TASK_010R_ACCEPTED_WITH_NONBLOCKING_NOTES**

GEO-01, GEO-02, GEO-03 and the public EXACT prohibition are independently verified closed at `ed9cf1b49f70716bd214a3212b2e7497ca5078ec`. Private exact coordinates and relationships survive the migration. No new P0/P1/P2/P3 finding was established. Two documentation/evidence notes do not block acceptance.

This is the requested narrow verification of TASK-010R, building on TASK-011's accepted areas. It does not reopen Foundation Baseline 002 or repeat the full architectural review. TASK-010 is accepted for continued Phase-1A development at this exact SHA; this is not production approval.

## INDEPENDENCE

Independent auditor: **YES**. This session audited TASK-011 and did not implement TASK-010R. Builder claims were checked against code, PostgreSQL behavior, API responses and mutation failures.

No source files were modified, no fixes made, no commits, push or deployment performed. Application source was mounted read-only for execution. Auditor probes, logs and mutation copies are outside the repository at:

`C:\Users\ihorf\AppData\Local\Temp\homies-task011r-ed9cf1b`

All database fixtures were synthetic and local. No production or external application target was accessed.

## EXACT SHA

- Audited SHA: **`ed9cf1b49f70716bd214a3212b2e7497ca5078ec`**.
- Expected/source branch verified: `claude/TASK-010R-geography-correctness-privacy`.
- TASK-010 candidate parent: `e87352a9862408e76e7ebee08b846dab728d4dac`.
- Accepted Foundation Baseline 002: `36231840ee52d6185e73fda07e54eab33ffe41f3`.
- Isolated detached worktree: `C:\Users\ihorf\.codex\worktrees\homies-task011r-audit\homies`.

The requested `git rev-parse HEAD`, `git status --short`, `git branch --show-current`, and `git log -5 --oneline` were run. Source HEAD/branch matched; the separate audit worktree was clean and detached. HEAD/status were rechecked after execution; staged/unstaged diffs remained empty. Git emitted a permissions warning reading the user-level ignore file; it did not indicate any changed repository files.

The exact repair diff contains 23 files, including the two repair commits; no substitute SHA was audited.

## ENVIRONMENT

Python **3.12.14**; PostgreSQL **16.4**; PostGIS **3.4.3**. Dependencies: SQLAlchemy 2.0.54, FastAPI 0.141.1, Alembic 1.20.0, psycopg 3.3.6, pytest 9.1.1, ruff 0.15.22, mypy 2.3.0. Exact version strings are retained in `environment.json`.

Cached `homies-api:latest` and `postgis/postgis:16-3.4` runtimes were used. Python test dependencies came from the existing dependency-only mount; application imports came from this exact audit worktree or its temporary mutation copy, not an older application's image contents.

The dedicated database container was `homies-task011r-postgis`, full ID `ef3d8a301149aa03f00a1e36321bede4fc2f4d92ddbaf83179028ad93e46d86b`, labeled `homies.audit=TASK-011R`, exposed only on host `127.0.0.1:55472`. Separate disposable databases isolated repository tests, auditor probes and mutation runs. After all checks, the label/ID were verified and only this container and its disposable volume were removed. Evidence and the clean detached worktree remain available.

## GEO-01

**CLOSED.** The original Mazowieckie + locality-bound Kazimierz request, with locality omitted, returns **422**. An independent before/after database count confirmed **zero Property, zero Address, zero Listing**. Thus there is nothing to publish and no orphan Address remains.

The following cases passed:

| Combination | Result |
|---|---|
| Małopolskie + Kazimierz | 201; repository test also publishes and searches successfully |
| Kraków county ancestor + Kazimierz | 201 |
| Kraków locality + Kazimierz | 201 |
| Warszawa locality + Kazimierz | 422; no partial rows |
| DE administrative area + PL GeoArea | 422 in the PostgreSQL repair suite |
| Locality-unbound country-wide GeoArea + valid place | 201 |

[service.py:133](C:/Users/ihorf/.codex/worktrees/homies-task011r-audit/homies/backend/app/modules/geography/service.py:133) uses the actual `AdministrativeArea.parent_id` hierarchy via the recursive descendant CTE. There is no Kraków/Poland special case. R01's removal of ancestry validation is killed by the original invalid request becoming 201.

## GEO-02

**CLOSED.** Independent real-PG requests used both Locality and GeoArea names of **80, 81, 120, 121 and 200 characters**, including Unicode. Each created and published successfully, preserved the full names in owner/public output, and matched city/district filters. No SQL error was observed by the engine error listener, including no SQLSTATE 22001. Exactly one Property and one Address were created per successful case.

All four narrow columns were explicitly inspected: `properties.city`, `properties.district`, `addresses.locality_text`, `addresses.district_text` remain empty for the referenced parts, even when stale typed values are also supplied. They are not a second authoritative copy.

Both area and locality import batches containing an initial valid row followed by a **201-character name** raised `GeographyError` identifying `official_name`. Committing after catching that controlled exception left the entire attempted batch unchanged: the valid prefix had not been partially applied. The 201-character controlled-input check is at the real area/locality import boundary; no writable GeoArea import API exists in this slice. Direct ORM writes remain subject to database column constraints.

The repair suite separately confirms oversized typed city/district input is 422. R02/R03/R04 expose the expected overflow/server-error behavior when the protections are removed.

## GEO-03

**CLOSED.** The real importer renamed the existing `L-KRK` reference to `Renamed locality` with the same Homies ID. Public detail, collection and owner display use the current reference. Search by the new city name finds the listing.

The independent probe also renamed the linked GeoArea and deliberately wrote stale values into **both Property and Address mirrors**. Public and owner city/district remained `Renamed locality` / `Renamed area`; combined current-name filtering returned the listing, and stale city/district filters returned none. R05–R07 fail when mirror authority is reintroduced.

## STRUCTURED VS LEGACY AUTHORITY

D-57 / 04a §17 match behavior: a referenced part reads the reference's current name for display and filtering. A part without a reference retains its typed fallback. Implementation decisions are based on presence of the reference, including partially structured addresses; it does not blindly treat every field of a STRUCTURED record as referenced.

Unstructured fallback passed the repository test and the independent migration probe. The latter produced actual `UNSTRUCTURED / LEGACY_BACKFILL` addresses, then verified owner city text and anonymous city filtering still work after both upgrades. Candidate-era stale mirror values are harmless while their references exist; cleanup is not necessary for these invariants.

## PUBLIC EXACT

**CLOSED at all four requested levels.**

| Level | Evidence |
|---|---|
| API | `public_location_precision=EXACT` returns 422; no ClassifiedOffer created. The OpenAPI enum excludes EXACT. There is no precision-update API; PATCH to listing detail returns 405 and cannot select EXACT. |
| Application | `public_point` contains no exact-return branch. Independent calls with EXACT, an unknown string and an empty string yield the same grid point as APPROXIMATE. DISTRICT yields no point. |
| Database | Independent direct INSERT and UPDATE with EXACT both fail SQLSTATE 23514 on `ck_classified_offers_location_precision`. |
| Migration | Existing EXACT records become APPROXIMATE; public coordinates are recomputed using the frozen SQL grid. Existing APPROXIMATE/DISTRICT rows remain coherent. |

The invariant is the enforced grid/no-point policy, not a mathematical claim that a grid center cannot coincidentally equal an input already at that center. The tested private sentinel points were distinct from their public grid centers. No unsupported owner-opt-in exception remains.

## PRIVATE EXACT PRESERVATION

**ACCEPTED.** The independent migration probe compared complete JSONB row values for Properties, Addresses and Spaces before/after TASK-010R, plus complete Listing rows excluding only the four intentionally mutable public-location fields. The comparison preserved IDs, private latitude/longitude, generated `exact_geog`, Address links, Space links, Listing links and all other compared values.

It exercised **3 Properties, 3 Addresses, 6 Spaces and 9 published Listings**. The authorized owner's Property API still returned each original exact coordinate after upgrade. Anonymous responses exposed only the reduced point or no point. The repository migration test adds no-coordinate, negative-coordinate and globe-edge cases across 5 Properties and 15 Listings.

## PRIVACY SENTINELS

Independent probes used distinct street, building, unit, postcode, raw-address and PRG address-point values, the actual private Address ID, and exact coordinate pair `50.061237, 19.937681`. The locality centroid was also set to that exact point to challenge geographic serialization.

For **each** of APPROXIMATE and DISTRICT, **13 public response surfaces/query variants** were checked:

- Anonymous Listing detail and unfiltered collection.
- City, locality, GeoArea and administrative-area filters.
- Bbox and radius/map filters.
- `/v1/geo/countries`, root/child `/v1/geo/areas`, locality autocomplete and locality search areas.

**Zero private sentinel leakage.** Non-map collection probes explicitly asserted the listing was present, avoiding a vacuous check of an empty response. DISTRICT listings appropriately do not appear in point-based map searches. Anonymous Property access returned 401; dormant legacy collection/detail listing routes returned 404. Owner responses retained private coordinates and address information.

These results cover the scoped API surfaces and generated responses, not arbitrary user-authored listing descriptions or external deployment logging systems.

## MIGRATION

**ACCEPTED.** Reviewed and executed `a7c9e1f3b5d7`:

`Foundation Baseline 002 schema d3f5b7a9c1e4 → TASK-010 e4f6a8b0c2d4 → TASK-010R a7c9e1f3b5d7`.

Fresh database-to-head also ran through the migration-backed fixtures. Existing EXACT, APPROXIMATE and DISTRICT listings were exercised. Independent full-row snapshots and repository case-specific assertions passed. Positive, negative, zero-adjacent, upper-edge and absent coordinates were covered across the two migration tests.

The update selects only EXACT listings, joins each Property by ID, preserves absent coordinate pairs as null, and applies floor-based grid calculations with the 90°/180° upper-edge adjustment. The tightened CHECK is installed after conversion. R11/R12 demonstrate failure when conversion or edge handling is removed.

Downgrade/re-upgrade passed. Documentation honestly states that downgrade widens the enum but **does not restore historical EXACT choices**. Losing that former public setting is intentional; private exact data is retained. This is not a new promise of lossless downgrade for all TASK-010 structured data.

## CLASSIFICATION REGRESSION

Targeted geography tests and the full SQLite suite retained APARTMENT/HOUSE acceptance, ROOM rejection as Property, ROOM Space creation/listing and APARTHOTEL_UNIT fail-closed publication. The independent migration probe also created and preserved ROOM Spaces. No classification design was reopened.

## FOUNDATION REGRESSION

A small relevant real-PG set passed: **6 publication-race cases** and **10 parameterized authority-loss-before-decision cases**, covering publication, revoke and Space archive behavior. Location/search and coordinate constraint regressions passed. This is targeted evidence; the full TASK-009 foundation audit and its mutation harnesses were not rerun.

## MUTATION REVIEW

All **R01–R12 were independently executed**, each with a green baseline before mutation. **12/12 killed**. Each failure log/JUnit was inspected; no collection or setup failure was counted. Mutations operated only on an external temporary copy. **204 original files** were SHA-256 checked after restoration; changed files: **0**. The audited worktree remained unchanged.

| Mutant | Observed meaningful failure |
|---|---|
| R01 | Invalid admin/GeoArea combination accepted: 201 rather than 422. |
| R02 | 81-character referenced name causes PostgreSQL varchar(80) overflow during request. |
| R03 | Oversized import gets DB varchar(200) overflow instead of controlled GeographyError. |
| R04 | Oversized typed district gets varchar(80) overflow instead of API rejection. |
| R05 | Stale city mirror matches a structured listing. |
| R06 | Stale district mirror matches a structured listing. |
| R07 | Display city is empty instead of the renamed reference. |
| R08 | API admits EXACT into the handler, which hits the still-active SQLite DB CHECK; request raises IntegrityError instead of returning 422. |
| R09 | Restored exact-return branch yields actual coordinates rather than grid center. |
| R10 | Direct DB EXACT update no longer raises the required constraint error. |
| R11 | Unconverted EXACT rows prevent installation of the new DB CHECK inside the migration test. |
| R12 | Broken upper-edge calculation violates public-latitude range while migrating 90° N. |

R02/03/04/08/11/12 fail inside the tested request/import/migration behavior, not test infrastructure. They are valid kills, but should not all be described as explicit assertions. The builder report's R08/R11 descriptions are corrected in the note below. No claim is made that these mutants exhaust all possible defects. G01–G10 were inspected through the prior TASK-011 evidence; they were not rerun in this narrow audit.

## CANONICAL DOCUMENTATION

D-57, D-58, 04a §16/§17 and 04's withdrawal note consistently establish reference authority and no public EXACT/owner opt-in. Current task/convergence status explicitly leaves TASK-010 unaccepted pending this re-audit. The earlier audit is archived with provenance; it is treated as history, not a new acceptance claim. The governance wording in the TASK-010 contract now correctly makes independent audit required.

The tested implementation matches these current decisions. Historical baseline descriptions of EXACT do not override D-58. One stale inline serializer comment remains, recorded below.

## TEST RESULTS

| Check actually run | Result |
|---|---|
| Targeted migration/geography/privacy/classification/OpenAPI/foundation set | **157 passed**, 15 warnings, 368.38 s |
| Included `test_geography_repair_pg.py` | **27 passed** |
| Included OpenAPI drift | **5 passed** |
| Full SQLite suite | **744 passed / 234 skipped**, 58 warnings, 553.75 s |
| Independent PostgreSQL probes | **18 passed**, 2 warnings, 91.36 s |
| ruff | Clean |
| mypy | Clean, **82 files**; existing untyped-function note |
| Mutation R01–R12 | **12/12 killed**, all baselines green |
| Full combined PostgreSQL suite | **NOT RUN** in this narrow audit |
| CI | **NOT RUN** |

The 157 cases comprise 27 repair PG, 38 geography, 19 geography PG, 23 location, 10 location PG, 19 coordinate PG, 6 publication-race, 10 authority-loss cases and 5 OpenAPI cases. Totals overlap with the full SQLite suite; they are not summed as unique coverage.

Exact inner commands, from `/repo/backend` with repository mount read-only and external caches/results:

```sh
python -m pytest tests/test_geography_repair_pg.py tests/test_geography.py tests/test_geography_pg.py tests/test_location.py tests/test_location_pg.py tests/test_coordinates_pg.py tests/test_publication_race_pg.py tests/test_publication_authority_race_pg.py::test_a_loss_committed_before_the_decision_refuses_the_publication tests/test_tst01_openapi_contract.py -q -o cache_dir=/audit/targetcache --basetemp=/audit/targettmp --junitxml=/audit/targeted.xml
python -m pytest -q -o cache_dir=/audit/sqlitecache --basetemp=/audit/sqlitetmp --junitxml=/audit/sqlite.xml
python -m ruff check app tests alembic scripts --no-cache
python -m mypy app --cache-dir=/audit/mypycache
python -m pytest -p tests.conftest /audit/probes.py -q -s -o cache_dir=/audit/probecache --basetemp=/audit/probetmp --junitxml=/audit/probes.xml
python /audit/run.py mutations
```

The SQLite invocation omitted TEST_DATABASE_URL. PG processes used only their dedicated disposable audit databases. `run.py` preserves the invocation wrapper and mutation subprocess commands. All assertion-bearing probes completed without needing a probe correction. An initial environment-version one-liner had a shell-quoting syntax error; the saved `environment.py` run succeeded and is the version evidence. No failed metadata command is counted as a test pass. No check was blocked by a model safeguard.

Evidence: `targeted.log/xml`, `sqlite.log/xml`, `probes.py`, `probes.log/xml`, `ruff.log`, `mypy.log`, `mutations.json`, `mutation-01` through `mutation-24` logs/XML, `mutation-restoration.json`, `environment.json`. File hashes are in `evidence-sha256.json`.

## NEW FINDINGS

No new P0/P1/P2/P3 finding. Two **NOTE** items:

**NEW FINDING — NOTE N11R-01 — stale owner-opt-in comment.** [schemas.py:278](C:/Users/ihorf/.codex/worktrees/homies-task011r-audit/homies/backend/app/modules/properties/schemas.py:278) still says exact coordinates may be public if the owner asked. This contradicts D-58/04a §16 but is an inline comment only; the API, application and DB prohibition passed. Expected: comment describes APPROXIMATE/DISTRICT without an opt-in exception. Suggested repair: correct the comment in routine documentation maintenance. Canonical decision required: **NO**. Nonblocking.

**NEW FINDING — NOTE N11R-02 — mutation failure descriptions inaccurate.** [mutation report:26](C:/Users/ihorf/.codex/worktrees/homies-task011r-audit/homies/docs/reviews/2026-09-26-task010r-mutation.md:26) labels R08 as 201-vs-422, and line 29 labels R11 as an assertion. The independently saved `mutation-16.xml` and `mutation-22.xml` instead show the still-active enum CHECK raising during the request and the tightened CHECK rejecting unmigrated EXACT rows. Expected: the evidence report states the observed kill mechanism. Suggested repair: update those rows and the adjacent kill-quality summary. Both remain meaningful behavioral kills; the 12/12 result is supported. Canonical decision required: **NO**. Nonblocking evidence wording.

## NONBLOCKING DEBT

Public-place N+1; exact case-sensitive city/district matching; no old-name aliases; candidate-era stale mirrors no longer read as authority; downgrade does not recover historical EXACT choice. The two notes above are documentation maintenance. Python 3.12 is now independently verified for the executed checks. CI and the full combined PostgreSQL suite remain unverified here. No unrelated known debt was converted into an acceptance blocker.

## FINAL VERDICTS

```text
GEO-01 = CLOSED
GEO-02 = CLOSED
GEO-03 = CLOSED
PUBLIC_EXACT = CLOSED
PRIVATE_EXACT_PRESERVATION = ACCEPTED
MIGRATION = ACCEPTED
PRIVACY_BOUNDARY = ACCEPTED

TASK_010R_ACCEPTED_WITH_NONBLOCKING_NOTES
```

P0: 0 · P1: 0 · P2: 0 · P3: 0 · NOTE: 2.

## TASK-010 FINAL ACCEPTANCE

```text
TASK_010_PHASE_1A_SLICE_ACCEPTED

SHA:
ed9cf1b49f70716bd214a3212b2e7497ca5078ec
```

Accepts Poland-wide geography, structured Address, Property classification, the private/public location model, Product & Growth Doctrine and foundation-audit preservation for continued Phase-1A development, using TASK-011's accepted areas and this narrow repair verification. It does not claim a populated national dataset, a finished geography UI, or production readiness. No repository status documents were edited by the auditor.

## PRODUCTION READINESS

**NOT ASSESSED / NOT READY**

## DEPLOYMENT

**NOT DEPLOYED**

## CHATGPT HANDOFF

```text
CHATGPT HANDOFF

Project: Homies

Task:
TASK-011R — Narrow Independent Re-audit of TASK-010R

Audited SHA:
ed9cf1b49f70716bd214a3212b2e7497ca5078ec

Independent auditor:
YES

GEO-01:
CLOSED

GEO-02:
CLOSED

GEO-03:
CLOSED

Public EXACT:
CLOSED

Private exact preservation:
ACCEPTED

Migration:
ACCEPTED

Privacy boundary:
ACCEPTED

TASK-010R:
TASK_010R_ACCEPTED_WITH_NONBLOCKING_NOTES

TASK-010:
ACCEPTED
TASK_010_PHASE_1A_SLICE_ACCEPTED

P0: 0
P1: 0
P2: 0
P3: 0

New findings:
NOTE N11R-01: stale inline owner-opt-in comment.
NOTE N11R-02: R08/R11 mutation kill descriptions need correction.
No new runtime blocker.

Tests actually run:
Python 3.12.14; PostgreSQL 16.4; PostGIS 3.4.3.
Targeted: 157 passed, including 27 repair PG and 5 OpenAPI.
Full SQLite: 744 passed / 234 skipped.
Independent PG probes: 18 passed.
ruff clean; mypy 82 files clean.
R01–R12: 12/12 killed; all baselines green; restoration verified.
Full combined PostgreSQL suite and CI: NOT RUN.
Worktree clean; dedicated disposable database removed.

Known debt:
Public-place N+1; case-sensitive name filters; no old-name aliases;
non-authoritative stale mirrors; historical EXACT choice not restored
on downgrade; two documentation/evidence notes.

Production readiness:
NOT ASSESSED / NOT READY

Deployment:
NOT DEPLOYED

REQUEST TO CHATGPT:
Adjudicate TASK-011R.

If TASK-010 is accepted, formally establish
ed9cf1b49f70716bd214a3212b2e7497ca5078ec
as the accepted TASK-010 Phase-1A slice and generate TASK-012.
```
