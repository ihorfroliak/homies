---
id: PROJECT-STATUS
type: status_index
as_of: 2026-10-01
current_baseline:
  id: IBB-001
  name: Integrated Backend Baseline 001
  sha: 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98
  status: accepted
production_ready: false
deployed: false
next_task: TASK-015 founder decisions on the Phase A contract, then TASK-015 Slice 1
---

# Project status — orientation index

> **Derived, not canonical.** A fast orientation page for humans and agents.
> It holds no decisions of its own: authority is [00-AUTHORITY](canonical/00-AUTHORITY.md),
> the canon, [IMPLEMENTATION-CONVERGENCE](canonical/IMPLEMENTATION-CONVERGENCE.md)
> and [DECISIONS](DECISIONS.md). If this page disagrees with them, they win —
> fix this page. Nothing is accepted because it is listed here.

**As of:** 2026-10-01 (BASELINE-001; updated by PR-002 and PR-003 integration and TASK-015 Phase A)

## Current accepted backend baseline

| | |
|---|---|
| Human name | **Integrated Backend Baseline 001** |
| ID | `IBB-001` |
| Accepted SHA | `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` |
| Git tag | `backend-baseline-001` |
| Status | **ACCEPTED FOR CONTINUED DEVELOPMENT** |
| Production | **NOT_READY** |
| Deployment | **NOT_DEPLOYED** |
| Record | [docs/baselines/IBB-001.md](baselines/IBB-001.md) |

There is one backend development line. All new backend work descends from
IBB-001 (or a documented successor baseline). The documentation commits that
recorded IBB-001 (BASELINE-001) sit on top of it and change no code; the
accepted code state is the SHA above, not a later documentation HEAD.

### Provenance

| Role | ID | Exact SHA | Verdict |
|---|---|---|---|
| PRODUCT parent | TASK-014 — Saved Listings, Saved Search & Alerts | `7ffb4f51dd315363362df1a5f8fc5c19a57767dc` | ACCEPTED (TASK-014RA) |
| INFRA parent | PR-001 — Runtime / CI / Readiness Baseline | `5cad442f07264ab25b3024c96fc691ad9c7a75fa` | ACCEPTED (PR-001RA2) |
| Integration | CONV-001 | `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` | merge of the two parents |
| Independent integration audit | CONV-001A | — | ACCEPTED WITH NONBLOCKING NOTES (`CONV_001_ACCEPTED_WITH_NONBLOCKING_NOTES`) |

Full history of every audit cycle: [docs/reviews/AUDIT-HISTORY.md](reviews/AUDIT-HISTORY.md).
Naming convention: [docs/engineering/TRACEABILITY.md](engineering/TRACEABILITY.md).

## Next serialized development

```text
IBB-001                     ACCEPTED
  ↓
MICRO-001                   DONE      evidence / docs / test cleanup (R0/R1) — on main at dacbe9e3
  ↓
PR-002                      BUILDER VERIFIED · MILESTONE AUDIT DEFERRED — release and migration compatibility (R2, D-88) — on main at 13a92ef7 (merge of be26fcb8)
  ↓
PR-003                      BUILDER VERIFIED · MILESTONE AUDIT DEFERRED — database client deadlines / failure containment (R2, D-88) — on main at 451b7e56 (merge of e54b3eec)
  ↓
TASK-015 Phase A            DONE (contract, READY WITH DECISIONS REQUIRED) — on its branch, docs only
  ↓
TASK-015 implementation     PLANNED   reports and moderation
```

PR-002 is **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88): integrated into
`main` for continued development after green CI — merge commit
`13a92ef77b66096021d3927fdb255b546a4ecc63` (parents `dacbe9e3` + candidate
`be26fcb8`, CI 5/5) — not independently verified, not production-ready:
[task](tasks/PR-002-release-migration-compatibility.md),
[policy](production/RELEASE-AND-MIGRATION.md). Its independent review is part of
the milestone / production-readiness audit.

PR-003 is **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88), integrated into
`main` by founder authorization — merge commit
`451b7e566a1958097b2df2266e2bb7cc41314621` (parents `13a92ef7` + candidate
`e54b3eec`, CI 5/5): [task](tasks/PR-003-db-failure-containment.md), D-89 …
D-91. It closes PR-001RA RA-3.

TASK-015 Phase A (reports & moderation basics) is a **contract only**:
[task](tasks/TASK-015-reports-moderation-phase-a.md) — READY WITH DECISIONS
REQUIRED; no TASK-015 runtime exists. Nothing after it is implemented.
MICRO-001: [scope and closure](tasks/MICRO-001-evidence-docs-test-cleanup.md).

**DEFERRED:** Phase-2 transactional renting (payments, ledger), short stay,
dedicated search/message infrastructure — by canonical decision only
([06 — Roadmap](canonical/06-ROADMAP.md)).

## Verification policy after IBB-001

Risk-based (R0 docs → builder + light checks; R1 ordinary → tests + CI;
R2 migrations/authorisation/concurrency/privacy → independent review where
material — from PR-002 on deferred into the milestone audit (D-88); R3 payments/production/deployment → independent audit + operational
evidence + founder approval). Details: [AUDIT-HISTORY](reviews/AUDIT-HISTORY.md#governance-change-after-ibb-001--risk-based-verification).

## Production

**NOT_READY · NOT_DEPLOYED.** Readiness matrix and open gaps:
[docs/production/PRODUCTION-READINESS.md](production/PRODUCTION-READINESS.md).
