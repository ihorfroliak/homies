# ARCHIVE — TASK-011 Codex independent audit of TASK-010

| Provenance | Value |
|---|---|
| Audit task | TASK-011 — Independent Audit of TASK-010 |
| Auditor | Codex (OpenAI Codex Desktop), independent of the builder |
| Audited SHA | `e87352a9862408e76e7ebee08b846dab728d4dac` (branch `claude/TASK-010-geography-address-property-classification`) |
| Date | 2026-09-26 (report file written 2026-09-26 00:46 local) |
| Verdict | **TASK_010_REQUIRES_TARGETED_FIXES** — P0 0 / P1 0 / P2 3 (GEO-01, GEO-02, GEO-03) / P3 0; EXACT public precision: CANONICAL DECISION REQUIRED |
| Source file | `%TEMP%\homies-task011-e87352a\TASK-011-audit.md` (auditor's evidence directory, outside the repository) |
| Source SHA-256 | `19a1484ef6fef19bb553581ef8d5d36397c41a6ba96b7b37b3652965d92ad57b` |
| Codex session | thread `01a09879-13f3-7382-bd99-6b9c006a0ff4` (Codex Desktop) |
| Archived by | Claude Code (builder) during TASK-010R, 2026-09-26 |

Everything below the rule is the auditor's report **byte-for-byte as written**
(not rewritten, sanitised or reconstructed). Links inside it point at the
auditor's detached worktree and evidence directory on the founder's machine;
they are kept as written. The adjudication of these findings is recorded in
`docs/DECISIONS.md` (D-57) and `docs/tasks/TASK-010R-geography-correctness-privacy.md`.

---

# TASK-011 — Independent Audit of TASK-010

Audited SHA: `e87352a9862408e76e7ebee08b846dab728d4dac`  
Expected/source branch: `claude/TASK-010-geography-address-property-classification`  
Accepted Foundation Baseline 002: `36231840ee52d6185e73fda07e54eab33ffe41f3`

The auditor did not implement TASK-010. The source checkout matched the requested SHA and branch. Inspection and execution used a separate detached worktree at `C:\Users\ihorf\.codex\worktrees\homies-task011-audit\homies`. HEAD was verified before and after; tracked and untracked status was clean. Git emitted an access warning for a user-level ignore file; diff checks succeeded. No repository source was edited, committed, pushed or deployed. Independent probes, mutation copies, logs and this report are outside the repository in `C:\Users\ihorf\AppData\Local\Temp\homies-task011-e87352a`.

**Result: TASK_010_REQUIRES_TARGETED_FIXES.** Three P2 correctness findings need repair. There is also an explicit privacy-contract decision; it is not presented as a new TASK-010 runtime regression. Foundation Baseline 002 is not reopened.

| Required gate | Verdict | Basis |
|---|---|---|
| MIGRATION | ACCEPTED | Fresh upgrade, baseline backfill and legacy-data downgrade/upgrade preservation verified. |
| PRIVACY_BOUNDARY | NEEDS_FIX | New private address fields remain private in tested responses; inherited opt-in EXACT contradicts the absolute TASK-011 B/C requirement and proposed D-54 wording. Canonical reconciliation required. |
| GEOGRAPHY_MODEL | NEEDS_FIX | GEO-01, GEO-02 and GEO-03: inconsistent references and compatibility failures. |
| EUROPE_READINESS | ACCEPTED | PL/DE/ES represented and exercised as data; no Poland-specific mandatory core fields. This is data-model readiness only. |
| PROPERTY_CLASSIFICATION | ACCEPTED | API/DB classification checks, ROOM separation and aparthotel fail-closed behavior verified. |
| PRODUCT_GROWTH_DOCTRINE | ACCEPTED | Authority integration, all ten dimensions and required operating principles present. |

Severity counts: **P0 0 / P1 0 / P2 3 / P3 0**. Notes below are separate from new runtime findings. The Phase-1A slice is not accepted by this review.

## NEW FINDING — GEO-01 — P2: incompatible administrative area and locality-bound search area can be published

- Source: [geography/service.py:129](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/geography/service.py:129). The locality match is checked only when the request supplies `locality_id`; the `admin_area_id` route does not validate the search area's locality against the selected administrative subtree.
- Violated requirement: TASK-011 J/N and TASK-010 structured-location coherence. Each reference can be valid individually while their combination describes contradictory locations.
- Reproduction: `test_incompatible_admin_and_search_area` submits `admin_area_id = Mazowieckie`, no locality, and the Kazimierz GeoArea linked to Kraków under Małopolskie. Property creation returns **201**, publication returns **200**, and the public place contains Mazowieckie plus Kazimierz. Filtering by both contradictory IDs returns this listing.
- Expected: reject an incompatible pair with a controlled validation response, normally 422. A locality-bound GeoArea must lie within the selected administrative subtree.
- Suggested repair: validate the GeoArea locality's administrative ancestry when an administrative area is selected. Keep legitimate country-wide search areas without a locality possible. Add negative and valid-descendant tests at the API/service boundary.
- Canonical decision required: **NO**.
- Evidence: `probes.py`, `probes.log`, `probes.xml`.

## NEW FINDING — GEO-02 — P2: valid reference names overflow compatibility fields and return HTTP 500

- Sources: [geography/models.py:189](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/geography/models.py:189), [geography/service.py:141](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/geography/service.py:141), [properties/router.py:276](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/properties/router.py:276), [properties/models.py:138](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/properties/models.py:138).
- Violated requirement: TASK-011 J/M, a valid structured reference must be usable without failing the compatibility path. Locality and GeoArea names allow 200 characters; Address text mirrors allow 120; Property city/district allow 80.
- Reproduction: `test_reference_name_exceeds_legacy_capacity` uses existing, valid reference entities with an 81-character locality name, a 121-character locality name, and an 81-character GeoArea name. Normal property-creation requests by reference ID return **500** on real PostgreSQL, SQLSTATE **22001**. Both Property and Address insertions roll back; no partial persisted rows were observed.
- Expected: support the domain's valid reference names, or reject incompatible input predictably under one coherent documented limit. An opaque reference ID should not unexpectedly produce a server error.
- Suggested repair: align compatibility storage with the authoritative name capacity, or derive display values without copying into narrower columns. Do not silently truncate authoritative names. Add PostgreSQL boundary-length tests.
- These are synthetic, model-valid names. This report does not claim a specific live Polish locality currently has such a name.
- Canonical decision required: **NO**.
- Evidence: three parameterized cases in `probes.py` and `probes.log`.

## NEW FINDING — GEO-03 — P2: importer rename leaves public display and supported city filtering contradictory

- Sources: [geography/service.py:249](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/geography/service.py:249), [properties/models.py:261](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/properties/models.py:261), [properties/router.py:117](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/properties/router.py:117), [properties/router.py:720](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/properties/router.py:720).
- Violated requirement: TASK-011 I/M. Supported reference updates must preserve identity without creating conflicting authoritative and compatibility behavior.
- Reproduction: create and publish a property linked to Kraków; call the real `import_localities` with the same source ID and a new name `Renamed locality`; commit. The locality ID remains stable. The same public response now has `place.locality.name = Renamed locality` but `city = Kraków`. Searching `city=Renamed locality` returns **0**, while the old name returns **1**.
- Expected: linked listings' compatibility display and supported filters reflect the current authoritative reference, with free-text fallback only for unstructured data.
- Suggested repair: derive linked compatibility values/filters from the authoritative reference or update all relevant mirrors transactionally during reference changes. Cover rename with an already published listing, not only import-table identity tests.
- This is a demonstrated display/search failure. Retaining mirror columns by itself is only migration debt.
- Canonical decision required: **NO**.
- Evidence: `test_import_rename_and_legacy_public_mirror`, `followup.log`, `followup.xml`.

## Privacy gate: inherited EXACT behavior needs explicit adjudication

Actual anonymous detail and collection responses were probed with private street, building, unit, postcode, raw-address and PRG address-point sentinels, including the private Address ID. These values did not appear in the tested public JSON. A locality centroid set to the property's private coordinates was not serialized through the new geography endpoints. Private Property responses were owner-gated; anonymous listing of properties returned 401, another user's list was empty, and the absent per-property GET and dormant legacy `/v1/listings` routes returned 404. Relevant stored audit payloads did not contain the sentinels. This is evidence for the surfaces tested, not proof about every possible deployment log sink.

For exact input **50.051237, 19.945671**:

| Owner-selected precision | Anonymous public output |
|---|---|
| APPROXIMATE | 50.0525, 19.948 — existing deterministic grid |
| DISTRICT | No public point |
| EXACT | 50.051237, 19.945671 — actual coordinates |

[location.py:53](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/backend/app/modules/properties/location.py:53) deliberately implements EXACT. The file is unchanged from Foundation Baseline 002. The TASK-010 contract itself records the existing three precision modes. This is **not newly introduced coordinate disclosure by a geography join**.

Nevertheless, TASK-011 B/C and proposed [D-54](C:/Users/ihorf/.codex/worktrees/homies-task011-audit/homies/docs/DECISIONS.md:16) say exact coordinates are private without an opt-in exception. The absolute gate therefore cannot be marked ACCEPTED. **CANONICAL DECISION REQUIRED:** either explicitly preserve the existing owner opt-in exception and reconcile the contract, or authorize a separate bounded policy change to prohibit public EXACT and define handling of existing EXACT listings. This audit neither chooses the policy nor modifies it. No new P1 runtime finding is claimed for an unchanged, explicitly selected baseline feature.

## A–U coverage and limits

| Item | Independent evidence and conclusion |
|---|---|
| A Migration | Real PG fresh upgrade to `e4f6a8b0c2d4`; repository baseline-backfill test; independent roundtrip with 8 Properties, 16 Spaces and 8 Listings. All legacy columns, IDs, links, exact/public coordinates and generated geography values compared unchanged. Backfill creates one UNSTRUCTURED/LEGACY_BACKFILL Address per Property without guessed reference IDs. Classification mapping and post-backfill unique/non-null address linkage inspected and tested. |
| B Privacy | Schema/router/serialization/OpenAPI and actual anonymous detail/collection/geography probes; owner-only Property responses. No tested private address sentinel leakage. EXACT exception prevents absolute gate acceptance, as above. |
| C Public point | Existing APPROXIMATE grid and DISTRICT behavior preserved; no new exact-centroid join leak. EXACT is inherited and explicit. |
| D Countries | Stable two-letter country-code constraints; PL plus synthetic DE four-level and ES three-level hierarchies, imports, creation and publication exercised. No required Polish municipality fields. No claim of foreign legal/payment/operational readiness. |
| E Hierarchy | Same-country parent, roots, self-parent rejection, level progression and cycle tests on PG. Additional three-node concurrent attempt: specific waiter PID observed blocked by the intended transaction; after release, the second transaction failed SQLSTATE 23514; no invalid edges committed. G02 removal of parent FOR SHARE killed. |
| F Locality | Separate settlement entity; CITY/TOWN/VILLAGE model, independent municipality association. Village import exercised without making it an administrative unit. |
| G GeoArea | Separate product-area model supports DISTRICT, NEIGHBOURHOOD (repository spelling) and SEARCH_AREA; not inserted into the official-parent tree. GEO-01 concerns validation of combinations. |
| H External IDs | Namespaced source/external uniqueness, per-entity-per-source partial unique indexes, exactly-one-target check and target FKs inspected; PG tests passed. TERYT namespaces and private PRG address-point references exercised. External IDs remain separate from UUID domain IDs. |
| I Import | Re-import stable IDs, rename and supported leaf reparenting exercised, including DE/ES. No live government API dependency. GEO-03 exposes downstream mirror drift despite correct identity preservation. General non-leaf reference-release orchestration is future work. |
| J Address | Required country, nullable street/building as supported, source/verification retained, Property-owned unique non-null address relation and Property unit number. No speculative Building requirement. GEO-01/02 need fixes. |
| K Classification | Category/subtype remain separate from Space, listing intent and rental mode. APARTMENT/HOUSE accepted; ROOM rejected as Property and retained as Space. API and PG negative combinations passed. |
| L Aparthotel | Repository tests plus independent canonical-only and legacy-only APARTHOTEL_UNIT cases: publish 409, anonymous detail 404 in both; no compatibility bypass. G09 killed. |
| M Compatibility | Ordinary request mapping and legacy backfill pass. Concrete long-name and post-import-rename failures are GEO-02/03; retaining temporary mirrors is not itself a finding. |
| N Filters | Country, locality, GeoArea and recursive administrative descendants tested; unrelated country/locality combination returns no results; G10 killed. GEO-01 can feed contradictory but same-country data into otherwise conjunctive filters. |
| O PostGIS | Existing exact/public geography preserved; new centroid/boundary type and intended GiST index checks in PG suite; invalid coordinate DB tests plus M12 mutation. No boundary population demanded. |
| P N+1 | Ten published fixtures: limit 1 → 9 SELECTs, 5 → 25, 10 → 45. Real linear query amplification; public limit capped at 100. Nonblocking performance debt on this evidence, not an unbounded normal-size correctness defect. |
| Q Doctrine | Canonical authority includes doctrine. UX, Trust & Safety, Automation, Efficiency, Marketplace Liquidity, Competitive Advantage, Beauty & Desirability, Growth, Scalability and Necessity present. Launch locally / Model nationally / Architect internationally and parallel Product + Growth recorded. Benchmark document labels strategic observations; no independent live competitor research claimed. |
| R Archives | Both requested TASK-009 Codex and Claude audit files exist with source/session/auditor/SHA/verdict provenance. Original external archive sources were not reconstructed or byte-compared; the requested archive/provenance check passed. |
| S Foundation | Targeted PG authority/publication/revoke/Space archive/chain-gain/proof-replacement/accept races passed; private/public coordinate regressions passed. Listing price-version CAS stale-edit/new-version tests passed in full SQLite. No fresh general foundation re-audit or concurrent CAS-specific PG probe was performed. |
| T Mutations | All G01–G10 independently rerun, green baselines then meaningful failed assertions. Additional M12 coordinate-range DB mutant killed. Source copies restored. See limitations below. |
| U Tests | Targeted 180 passed; full SQLite 740 passed/207 skipped; ruff clean; mypy 82 files clean; independent probes and mutations detailed below. Full combined PostgreSQL suite and CI not run. |

Downgrade qualification: the tested downgrade preserves pre-existing legacy data and relationships. It intentionally drops the new geography/address/classification schema. It is **not a lossless rollback for new structured data entered after upgrade**; no such production guarantee is accepted here.

The two archived review files' SHA-256 hashes at the audited commit are:

- Codex archive: `e3e17acbf8aef83906cee24609107c5e5281293bc42fbaf29759189a4b936dfa`.
- Claude archive: `3cee9ebcd65fd60ff823206f269619286402bcb0c96d38ef461c6c7c9ff9eba4`.

## Execution evidence

Local, synthetic, disposable environment only: Python **3.12.14**, PostgreSQL **16.4**, PostGIS **3.4.3**. Package versions are recorded in `environment.json`. Cached Docker runtimes/dependencies were used; application imports came from the exact mounted worktree or its outside-repository mutation copy. No external API or production target was accessed.

The audit's dedicated PostgreSQL container was `homies-task011-postgis`, ID `e720556ec9c11b0054f9b682d9aa8a4de7c8319f308ed8ac6143a8854292485a`, labeled `homies.audit=TASK-011`, bound to local port 55471. Separate test/probe/mutation databases avoided concurrent schema resets. After all runs, its identity/label was verified and only that container and its disposable volume were removed. Other audit environments were not removed.

Repository tests executed from `/repo/backend` with the source mounted read-only. Cache/output directories were under `/audit`:

```sh
python -m pytest tests/test_geography.py tests/test_geography_pg.py tests/test_location.py tests/test_location_pg.py tests/test_coordinates_pg.py tests/test_publication_authority_race_pg.py tests/test_publication_race_pg.py tests/test_publication_chain_gain_race_pg.py tests/test_publication_proof_replacement_pg.py tests/test_membership_accept_race_pg.py tests/test_tst01_openapi_contract.py -q -o cache_dir=/audit/cache312 --basetemp=/audit/tmp312 --junitxml=/audit/targeted312.xml
# 180 passed, 11 warnings, 357.92s; includes 54 TASK-010 cases and 5 OpenAPI drift cases.

python -m ruff check app tests alembic scripts --no-cache
# All checks passed.
python -m mypy app --cache-dir=/audit/mypycache
# Success: no issues in 82 source files; existing unchecked-untyped-function note.

python -m pytest -q -o cache_dir=/audit/sqlitecache --basetemp=/audit/sqlitetmp --junitxml=/audit/sqlite.xml
# Without TEST_DATABASE_URL: 740 passed, 207 skipped, 57 warnings, 545.39s.

python /audit/run_mutations.py
# G01–G10: 10/10 killed; independent baseline before each mutation.
python /audit/coordinate_mutation.py
# M12: baseline 8 passed; mutant 1 failed, expected IntegrityError no longer raised.
```

Independent probes were executed using `python -m pytest -p tests.conftest /audit/probes.py` with explicit external cache/temp/JUnit paths. The initial run was **11 passed / 1 failed**: the auditor's migration fixture used `name` instead of the existing required Space `label`, so setup through the API failed. Only the outside-repository probe was corrected. The focused follow-up selected `migration_preserves_relationships_and_coordinates`, `import_rename_and_legacy_public_mirror`, and `aparthotel_each_column_fails_closed`: **4 passed / 11 deselected**. There are **15 distinct completed independent probe cases** in total. This does not mean 15 product invariants passed: observation probes intentionally assert and record the three demonstrated defects and the EXACT behavior.

Reproduce the final independent probe set against a newly provisioned disposable database using:

```sh
python -m pytest -p tests.conftest /audit/probes.py -q -s -o cache_dir=/audit/repro-cache --basetemp=/audit/repro-tmp --junitxml=/audit/repro.xml
```

The source of each probe and its inputs/assertions is retained. Logs `probes.log` and `followup.log` preserve the initial harness error and corrected result; no failed execution is hidden.

### Mutation quality

All kills were inspected in JUnit/logs, not inferred from exit status alone:

| Mutation | Actual failed assertion |
|---|---|
| G01 | Forbidden postal_code key appears in public JSON. |
| G02 | Second hierarchy transaction no longer waits for the first. |
| G03 | Invalid parent/child level no longer raises DB error. |
| G04 | ROOM Property request returns 201 instead of 422. |
| G05 | DB ROOM category insertion no longer raises error. |
| G06 | Duplicate source/external identifier no longer raises error. |
| G07 | Cross-country locality request returns 201 instead of 422. |
| G08 | Backfill provenance becomes USER_INPUT instead of LEGACY_BACKFILL. |
| G09 | Aparthotel publishes with 200 instead of 409. |
| G10 | Region query loses its descendant listing. |
| M12 | Invalid exact latitude no longer raises IntegrityError. |

Limits: G01 inserts an empty forbidden field, so it guards the DTO contract, not every conceivable value-exfiltration path; actual sentinel probes supplement it. G02 kills on a missing wait, not a committed cycle; the independent three-node probe checks the intended blocker PID and committed state. G08's label says “guesses structured,” but its actual edit only changes provenance; its kill does not independently establish coverage of arbitrary guessed IDs. No setup/collection failures were counted as kills. The mutation copy's **201 original files** were SHA-256 checked after restoration with no changed files; coordinate migration bytes were also restored and hashed. The actual worktree was never mutated.

## Nonblocking notes and bounded next work

- Optimize public-place N+1 before a meaningful traffic/load target; this audit does not invent a performance acceptance threshold.
- TASK-010 says independent audit is “recommended, not foundation-mandatory” although governance 05 §9 requires it for exact-address and data-transforming migration work. Correct that wording. The independent audit has now actually occurred, so this documentation mismatch is not an extra runtime blocker.
- Reference-release ingestion beyond tested leaf updates, populated national datasets, future Building normalization, and eventual mirror removal remain bounded future work. No full foreign-market launch readiness is asserted.
- Full PostgreSQL suite, CI, deployment and production readiness were not assessed. Previously reported builder totals are not repeated as independent results.
- No requested probe was prevented by a model safeguard. The unexecuted full PostgreSQL suite is a scope/runtime limit, not a pass or a safeguard refusal.

Before acceptance, repair GEO-01/02/03 with regression tests, adjudicate the EXACT policy wording, and request a narrow exact-SHA re-audit of those changes plus relevant regressions. No repair was made in this auditor session.

PRODUCTION READINESS: **NOT ASSESSED / NOT READY**  
DEPLOYMENT: **NOT DEPLOYED**

## CHATGPT HANDOFF

Project: Homies  
Task: TASK-011 — Independent Audit of TASK-010

Audited SHA: `e87352a9862408e76e7ebee08b846dab728d4dac`

Migration: ACCEPTED  
Privacy boundary: NEEDS_FIX — reconcile inherited owner-opt-in EXACT with the absolute TASK-011/D-54 wording; no new geography coordinate leak found.  
Geography model: NEEDS_FIX  
Europe readiness: ACCEPTED — data model only  
Property classification: ACCEPTED  
Product & Growth Doctrine: ACCEPTED

TASK-010: **TASK_010_REQUIRES_TARGETED_FIXES**

P0: 0  
P1: 0  
P2: 3  
P3: 0

New findings:

- GEO-01: contradictory admin area and locality-bound GeoArea accepted and published.
- GEO-02: valid reference names overflow legacy mirrors and return HTTP 500.
- GEO-03: import rename leaves public city and legacy search stale.

Tests actually run: Python 3.12.14; PG16.4/PostGIS3.4.3; targeted 180 passed including 5 OpenAPI; full SQLite 740 passed/207 skipped; ruff clean; mypy 82 files clean; 15 independent observation cases completed after correcting one auditor fixture error; G01–G10 10/10 killed plus coordinate M12 killed with green baselines. Full PostgreSQL suite and CI not run. Exact worktree remains clean; dedicated disposable database removed.

Known debt: public-place N+1; temporary mirrors; reference-release ingestion; optional Building normalization; governance wording. EXACT policy requires explicit canonical reconciliation and is not a newly introduced runtime defect.

Production readiness: NOT ASSESSED / NOT READY  
Deployment: NOT DEPLOYED

REQUEST TO CHATGPT: Adjudicate TASK-011. Current independent verdict requires targeted fixes, so do not establish an accepted TASK-010 slice yet. If TASK-010 is subsequently accepted, establish the accepted Phase-1A product slice and generate the next product task.
