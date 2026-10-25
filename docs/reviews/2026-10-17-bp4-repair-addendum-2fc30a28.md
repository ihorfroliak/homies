# BP-4 independent repair addendum — BP4-IR-01

Tests executed: 2026-10-17; addendum finalized after recovery on 2026-10-18. Independent reviewer: `/root/bp9_independent_review`, not the implementer.

**BP4-IR-01 CLOSED on the repaired exact candidate.** The two independent assertions that failed on the original candidate now pass unchanged. No remaining P0/P1/P2/P3 defect was established in the bounded repair. The original report remains immutable. This addendum records one nonblocking execution limitation below; it does not grant founder acceptance, merge or deployment authorization.

## Identity

- Repaired commit: `2fc30a28939c7d8b8a5b6f62a71a920ad444d693`.
- Repaired tree: `c8ae64d1263e41c4edbcabc96374cfe6834559cc`.
- Original reviewed commit: `d138fadf9d5fdcc245fae31fe7f2515283c979e3`.
- Original report: `2026-10-17-bp4-independent-review-d138fadf.md`; SHA256 remains `79bcb413a8d9c1b50124b3c1250c3f36657adb2463f228e7213c3574dab6a88c`.
- Own detached worktree: `C:/Users/ihorf/.codex/worktrees/bp4-repair-independent-audit/homies`. Git SHA/tree and clean status checked before and after review; source remained read-only and unchanged.

## Bounded closure

Only the delta from the original BP-4 candidate was reviewed: `display.py` changes the predicate from a nonzero canonical combining class to Unicode mark-category membership, the permanent projection tests add the two class 0-mark examples, and the task contract records the repair. No authorization, query, DTO, API-shape or migration change occurred in this delta.

At `backend/app/modules/engagement/display.py:24`, `unicodedata.category(char).startswith("M")` retains consecutive Mn/Mc/Me characters following the first code point. This addresses the exact contract violation while retaining the first/last whitespace-word rule, existing decomposed-accent behavior and raw Unicode spelling. It is not claimed as a full grapheme-cluster parser, which was not requested.

Independent unchanged reproductions now return:

- `आशा किरण` → `आशा कि.`
- `মিনা দাস` → `মিনা দা.`

CANONICAL DECISION REQUIRED: **NO**. The correction implements the existing task-contract mark-retention requirement. The historical P3 stays recorded against the original SHA and is closed only for this repaired SHA.

## Checks actually executed

Same Linux Python 3.12.15 / pytest 9.1.1 cached test image as the original review; candidate and external probes mounted read-only; `ENV=test`, bytecode disabled, network disabled, synthetic SQLite only. No PostgreSQL instance or production access.

1. `python -m pytest -p no:cacheprovider tests/test_bp4_requester_display.py tests/test_tst01_openapi_contract.py -q`: **25 passed, 1 fixture setup error**, 17.39 seconds. The error is retained below.
2. Unchanged single-case rerun, `tests/test_bp4_requester_display.py::test_current_empty_name_uses_fallback_without_stored_legal_identity`: **1 passed**, 7.12 seconds. Thus 26 distinct repository cases have passing results across the runs; the initial 26-case invocation is not described as clean.
3. Unchanged external `test_bp4_independent.py`: **4 passed**, 16.68 seconds. Both original Unicode failures pass, and the multiple-row scalar-query batching and authorization-before-projection controls still pass. External probe SHA256 remains `6b91a4edabcc635e79bd2705b568f832ccaae6f432b0b50004f09705ba2281ab`.
4. Ruff on `app/modules/engagement/display.py` and `tests/test_bp4_requester_display.py`: **passed**.
5. `python -m mypy --cache-dir=/tmp/bp4-repair-mypy app/modules/engagement/display.py`: **Success: no issues found in 1 source file**, exit 0, recovered on 2026-10-18. The prior process output was unavailable after the usage interruption; no result was inferred from it. Only this previously unconfirmed check was rerun, with output persisted to `BP-4-repair-mypy-recovery.txt`.
6. Original-to-repaired `git diff --check`: **passed**; final source status **clean**, SHA/tree exact.

## NOTE — initial fixture setup error retained

Location: `backend/tests/test_bp4_requester_display.py:43`. During the first focused run, `_start(...).json()["conversation"]` raised KeyError because the fixture's HTTP response lacked that key. The fallback test body did not execute in that attempt. The raw response/status was not captured by the fixture, so this review does not attribute the event to JWT time, networking, the Unicode fix or another cause. The single case passed unchanged on rerun; no source, authentication behavior or clock tolerance was changed.

Relevant invariant: test evidence must distinguish setup failure from an executed product assertion and must not count failed invocations as passes. Expected treatment: retain this record; if the intermittent setup issue is investigated separately, record the status/response in the fixture to establish cause. Suggested repair here: none to the Unicode production change. CANONICAL DECISION REQUIRED: **NO**. This is a nonblocking evidence limitation, not a second demonstrated BP-4 product defect.

## Scope and status

No broad BP-9 audit or original full BP-4 regression suite was repeated. Original privacy/static findings remain supported by the original report and unchanged relevant source; focused independent batching/authorization probes were repeated because they are small and directly tied to this projection. No full-suite, mutation, browser, TypeScript or production-readiness claim. CI for the repaired candidate remained pending in the parent assignment and was not independently retrieved here; repository archival and founder acceptance remain separate steps.

This addendum and its execution record are external artifacts for verbatim parent archival. The report checksum is provided in a separate sidecar.
