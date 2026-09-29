# Project status — orientation index

> **Derived, not canonical.** A fast orientation page for humans and agents.
> It holds no decisions of its own: authority is [00-AUTHORITY](canonical/00-AUTHORITY.md),
> the canon, [IMPLEMENTATION-CONVERGENCE](canonical/IMPLEMENTATION-CONVERGENCE.md)
> and [DECISIONS](DECISIONS.md). If this page disagrees with them, they win —
> fix this page. Nothing is accepted because it is listed here.

**As of:** 2026-09-29 (written by the TASK-014 builder)

## CURRENT ACCEPTED PRODUCT BASELINE

TASK-013 (Phase-1A slice) — `3f324b6ddff6c7557894eb5f65736729d956f7eb`
(`TASK_013_PHASE_1A_SLICE_ACCEPTED`, D-77; TASK-013RA archived in docs/reviews).
TASK-014 is **not** accepted.

## CURRENT PRODUCT CANDIDATE

TASK-014 — saved listings, saved search & alerts — branch
`claude/TASK-014-saved-search-alerts`, candidate SHA: the tip of that branch
named in the TASK-014 builder report (this page cannot contain its own
commit's SHA). Contract:
[TASK-014](tasks/TASK-014-saved-listings-saved-search-alerts.md).

## CURRENT INFRA CANDIDATE

PR-001R — `70be78bfd746b63a1444e1dd7eb82023226215d3`
(`claude/PR-001R-runtime-ci-repair`), awaiting PR-001RA. Separate ancestry; not
merged into the product branch.

## PRODUCTION

**NOT READY · NOT DEPLOYED.**

## ACTIVE / NEXT GATES

1. TASK-014 independent audit (TASK-014A).
2. PR-001RA (independent audit of PR-001R).
3. Future product + infra convergence (one branch, one Alembic head, CI run).
