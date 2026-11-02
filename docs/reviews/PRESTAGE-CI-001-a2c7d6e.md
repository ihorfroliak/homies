# PRESTAGE-CI-001 — test isolation continuation

Exact reviewed candidate: `a2c7d6eca1ee745c56bf067e20a1f3949c17412a`.
Comparison: `f0d163e0cbab1b90493f04480c5224e02391116a`.
Date: 2026-11-02. Read-only specialist: `/root/cutoff_failure_review` (test engineer).
This is the bounded source-review receipt, not a new foundation audit or CI acceptance.

## Reviewer result

No P0–P3 findings in the bounded test repair. No canonical decision required.

- Deterministic behavioral coverage: `backend/tests/test_search_validation_pg.py:165–188` tests both DST directions in three zones, binds UTC timestamps, and pins both decision clocks. Assertions distinguish the exact cutoff from its one-microsecond inside neighbor. Calendar-day arithmetic or changing `>` to `>=` would produce incorrect counts and fail these assertions.
- Isolation repaired: `backend/tests/test_listing_freshness_tz_pg.py:59–68` removes the hook in `finally`, disposes idle sessions, and asserts a new checkout starts in UTC. Lines 223–225 use transaction-local timezone changes in the standalone reminder test.
- Production unchanged: `backend/app` tree matches the comparison revision: `8c703ddb4980092af7f4758e3944e2c603ba4183`.

NOT VERIFIED by this reviewer: execution, mutation trials, or ordered-suite results. Parent-reported reproduction supports the original diagnosis; exact-candidate runtime evidence remains separate.

## Builder execution evidence (separate from review)

Disposable PostgreSQL16/PostGIS3.4 container `homies-prestage-test-pg`, database `homies_prestage_e2e`, synthetic data only; no published database port. Original cutoff test under Europe/Warsaw reproduced the CI failure: `(1,1,0)` instead of `(2,2,0)`. At fixed 2026-11-02T12Z, calendar subtraction produced age1817940s versus elapsed subtraction1814340s (21-day threshold1814400s).

At candidate a2c7d6e: Ruff passed; ordered `test_listing_freshness_tz_pg.py` then `test_search_validation_pg.py`: **93 passed**, 17 deprecation warnings, 152.71s. Python3.12, pre-existing image `homies-fevis-py312:latest`; this run did not use the updated dependency image.

Dependency-only successor image `homies-prestage-py312:20261102`: installed dnspython2.9.0 and msgpack1.2.3; `pip check` passed, all70 constraints matched installed metadata, full constraints `pip-audit --no-deps --disable-pip` reported no known vulnerabilities without suppressions. Pin source commit5b410c13708ac987676f71e6dba16a12d75b2eb2 reused with provenance in8a12a2023eea2a80e93addbf1f7e09b38bcb4255. No production application or migration change.

Full exact-head CI including restore and subsequent security canary remains a separate mandatory acceptance gate. No merge or deployment authorization is inferred from these results.
