# PR-003 — Database Client Deadlines & Failure Containment

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88) — candidate on its branch, **not merged to `main`**; not independently verified; **production NOT READY · NOT DEPLOYED** |
| Risk class | **R2** (database runtime, failure semantics, health) |
| Owner (writer) | Claude Code |
| Baseline | `main` `13a92ef77b66096021d3927fdb255b546a4ecc63` (IBB-001 + MICRO-001 + PR-002) |
| Branch | `claude/PR-003-db-failure-containment` |
| Closes | PR-001RA **RA-3** (health endpoints share the business thread pool) |
| Decisions | D-89 (deadline policy), D-90 (failure semantics), D-91 (health isolation and workers) |

## Goal

No request, worker, health probe or startup check may wait on the database
without a bound; a database that stops answering must cost a bounded amount of
time and capacity, be reported honestly, and leave nothing poisoned behind.
Success semantics are unchanged.

## Phase A — BEFORE (13a92ef, production-like, measured)

Evidence outside the repository: `homies-audit-evidence/PR-003-builder/`
(`subagents/FAILURE-OPERABILITY-INVESTIGATION.md` — scenarios S1–S13 on the
production image as `homies_app` behind a controllable proxy and directly;
`subagents/DB-RUNTIME-INVESTIGATION.md` — mechanisms E1–E10). Monotonic timing.

| # | Scenario | BEFORE |
|---|---|---|
| S1 | healthy | reads p50 25 ms; writes p50 33 ms |
| S2 | database stopped, warm pool | 500 in ~3 s (connect_timeout); `/readyz` 503 2.0 s |
| S3 | unreachable (partition), warm pool | **no response in 150 s** (bounded only by TCP retransmission, ~15 min) |
| S4 | connect stall | 500 in ~3 s |
| S4b | cold start during a connect stall | **startup not finished after 75 s** (startup engines had no connect_timeout) |
| S5 | frozen (`docker pause`), warm pool | reads and writes **no response in 75 s**; a write the client abandoned **committed at unpause** |
| S6a | 25 s lock wait, healthy server | request took 23.9 s (no lock/statement timeout) |
| S6b | frozen during a statement | no response in 75 s |
| S7/S7b | frozen at COMMIT | client timeout for a committed write (S7); write committed after the client gave up (S7b) |
| S8/S9/S10 | backend killed / idle connections lost / restart | fail fast; pre-ping heals — already fine |
| S11 | 60-burst + load while frozen, pool not saturated | `/healthz` up to 5.2 s; 55× 500 in 3–33 s |
| S11b/S13 | frozen with the whole pool checked out, > 40 requests | **`/healthz` up to 75.9 s**, `/readyz` client timeouts at 90 s; after unpause **0 successes for 30 s, errors until +91 s** |
| S12 | workers | frozen: **silently stuck**, holding 2 connections; refused: **126 log lines/s**, no backoff, no liveness signal |

Root cause: the application engine had no deadline on anything after the TCP
connect — a frozen or partitioned server never answers, its kernel may still
acknowledge TCP, so neither server-side timeouts nor TCP timeouts end the
wait; pre-ping is a query and hangs too. Each hung request holds an AnyIO
thread (40) and a pooled connection (15), queued requests wait 30 s for the
pool, the sync health endpoints queue behind them, and one async handler
(`upload_media`) ran SQL on the event loop itself.

## Deadline model (D-89)

One policy: `Settings.db_*` → `app/core/db.DatabaseDeadlines`. Each bound is a
different wait; none stands in for another.

| Wait | Bound | Where | Outcome when exceeded |
|---|---|---|---|
| TCP connect + startup + auth | `connect_timeout` **3 s** | libpq | `ConnectionTimeout` → 503 `connection` |
| pooled connection | `pool_timeout` **5 s** (was 30 s) | SQLAlchemy QueuePool | `TimeoutError` → 503 `pool_timeout` |
| row/table lock | `lock_timeout` **2 s** | server (session option) | `LockNotAvailable` → 503 `lock_timeout`; connection kept |
| one statement | `statement_timeout` **5 s** | server | `QueryCanceled` → 503 `statement_timeout`; connection kept |
| client gone mid-statement | `client_connection_check_interval` **2 s** | server (PG ≥ 14, Linux) | server stops work nobody waits for, releases locks |
| idle in transaction | `idle_in_transaction_session_timeout` **60 s** | server | session ended, locks released |
| server that does not answer at all | **client deadline = statement_timeout + 2 s = 7 s** | `app/core/db_deadline.py` | socket shut down; `DatabaseDeadlineExceeded(operation)`; connection invalidated → 503 `client_deadline` / `commit_unknown` |
| readiness decision | 3 s (unchanged) | `app/core/health.py` | 503 |
| migration lock | 10 s (PR-002, unchanged) | `app/scripts/migrate.py` | exit 1 |

The client deadline arms every blocking driver call of the application's
pooled engines — `execute`/`executemany` (results are received inside them),
`commit`, `rollback` (pool reset included) and the pre-ping — on one watchdog
thread. A live server always answers within `statement_timeout`, so the
deadline only fires when the server cannot. It shuts the socket down (never
closes the descriptor libpq owns), the waiting call wakes with an error, psycopg
marks the connection broken and SQLAlchemy invalidates it; the pool reconnects
lazily. No cancel request is sent: that would be another network wait on the
same unresponsive server. Worst case for one request on a frozen server:
pre-ping 7 s + reconnect 3 s (measured 10.00 s) — bounded.

## Failure semantics and transaction safety (D-90)

| Failure | Transaction | Client sees | Retry |
|---|---|---|---|
| connect / pool wait / lock / statement timeout | never committed | 503 + `Retry-After: 5` | safe |
| client deadline during a statement | never committed (server rolls back when it sees the session gone) | 503 | safe |
| client deadline during COMMIT | **unknown** — may have been applied (proved: it was, after resume) | 503 "outcome is unknown; check before repeating" | safe only for idempotent writes |
| anything else (constraint, bug) | unchanged | unchanged (4xx / generic 500) | — |

Representative writes after an unknown COMMIT:

| Write | Resolution on retry | Evidence |
|---|---|---|
| saved search (`POST /v1/me/saved-searches`) | **resolved** by its natural key: 409 + `Location`, one row | `test_a_saved_search_whose_commit_is_unknown_is_resolved_by_its_natural_key` |
| saved listing | **resolved**: save is idempotent (200 "already saved") | existing TASK-014 tests |
| viewing request | **resolved**: one held viewing per tenant and listing (409) | existing viewing tests |
| conversation start / message | thread **resolved** (one active thread per tenant and listing); the message itself **may be duplicated** | known debt |
| property / listing create | **NOT resolved**: a retry creates a second draft (private, archivable) | characterization test `test_known_debt_a_property_whose_commit_is_unknown_is_duplicated_by_a_retry` |
| worker transitions | **resolved**: dedup keys, UNIQUE constraints, conditional updates; notification delivery at-least-once with an idempotency key | TASK-014 / OAT-03 suites |

Known debt: an `Idempotency-Key` for creates (property, classified, message) —
a follow-up, not a runtime-hardening change. The `DatabaseWriteOutcomeUnknown`
alert makes every occurrence visible.

`get_db` closes the session quietly: a rollback that fails because the
connection is already gone must not replace the request's own error (it would
turn "outcome unknown" into a rollback failure).

## Health isolation and workers (D-91)

* `/healthz`, `/readyz`, `/metrics` are `async def`: they run on the event loop
  and never wait for a thread-pool token. Readiness awaits an async probe; one
  in-flight probe per database (single flight); the decision at 3 s returns
  the response, the driver's clean-up continues in the background. Not done by
  enlarging the thread pool.
* No SQL on the event loop: `upload_media` (async, streams the body) runs its
  database and storage work in the thread pool; a test guard fails any
  Phase-1 test that executes SQL on an event-loop thread.
* Workers (notifications, saved-search-alerts, listing-freshness — the
  composition's three) share `app/core/worker_loop.run_loop`: a failed pass is
  logged and counted, the wait backs off after consecutive failures (1 s · 2ⁿ,
  capped at 60 s, never below the interval), each pass is bounded by the
  deadlines, `stop()` is no longer blocked by a hung pass.
* Startup and release checks (`app/core/schema.py`) use the bounded engine;
  their decisions (PR-002) are unchanged. The migration job (`migrate.py`,
  PR-002) is **not** changed: its connect/statement waits rely on the job
  runner's timeout — recorded debt.

## Observability

Bounded labels only (no ids, SQL, URLs, messages, addresses):

| Metric | Labels |
|---|---|
| `homies_db_client_deadline_exceeded_total` | `operation` ∈ statement, commit, rollback |
| `homies_db_unavailable_responses_total` | `reason` ∈ pool_timeout, connection, lock_timeout, statement_timeout, client_deadline, commit_unknown |
| `homies_worker_passes_total` | `worker` (3 names), `outcome` ∈ ok, failed |
| `homies_worker_consecutive_failures`, `homies_worker_next_pass_due_timestamp_seconds` | `worker` |
| `homies_db_pool_connections_in_use`, `homies_db_pool_connections_capacity`, `homies_threadpool_tokens_in_use`, `homies_threadpool_tokens_total` | none |

Alerts (promtool-tested, ticket severity): `DatabaseStoppedAnswering`,
`DatabaseWriteOutcomeUnknown`, `WorkerOverdue` (closes the "no worker
heartbeat" gap), `WorkerFailing`. 503s already count in `HighServerErrorRate`.

## Evidence (builder, local — 2026-10-01)

Python 3.12.14 test image, PostgreSQL 16.4 / PostGIS 3.4.3 (disposable
containers). Code at `ca6d820` (test-only commits after the runtime). Only runs
that actually happened are listed.

| Gate | Result |
|---|---|
| ruff, mypy (112 files) | clean |
| full SQLite | 1202 passed, 423 skipped, **1 failed** — `test_task014r_repairs::test_x07…`: unasserted `pause` call; consistent with the known JWT clock flake (cause unconfirmed); the file passed 3/3 alone. An earlier run's failure (`test_approving_a_quarantined_file…`, 401) also passed alone |
| full PostgreSQL/PostGIS (restore drills mandatory) | **1625 passed, 1 skipped** (Stripe live, not requested), 0 failed |
| earlier full PG run (before two test fixes) | 3 failed: JWT 401 flake; restore drill duplicate `TEST_FIXTURE` source — leaked by the new property test, fixed in `7d42264`; `test_release_pg::test_a_second_runner_waits_at_most_the_lock_timeout` 12.44 s > 12 s — **pre-existing**: the same test fails on the untouched baseline `13a92ef` copy (12.57 s) on this machine, and passed in the final run |
| PR-003 fault suite (`test_db_deadlines_pg.py`, 14 tests) | passed (in the final PG run) |
| OpenAPI drift (in suite), Spectral, AsyncAPI | drift test passed; Spectral 0 errors (49 pre-existing warnings); AsyncAPI valid |
| promtool | `check rules` 17 rules SUCCESS; `test rules` SUCCESS (incl. 4 new alerts) |
| production image | built from `git archive` of the candidate with `GIT_SHA`; started `ENV=production` as `homies_app` after the PR-002 migration job; used for every AFTER probe |
| Phase A probe kit, AFTER | table below |
| mutation (load-bearing controls) | 21 mutants. Round 1: 19 KILLED, 2 SURVIVED (M13 quiet close, M19 watchdog wake-up order), 1 INVALID (M16, selector matched no test). Tests strengthened (`ca6d820`); round 2: M13, M16, M19 KILLED → **21/21 KILLED**. Green baseline first (118 passed). Runner and results outside the repository (`PR-003-builder/mutation/`) |
| CI | run on the branch — see the final report |

## AFTER — same probe kit, production image of the candidate

Production image built from `git archive` of the candidate (`6d86a67`, S12
re-run on `45b2d91` after the worker-log fix), `ENV=production`, `homies_app`,
same proxy topology. Raw: `subagents/B-work/results/*_after*.json`.

| # | Scenario | BEFORE | AFTER |
|---|---|---|---|
| S1 | healthy | reads p50 25 ms, writes 33 ms | reads p50 31 ms, writes p50 76 ms (unchanged class; local noise) |
| S2 | stopped, warm pool | 500 ~3 s; burst 500 3.2–21.2 s | **503** ~3.0 s; burst 503 3.1–10.2 s (p50 5.4); `/healthz` in burst 0.38 s |
| S3 | unreachable, warm pool | no response in 150 s | **503 in 9.9 s**, next 3.0 s; recovery 0.07 s |
| S4b | cold start, connect stall | not started after 75 s | **startup fails after 7.2 s** (exit 3) |
| S5 | frozen, warm pool, read + write | no response in 75 s; abandoned write committed | **503 in 9.9 s** both; recovery 0.06 s |
| S6a | 25 s lock wait | 23.9 s | **503 in 2.1 s** (`lock_timeout`) |
| S6b | frozen during a statement | no response in 75 s | **503 in 7.1 s** (client deadline) |
| S7 | COMMIT applied, reply frozen | client timeout on a committed write | **503 "outcome unknown" in 7.0 s**; row committed — consistent with the message |
| S7b | COMMIT held before the server | write committed after the client gave up | **503 "outcome unknown" in 7.0 s**; committed at release — the client was told it might be |
| S11 | 60-burst + 2 req/s, frozen | `/healthz` up to 5.2 s; 500 in 3–33 s | `/healthz` ≤ 0.04 s; `/readyz` 503 in ~2.0 s; burst 503 3.2–13.3 s |
| S11b | frozen, whole pool checked out, > 40 requests | `/healthz` up to 75.9 s; `/readyz` client timeouts 90 s; after unpause 0 successes for 30 s, errors to +91 s | **`/healthz` max 0.033 s**, **`/readyz` max 2.06 s**; every request 503 within 13.3 s; after unpause first 200 at **+0.4 s**, last non-200 +0.7 s |
| S12 | workers: refused / stopped / frozen | 126 log lines/s / 35 lines/s / silently stuck | **0.5 / 0.3 / 0.4 lines/s**; frozen passes fail bounded; all recover after heal; `homies_worker_*` metrics live |

What did not change: the ghost-write possibility itself (S7b) — a COMMIT that
reached the server before it froze can still apply. PR-003 makes the client
answer honest ("outcome unknown"); preventing the duplicate on retry needs
idempotency (debt above).

## Out of scope (unchanged)

JWT clock leeway (MICRO-002 recommendation only), DATA-001 (proposal only),
TASK-015, the migration job, deployment, any provider. Dormant booking /
payments / ledger / short-stay runtime are not reactivated (the dormant
Stripe webhook keeps its SQL-on-loop shape; it is not composed).
