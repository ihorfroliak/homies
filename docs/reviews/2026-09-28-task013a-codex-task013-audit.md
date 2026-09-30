# TASK-013A — Independent Audit of TASK-013

## EXECUTIVE VERDICT

**TASK_013_REQUIRES_TARGETED_FIXES.** Discovery's shared filter model, public-point spatial boundary, price semantics, bounded rendering queries, and archive preservation have substantial independent support. Search validation nevertheless allows anonymous requests to produce HTTP 500. A separate map-count race can produce a negative number of listings without a point.

Findings: **P0 0 · P1 0 · P2 1 · P3 1**. Two additional notes concern URL/input budgets and regression-environment reliability. No exact-location inference channel was found in the inspected implementation or executed probes. No acceptance marker is issued.

## INDEPENDENCE

Read-only independent audit; TASK-013 was not implemented by this auditor. No application/test/repository files were edited, no commit or push or PR was made, and no deployment or production operation occurred. A managed detached worktree was created at the exact commit; containers mounted it read-only. Python bytecode and pytest/static-analysis caches were disabled or placed outside the repository. Mutation changes were made only in `/audit/mutation-copy`, an external copy.

Evidence directory: `C:\Users\ihorf\AppData\Local\Temp\homies-task013a-56567d2`. The scripts, logs, XML results, SQL plans, mutation copies, and this report are there. Synthetic PostgreSQL databases used only the newly created, network-isolated container `homies-task013a-56567d2-db`. Existing development/production databases were not used.

## EXACT SHA

Audited: **56567d24bd764563bc21707c0c027e637a206e16**.

Source branch verified as `claude/TASK-013-search-map-discovery`; source and audit worktree initially clean. Audit worktree: `C:\Users\ihorf\.codex\worktrees\task013a-audit\homies`, detached HEAD. `git merge-base --is-ancestor` returned 0 for both accepted parent `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` and Foundation Baseline 002 `36231840ee52d6185e73fda07e54eab33ffe41f3`. Final verification is recorded in `git-final.txt`. **STOP CONDITION:** the shared source checkout subsequently advanced to `4416e2b14b007ba50aab41cad8e23deea32c4678`. Its final SHA did not match the requested SHA. The last explicit detached-worktree check still showed the requested SHA, detached/clean, with both ancestry checks passing. Following the instruction to stop on mismatch, no further audit execution or inspection of the newer commit was performed. All completed evidence and findings below apply only to the requested frozen SHA; report finalization preserves that evidence and does not extend the audit to the new source HEAD.

Canon consulted: 00 authority, 01/02 principles, 04a §§16–21, 05 governance, 07 doctrine, D-57–D-75, convergence dispositions, roadmap, TASK-013 contract, builder mutation report, and the complete TASK-013 code/migration/mutation diff. Accepted earlier slices were not reopened without TASK-013 evidence.

## ENVIRONMENT

Python **3.12.14**, PostgreSQL **16.4**, PostGIS **3.4.3**. SQLAlchemy 2.0.52, FastAPI 0.141.1, Pydantic 2.13.4, Alembic 1.19.1, psycopg 3.3.4, pytest 9.1.1, ruff 0.15.22, mypy 2.3.0, Pillow 12.3.0, PyJWT 2.13.0. Exact runtime details: `environment.json`.

The cached backend image initially lacked pytest and Pillow. Those failed startup/collection attempts are not test results; dependencies were installed in the external audit directory before substantive runs. No repository dependency change was made.

**Observed environment limitation:** the Docker runtime wall clock moved backwards repeatedly (up to 0.765 seconds in one sampled step). A standalone synthetic-token probe reproduced `ImmatureSignatureError` after an 80 ms wait: a token issued at `06:37:18.200802Z` was decoded at `06:37:17.486941Z`. See `clock.json` and `delayed-jwt.json`. Authentication was not patched to ignore this.

## 1. SEARCH_MODEL — NEEDS_FIX

`SearchQuery` is parsed by the same dependency for list and map. Both row selectors use `select_matching`; counts construct their own COUNT projection but reuse the identical `from_clause` and `filters`. Thus the literal builder claim that all selection goes through `select_matching` is slightly overstated, but there is one filter implementation. The inspected AND/OR/ALL composition is correct.

Independent PostgreSQL compound probing combined overlapping/multiple administrative seeds, locality alternatives, a search area, legacy city/district, bbox and two `has` attributes, and asserted exact IDs on both surfaces. Existing search cases and mutation S08 also exercise exclusions, not merely an all-matching dataset.

The 52-request validation matrix found **HTTP 500** for `10**100` numeric bounds and NUL-bearing city/place IDs on both list and map. PostgreSQL reported integer/bigint overflow or NUL-in-text `DataError`. Invalid furnished/parking values return empty 200 responses despite the stated unknown-values→422 contract. See F13A-01.

NaN/Inf in radius coordinates and bbox, malformed/empty bbox, unknown sort/category/subtype/space type, incompatible classification, invalid attributes, and list offset 10001 were refused as tested. Nonexistent reference IDs returned empty results; cross-country existing IDs returned 422. Those are public reference identifiers, so the existence signal is not a private residential-address enumeration channel. Map has no offset parameter; it ignores an extra offset, rather than implementing offset paging.

## 2. PUBLIC_ELIGIBILITY — ACCEPTED

All four query paths (list rows/count, map rows/count) include `freshness.public_clause`. Independent supported-workflow probes archived a Space and revoked an authority, then tested broad, price, bbox and sort queries; the affected listings remained absent. Synthetic stale/draft/archived offers were also excluded. Existing publication/APARTHOTEL/authority tests form the regression evidence; TASK-013 does not introduce a bypass of those publication guards.

Exact 21×24h eligibility was independently tested at a pinned decision instant, under Europe/Warsaw and Pacific/Kiritimati set on connection checkout. Exactly at the threshold: absent from list, map and map count without a sweep. One microsecond before: present. SQL uses the same production elapsed-seconds predicate. Existing timezone tests additionally exercise database-returned zoned instants and other public routes.

Scope qualification: the inherited public clause checks active status and freshness; it does not independently re-prove every authority chain or Space state at every read. The accepted lifecycle mechanisms take listings down. No new TASK-013 authority/lifecycle regression was established, and this audit does not silently redesign the accepted eligibility model.

## 3. GEOGRAPHY — ACCEPTED

The recursive CTE is seeded once with all selected administrative IDs. Overlapping ancestor/descendant seeds can duplicate CTE rows internally, but IN semantics avoid result multiplication. The independent multi-admin + multi-locality + search-area + city/district + bbox + amenities query returned exactly the intended listing. The existing PostgreSQL cases cover countries, descendants, multiple localities, search areas and unstructured records; the re-anchored mirror/descendant mutants test behavioral failures.

D-57 is preserved: references determine city/district when present; mirrors participate only when that reference is absent. Unstructured addresses match their known country and legacy names, but not finer structured IDs. This is coherent with D-57/D-68. No CTE name collision was reproduced.

## 4. SPATIAL_PRIVACY — ACCEPTED

Both spatial predicates explicitly use `classified_offers.public_geog`; map projection uses public latitude/longitude. There is no distance sort; other sorts use publication time, monthly total, offered area or available date, then ID. Counts share the same spatial predicates. No inspected discovery SQL reads `exact_geog` for selection or order.

The independent inference probe created points on/adjacent to grid boundaries, an ordinary exact point distinct from its public centre, a DISTRICT listing and a coordinate-free listing. It issued **75 box/radius query combinations against both list and map**, then changed all private property coordinates to Sydney while retaining the public points and repeated the same 150 requests. All result sets were unchanged; list/map/count agreement held; DISTRICT/no-point listings never entered spatial results. Small sliding boxes and circles of 1/20/150/300 m included both empty and nonempty answers. Evidence: `spatial.json`.

This is 300 observed surface requests, not a claim to exhaust all possible coordinates. The code dependency on public points explains why further query sequences cannot distinguish exact locations that retain the same public point. Existing sentinel tests check private address, coordinate, phone, identity and address-ID exclusions. Independent radius-exact mutant A01 and viewport-exact S02 must be killed behaviorally (see mutation section).

## 5. LIST_MAP_CONSISTENCY — NEEDS_FIX

On stable data, filtered map IDs equaled all matching list IDs having public points. Inside a bbox, the sets and totals agreed and without-point was zero. Independent price-filtered pagination compared list and map order for every sort. Cap behavior was checked at 499/500/501 point-bearing listings: 499/500 markers with `truncated=false`, then 500 markers with `truncated=true`. Actual cap was 500.

**F13A-02:** map total and with-point are separate statements. A committed publication between them produced `total=0, with_point=1, without_point=-1`, while returning the marker. This is reproducible snapshot inconsistency, not a privacy leak. At Phase-1A traffic the window is small, so this is P3; combining the two aggregate counts in one statement is a bounded correction.

A separately pinned expiry crossing between list COUNT and row SELECT produced `total=1, items=[]`. Separate list/map requests and READ COMMITTED statements do not promise a stable browsing snapshot. The UI must tolerate ordinary drift; negative cardinalities should still be prevented. `map-count-interleaving.json`, `expiry-interleaving.json`, `edge.py`, `extra.json` contain evidence.

## 6. PRICE_SEMANTICS — ACCEPTED

Filters use the named stored integer summaries, inclusive comparisons, and no floating-point conversion or FX: base rent, stated mandatory monthly total, and first month plus mandatory one-offs including deposit. Component summarization and search agree in tested combinations.

The independent PUT /price probe tested INCLUDED with zero/nonzero utilities, ESTIMATED with a positive amount, and NOT_STATED at zero when not included, while also setting rent, admin fee, parking and deposit. It checked labels, monthly/move-in sums, and exact inclusive filter boundaries after each update. INCLUDED utilities are not added twice. Zero not-included utilities are represented as unstated by the current component model, consistent with the label rather than a promise of zero consumption cost.

Provider/agency-fee facets are reasonably deferred: `AGENCY_FEE` is an enum value, but no current public input records it and no listing provider relationship exists. Inferring agency status from the authority holder would be unjustified.

## 7. AVAILABILITY — ACCEPTED

`available_by` compares directly with the stated date, excluding NULL. Unknown dates remain in general search and sort last under available_soonest. `_move_in` takes the UTC date of the database decision instant. Independent PUT/compound probes plus existing freshness/timezone suites and F12 mutation cover this. D-64 is unchanged.

## 8. SORT_PAGINATION — ACCEPTED

All five sorts explicitly use NULLS LAST and ID ascending as the tie-breaker. Independent PostgreSQL testing set equal publication timestamps, equal prices, areas and availability dates, then paged every sort in chunks of three and asserted exact sorted IDs without duplicates/gaps. Filtered 101-listing tests also compared map and list order. Existing tests cover UNKNOWN last and confirmation not bumping newest.

An independent insert between offset pages duplicated the previous page's last ID on the next page. Pause followed by republish moved an old listing to the top, as declared. These are real trade-offs, not snapshot-safe pagination. At Phase-1A scale the documented offset model is acceptable; Saved Search/alerts should use stable IDs and their own delivery cursor, not offsets. Republish can be gamed to bump supply; monitor behavior before changing the approved publication semantics. Evidence: `offset-drift.json`, `paging.xml`, `ties-media.xml`.

## 9. PERFORMANCE_QUERY_COUNT — ACCEPTED

Independent counts on 101 listings with locality+search-area, locality-only and admin-only addresses:

| List limit | 1 | 10 | 24 | 50 | 100 | Map |
|---|---:|---:|---:|---:|---:|---:|
| SQL statements | 8 | 9 | 9 | 9 | 9 | 4 |

A second probe attached an actual approved synthetic image to each of ten structured listings: 9 statements at both limits 1 and 10. Media and price-component loaders remain batched. The benchmark's 100 returned rows had property/space identifiers matching their database foreign keys; no row multiplication or incorrect contains_eager association was found. Evidence: `query-count.json`, `media-query-count.json`, `extra.json`. The parent 10/49/105 measurement was not independently re-timed; current counts were measured independently.

EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) on **5,003 synthetic listings** with varied geography, prices, publication/confirmation dates and availability:

| Query | Execution ms | Notable index use |
|---|---:|---|
| Default first page | 33.063 | sequential/hash plan |
| Locality | 23.290 | ix_addresses_locality |
| Multiple admin areas | 41.806 | recursive/sequential/hash plan |
| Search area | 23.770 | ix_addresses_geo_area |
| Bbox | 25.612 | ix_classified_offers_public_geog; status_confirmed |
| Radius | 0.792 | public_geog; property/space keys |
| Rent range | 5.940 | ix_classified_offers_primary_price_minor |
| Monthly total | 5.738 | estimated_monthly_total_minor |
| Available by | 12.708 | sequential/hash plan |
| Compound | 21.369 | primary_price_minor; status_confirmed; keys |

These are local, concurrent-audit diagnostics, not latency SLOs or production readiness. Both new indexes were selected on this dataset. Default sorting and exact counts will merit fresh measurement at higher volumes; these results do not establish a clearly missing mandatory index. Full plans and SQL: `explain.json`; summary: `explain-summary.json`. Synthetic clone generation retains legitimate foreign-key relationships and price components, rather than disconnected offer rows.

## 10. INDEXES_MIGRATION — ACCEPTED

`d0f2b4c6e8a1_discovery_indexes.py` contains exactly two upgrade create-index operations and their two downgrade counterparts, no data transform. Names/columns match ORM metadata. The migration-chain test and the TASK-012→TASK-013 upgrade/downgrade/upgrade-on-data test are included in the PostgreSQL results. Independent synthetic databases were also migrated from empty to head for each probe session.

Index use was independently established above. Plain CREATE INDEX takes a table write-blocking lock; this is acknowledged in the migration/rollout notes. No production rollout was attempted.

## 11. PRIVACY_SECURITY — NEEDS_FIX

No inspected output schema includes owner/user IDs, authority/LegalParty details, phone, private Address ID, PRG address-point ID or exact coordinates. List's property/space IDs are its existing public entity references. Existing media/privacy/sentinel tests and independent spatial/media probes support the boundary. NUL/overflow errors returned generic 500 bodies, not SQL or stored private data, but they remain a validation defect (F13A-01).

The query echo is `urlencode` inside JSON, not executable HTML. The tested script-like city was encoded; UI code must continue treating it as data. Names/buckets bound metrics: 40 distinct attacker-like city values created no value-bearing labels. Radius ≤50,000 m, list limit ≤100, offset ≤10,000 and map cap ≤500 are implemented. Catalogue validation enforces known filterable `has` codes. The documented actual parameter is repeated `has`; `has[]` is an unknown key and is silently ignored by FastAPI, so clients must use the documented spelling.

No application-level length/count bounds exist for repeated place IDs or free-text search strings. A 10,000-character city and 1,000 distinct locality IDs were accepted and echoed. This is a future resource-budget concern; the probe did not establish resource exhaustion or private-data disclosure. See F13A-03 (NOTE).

## 12. URL_STATE_AND_GROWTH — ACCEPTED

Parameter names/pairs and multi-values are sorted, repeated values deduplicated, default newest omitted, booleans/date/finite-float representations stable. Nonempty and zero-result searches round-tripped to the same responses in independent tests. No hidden search state was found.

Good enough for current bookmarkable searches, with a pre-Saved-Search note: semantically equivalent empty city and absent city produce different keys; -0.0 and +0.0 may also differ. Length budgets are absent. Establish normalization/versioning before treating these strings as universal deduplication/SEO identities. This does not require implementing Saved Search in TASK-013.

## 13. ARCHIVE_INTEGRITY — ACCEPTED

The original TASK-012RA source report was read as raw bytes. SHA-256 exactly matched **e336e1b5330089edf436e243c7c5dae163bf865ec95a94f6faa48ee86bcb872d**. The archive suffix starting at byte offset **1225** equals all **11,624** source bytes; no CR stripping or newline normalization was used. `archive.json` records the check.

All eight already-existing `*-audit.md` Git blobs were byte-identical between parent and audited commit (`previous-archives.json`). `.gitattributes` only disables text normalization for the intended archive pattern; it does not rewrite existing blobs. This is appropriate for verbatim audit preservation. D-75, convergence and roadmap correctly record TASK-012 acceptance at full SHA `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` and keep TASK-013 pending.

## 14. REGRESSION — NOT_ASSESSED

Both full suites were executed. Their original outcomes are retained, not rewritten as green:

| Run | Passed | Failed | Errors | Skipped | Duration |
|---|---:|---:|---:|---:|---:|
| Full SQLite | 799 | 2 | 1 | 301 | 604.12 s |
| Full PostgreSQL/PostGIS-enabled | 1089 | 4 | 0 | 10 | 1304.93 s |
| SQLite failure rerun + S09 baseline | 4 | 0 | 0 | 0 | 8.03 s |
| PostgreSQL full-run failure rerun | 4 | 0 | 0 | 0 | 14.22 s |
| Previously skipped restore module | 9 | 0 | 0 | 0 | 72.70 s |

SQLite failures: below-one-month rejection, authority-to-confirm setup, and negative-price setup, all with freshly issued tokens returning 401. PostgreSQL failures: concurrent double booking (one winner but only nine of eleven expected 409 losers), availability setup (401), media setup (401), and mandate draft setup (missing id). All four passed unchanged on targeted rerun. The two less-specific initial failures are consistent with the independently demonstrated clock issue, but their initial logs do not prove the exact JWT error. No production/auth behavior was weakened.

The full PG run initially skipped nine restore cases because the Python image lacked pg_dump/pg_restore, plus the intentionally gated Stripe live module. PostgreSQL **16.4** client binaries and their libraries were copied from the audit-owned DB container to external `pgtools`; wrapper scripts then ran all nine synthetic restore tests successfully. No production backup/restore was involved.

In aggregate, each of the 1,102 non-live cases had a passing observation across the PostgreSQL-enabled run and its reruns/supplement. This is **not** a single clean full-suite run. The NOT_ASSESSED gate means unqualified clean-run regression certification is withheld in this unstable-clock environment; it does not mean the suites were skipped. CI remains NOT RUN. The final shared-source SHA mismatch is an additional provenance stop, not a regression finding about the frozen commit.

Targeted modules within the full PG-enabled run: new search 22 + 10 passed; freshness PG 11 and timezone PG 46 passed; geography repair PG 27 passed; location PG 10 and coordinate PG 19 passed; publication race/authority/chain-gain/proof-replacement modules 6/37/2/17 passed; migration suite 13 passed; OpenAPI contract 5 passed. Media 20, media pipeline 45, media migration 1 passed; media regressions 15 passed plus one setup failure later passed. `suite-breakdown.json` records every module and skip reason. The TASK-013 migration data-preservation/downgrade/upgrade test passed inside the ten new PG search tests.

## MUTATION REVIEW

**22/22 reviewed mutants killed behaviorally after a green baseline; zero survivors.** Initial invalid baselines for S09 and F13 are retained in `mutations.json`; successful clean-baseline reruns are in `mutations-retry.json`. Consolidation: `mutations-final.json`. All failure traces were read. Setup/collection errors and fresh-token failures were not credited as kills.

| Mutant | Observed meaningful failure |
|---|---|
| S01 | stale/paused listings enter the list |
| S02 | exact-home bbox finds the listing |
| S03 | administrative descendant query loses expected IDs |
| S04 | unknown move-in listing enters available_by |
| S05 | listing exactly on rent ceiling disappears |
| S06 | stale city mirror returns a structured listing |
| S07 | price-sort page IDs differ from sorted tie IDs |
| S08 | filtered map includes an excluded expensive listing |
| S09 | exact latitude appears in public map JSON (rerun) |
| S10 | queries grow to 9/40/82 for 1/10/24 rows |
| S11 | cross-country contradiction returns 200 |
| S12 | category/subtype contradiction returns 200 |
| F12 | UNKNOWN matches available_by after re-anchoring |
| F13 | zero lease term reaches UPDATE and raises SQLite CHECK IntegrityError instead of 422 (rerun) |
| R05 | stale city mirror matches |
| R06 | stale district mirror matches |
| G10 | region search omits descendants |
| A01, independent | radius on exact_geog finds a home in a 20 m exact-point circle |
| A02, independent | count missing rent ceiling reports 7 where filtered list has 6 |
| A03, independent | map order differs from requested ascending order |
| A04, independent | count without eligibility reports 4 rather than 1 |
| A05, independent | country filtering drops the unstructured listing |

F13 is a meaningful endpoint-path behavioral exception caused by the mutant, **not** a setup/collection error; it should not be described as an assertion-only kill. All S kills here were assertion failures. The unchanged baseline was green immediately before each credited mutation.

S01–S12 and the re-pointed F12/F13/R05/R06/G10 definitions were taken from the audited SHA. Five additional mutations were independently authored in external `mutations.py`. The remaining historical F/Z/R/G mutants were **NOT RUN**; the builder's broader mutation totals are not adopted as independent evidence.

SHA-256 restoration covered all **352 files** of the external copy after each batch, with `changed=[]` in both `mutation-restoration.json` and `mutation-restoration-retry.json`. The original worktree was never mutated. Per-run traces are `mutation-01.log` through `mutation-42.log` and `mutation-101.log` through `mutation-104.log`, with matching XML. Mutation scripts use one green baseline per mutant, not one baseline for an entire batch.

## TEST RESULTS — ONLY EXECUTED CHECKS

The reproducible Windows entrypoint is `& $env:TEMP\homies-task013a-56567d2\launch.ps1 <mode>`. It runs Python in the cached backend image with the repository mounted **read-only**, `/audit` mapped to the evidence directory, `PYTHONDONTWRITEBYTECODE=1`, and `PYTHONPATH=/audit/deps:/repo/backend`. Database URLs name only the isolated audit container. See `launch.ps1` and `run.py` for the exact complete Docker arguments and subprocess commands.

Core commands actually executed inside that runner:

```text
python -m pytest -q -p no:cacheprovider --basetemp=/audit/sqlitetmp --junitxml=/audit/sqlite.xml
python -m pytest -q -p no:cacheprovider --basetemp=/audit/postgrestmp --junitxml=/audit/postgres.xml
python -m ruff check app tests alembic scripts --no-cache
python -m mypy app --cache-dir=/audit/mypycache
python -m app.scripts.export_openapi --check
python -m pytest -p tests.conftest /audit/probes.py -q -s -p no:cacheprovider --basetemp=/audit/probetmp --junitxml=/audit/probes.xml
python -m pytest -p tests.conftest /audit/edge.py -q -s -p no:cacheprovider --basetemp=/audit/edgetmp --junitxml=/audit/edge.xml
python -m pytest -p tests.conftest /audit/benchmark.py -q -s -p no:cacheprovider --basetemp=/audit/benchtmp --junitxml=/audit/benchmark.xml
python /audit/extra.py
python /audit/mutations.py
python /audit/mutations.py retry
PG_BIN=/audit/pgbin python -m pytest tests/test_dr_restore_pg.py -q -p no:cacheprovider --basetemp=/audit/restoretmp --junitxml=/audit/restore.xml
```

`edge.py` initially contained five tests; two paging tests and one media/tie test were then appended and run by explicit node ID (`paging` and `ties-media` modes), not represented as a second full eight-test edge run. The validation and interleaving tests intentionally assert observed defective behavior to make evidence reproducible; their passing status does not mean the product passes those gates.

Independent probe results: `probes` 5 passed; `edge` initial 5 passed; `benchmark` 1 passed; `paging` 2 passed; `ties-media` 1 passed; `extra.py` all assertions passed. Ruff clean; mypy no issues in 87 files; OpenAPI snapshot up to date. Failed SQLite cases plus the S09 baseline were rerun: 4 passed. PostgreSQL failure rerun: 4 passed; synthetic restore supplement: 9 passed. Additional exact retry commands/results are in the evidence scripts and logs.

**NOT RUN:** CI, paid-provider/Stripe live tests, production tests, production DR/readiness, deployment/load SLO validation. No claim of live-provider readiness follows from local tests.

## NEW FINDINGS

### F13A-01 — P2 MEDIUM — Unbounded/unsafe query values reach database adaptation

**Location:** `backend/app/modules/properties/search.py:172–175, 187–210` (input declarations), `:263–279` (ID handling), `:340–369` (filter construction); both public routes consume this dependency.

**Requirement:** TASK-013 validation contract/D-68 and audit gate 1 require invalid input to receive 422 rather than 500; unknown supported catalogue values must be rejected. Public anonymous input must be validated before SQL adaptation.

**Reproduction:** run `launch.ps1 probes` and `launch.ps1 edge`. Minimal anonymous GETs on either `/v1/classifieds` or `/v1/classifieds/map`:

```text
?max_rent=10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
?min_rooms=10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
?city=%00
?locality_id=%00
```

**Observed:** HTTP 500, generic Internal Server Error. The independent exception probe identifies PostgreSQL integer/bigint overflow and `PostgreSQL text fields cannot contain NUL (0x00) bytes`. `min_area_m2` and `max_term_months` huge values also fail. `furnished=INVALID` and `parking=INVALID` instead return 200/empty, an additional gap in the promised validation vocabulary.

**Expected:** bounded supported numeric values and valid text/reference syntax proceed; invalid values return a stable 422 without invoking an invalid database operation. Unknown furnished/parking values return 422.

**Suggested bounded repair:** add DB-compatible upper bounds to all numeric filters; reject NUL in all accepted text/ID paths; validate furnishing/parking against their existing catalogues; add PG-backed endpoint regressions for both surfaces. Define conservative text/repeat budgets in the same boundary if desired. Do not catch every SQL error as 422; prevent these known invalid inputs. Existing list inputs share some inherited weaknesses, but new rent filters, the new map surface and the replaced canonical dependency are TASK-013's responsibility.

**CANONICAL DECISION required:** NO for 422 validation and existing catalogues. If arbitrary product-level limits beyond DB representability are chosen, record their rationale; no location-policy change is needed.

### F13A-02 — P3 LOW — Map count arithmetic can become negative during publication

**Location:** `backend/app/modules/properties/router.py:848–849, 872`.

**Requirement:** D-71 / 04a §21 / map response contract: `with_point` and `without_point` partition the matching total; counts describe the same matching universe.

**Reproduction:** `launch.ps1 edge`, `test_map_count_interleaving`. Start with a paused, fresh point-bearing listing. Execute the map total count (0); in a separate audit DB transaction publish/activate that listing; continue the point count and row select. The probe interposes only at the count-call boundary and commits a synthetic database update, leaving production query code intact.

**Observed:** HTTP 200 with a marker, `total=0`, `with_point=1`, `without_point=-1`. Evidence: `map-count-interleaving.json`.

**Expected:** nonnegative counts computed over one consistent aggregate view. Ordinary offset drift across independent requests is a separate accepted limitation.

**Suggested bounded repair:** calculate total and with-point in one SQL aggregate statement using the same predicate/decision instant; derive without-point from those values. Decide explicitly whether row results also need the same snapshot, without changing offset semantics merely for this fix. Clamping a negative number would hide, not repair, the inconsistent partition.

**CANONICAL DECISION required:** NO. P3 because the exposure window is narrow and affects count presentation, with no demonstrated privacy or authorization breach.

## NONBLOCKING DEBT

**F13A-03 — NOTE — URL and request budgets before Saved Search.** `search.py:96–147,172–179`: no text/repeat count bound; empty and absent no-op values need not share a canonical key. Independent accepted requests with 1,000 locality IDs and 10,000-character city prove the present behavior. URL encoding keeps the echo data-safe; no stored private value or demonstrated XSS is involved. Suggested follow-up: finite input budgets and a versioned normalization contract before deduplication/SEO/alerts depend on it. No canonical decision is necessary for basic normalization; product limits should be documented.

**F13A-04 — NOTE — Stable regression environment required.** See ENVIRONMENT and REGRESSION. Backward clock jumps can invalidate new JWTs and make otherwise unrelated test setup fail. Preserve failures and rerun on a stable clock; do not count these as mutation kills or weaken JWT verification for audit convenience. This is not evidence of a TASK-013 auth regression. No canonical decision required.

Offset paging under concurrent writes, republish bumping, exact-count cost, owner-view N+1, provider/agency facets, client clustering and future SEO remain documented debt. No production claim is made from the 5k benchmark. The measured count race is specifically F13A-02, not hidden among generic pagination limitations.

## FINAL VERDICTS

| Gate | Verdict |
|---|---|
| 1 Search model | NEEDS_FIX |
| 2 Public eligibility | ACCEPTED |
| 3 Geography | ACCEPTED |
| 4 Spatial privacy | ACCEPTED |
| 5 List/map consistency | NEEDS_FIX |
| 6 Price semantics | ACCEPTED |
| 7 Availability | ACCEPTED |
| 8 Sort/pagination | ACCEPTED |
| 9 Performance/query count | ACCEPTED |
| 10 Indexes/migration | ACCEPTED |
| 11 Privacy/security | NEEDS_FIX |
| 12 URL state/growth | ACCEPTED |
| 13 Archive integrity | ACCEPTED |
| 14 Regression | NOT_ASSESSED |

**Overall: TASK_013_REQUIRES_TARGETED_FIXES.** P0 0; P1 0; P2 1; P3 1. The primary bounded repair is search-input validation. The map-count correction is small but classified nonblocking P3. A narrow re-audit should reproduce both and repeat the affected search/PG/mutation tests in a stable-clock environment. The shared source advanced during this audit; obtain an explicit new handoff SHA for any repair/newer-commit audit. No changes at `4416e2b14b007ba50aab41cad8e23deea32c4678` were assessed.

## PRODUCTION READINESS: NOT ASSESSED

## DEPLOYMENT: NOT DEPLOYED

CHATGPT HANDOFF

Project: Homies

Task:
TASK-013A — Independent Audit of TASK-013

Audited SHA:
56567d24bd764563bc21707c0c027e637a206e16

Independent auditor:
YES

Search model: NEEDS_FIX
Public eligibility: ACCEPTED
Geography: ACCEPTED
Spatial privacy: ACCEPTED
List/map consistency: NEEDS_FIX
Price semantics: ACCEPTED
Availability: ACCEPTED
Sort/pagination: ACCEPTED
Performance/query count: ACCEPTED
Indexes/migration: ACCEPTED
Privacy/security: NEEDS_FIX
URL state/growth: ACCEPTED
Archive integrity: ACCEPTED
Regression: NOT_ASSESSED

TASK-013:
TASK_013_REQUIRES_TARGETED_FIXES

P0: 0
P1: 0
P2: 1
P3: 1

New findings: F13A-01 invalid anonymous query values cause 500; F13A-02 concurrent publication can make map without_point negative.
Tests actually run: full SQLite 799 passed / 2 failed / 1 error / 301 skipped; full PG-enabled 1089 passed / 4 failed / 10 skipped; all seven failed cases passed on rerun; nine initially skipped synthetic restore tests passed separately; independent probes, ruff, mypy and OpenAPI passed. No single clean full-suite run; CI not run.
Mutations: 22/22 meaningful kills after green baselines: S01–S12, five re-anchored regressions, five independent mutants; SHA-256 restoration verified.
Known debt: input/key budgets, offset and republish trade-offs, exact-count cost, deferred facets/clustering/SEO; unstable Docker wall clock limits clean regression evidence.

Production readiness:
NOT ASSESSED

Deployment:
NOT DEPLOYED

REQUEST TO CHATGPT:
Adjudicate TASK-013A. If TASK-013 is accepted, formally establish the accepted SHA as the TASK-013 Phase-1A slice and determine the next vertical slice (proposed: TASK-014 Saved Search / alerts). If fixes are required, request a bounded builder repair and a narrow re-audit.
