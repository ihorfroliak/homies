# Project status — orientation index

> **Derived, not canonical.** A fast orientation page for humans and agents.
> It holds no decisions of its own: authority is [00-AUTHORITY](canonical/00-AUTHORITY.md),
> the canon, [IMPLEMENTATION-CONVERGENCE](canonical/IMPLEMENTATION-CONVERGENCE.md)
> and [DECISIONS](DECISIONS.md). If this page disagrees with them, they win —
> fix this page. Nothing is accepted because it is listed here.

**As of:** 2026-09-29 (written by the TASK-014R builder)

## CURRENT ACCEPTED PRODUCT BASELINE

TASK-013 (Phase-1A slice) — `3f324b6ddff6c7557894eb5f65736729d956f7eb`
(`TASK_013_PHASE_1A_SLICE_ACCEPTED`, D-77; TASK-013RA archived in docs/reviews).
TASK-014 is **NOT YET ACCEPTED**.

## CURRENT PRODUCT CANDIDATE

TASK-014 `196c88796cf34a6b19860259cc6ff81c94dbe8d2` → TASK-014A
(`TASK_014_REQUIRES_TARGETED_FIXES`, archived) → **TASK-014R — CANDIDATE** on
`claude/TASK-014R-alert-integrity-repair`; candidate SHA: the tip named in the
TASK-014R builder report (this page cannot contain its own commit's SHA).
**TASK-014RA REQUIRED.** Contract:
[TASK-014](tasks/TASK-014-saved-listings-saved-search-alerts.md).

## CURRENT INFRA CANDIDATE

PR-001R2 — `5cad442f07264ab25b3024c96fc691ad9c7a75fa`
(`claude/PR-001R2-readiness-repair`), awaiting PR-001RA2. Separate ancestry; not
merged into the product branch.

## PRODUCTION

**NOT READY · NOT DEPLOYED.**

## ACTIVE / NEXT GATES

1. TASK-014RA (independent audit of TASK-014R, exact SHA, stable-clock evidence).
2. PR-001RA2 (independent audit of PR-001R2).
3. MICRO-001 → CONV-001 (one branch, one Alembic head, CI run) → PR-002 B → PR-003 → TASK-015.
