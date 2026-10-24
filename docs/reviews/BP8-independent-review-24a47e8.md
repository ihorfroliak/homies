# BP-8 independent exact-SHA review

Date: 2026-10-14. Reviewer: separate Codex read-only review agent, not the BP-8 writer.

**Audited commit:** `24a47e81cfd31948e4de642ff7c2cb2fbe5bf521`  
**Audited tree:** `b29e0ceac644c026ecaa3d3e5dd01cc625b27f27`  
**Implementation baseline:** PR #7 merge `38db9c100eae331fbe978432c9197d5ceb893121`  
**Documentation-only parent:** `4ab5f27b802709c074e520648adfddb386d731b3`  
**Separate detached worktree:** `C:/Users/ihorf/.codex/worktrees/bp8-independent-review/homies`

## Verdict

PASS for the bounded BP-8 independent review: no actionable P0, P1, P2 or P3 finding identified in the reviewed implementation delta. This is a review verdict, not merge authorization or production certification. Required exact-head CI and later founder merge approval remain separate gates. IBB-001 and the existing production-not-ready disposition are unchanged.

## Scope and authority

Read AGENTS.md, canonical 00 precedence, 02 business logic, 05 governance (including sections 9 and 14), 04a section 24, D-104 OD-2 / D-105 OD-8, D-111 execution authorization, the approved BP-8 task contract, and the relevant contact-reveal convergence disposition. Inspected the BP-8 product delta in properties/router.py, its two new test modules, and the OpenAPI / generated TypeScript documentation changes. Existing moderation and publication paths were read only to establish the lock and generation contracts used by BP-8. BP-5/BP-6 were not re-audited.

No repository files were edited, and no commits, pushes, merges or deployments were performed. The worktree SHA/tree and clean Git status were verified again after testing.

## Findings

- P0 CRITICAL: none identified.
- P1 HIGH: none identified.
- P2 MEDIUM: none identified.
- P3 LOW: none identified.
- Canonical decision required: no new contradiction identified within BP-8.
- Optional improvements: none proposed as acceptance conditions.

## Evidence supporting the verdict

1. **Current-generation refusal covers new and repeat disclosures.** `backend/app/modules/properties/router.py:1017` introduces the locked listing read and `:1026` checks the existing listing/requester/public-generation restriction. `reveal_contact` calls it at `:1071`, before the viewer lock and repeat branch at `:1086`. This satisfies 04a section 24 and D-105 OD-8. The HTTP tests exercise both a first disclosure and a repeat, including an updated phone and a full quota, with an exact neutral 409 response. They assert unchanged reveal/audit counts and quota use and check the private reason/phone canaries. An exact-response assertion also rejects any additional old-phone or reason disclosure in the refusal payload.

2. **Generation and isolation semantics remain intact.** The helper uses the current listing generation, and `populate_existing=True` refreshes the identity-mapped row. The HTTP tests exercise another requester, another listing, actual pause/publish transitions, free repeats and normal new-disclosure quota after republish. The PostgreSQL stale-generation test preloads the old listing, performs a real republish and verifies that the refreshed generation permits normal contact access. No new generation column, migration or quota unit was introduced.

3. **Lock ordering matches the existing writers.** `router.py:1022` uses `FOR SHARE OF classified_offers`, before the existing viewer `FOR NO KEY UPDATE` at `:1079`. The explicit OF avoids locking nullable eager-joined relations. The restriction writer in `backend/app/modules/trust/decisions.py:755` takes the listing NO KEY UPDATE lock; publication in `backend/app/modules/properties/publicity.py:86` selects the listing FOR UPDATE. These conflict with SHARE. Four real PostgreSQL schedules cover new/repeat disclosures and restriction-first/reveal-first orders, observe the second operation blocked through `pg_blocking_pids`, then assert the correct result, persisted reveal/audit counts, subsequent refusal and no deadlock-count increase. A reveal ordered first can finish; a restriction committed first causes refusal. This does not claim to revoke knowledge already disclosed.

4. **Rollback does not reuse the old listing authorization.** `router.py:1113` reacquires the listing lock and rechecks public status, current generation restriction and contact mode after the integrity-conflict rollback. The focused fallback test injects a conflict, commits an actual restriction after rollback, and requires neutral 409 with no reveal/audit rows. This is a synthetic conflict probe, not a claim that the normal PostgreSQL viewer lock allows such a unique conflict.

5. **Unchanged gates and accounting are exercised.** Anonymous/unverified-phone, nonpublic and messages-only refusals remain, and the existing quota suites plus F03 PostgreSQL tests verify quota saturation, rolling-window behavior, serialization of competing disclosures and repeat accounting. The new helper returns no reason data; the disclosure audit call and metrics labels remain unchanged. OpenAPI drift tests pass, and the generated TypeScript diff changes only the matching 409 documentation.

## Checks actually run by this reviewer

All test commands used `bp10c-test:c385136` (Python 3.12.15) with the repository mounted `/repo:ro`, container `--read-only`, a writable `/tmp` tmpfs, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=/repo/backend`, and pytest cache disabled. No auth/token validation was bypassed.

**Independent disposable database:** `postgis/postgis:16-3.4`, PostgreSQL 16.4 / PostGIS 3.4.3, container `bp8-independent-review-24a47e8-pg`, id `40801ea474ba29da6c8000274629c4d1123d6cdb260b464db04c0783a48ce618`. Database storage, socket directory and `/tmp` were tmpfs. The initial random localhost port was 51478; after the interrupted session it restarted at verified random port 53598. TEST_DATABASE_URL referenced only database `bp8review` on this container, never the writer's database or development/production databases. Only synthetic fixtures were used. This reviewer removed that container after testing.

| Command / check | Observed result |
|---|---|
| `python -m pytest -p no:cacheprovider -q tests/test_bp8_contact_restriction.py tests/test_bp8_contact_restriction_pg.py tests/test_reveal_quota.py tests/test_reveal_quota_pg.py tests/test_tst01_openapi_contract.py` | **37 passed in 82.78s**, one existing Starlette/httpx deprecation warning |
| `python -m pytest -p no:cacheprovider -q tests/test_concurrency_r4_pg.py -k f03` after database recovery | **2 passed, 5 deselected in 6.89s**, same deprecation warning |
| `ruff check --no-cache app/modules/properties/router.py tests/test_bp8_contact_restriction.py tests/test_bp8_contact_restriction_pg.py` | **All checks passed** |
| `mypy --cache-dir=/tmp/mypy-cache app` | **Success: no issues found in 126 source files**; existing notes about unchecked untyped function bodies |
| `git diff --check 4ab5f27b802709c074e520648adfddb386d731b3 HEAD` | Passed |
| Final `git status --porcelain` and `git rev-parse HEAD 'HEAD^{tree}'` | Clean, exact identities above |

## NOTE: interruption and verification limits

- **Location/evidence:** local review environment / `tests/conftest.py:317`. After session interruption Docker reported this reviewer's database exited 255. One F03 invocation then produced **2 setup errors, 5 deselected in 3.51s**, because the isolated database connection closed. No test assertion ran in that attempt. Only this database was restarted; its new port/readiness was verified before the successful rerun. This was an observed unavailable database, not an inferred application defect or a blanket clock explanation. No canonical rule was violated; expected test behavior is to use a live disposable database; repair was the isolated restart; canonical decision required: **no**.
- The original mypy process handle and completion output were lost during interruption; no success is credited to that run. The independently observed successful rerun is recorded above.
- Test-quality review found meaningful assertions that would fail for removal of the restriction gate, moving it behind repeats, removing the conflicting listing lock, or retaining a stale generation. **No mutation run was performed**, so no killed-mutant claim is made.
- The fallback regression uses a synthetic IntegrityError on SQLite; the PostgreSQL schedules verify actual listing-lock serialization. No exhaustive fallback-conflict concurrency proof or exhaustive deadlock proof is claimed.
- No independent frontend build/typecheck, full backend suite, backup/restore run or CI certification was performed in this bounded review. The generated TypeScript change was inspected as a matching documentation-only diff. The parent writer's results were not counted as this reviewer's results.