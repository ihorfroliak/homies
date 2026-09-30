# MICRO-001 — evidence, documentation and test cleanup

| Field | Value |
|---|---|
| Status | DRAFT — **PLANNED, NEXT** after IBB-001; not started |
| Risk class | **R0/R1** (docs, wording, tests, evidence tooling) |
| Owner (writer) | Claude Code |
| Bounded contexts written | tests, evidence harness, docs; no runtime code expected |
| Baseline | Integrated Backend Baseline 001 (IBB-001), `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` |
| Branch | `claude/MICRO-001-<short-name>` (from IBB-001 or its documented successor) |
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
