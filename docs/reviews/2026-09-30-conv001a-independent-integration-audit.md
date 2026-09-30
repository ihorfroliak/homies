# CONV-001A — Narrow Independent Integration Audit (Homies)

Independent read-only auditor: Claude Code, fresh session. This session did not build CONV-001, TASK-014 or PR-001.
Nothing was fixed, committed, pushed, merged or deployed.
Date: 2026-09-30, about 12:25–13:30Z.

| | |
|---|---|
| Audited SHA | `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` (`claude/CONV-001-product-infra`, local and origin tip) |
| PRODUCT parent (P1) | `7ffb4f51dd315363362df1a5f8fc5c19a57767dc` (TASK-014, accepted by TASK-014RA) |
| INFRA parent (P2) | `5cad442f07264ab25b3024c96fc691ad9c7a75fa` (PR-001, accepted by PR-001RA2) |
| Merge base | `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` |
| Evidence harness | `9aba64fc2e2ffc6973221253b45f5fe6aca9df86` (`evidence/CONV-001-stable`) |
| CI run / evidence run | `36644550108` / `36644558783` (job `109664394956`) |
| Evidence folder | `C:\Users\ihorf\Projects\homies-audit-evidence\CONV-001A\` (`CHECKPOINT.md`, `logs/`, `probes/`, `mut/`, `copy/`) |

The audit ran in a fresh detached worktree (`CONV-001A/wt`), which stayed clean. Code ran from a byte-exact LF `git archive` of the candidate (`CONV-001A/src`). The auditor built its own images from that source:

- `cva-test:5abfd7b` (sha256:a9adb411…);
- `cva-prod:5abfd7b` (sha256:4f4ed4a6…).

Builder images were not reused. Databases were disposable `postgis/postgis:16-3.4` containers with synthetic credentials. They have been removed.

---

## 1. Merge provenance — ACCEPTED

| Check | Result |
|---|---|
| `git rev-parse HEAD` | `5abfd7bc…` ✔ |
| `git status --short` | empty ✔ |
| `%P` | `7ffb4f51… 5cad442f…`: exactly two parents, in product-then-infra order ✔ |
| `git merge-base P1 P2` | `879bf56c…` ✔ |
| Parents rewritten? | No. The parent SHAs are the accepted SHAs themselves, so the histories are the accepted objects ✔ |
| Squash, rebase or cherry-pick substitute? | No. It is a true 2-parent merge commit ✔ |
| Hidden post-merge commits? | No. Local branch, `origin` and `ls-remote` all equal `5abfd7bc` ✔ |
| Harness | `9aba64f` has the single parent `5abfd7b` and adds only `.github/workflows/evidence-conv001.yml` and `evidence/conv_sentinels.py` ✔ |

## 2. Audit archives — ACCEPTED

| Archive in candidate | sha256 | Original |
|---|---|---|
| `docs/reviews/2026-09-29-task014ra-independent-task014r-audit.md` | `6c156fe6…4d909` | `TASK-014RA/TASK-014RA-FINAL-REPORT.md`, identical |
| `docs/reviews/2026-09-29-pr001ra2-independent-pr001r2-audit.md` | `18341ba7…8aa` | `PR-001RA2/PR-001RA2-FINAL-REPORT.md`, identical |
| `docs/reviews/2026-09-29-pr001ra-independent-pr001r-audit.md` | `aac50ec0…7cd` | `PR-001RA/PR-001RA-FINAL-REPORT.md`, identical |

The hashes match both the committed blob (`git show HEAD:…`) and the checked-out file.

`.gitattributes` keeps `docs/reviews/*-audit.md -text`. The merge only dropped a leading blank line; the result is the infra parent's file byte for byte. `git ls-files --eol` shows `attr/-text` on all 2026-09-28/29 independent audit reports, with no normalisation.

## 3. Scope boundary — ACCEPTED

- **Independent re-merge.** A fresh `git merge --no-commit 7ffb4f5 + 5cad442` on a scratch worktree conflicts only in `.gitattributes` (AA), `docs/DEVLOG.md` and `docs/canonical/IMPLEMENTATION-CONVERGENCE.md`. This matches the builder's claim.
- **Candidate vs mechanical merge.** Comparing the candidate with the mechanically merged index, the only code difference is `backend/tests/test_public_generation.py`. The other differences are conflict resolution in the three files above, `PROJECT-STATUS.md`, and the two new archives.
- **Combined diff.** `git show --cc` agrees: it shows hunks only for that test, three docs and two archives.
- **Nothing unrelated.** There is no business feature, no schema change, and no PR-002, PR-003 or TASK-015 work.
  - `alembic/versions` is identical to P1: 26 revisions. The infra line added no migration (`879bf56..5cad442` has no version diff).
  - There is no `schema_lineage`, release-manifest or lineage machinery (grep is empty).
  - There is no provider activation.
  - `ops/`, `.github/` and `backend/Dockerfile` are identical to P2. `backend/pyproject.toml` and `constraints.txt` are identical to P2.

## 4. Semantic test interaction (atomicity × generic 500) — ACCEPTED

The merged test is at `backend/tests/test_public_generation.py:167-182`. It still injects the failure after `_open_episode` has written the generation, the event and the work item.

It then asserts:

- `assert_unhandled_500`: HTTP 500 with the body `{"detail":"Internal Server Error"}`, and a `homies.http` log record whose `exc_info` is `RuntimeError`;
- the offer is still `("draft", 0, None)`;
- `_state(oid) == (0, [], [])`, meaning no generation, no work item and no event.

The product invariant assertions are unchanged; only `pytest.raises` was replaced. **This is not a weakening.**

Independent evidence:

| Probe | Result |
|---|---|
| `probes/test_cva_probes.py::test_a_pg_…fresh_connection`, run on real PostgreSQL/PostGIS in two variants (failure after the fully flushed episode, and before it) | HTTP 500 with a generic body. `X-Request-ID` echoes the caller id. The `homies.http` record carries `exc_info` RuntimeError and `request_id` equal to that id. The client sees no class, message or trace. A **fresh raw psycopg connection** then finds: offer `('draft', 0, None)`, 0 `listing_public_generations`, `domain_events` count unchanged, 0 `ListingBecamePublic`, 0 matches/deliveries/user_notifications, 0 `idle in transaction`. A retried publish gives generation 1 exactly, one row and one dedup key. **PASS** |
| The same probe on SQLite | PASS |
| Mutant **T1**: `db.commit()` added at the end of `_open_episode` (a partial episode survives) | Merged test **KILLED** by its assertion `'active' != 'draft'`. Baseline was green first |
| Mutant **T2**: the request-id middleware catches only `ZeroDivisionError` (the 500 contract is lost) | Merged test **KILLED**: the exception escapes the TestClient and the test FAILS, not ERRORs. Baseline was green first |

Logs: `logs/probe-A-B-*.txt`, `logs/mut-T1.txt`, `logs/mut-T2.txt`.

## 5. Alembic — ACCEPTED

`backend/alembic/env.py` is an exact union of both sides:

- from the product side, imports of `ListingPublicGeneration`, `SavedListing`, `SavedSearch`, `AlertDelivery` and `SavedSearchMatch`;
- from the infra side, the `%`→`%%` escaping and `fileConfig(..., disable_existing_loggers=False)`, gated by `configure_logger`.

Results:

- `alembic heads` gives `f3b5d7e9a1c2 (head)`, one head (`logs/gates.log`).
- There is no merge migration and no tuple `down_revision`.
- The CLI was run from the production image against a database whose owner password contains `%` (URL-encoded as `%25`). It exited 0, wrote 26 `Running upgrade` INFO lines (logging works), and leaked no password (`logs/rt-alembic-cli.txt`).
- At runtime, app self-verification logs `schema verified at head f3b5d7e9a1c2`, and `alembic.runtime.migration` INFO lines appear in the JSON log, so loggers are preserved.

## 6. Migration integration — ACCEPTED

All of these ran on real PG 16.4 / PostGIS 3.4.3:

- **Fresh `base → head`:** in the PG suite fixture, the CI-equivalent `alembic upgrade head` (`logs/suites/pg-migrate.log`), the runtime cluster, and probe `test_fresh_install_and_populated_task013`. All passed.
- **TASK-013-shaped database `d0f2b4c6e8a1 → f3b5d7e9a1c2`:** the auditor's own earlier TASK-014RA probes, re-run on the merge.
  - `test_t14ra_mig013_pg`: a populated TASK-013 database with no `ListingBecamePublic` history, upgraded to head. **Declared backfill only; no notification flood.** 1 passed.
  - `test_t14ra_migration_pg`: single head, generation round trip, no duplicate `dedup_key`s. 4 passed.
- **TASK-014-shaped database under the integrated runtime:** the auditor dumped a head database containing TASK-014 rows (offer, generation, saved search, match, 4 deliveries, event, user notification) and restored it as `homies_rt2`. It then applied `ops/sql/app_role.sql` and reset the generation to `pending`.
  - The production image starts under `homies_app`. Schema and ledger privileges are verified, 3 workers start, and `/readyz` answers 200.
  - The alert worker reprocessed the pending item to `done`. Matches (1), deliveries (4), events (1) and user notifications (1) were unchanged: **no duplicates**.

Downgrade was exercised only inside probes. It is not claimed as a production rollback.

## 7. Application composition — ACCEPTED

`backend/app/composition.py` is an exact union:

- from the product side: `saved` and `alerts` routers, their tags, and the `saved-search-alerts` worker;
- from the infra side: `request_id_middleware` registered last, which makes it outermost.

| | PRODUCT | INFRA | MERGED |
|---|---|---|---|
| OpenAPI operations | 91 | 76 | **91** |
| Workers | notifications, listing-freshness, saved-search-alerts | notifications, listing-freshness | notifications, listing-freshness, saved-search-alerts |
| user_middleware (outer→inner) | metrics, rate_limit | request_id, metrics, rate_limit | **request_id, metrics, rate_limit** |

The operation sets satisfy PRODUCT ⊆ MERGED, INFRA ⊆ MERGED and MERGED == PRODUCT ∪ INFRA. Nothing is lost and nothing extra appears.

- Present: `/healthz`, `/readyz`, `/metrics`, saved listings and searches, matches, inbox, notification preferences, unsubscribe and map.
- The generic 500 works on product routes (§4, §8).

Sources: `logs/inv-*.json`, `logs/openapi-union.txt`.

## 8. Middleware — ACCEPTED

The effective order is request_id → metrics → rate_limit, as the inventory shows. Probe `test_b_middleware_paths_all_correlated`, run on the real Phase-1 app, gave:

| Request | Result |
|---|---|
| `/healthz` | 200, caller id echoed |
| `/v1/classifieds` | 200, generated 32-hex id |
| Validation failure | 422 with the id |
| `/v1/me/saved-searches` without auth | 401 with the id |
| Real 429 on the TASK-014 `unsubscribe` policy | 429 with the id and `Retry-After ≥ 1` |
| Real unhandled 500 on `/publish` | 500 with the id and a correlated log record |

Metrics counted both the `5xx` on the publish route and the `4xx` on unsubscribe.

A runtime check against the production image confirmed that every `/healthz` and `/readyz` response echoes the caller id, including during outages.

## 9. Config — ACCEPTED

`backend/app/core/config.py` is an exact union:

- the infra side's fail-closed ENV warning, dev-database detection, and removal of the Redis/Meili/NATS settings;
- the product side's saved-search worker settings, limits and `public_web_base_url`.

The production image (`ENV=production`) was tested against this matrix (`logs/cfg-*.txt`):

| Config | Result |
|---|---|
| `JWT_SECRET` empty / known default / `WEBHOOK_SECRET` short | **REFUSE** (exit 3, `InsecureConfigurationError`) |
| `DATABASE_URL` with dev creds `homies:homies` / loopback `:5433/homies` / sqlite / unset (default) | **REFUSE** (exit 3) |
| `DATABASE_URL=""` | exit 1 (URL parse at import; pre-existing, still fails closed) |
| Valid synthetic config under `homies_app` | **START** |

No secret appeared in any log. No security rule was weakened.

## 10. Test fixtures — ACCEPTED

`backend/tests/conftest.py` is an exact union: `assert_unhandled_500` comes from the infra side, and the TASK-014 tables were added to both PG cleanup lists.

- The two lists are identical.
- They cover all 55 application tables in a migrated database.
- The only tables left out are `alembic_version`, `spatial_ref_sys` and the seeded reference tables (`countries`, `geo_sources`, `attribute_definitions`). That is intentional.
- SQLite still uses `StaticPool` and `create_all`/`drop_all` per test.

Both full suites are green, and the probe runs were order-independent (§18). No state leak was found.

## 11. OpenAPI union — ACCEPTED

- The merged generated spec equals the committed `docs/api/openapi.json`, which equals P1's spec. The drift test passed in both suites.
- The infra parent's spec equals the ancestor `879bf56`'s spec: infra changed no API.
- The only infra-op definition that differs in the merge is `GET /v1/classifieds`, and that is product evolution from TASK-013/014.
- Spectral: 0 errors, 49 warnings, exit 0. AsyncAPI validate: exit 0 (`logs/spectral.txt`).

## 12. Product parent preserved — ACCEPTED

I re-ran my own independent TASK-014RA probes against the merged candidate: `test_t14ra_repairs_pg.py` and `test_t14ra_scale_validity_pg.py`, **54/54 pass**. They cover:

- F2 corrupt canonical query and fingerprint → INVALID for every consumer, plus send-time suppression;
- X13, another user's search cannot authorise;
- X18, paused / notifications-off searches create no match rows;
- F1, capabilities durable before SMTP, crash and retry;
- N3, F4, F5.

One of my own probes (`test_f4_unrelated_integrity_error_still_raises`) had expected an `IntegrityError` to escape the TestClient. On the merge it fails for exactly the §4 reason. Adapted to the generic-500 contract (500, rid, logged `IntegrityError`, row unchanged), it passes.

The committed product mutation runner, run on a fresh copy, killed **16/16**, and the copy was restored byte-identical. The product sentinels X13, X18, F1-a, F1-b, F2-a and F2-b were all KILLED (§19). Public-generation atomicity is covered in §4.

## 13. Infra parent preserved — ACCEPTED

- **m12:** removing `wait_for` gives "/readyz did not answer within 21 s … decision deadline is missing". KILLED.
- **Canary:** c01 (name-only detection) and c02 (any version) were both KILLED. The real canary run exited 0 with 9 PYSEC advisories, and the shipped pins audit clean.
- **Unhandled 500:** M01 was KILLED. The generic 500, request id and correlated log were confirmed on a product route (§4, §8).
- **Production guard:** M06 and M07 were KILLED, and the runtime matrix in §9 refuses as expected.
- **Image default:** M08 was KILLED. At runtime the image reports `ENV=production`, Python 3.12.14 and 26 migrations.

## 14. Readiness — ACCEPTED

The production image ran against its own PG container (`logs/rt-readiness.txt`):

| State | /healthz | /readyz |
|---|---|---|
| Healthy | 200 | 200 |
| Stopped | 200 | **503** in 4.28 / 4.12 s (`TimeoutError`) |
| Recovered | 200 | 200 |
| Frozen (`docker pause`) | 200 | **503** in 2.30 / 2.27 s (`ConnectionTimeout`) |
| Recovered | 200 | 200 |

These times match PR-001RA2. RA-3 (thread-pool isolation) was not tested for a fix and is not claimed fixed.

## 15. Workers — ACCEPTED

Probe `test_cva_workers.py` covers the lifespan under a non-test env with every flag on, including `BOOKING_EXPIRY_WORKER_ENABLED`:

- `started_workers` is exactly (notifications, listing-freshness, saved-search-alerts);
- each worker is started once and stopped once, and `ensure_schema` runs once;
- the booking-expiry worker never starts;
- with all flags off, no worker starts.

The runtime logs agree: one "notification worker started", one "saved-search alert worker started", the freshness sweep ran, and there was no booking-expiry log.

## 16. Phase boundary — ACCEPTED

- `test_phase1_boundaries.py` and `test_phase1_runtime.py` pass, together with the worker probe: 41 passed.
- The merged spec has no bookings, payments, ledger, payout, webhook or short-stay paths.
- The admin paths are the Phase-1 set, the same as the parents'.

## 17. Exact-SHA evidence — ACCEPTED

I read the public GitHub API without authentication.

- **CI run `36644550108`:** workflow `ci.yml`, event `push`, `head_sha` = `5abfd7bc6f6b…`, attempt 1. All 5 jobs succeeded: backend, image, secrets, monitoring, contracts.
- **Evidence run `36644558783`:** head `9aba64f`, event push, success.
  - The harness checks out `ref: SOURCE_SHA` explicitly. It asserts `rev-parse == SOURCE_SHA` and `%P == "P1 P2"`.
  - The `provenance` annotation reads: `checked_out=5abfd7bc… parents=7ffb4f51… 5cad442f…`.
  - This is not a PR merge ref.

## 18. Evidence completeness — ACCEPTED

The builder's evidence annotations were read from the public API. Raw logs return **403** and the artifact zip needs sign-in, so neither was seen.

| | Builder (evidence annotations) | Auditor, independent local run (exact-SHA LF source, own images) |
|---|---|---|
| Python | 3.12.14 | 3.12.14 |
| PostgreSQL / PostGIS | 16.4 / 3.4.3 | 16.4 / 3.4.3 (`postgis/postgis:16-3.4`) |
| SQLite suite | 1071 passed, 372 skipped | **1071 passed, 372 skipped, 0 failed** (exit 0) |
| PG suite (`HOMIES_REQUIRE_RESTORE_DRILL=1`, coverage) | 1442 passed, 1 skipped | **1442 passed, 1 skipped (Stripe live only), 0 failed**; coverage 91.9% (exit 0) |
| TASK-014R mutations | 16/16 killed | **16/16 killed** |
| Integration sentinels | 13/13 KILLED | **13/13 KILLED** |
| Gates | — | pinned == installed 70/70, heads = 1, ruff, mypy, pip-audit clean, canary OK |

- **Restore drills were not skipped.** Run directly, the 10 drill tests passed.
- **A missing drill fails red.** With `HOMIES_REQUIRE_RESTORE_DRILL=1` and `pg_dump` removed, collection ERRORs. Without the variable, the drill skips (`logs/drills.txt`).
- **The evidence annotation's drill count is not meaningful.** It reports "1 drill testcases in junit", but that number is an artefact (see CV-N1). The trustworthy signals are "skipped drills: 0" and the skip list, which contains only Stripe.

## 19. Integration sentinels — ACCEPTED

I ran the harness's `evidence/conv_sentinels.py` myself (sha256 `25fb6f9d…`) on the auditor's database. Result: **13/13 KILLED**.

- Every baseline was green on the first try, with no reruns needed.
- Every kill was a pytest exit 1 with FAILED tests and no ERROR lines, and the source SHA-256 was restored.
- The recorded `E` lines are behavioural assertion failures:
  - X13: delivery `delivered` instead of `suppressed`;
  - X18: match rows `!= []`;
  - F1-a: link disabled `notifications_enabled`;
  - F1-b: new capability ≠ reused;
  - F2-a/b: `'VALID' == 'INVALID'`;
  - m12: 21 s deadline;
  - c01/c02: `detected` True;
  - M01: RuntimeError escapes;
  - M06/M07: `DID NOT RAISE InsecureConfigurationError`;
  - M08: the `ENV ENV=production` Dockerfile contract, backed by the runtime image check in §13.
- Coverage: product F2, X13, X18 and unsubscribe durability (F1-a/b) are included, and infra m12, canary, unhandled 500, env/database guard and image default are included.

## 20. Restore / monitoring — ACCEPTED

- CI still has `HOMIES_REQUIRE_RESTORE_DRILL: "1"`, and the drills are required (§18).
- `promtool check config` passed, `check rules` found 13 rules, the rule unit tests passed, and `amtool check-config` passed (`logs/monitoring-image.txt`).
- `ops/monitoring` is identical to the infra parent.
- The CI synthetic restore is **not** production backup or DR evidence.

## 21. Status truth — ACCEPTED

- `PROJECT-STATUS.md`, `IMPLEMENTATION-CONVERGENCE.md` and `DEVLOG.md` all state:
  - TASK-014 accepted at `7ffb4f51…`;
  - PR-001 accepted at `5cad442f…`;
  - CONV-001 an integration candidate, **CONV-001A REQUIRED**, not accepted;
  - NOT READY / NOT DEPLOYED.
- The pages give the candidate SHA by reference ("named in the builder report"), because a commit cannot contain its own SHA. The current status is unambiguous.
- The verdict labels match the archived reports.
- No non-empty line of either parent's DEVLOG was lost. In CONVERGENCE the only replaced lines are the Redis/Meili/NATS rows, which took the infra side's "REMOVED" rows (an infra change from the ancestor).
- Historical sections are intact.

## 22. Known debt — not reopened

I found no CONV-001 regression in the carried debt:

- PR-003: RA-3 and business-request DB deadlines;
- TASK-014: N-2, RA-N1, X04 CAS, RA-N5;
- MICRO-001: F13RA-N01, token wording / D-81, RA2-N1;
- tooling: F13RA-N02, Node 20 deprecation (seen again as a warning annotation), N-A/C/D/E/F.

## 25. Findings

### CV-N1 — NOTE — the evidence harness miscounts drill test cases
- **File:** `.github/workflows/evidence-conv001.yml:110` (harness `9aba64f`, evidence only, never merged).
- **Parent invariant affected:** none. This is evidence presentation only.
- **Reproduction:** pytest's `--junitxml` output is one line. On `tests/test_request_id.py` the auditor measured `wc -l` = 0 with 13 `<testcase` elements, and `grep -c` = 1. So `grep -cE 'test_dr_restore' pg.xml` always prints 1.
- **Expected:** the annotation gives the number of drill test cases.
- **Actual:** "1 drill testcases in junit". The real number is 10, all of which passed locally.
- **Impact:** none on the candidate. The "skipped drills: 0" and skip-list annotations remain meaningful.
- **Bounded repair:** count with `grep -o '<testcase [^>]*test_dr_restore' pg.xml | wc -l` in future harnesses.
- **Canonical decision required:** NO.

### CV-N2 — NOTE — the Phase-1 restore drill does not cover TASK-014 tables
- **File:** `backend/tests/test_dr_restore_phase1_pg.py:49-52` (`TABLES`).
- **Parent invariant affected:** none weakened. The infra drill predates TASK-014, and the product parent had no drill. This gap is exposed by the merge, not introduced by it.
- **Reproduction:** `TABLES` contains none of `listing_public_generations`, `saved_searches`, `saved_search_anchors`, `saved_search_matches`, `alert_deliveries`, `user_notifications`, `notification_preferences`, `unsubscribe_tokens` or `saved_listings`. The drill seeds no saved search.
- **Expected (target):** Phase-1 backup/restore evidence also covers saved-search/alert state and capability tokens.
- **Actual:** only an incidental `ListingBecamePublic` event and generation row exist from the publish. Their values are not compared.
- **Impact:** low. The auditor's manual pg_dump → pg_restore of a TASK-014-shaped database, followed by an integrated start, preserved all rows and did not duplicate work (§6). This is not production DR evidence.
- **Bounded repair:** extend `TABLES` and the seed with one saved search, match, delivery and unsubscribe token.
- **Canonical decision required:** NO.

### CV-N3 — NOTE — the merged atomicity test does not assert the correlation id
- **Files:** `backend/tests/conftest.py:445-456` (`assert_unhandled_500`), `backend/tests/test_public_generation.py:176`.
- **Parent invariant affected:** none. The request-id contract is proven by the infra tests (`test_request_id.py`, on a synthetic app) and by the auditor's probe on the product route.
- **Reproduction:** read the code. The helper checks status, body and the logged exception type. It does not check `X-Request-ID` or that `record.request_id` matches.
- **Expected:** the integration test proves the whole infra 500 contract on a product route.
- **Actual:** the contract is proven only partly in the candidate's own suite, and fully by the auditor probe.
- **Impact:** a regression that dropped the id only on product routes would not be caught by this test. `test_request_id.py` does cover the shared middleware.
- **Bounded repair:** add 2 assertions (header present, and it equals the log record's `request_id`) to `assert_unhandled_500`.
- **Canonical decision required:** NO.

## 24. Required results

```text
MERGE_PROVENANCE          = ACCEPTED
AUDIT_ARCHIVES            = ACCEPTED
SCOPE_BOUNDARY            = ACCEPTED
ATOMICITY_500_INTERACTION = ACCEPTED
ALEMBIC_INTEGRATION       = ACCEPTED
MIGRATION_INTEGRATION     = ACCEPTED
APPLICATION_COMPOSITION   = ACCEPTED
MIDDLEWARE_INTEGRATION    = ACCEPTED
CONFIG_INTEGRATION        = ACCEPTED
TEST_INFRA_INTEGRATION    = ACCEPTED
OPENAPI_UNION             = ACCEPTED
PRODUCT_PARENT_PRESERVED  = ACCEPTED
INFRA_PARENT_PRESERVED    = ACCEPTED
READINESS_INTEGRATION     = ACCEPTED
WORKER_INTEGRATION        = ACCEPTED
PHASE_BOUNDARY            = ACCEPTED
EXACT_SHA_EVIDENCE        = ACCEPTED
EVIDENCE_COMPLETENESS     = ACCEPTED
INTEGRATION_SENTINELS     = ACCEPTED
OPERABILITY_REGRESSION    = ACCEPTED
STATUS_TRUTH              = ACCEPTED
```

## 26. Final verdict

```text
P0:   0
P1:   0
P2:   0
P3:   0
NOTE: 3 (CV-N1, CV-N2, CV-N3)
```

**CONV_001_ACCEPTED_WITH_NONBLOCKING_NOTES**

```text
INTEGRATED_BASELINE_ACCEPTED

SHA:
5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98

PRODUCT PARENT:
7ffb4f51dd315363362df1a5f8fc5c19a57767dc

INFRA PARENT:
5cad442f07264ab25b3024c96fc691ad9c7a75fa
```

This audit does not merge anything to `main`; that needs separate authorisation. MICRO-001, PR-002, PR-003 and TASK-015 have not been started. Control returns to ChatGPT and the founder.

```text
PRODUCTION READINESS:
NOT READY

DEPLOYMENT:
NOT DEPLOYED
```

An accepted integrated baseline is not the same as production readiness.

---

```text
CHATGPT HANDOFF

Project:
Homies

Task:
CONV-001A — Narrow Independent Integration Audit

Audited SHA:
5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98

PRODUCT parent:
7ffb4f51dd315363362df1a5f8fc5c19a57767dc

INFRA parent:
5cad442f07264ab25b3024c96fc691ad9c7a75fa

Independent auditor session:
YES

Merge provenance:
ACCEPTED (exact 2-parent merge, base 879bf56, no post-merge commits; re-merge reproduces builder conflicts; only code delta = test_public_generation.py)

Atomicity / generic-500 interaction:
ACCEPTED (fresh-connection PG probe: 500 + rid + correlated log, zero partial generation/event/work item; merged test kills T1 partial-commit and T2 escaping-500 mutants)

Alembic:
ACCEPTED (one head f3b5d7e9a1c2; env.py exact union; %-escaping + logging verified from prod image)

Application composition:
ACCEPTED (91 = 91 ∪ 76 ops; request_id → metrics → rate_limit; 3 workers)

Config/security:
ACCEPTED (missing/weak secrets, dev creds, dev DB, sqlite, unset URL → refuse; valid synthetic → start)

OpenAPI:
ACCEPTED (PRODUCT ⊆ MERGED, INFRA ⊆ MERGED, merged == product spec, infra spec == ancestor; drift OK; Spectral 0 errors)

Product parent preservation:
ACCEPTED (auditor TASK-014RA probes 54/54 incl. F2/X13/X18/F1; product runner 16/16)

Infra parent preservation:
ACCEPTED (m12, c01, c02, M01, M06, M07, M08 killed; runtime matrix; image ENV=production)

Exact-SHA evidence:
ACCEPTED (CI 36644550108 push head_sha 5abfd7b, 5/5 jobs; harness 9aba64f run 36644558783 checks out SOURCE_SHA + verifies both parents; not a PR merge ref; raw logs/artifact 403 — annotations + independent local reproduction)

Integration sentinels:
ACCEPTED (13/13 KILLED, re-run independently; green baselines, assertion failures, source restored)

Full SQLite:
1071 passed / 372 skipped / 0 failed (independent local, exit 0)

Full PostgreSQL/PostGIS:
1442 passed / 1 skipped (Stripe live) / 0 failed, coverage 91.9% (independent local, PG 16.4 / PostGIS 3.4.3, HOMIES_REQUIRE_RESTORE_DRILL=1; 10 drill tests passed)

P0:
0

P1:
0

P2:
0

P3:
0

NOTE:
3

Overall verdict:
CONV_001_ACCEPTED_WITH_NONBLOCKING_NOTES

Integrated baseline accepted:
YES

Accepted integrated SHA:
5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98

Remaining debt:
CV-N1 harness drill-count annotation meaningless (evidence only); CV-N2 Phase-1 restore drill omits TASK-014 tables; CV-N3 assert_unhandled_500 does not assert X-Request-ID/log request_id; carried: PR-003 (RA-3 health isolation, business DB deadlines); TASK-014 N-2, RA-N1, X04 CAS, RA-N5; MICRO-001 F13RA-N01, token wording/D-81, RA2-N1; tooling F13RA-N02, Node 20 deprecation, N-A/N-C/N-D/N-E/N-F

Production:
NOT READY

Deployment:
NOT DEPLOYED

May begin MICRO-001 / PR-002 sequencing:
YES — after ChatGPT/founder adjudication and freeze of the integrated baseline; one serialized task at a time (not started by this audit)

REQUEST TO CHATGPT:
Adjudicate CONV-001A and, if accepted, freeze the integrated baseline and authorize the next serialized task.
```
