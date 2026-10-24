# BP-9 — Verified private engagement authority

Status: BUILDER_VERIFIED; candidate, independent exact-SHA review and CI required.
Baseline: `4ed8fe8ab334a8d8e344b80e266da2be3b661aee` (integrated BP-8).
Authority: founder HOMIES-DELIVERY-002 section 7 (2026-10-16), D-105,
04a section 24, FE-003 section 3.9; governance 05 section 9. Risk: R2.
Sole writer: Codex BP-9 builder, isolated branch `codex/BP-9-verified-engagement-authority`.

## Scope and invariants
Every private provider engagement read/write requires an in-force authority
chain with MANAGE_MESSAGES or MANAGE_VIEWINGS and a VERIFIED PropertyAuthority
root. Include inbox, thread, send/replay, assignment, stage, provider participant,
viewing management/settings and BP-6 cancellation notification recipients.
Requester access to their own engagement is preserved. Assignment is not a
capability. Conflicts and self-dealing still consider unverified authority.
Refusals remain neutral 404 without requester data. No migration, unrelated
property permission changes, quotas/idempotency changes, deployment or merge.

Recheck current side after advisory/row waits and rollback recovery. Resolve
property links with current scalar queries, not preloaded ORM identities.
This is the bounded CX-02 post-wait repair, NOT a transaction-atomic or strict
commit-time authorization protocol; later concurrent revocation remains outside
this promise. No new locked-proof semantics or canonical decision is invented.

## Acceptance and verification
Exercise verified owner/organization/representative, unverified root, expired
or revoked mandate, missing scope, unrelated account, ownership change,
private-data non-disclosure, recipient filtering, and requester continuity.
PostgreSQL causal waits must reject revoked providers before replay/write;
preloaded objects must not confer stale access. Preserve BP-10 idempotency,
BP-5/BP-6 cancellation, BP-8 restrictions and conservative conflict guards.
Targeted SQLite and disposable PostgreSQL/PostGIS tests, Ruff, mypy, API drift,
required feature-branch CI; independent review at the frozen exact SHA.

## Delivery
Feature-branch commit/push and Draft PR only. BP-9/BB-10 remains an external
provider beta gate until integrated and verified. IBB-001, all unrelated debt,
BARRIER / rollback BLOCKED, production NOT READY / NOT DEPLOYED preserved.
BP-11 proceeds separately on the same baseline; its availability changes must
be explicitly converged before dependent product slices are considered ready.

## Evidence
Implemented VERIFIED-root checks in provider inbox/read/write, assignment,
viewing private operations/settings and BP-6 recipients. Provider participant
capture requires active scoped verified root/party (and active organization).
Requester access, conservative self-dealing/moderation conflicts and general
property management permissions are preserved. Current-side rechecks follow
advisory/row waits, assignment-target evaluation follows the row wait, and
append rollback recovery rechecks before exposing the winner.

Actual local evidence (2026-10-16; synthetic data only):

* Source-pinned host Python 3.14.3: BP-9 initial HTTP + existing conversation/
  viewing regressions **100 passed** (182.90s).
* Expanded selection: BP-9 HTTP/PG, BP-10 HTTP/PG, BP-5 cancellation, BP-6
  HTTP/PG, OpenAPI drift: **117 passed / 2 failed** (209.37s). All 24 BP-9 HTTP
  and 11 BP-9 PostgreSQL cases passed. The two inherited BP-10 T10/T12 commit
  uncertainty probes hit Windows socket deadline behavior; the watchdog fired
  but the worker exceeded 7.5s. They are not reported as local Windows passes.
* Those two unchanged probes rerun on Linux **Python 3.12** using
  `bp10c-test:c385136`: **2 passed / 19 deselected** (26.84s).
* Two additional unverified-manager moderation conflict controls: **2 passed**
  (4.27s). Total new permanent cases: 26 HTTP + 11 PostgreSQL.
* Initial PostgreSQL-only development run: **10 passed** (55.06s); expanded
  run adds the settings-row wait. Each causal wait observes `pg_blocking_pids`,
  denies with 404 after revocation, checks no message/lead/viewing mutation,
  and checks deadlock count unchanged. Preloaded property-link change denied.
* Ruff clean; mypy **126 files clean**; `git diff --check` clean. OpenAPI
  drift is included in the expanded selection. No schema/API shape changes.

Initial development failures retained: five fixture assertions expected 201
for the mandate endpoint, whose actual accepted response is 202; fixed tests.
The initial Docker conversation/viewing run had 82 passes plus two JWT 401
failures/setup errors; host rerun passed, with no authentication bypass or
clock tolerance change. An initial default interpreter lacked fastapi and an
initial verification command referenced a nonexistent OpenAPI test filename;
those invocations establish no test evidence.

Disposable local PostgreSQL 16/PostGIS 3.4 only: unique `homies-bp9-pg-20261016`,
tmpfs database `bp9`, random loopback port 60313. No development/production DB.
No full-suite, mutation, independent-review or CI-green claim until those run.
The post-wait repair addresses bounded CX-02 schedules; strict commit-time
revocation safety remains explicitly outside this contract. Other BP-10 debt
and all existing limitations remain. Draft PR is not acceptance or integration.
