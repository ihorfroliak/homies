# BP-3 independent repair addendum

Date: 2026-10-17. Exact candidate: 55c9d43d218b9fa749789348adeccc59306fe9ea.
Tree: 97298ecda763f6fa7550762cae6a446dbd47e7b1.
Prior reviewed candidate: 94935fa132ef821f3d67ffe95ebc1526a5ec9d5e.
Worktree: C:/Users/ihorf/.codex/worktrees/delivery002-bp3-repair-audit/homies.

Verdict: PASS for the focused repair and original bounded BP-3 review, read together. P0/P1/P2/P3 open findings: 0. No canonical decision required. This closes the direct-call compatibility defect in the reviewed change; it is not merge approval, CI certification, production readiness or BP-9 acceptance.

Scope: only the three-file repair diff, its causal regression and API invariance. Original review and subsequent-CI note remain immutable. No broader audit repeated.

The prior default was a FastAPI Query object outside dependency resolution. router.py:798-805 now retains user and db as the first positional parameters, puts Query metadata in Annotated and gives scope the real Python default PUBLISH_LISTING. Existing calls using my_classifieds(user=..., db=...) and positional user/db therefore enter the unchanged owner branch. The added direct-call regression exercises that branch using a legitimate unverified draft owner and checks freshness_detail. Inspected the actual PostgreSQL R9 call site, which uses user/db keywords without scope. Authorization predicates, engagement DTO, owner projection and published API schema are otherwise unchanged.

Independently executed in network-disabled Python 3.12 image bp10c-test:c385136 with candidate backend/docs mounted read-only, PYTHONDONTWRITEBYTECODE=1, SQLite-only database URLs and pytest cache disabled:
python -m pytest -p no:cacheprovider -q tests/test_bp3_provider_enumeration.py tests/test_tst01_openapi_contract.py
Result: 19 passed, 1 inherited Starlette httpx deprecation warning in 21.92s (13 BP-3 cases and 6 API checks).
Focused Ruff on changed router/test files: All checks passed (shared linter invocation also checked AGENT-002's two repaired Python files).
Git confirmed exact HEAD/tree, empty status and detached HEAD. No source modification.

Limits: actual PostgreSQL R9 was NOT independently rerun; the builder's 20-test run including that case remains builder evidence. The direct-call regression and signature inspection establish the specific repaired failure mechanism. No full suite, mypy, frontend generation/typecheck, remote CI or deployment checks executed for this addendum. Existing original-review limits remain. Required CI and founder merge decision remain separate gates.
