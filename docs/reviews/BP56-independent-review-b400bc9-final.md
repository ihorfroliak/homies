# Final independent BP-5 / BP-6 review — b400bc9

Date: 2026-10-13. Reviewer: the separate read-only Codex context that reviewed the original BP-5/BP-6 implementation; not the implementation writer.

**Exact reviewed SHA:** `b400bc9ea8f638e5915c9892b29abe444db7d242`.

**Exact tree:** `225cc074f8358b521bbf79f033b57313ebe7821e`.

**Implementation base:** `74a7065e167e6cea8d4251a17138ffe775b02a54`.

**Own isolated checkout:** `C:/Users/ihorf/.codex/worktrees/bp56-independent-review/homies`, clean and detached at the exact SHA above. Identity and clean status verified after the final checks.

## Verdict

**PASS WITH NONBLOCKING NOTE, within this bounded independent review.** The original P2 verification finding is closed by independently executed corrections. No open new P0/P1/P2/P3 defect was established in BP-5/BP-6 or the correction deltas. The inherited BP-9/BB-10 authority-verification NOTE remains open under its accepted separate-task disposition.

This is not full-suite or CI certification, production readiness, deployment approval, founder acceptance or permission to merge PR #7. Required checks must pass on this exact head, and subsequent founder merge authorization remains required. Remote CI was not independently queried by this reviewer; its final result belongs in the delivery receipt.

## Evidence chain and resolved findings

The original implementation was independently reviewed at `f7e7280ba2afdc8ea1c467499b9a28b5a08972ed`, tree `b24737acc7e610b63d9cb230683435cb8d6b4df3`. Initial detailed report: adjacent `BP56-independent-review-f7e7280.md`, SHA256 `4910b6a6e0c4482804cf5a587a641b977b494140c50a5a95d4a221da75b3458d`.

Actual independent original results: focused BP-5/BP-6/release/schema/OpenAPI **106 passed**; two additional semantic probes **2 passed**; broader PostgreSQL viewing/moderation/restore/release/migration run **65 passed / 3 failed**; separately reproduced overlapping-CHECK assertion **1 failed**. Ruff passed, mypy passed for 126 source files, diff hygiene passed. The real restore drill ran with `HOMIES_REQUIRE_RESTORE_DRILL=1`. These historical failures remain recorded; they are not rewritten into successes.

The original **P2 MEDIUM** concerned four obsolete verification expectations: two tests looked for conversation blocking after BP-6 deliberately moved the first conflicting lock to the listing; one expected an in-flight viewing request to succeed before restriction commit; one required the old CHECK name when both the new source-state and old timestamp constraints correctly rejected the row. No canonical decision was required: the approved task already fixed the intended semantics.

At `fec999399c64837fa8431aa98535df889625d98e`, tree `3ce1c43793e39b0f0a35deda543ac44a46e2b857`, the reviewer inspected the complete six-file test/documentation delta and independently ran all four corrected cases plus all eight changed race-cleanup schedules: **12 passed, 1 existing deprecation warning, 44.87 seconds**. Final output was recovered from the already completed process after a usage-limit interruption; this was not another full-suite run. Changed-file Ruff and diff hygiene passed. That closes the P2 finding. Detailed addendum: adjacent `BP56-independent-review-fec9993-addendum.md`, SHA256 `86d4560102e5e78c01bfdbaf805093d89f4302ee26e33cbaed22b608b9d78015`.

The parent then reported a remaining CI test-only failure at `backend/tests/test_moderation_core.py:533`: the static current-head assertion still named BP-10's `11d778ab87a3`, while the actual Alembic head and release manifest correctly named BP-5's `23e89acb98b4`. This reviewer inspected that stale assertion directly; the parent's full-CI totals are not claimed as reviewer-executed results.

## Final b400bc9 delta and independently executed check

Pinned the own checkout to `b400bc9ea8f638e5915c9892b29abe444db7d242` after the prior review processes finished. Inspected the entire delta from fec9993: only the migration-head assertion/comment in `backend/tests/test_moderation_core.py` and appended historical evidence in DEVLOG/task contract. The test still independently compares actual Alembic heads, the release manifest and the explicitly intended new head. It was not deleted, skipped or weakened into a comparison against itself.

Executed with image `bp10c-test:c385136`, Python 3.12.15, read-only container and repository mount, tmpfs `/tmp`, `DATABASE_URL=sqlite://`, and no TEST_DATABASE_URL:

```text
python -m pytest -q -p no:cacheprovider tests/test_moderation_core.py::test_one_migration_head_and_it_is_the_release_head
```

**Result: 1 passed, 1 existing Starlette/httpx TestClient deprecation warning, 3.84 seconds.** No database server or PostgreSQL suite was needed or repeated for this static correction.

Additional final-SHA checks:

- `python -m ruff check --no-cache tests/test_moderation_core.py`: all checks passed.
- `git diff --check fec999399c64837fa8431aa98535df889625d98e HEAD`: clean.
- `git diff --quiet f7e7280ba2afdc8ea1c467499b9a28b5a08972ed HEAD -- backend/app backend/alembic docs/api/openapi.json frontend/web/src/api/schema.d.ts`: exit 0. All reviewed product implementation, migrations and generated API contracts are unchanged from the original source review.
- Exact HEAD, tree and clean worktree status verified.

The residual static pin issue is resolved by inspection and this independent execution. No additional implementation audit or repeated PostgreSQL run was necessary for the final two-line test correction.

## Retained NOTE — inherited provider authority gate

**Location:** `backend/app/modules/trust/notices.py:110`, through `backend/app/modules/properties/authority.py:209`.

**Evidence and invariant:** The new provider cancellation notices use current MANAGE_VIEWINGS holders through the existing three-chain lookup. That helper does not filter the root PropertyAuthority to VERIFIED. D-105 / 04a section 24 requires verified private-engagement authority; its BP-9/BB-10 implementation is expressly deferred outside this bounded task.

**Expected follow-up / suggested repair:** Include this new provider notice surface in BP-9's verified-root authorization and recipient regression coverage, alongside the existing private-engagement reads/writes. Keep BB-10 open before provider beta. This is an inherited dependency, not a finding that the cancellation payload contains private allegations or a request for an unrelated repair here.

**Canonical decision required:** No; the rule and separate-task disposition already exist. NOTE remains open, nonblocking for this bounded continued-development review, and does not authorize beta release.

## Limits, isolation and authority

The reviewer did not independently execute the entire repository suite, remote CI, frontend generation/typecheck, production-volume migration/restore, mutation testing or production operations. Evidence above states precisely which checks ran and at which SHA; unchanged-code results are carried through verified product-identical deltas, not relabeled as full runs at the final head. Exact-head required CI remains a separate delivery gate.

All PostgreSQL review work used new synthetic databases in the uniquely named disposable container `homies-bp56-review-20261012` on reviewer-only localhost port 60116. Its tmpfs data and container were removed after review tests completed. The parent's port 55556 database and existing port 5432 database were never connected to or changed. No reviewer product edit, commit, push, merge or deployment occurred. Test probe and review reports are stored outside the checkout.

The founder retains final acceptance and new-PR merge authorization. IBB-001 remains the last formal baseline; the report does not alter FE-003 authorization or production/deployment flags.
