# Independent BP-5 / BP-6 bounded correction addendum

Date: 2026-10-13. Same separate reviewer context as the initial report; not the implementation writer.

- Reviewed SHA: `fec999399c64837fa8431aa98535df889625d98e`.
- Reviewed tree: `3ce1c43793e39b0f0a35deda543ac44a46e2b857`.
- Delta base: `f7e7280ba2afdc8ea1c467499b9a28b5a08972ed`.
- Own checkout: `C:/Users/ihorf/.codex/worktrees/bp56-independent-review/homies`; clean detached HEAD and tree verified after pinning and again on 2026-10-13.
- Prior report: adjacent `BP56-independent-review-f7e7280.md`, SHA256 `4910b6a6e0c4482804cf5a587a641b977b494140c50a5a95d4a221da75b3458d`. That report and its historical failed results remain unchanged.

## Bounded verdict

**Original P2 verification finding CLOSED at this SHA.** The four obsolete regression cases were corrected without weakening implementation invariants and passed independent execution. No new P0/P1/P2/P3 defect identified in the correction delta. The inherited BP-9/BB-10 NOTE remains open under its existing disposition.

This closes only the independent finding. Required exact-head CI and founder acceptance/merge authorization remain separate gates. During finalization the parent reported one further full-CI failure caused by an old migration-head assertion in `test_moderation_core.py:533`; this addendum does not claim that CI is green or that the candidate can merge. A subsequent bounded test-pin correction is expected and requires a tiny delta check.

## Delta inspected

Exactly six files changed: three test modules, DEVLOG, PROJECT-STATUS and the task contract. Verified by full Git delta inspection and `git diff --quiet` that `backend/app`, `backend/alembic`, the OpenAPI snapshot and generated frontend API schema are identical to the initial implementation reviewed at f7e7280. No implementation review was restarted.

- E-R1c and E-R2 observe the earlier `classified_offers` blocker using the same PostgreSQL blocker-PID helper; they retain final refusal/head/single-effect assertions and now release and join workers in finally paths.
- F6b observes the in-flight listing wait, commits the restriction, then requires `RECONTACT_BLOCKED` and zero new viewings, including a repeated request. It no longer withholds the commit while incorrectly requiring a successful request.
- The contradictory cancellation-state test permits either applicable named CHECK, while a separate source-free live-row mutation isolates the original `ck_viewings_cancelled_state` timestamp backstop. SQLSTATE assertions remain.
- The BP-6 race finalizer closes its paused session before the worker-termination assertion. Its eight ordering cases retain real blocking, final actor/timestamp/fact/notice and deadlock assertions.
- Documentation records actual failed and passing runs and unresolved gates without claiming full certification. No accepted semantics, product code, database guards or release compatibility metadata changed.

## Independently executed evidence at fec9993

The test process completed before the usage-limit interruption; its final output was recovered from existing session 8605 on 2026-10-13. It was not rerun or presented as a newly executed full suite.

**12 passed, 1 warning in 44.87 seconds:** four corrected tests plus eight parameterized cases of `test_restriction_serializes_both_orders`.

Exact pytest arguments:

```text
python -m pytest -q --tb=short -p no:cacheprovider
 tests/test_engagement_safety_pg.py::test_e_r1c_continuing_a_thread_waits_for_its_closure_and_is_barred
 tests/test_engagement_safety_pg.py::test_e_r2_two_moderators_restrict_once
 tests/test_engagement_safety_pg.py::test_f6b_a_restriction_in_flight_blocks_then_refuses_the_request
 tests/test_concurrency_r4_pg.py::test_no_viewing_is_ever_confirmed_with_a_cancellation_time
 tests/test_bp6_restriction_pg.py::test_restriction_serializes_both_orders
```

Same independently verified Python 3.12.15 / PostgreSQL 16.4 / PostGIS 3.4.3 runtime and read-only Docker invocation as the initial report. Repository mounted read-only at `/repo`; container root read-only; `/tmp` tmpfs; `DATABASE_URL=sqlite://`; `TEST_DATABASE_URL` pointed only to reviewer synthetic database `bp56review` through localhost port 60116. The single warning was the existing Starlette/httpx TestClient deprecation.

Additional independently completed checks:

- `python -m ruff check --no-cache tests/test_bp6_restriction_pg.py tests/test_concurrency_r4_pg.py tests/test_engagement_safety_pg.py`: **All checks passed** on 2026-10-13. A prior attempt was not executed because automatic approval review hit the usage limit; only this successful retry is claimed.
- `git diff --check f7e7280ba2afdc8ea1c467499b9a28b5a08972ed HEAD`: clean.
- Product/migration/generated-contract diff: empty, exit 0.
- HEAD/tree/status verification: exact identities above; clean checkout.

Initial unchanged-code evidence remains attributed to f7e7280: focused 106 passed; independent semantic probes 2 passed; broader PostgreSQL 65 passed/3 failed; separate obsolete CHECK assertion 1 failed; Ruff clean; mypy clean for 126 files; actual restore drill executed. The four failures are now resolved by the independently verified correction; this is not a claim that the entire repository suite was independently executed at fec9993.

## Retained NOTE and limitations

At `backend/app/modules/trust/notices.py:110`, provider notice recipients use existing `authority.holders(..., MANAGE_VIEWINGS)` semantics. The root VERIFIED PropertyAuthority requirement remains expressly deferred to BP-9/BB-10; that task must include this notice surface. No canonical decision is required; the rule is already decided. This review neither expands scope into the deferred authorization repair nor declares it closed.

The reviewer did not independently execute remote CI, the complete repository suite, frontend generation/typecheck or production operations. The parent-reported CI failure remains an external verification gate until its correction and the required checks are complete. No mutation-kill, production readiness, deployment or merge claim is made.

After all reviewer test processes completed, the unique disposable container `homies-bp56-review-20261012` (ID `b7d71e59ca52ef67017a9840867b5f8257f786b0d838d0bdc3565aecd3c44ae2`) was inspected and removed on 2026-10-13, deleting only its synthetic tmpfs databases. Neither the parent's database on 55556 nor the existing database on 5432 was connected to, changed or removed.
