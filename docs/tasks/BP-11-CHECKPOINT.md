# BP-11 checkpoint — 2026-10-17

Task: BP-11 public viewing slots. Sole writer: BP-11 child agent.
Base: 4ed8fe8ab334a8d8e344b80e266da2be3b661aee.
Branch: codex/BP-11-public-viewing-slots; not committed/pushed yet.
Contract: docs/tasks/BP-11-public-viewing-slots.md.
Baseline completed BEFORE production changes: opt-in PostgreSQL endpoint
benchmark, 10 fixtures, 3 serial + 4 concurrent each, 1 passed in 174.49s.
Evidence: docs/tasks/BP-11-baseline.json (do not rerun unnecessarily).
DB: own disposable homies-bp11-builder-20261016, tmpfs, localhost port52018;
unrelated homies-postgres must never be touched.
Current code: bounded interval projection, dedicated limiter, explicit
trusted-peer configuration and Uvicorn no-proxy-headers implemented.
Optimized benchmark: 1 passed in 18.70s, BP-11-optimized.json. All ten
fixtures have exactly equal returned slot arrays; maximum schedule SQL
2488 -> 8 per request, median wall 7415.28 -> 126.02 ms. Baseline is final.
First functional run: 92 passed / 2 failed (new test mistakes: synthetic
non-column moderation flag and incorrect total-query expectation). Both
corrected; held case now uses actual moderation API. New row-budget and
real TCP/Uvicorn tests plus observed PostgreSQL capacity race authored.
First Ruff found 20 fixture-import F811 errors, suppression amended.
Follow-up pytest collected nothing because path test_viewings_dst.py was
mistyped; correct path is test_viewing_dst.py. Mypy command NOT EXECUTED:
automatic approval review hit usage limit (not a safety determination).
Latest focused run: 122 passed / 1 failed in146.69s. All BP-11 tests,
including real TCP/Uvicorn peer attribution and observed PostgreSQL capacity
blocking, passed. Failure: pre-existing stranger-action test received401
instead of404 on its second action; isolated rerun plus OpenAPI6 passed7/7
in7.32s without authentication changes. Cause not certified locally; stable
CI remains required. Ruff now clean after explicit shared fixture bindings.
Mypy clean126files. OpenAPI generated; web generated API check and typecheck
passed. npm ci completed481packages; hostNode24.14 produced transitive engine
warnings (CI runtime is authoritative). Two extra maximum-capacity/booking-
horizon tests passed2/2 in6.68s; final Ruff clean after those additions.
No independent review yet; this is the builder freeze checkpoint. Last DB
version read retried after limit reset: PostgreSQL16.4/PostGIS3.4.3 confirmed.
Performance/operational/test records and DEVLOG now complete; diffcheck clean.
NEXT: commit/push/Draft; parent exact-SHA review and required CI. Do not rerun
completed baseline/after benchmarks. No merge/deployment.
366-day horizon is a new operational request bound authorized by directive6.4,
not an assertion of previously approved one-year product semantics.
