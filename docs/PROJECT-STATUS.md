# Project status — orientation index

> **Derived, not canonical.** A fast orientation page for humans and agents.
> It holds no decisions of its own: authority is [00-AUTHORITY](canonical/00-AUTHORITY.md),
> the canon, [IMPLEMENTATION-CONVERGENCE](canonical/IMPLEMENTATION-CONVERGENCE.md)
> and [DECISIONS](DECISIONS.md). If this page disagrees with them, they win —
> fix this page. Nothing is accepted because it is listed here.

**As of:** 2026-09-30 (written by the CONV-001 builder)

## ACCEPTED BASELINES (separate lines)

| Line | Accepted SHA | Verdict |
|---|---|---|
| PRODUCT — TASK-014 (Phase-1A slice) | `7ffb4f51dd315363362df1a5f8fc5c19a57767dc` | `TASK_014_PHASE_1A_SLICE_ACCEPTED` (TASK-014RA) |
| INFRA — PR-001 (runtime / CI / readiness) | `5cad442f07264ab25b3024c96fc691ad9c7a75fa` | `PR_001_BASELINE_ACCEPTED` (PR-001RA2) |

Common ancestor: `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` (TASK-012 accepted line).

## CURRENT INTEGRATION CANDIDATE

**CONV-001** — one merge commit of both accepted lines on
`claude/CONV-001-product-infra` (SHA in the CONV-001 builder report; this page
cannot contain its own commit's SHA). **CONV-001A REQUIRED.** Not accepted.

## PRODUCTION

**NOT READY · NOT DEPLOYED.**

## ACTIVE / NEXT GATES

1. CONV-001A (independent integration audit, exact SHA).
2. MICRO-001 (R0 wording cleanup) after the integrated baseline is accepted.
3. PR-002 Phase B (blocked until CONV-001 is accepted) → PR-003 → TASK-015 delta → TASK-015 B.
