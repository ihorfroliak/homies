# FE-UX-KRK-002R — targeted frontend hardening

Founder directive 2026-11-06. Risk class R1: frontend client state and tests; no backend,
schema, API, authorization or lockfile change. Builder: Claude Code. Reviewer: Codex.

Base: `353324acb3d7784a4f798f5eaa400dbef30ea136` (Draft PR26, stacked on Draft PR25), under
exact-SHA review, so PR26 is not updated. Branch `claude/FE-UX-KRK-002R-hardening`, own
worktree. No additional PR. Integration into PR26 is proposed after that review completes.

## Scope and method

UX-R1 viewing time zone, UX-R2 return to results, UX-R3 map selection, UX-R4 map card
freshness, UX-R5 back/forward cache, UX-R6 retry and recovery. Reproduce first, fix second,
verify third. Regression tests were committed before the fixes (`4b561ec`); that commit alone
does not typecheck, because the unit tests import what the fixes add.

Recorded decisions kept: API-returned time zone is authoritative and Warsaw is never hard-coded
(handoff C-7); FE-003's explicit UTC fallback applies when no schedule exists. Results:
[receipt](../reviews/FE-UX-KRK-002R-verification.md).

## Repair after review (2026-11-07)

Review of `77f07ec`: [REQUEST_CHANGES](../reviews/2026-11-07-fe-ux-krk-002r-codex-review.md) with
F-01 (focus after a last page that adds no listing), F-02 (accessible names of viewing actions) and
F-03 (test gap and a wrong mutation claim). Same scope and risk class; no new canonical decision.
Failing regressions committed first (`94aeb1f`), fixes `f8c53fb` and `25fc884`.
