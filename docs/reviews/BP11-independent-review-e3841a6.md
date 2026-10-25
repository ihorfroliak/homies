# BP-11 independent exact-SHA review

Date: 2026-10-17. Reviewer: separate Codex review agent; did not implement BP-11.

Verdict: BP11_INDEPENDENT_REVIEW_PASSED_WITH_NONBLOCKING_NOTES.
P0 CRITICAL 0; P1 HIGH 0; P2 MEDIUM 0; P3 LOW 0; NOTE 2.
No newly demonstrated canonical violation or blocking regression in the bounded BP-11 delta. This is a continued-development review recommendation, not merge authorization or production certification.

## Identity and scope

Candidate: e3841a638b4cc54bba10b2caed29569aaffd54e5.
Candidate tree: 02e5440867d0e980d125df2fc603443150488273.
Baseline: 4ed8fe8ab334a8d8e344b80e266da2be3b661aee.
Draft PR: 14 (parent-supplied).
Independent worktree: C:/Users/ihorf/.codex/worktrees/bp11-independent-review/homies.
Final git rev-parse verified both identities; final git status --short was empty.

Reviewed the 19-file baseline-to-candidate delta, focused on availability, public projection, rate limiting, proxy attribution, tests and performance evidence. Read AGENTS, 00-AUTHORITY, governance 05, D-104 OD-6, 04a section 24, the BP-11 task/performance records and relevant convergence dispositions. Existing BP-9 private-authority debt and unrelated baseline contexts are not reopened. No repository source changes, commits, pushes or deployments were made.

## Verified behavior

- Public slots route (backend/app/modules/engagement/viewings.py:509) no longer depends on authentication, but checks existing public freshness/visibility before reading the schedule. Draft, paused, archived, stale, aged and held listings and missing IDs return the neutral 404. Authentication is retained on configuration, booking and participant/provider routes.
- ViewingSlotsOut projects only UTC starts, duration_minutes and IANA timezone. No settings, windows, blackout reasons, capacity, booking records, identities, contact details or exact address are projected. Guest and authenticated projections are equal; no-settings nullable output and disabled-settings behavior are covered.
- slots() at line 343 replaces per-candidate SQL with range-filtered inputs and sorted interval endpoint counts. The count remains the number of strict overlapping confirmed intervals, not peak simultaneous occupancy. Both buffers, notice, blackouts, duplicate starts and unique-instant DST handling retain their prior semantics within operational ceilings.
- At most three availability queries occur, independent of candidate count. Extra sentinel rows detect overflow rather than silently truncating: windows 2,000, blackouts 2,000, bookings 10,000, attempted candidates 100,000. Existing tests lower the budgets to exercise each retryable neutral 503 branch. Public start bound is today through +366 days in the schedule zone, with a 1–31 day page; the public horizon does not restrict an otherwise valid authenticated booking beyond it. Shared computation ceilings can still return operational 503 to a booking that uses slots(); they do not change stored schedule records or permit false availability.
- Dedicated viewing_slots bucket is shared across listing/date/auth variants, fails closed, returns 429/Retry-After and executes before database work. The independent exhausted-bucket test observed zero SQL statements, including a forged forwarding header and invalid bearer token.
- Forwarding is honored only with configured trusted socket-peer CIDR and sufficient declared hops; intermediate suffix entries must also be trusted and the client address must parse. Empty CIDRs, untrusted peers and invalid chains fall back to socket peer. Docker CMD explicitly disables Uvicorn proxy rewriting. Real TCP/Uvicorn tests passed for trusted and untrusted forwarding.
- Request/confirmation capacity locks remain intact (viewings.py:564 and 651). Real PostgreSQL read/write test observed pg_blocking_pids: public read saw committed capacity during uncommitted confirmation, the booking waited for the settings lock, then refused occupied capacity. Next public read was empty; one confirmed booking remained; no deadlock increment. Existing confirmation-race test also passed.

## Actual independent execution

Python 3.12 cached image bp10c-test:c385136; PostgreSQL/PostGIS image postgis/postgis:16-3.4. Source mounted read-only. Created only bp11-independent-pg-e3841, network none, tmpfs database bp11review. Test containers shared only that isolated container network namespace. No connection to homies-postgres, hh-test-pg or any other agent database. Removed the audit database container after completion; test containers used --rm.

1. Focused repository suite: 131 passed, one existing Starlette/httpx deprecation warning, 135.84 seconds. Files: test_bp11_public_slots.py, test_bp11_public_slots_pg.py, test_viewings.py, test_viewings_pg.py, test_viewing_dst.py, test_sec01_ratelimit.py, test_tst01_openapi_contract.py. PostgreSQL tests ran, not skipped. This includes six OpenAPI contract checks. Initial attempted invocation had misspelled DST/OpenAPI test paths and collected no tests; the corrected run above completed cleanly.
2. Independent seeded differential probe: 120 cases, seed 20261017, zero output mismatches against slots() extracted from the exact baseline commit; maximum three optimized core SQL statements. Varied weekly/one-off windows and validity ranges, positive interval lengths/statuses, notice, both buffers, capacities, duration and dates; exercised Europe/Warsaw, UTC, America/New_York and Australia/Lord_Howe. Synthetic SQLite comparison supplements rather than replaces the PostgreSQL locking checks. Probe and extracted baseline are saved beside this report, not in the checkout.
3. Three reviewer-authored edge checks: 3 passed, 6.02 seconds. America/Los_Angeles and Pacific/Kiritimati opposite UTC-date boundaries and zero-SQL exhausted limiter. External test location generated three harmless unknown-marker warnings from imported pre-existing legacy tests.
4. Optimized PostgreSQL benchmark replay: 1 passed, 20.16 seconds. All ten complete output arrays equal the committed optimized arrays and, transitively, the committed baseline arrays. Independent replay reproduced 8 endpoint SQL statements for configured fixtures, 5 without settings, and 32/20 SQL statements for four concurrent reads. Maximum-days fixture: 2,480 attempted starts, 2,480 outputs, 95.86 ms median in this independent run. Full fixture: zero outputs, 111.28 ms median. These are diagnostic local samples.
5. Parsed both committed benchmark JSON files in full without dumping them. Every paired slot array is identical; reported SQL counts and medians match the table, including 2,488 to 8 calls and maximum-days median 7,415.28 to 126.02 ms. Dense-fixture plan reports the documented 19 shared buffers, 0.190 ms planning and 0.770 ms execution. The independent run supports the optimization; no new baseline timing replay or independent proof of the builder's chronological execution is claimed.

Independent artifacts: BP11-independent-differential.py; test_bp11_independent_edges.py; BP11-independent-optimized.json; BP11-independent-metrics-summary.json; BP11-independent-checkpoint.txt.

Parent separately reported exact-candidate CI run 39007470216 SUCCESS. This reviewer did not fetch that run. Ruff, Mypy, web generation/typecheck, full-suite and mutation results were not independently rerun by this reviewer; their builder/CI evidence must remain attributed to those sources.

## Nonblocking notes and limits

NOTE BP11-N1 — distinguish cursor timing from full result processing.
Location: backend/tests/test_bp11_benchmark_pg.py:49–55; docs/tasks/BP-11-performance.md:3.
Rule: governance 05 sections 10–11 require precise evidence claims; no demonstrated canonical behavior violation.
Evidence: sql_ms is measured between SQLAlchemy before_cursor_execute and after_cursor_execute events. It includes cursor execution/driver work but not subsequent SQLAlchemy row conversion and ORM materialization. The prose phrase “result handling” must not be read as all end-to-end result processing. HTTP wall timing does include endpoint work. The EXPLAIN statements are separately constructed representative projections, not an interception of the exact production statement including its LIMIT.
Expected behavior: keep SQL execution, end-to-end request and representative server plan metrics distinct.
Suggested repair: clarify these measurement boundaries when the evidence document is next reconciled; do not recalculate or reinterpret sql_ms as total ORM time. No acceptance blocker; SQL count reduction and output equivalence remain directly verified.
CANONICAL DECISION REQUIRED: NO.

NOTE BP11-N2 — deployment trust and limiter topology remain prerequisites.
Location: backend/app/core/ratelimit.py:245; backend/app/core/config.py:74–81; backend/Dockerfile:34; docs/tasks/BP-11-performance.md:47–62. Existing frontend/web/src/server/client-ip.ts:7 still describes the former hop-only backend setup.
Rule: contract requires trusted proxy CIDRs/hops and original socket peer; production infrastructure is outside authorization.
Evidence: default empty CIDRs safely aggregate traffic under the proxy address even if TRUST_PROXY_HOPS was already set. The limiter remains per process. Custom launchers that enable Uvicorn rewriting can bypass the app's intended original-peer boundary. The shipped Docker path and synthetic TCP tests are verified; actual production ingress/web-server trust topology is not.
Expected behavior: before rollout, verify actual CIDRs/hop count, no-proxy-headers, upstream header sanitization and per-process scaling assumptions. Old frontend setup wording should not be copied as complete deployment instructions.
Suggested repair: use the BP-11 deployment prerequisites and reconcile old setup comments/runbooks when deployment configuration is authorized; a shared limiter requires separate operational work before scale-out. No new runtime defect is asserted for a correctly configured shipped deployment.
CANONICAL DECISION REQUIRED: NO.

No production state, provider activation, whole-repository baseline acceptance or formal IBB-001 replacement is implied. Prior BP-5 BARRIER/rollback blockers and other recorded debt remain unchanged.
