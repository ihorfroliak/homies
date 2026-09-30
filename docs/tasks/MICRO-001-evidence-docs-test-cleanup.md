# MICRO-001 — evidence, documentation and test cleanup

| Field | Value |
|---|---|
| Status | **CANDIDATE** — implemented on `claude/MICRO-001-evidence-docs-tests` (builder, R0/R1); final SHA in the MICRO-001 report |
| Risk class | **R0/R1** (docs, wording, tests, evidence tooling) |
| Owner (writer) | Claude Code |
| Bounded contexts written | tests, evidence harness, docs; no runtime code expected |
| Baseline | Integrated Backend Baseline 001 (IBB-001), `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` |
| Branch | `claude/MICRO-001-evidence-docs-tests`, from `main` `507a96773ee8476d6ba26bc7f547f64a831369e9` (descends from IBB-001) |
| Independent audit required | **no** — unless the implementation unexpectedly changes runtime behaviour (then reclassify R2 and stop) |

## Goal

Close the small, nonblocking notes carried into IBB-001 so the evidence and
the wording say exactly what the code does. No product, database or runtime
behaviour changes.

## Planned scope

| Item | Source | Planned change |
|---|---|---|
| F13RA-N01 | [TASK-013RA](../reviews/2026-09-28-task013ra-codex-task013r-audit.md) | correct the worst-case canonical-length test and D-76 wording: percent-encoded Unicode ids can reach the 16 384 backstop within per-field budgets; the backstop itself is the guarantee |
| TASK-014 token wording / D-81 (RA-N2) | [TASK-014RA](../reviews/2026-09-29-task014ra-independent-task014r-audit.md) | contract line "two fresh unsubscribe tokens" and D-81's old `secrets.token_urlsafe(32)` sentence / status column → the HMAC-derived single-use capability as amended by TASK-014R |
| RA2-N1 | [PR-001RA2](../reviews/2026-09-29-pr001ra2-independent-pr001r2-audit.md) | pin or document the readiness decision-budget value (`PROBE_DEADLINE_S`) in a test, so mutant m12b (3.0 → 60.0) is killed |
| CV-N1 | [CONV-001A](../reviews/2026-09-30-conv001a-independent-integration-audit.md) | evidence harness: count JUnit `<testcase>` elements for the drill annotation, not matching lines (the real CONV result was 10 drills passed) |
| CV-N2 | CONV-001A | extend the Phase-1 restore drill to seed and verify the TASK-014 tables: `listing_public_generations`, `saved_searches`, `saved_search_anchors`, `saved_search_matches`, `alert_deliveries`, `user_notifications`, `notification_preferences`, `unsubscribe_tokens`, `saved_listings` (coverage gap, not a known restore defect) |
| CV-N3 | CONV-001A | `assert_unhandled_500` also asserts `X-Request-ID` on the response and its equality with the logged `record.request_id` |

## Out of scope

PR-002, PR-003 (health isolation, database client deadlines), TASK-015,
TASK-014 N-2 / RA-N1 retry policy, X04, RA-N5, any runtime or schema change,
the local Docker clock.

## Acceptance criteria

Builder evidence: ruff, mypy, OpenAPI drift unchanged, full SQLite and
PostgreSQL/PostGIS suites green in CI on the exact SHA; the RA2-N1 mutant
killed; the drill annotation reports the real testcase count.

## Closure (builder, 2026-09-30)

No runtime behaviour, schema or OpenAPI change. The one application-source
edit is a comment in `properties/search.py`, proven comment-only (identical
Python AST before and after).

| Item | State | What changed | Evidence |
|---|---|---|---|
| F13RA-N01 | **CLOSED** | the false "worst case fits" test replaced by `test_per_field_budgets_alone_do_not_bound_the_canonical_query` and `test_the_canonical_bound_is_exact_at_the_api` (list + map: unique, individually valid percent-encoded 4-byte-character ids; exactly 16 384 → 200, 16 385 → 422); D-76 and the `search.py` comment now call the bound independent. Query limits unchanged | `tests/test_search_validation.py` |
| TASK-014 token wording / D-81 | **CLOSED** | contract §delivery and D-81 describe the HMAC-derived, per-delivery, retry-stable, single-use capability; D-81 status → accepted (TASK-014RA, IBB-001) | docs only |
| RA2-N1 | **CLOSED** | `tests/test_readiness_budget.py`: the decision budget is 3 s, and a probe whose connect never returns is decided not ready within [3 s, 4 s) on the monotonic clock. Makes no claim about total HTTP completion. Mutant m12b (3.0 → 60.0) killed by both tests | local mutant run |
| CV-N1 | **CLOSED** | `backend/scripts/ci/junit_drills.py` counts drill `<testcase>` elements and outcomes; CI writes `junit.xml` and a new step fails when no drill passed or any was skipped/failed; unit tests use a one-line report of 10 drills; a CI-contract test pins the step | `tests/test_junit_drills.py`, `tests/test_ci_contract.py` |
| CV-N2 | **CLOSED** | the Phase-1 drill seeds a verified renter, saved search, preference, saved listing and alert work (both channels), then proves the nine TASK-014 tables non-empty before and identical after restore, the saved search still VALID (canonical + fingerprint), emailed capabilities still resolving by hash, and the delivery / match uniqueness guards still refusing on the copy | `tests/test_dr_restore_phase1_pg.py` (10 drills passed on PostgreSQL 16.4 / PostGIS 3.4.3) |
| CV-N3 | **CLOSED** | `assert_unhandled_500` also asserts `X-Request-ID` present, equal to the caller's id when supplied, and equal to the logged record's `request_id`; the merged atomicity test supplies its own id; meta-tests prove the helper refuses a missing / mismatched id | `tests/test_assert_unhandled_500.py`, `tests/conftest.py` |

Remaining documentation debt noticed, not in scope: D-76 and D-78…D-80, D-82
status columns still read "pending" although TASK-013 and TASK-014 are accepted.
