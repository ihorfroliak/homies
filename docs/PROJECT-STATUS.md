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
next_task: PROGRAM-001 (program branch claude/PROGRAM-001-product-growth-frontend) — external review, then founder merge decision
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
TASK-015 Phase A            DONE (contract; founder D-1…D-9 approved, D-92) — on main at 985db7ae
  ↓
TASK-015 Slice 1            BUILDER VERIFIED · MILESTONE AUDIT DEFERRED — moderation core + publication hold (R2) — on main at 1a65d381 (merge of 1ccf1a18)
  ↓
TASK-015 Slices 2+3         BUILDER VERIFIED · MILESTONE AUDIT DEFERRED — listing reports, moderator API, owner notices (R2) — on main at 4bf66108 (merge of 7a51236d)
  ↓
TASK-015 Slice 5            BUILDER VERIFIED · MILESTONE AUDIT DEFERRED — review requests / owner reconsideration (R2) — on main at 1de34bf5 (merge of 3146fed3)
  ↓
TASK-015 Slice 4a           BUILDER VERIFIED · MILESTONE AUDIT DEFERRED — message reports, evidence, redaction (R2) — on main at 03268432 (merge of ff433303)
  ↓
TASK-015 Slice 4b           BUILDER VERIFIED · MILESTONE AUDIT DEFERRED — conversation closure, close_engagement, viewing protection, photo restriction (R2) — on the PROGRAM-001 branch, NOT on main
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

TASK-015 Phase A (reports & moderation basics): [contract](tasks/TASK-015-reports-moderation-phase-a.md)
on `main` (`985db7ae`); founder decisions D-1 … D-9 approved (D-92). TASK-015
Slice 1 ([task](tasks/TASK-015-S1-moderation-core.md), D-93, 04a §23) is on
`main` (`1a65d381`, merge of `1ccf1a18`): immutable moderation decision chain,
publication hold enforced in `make_public`. TASK-015 Slices 2+3
([task](tasks/TASK-015-S23-listing-report-moderation-loop.md), D-94) are on
`main` (`4bf66108`, merge of `7a51236d`): listing reports, moderator
queue/review/decisions, owner moderation state and TRANSACTIONAL inbox notices.
TASK-015 Slice 5 ([task](tasks/TASK-015-S5-moderation-review-requests.md),
D-95) is on `main` (`1de34bf5`, merge of `3146fed3`). TASK-015 Slice 4a
([task](tasks/TASK-015-S4A-message-moderation.md), D-96) is on `main`
(`03268432`, merge of `ff433303`, externally reviewed): message reports,
bounded audited moderator evidence, CONTENT_REMOVED redaction; rollback to S5
is a security barrier; L9 legal validation required before launch. TASK-015
Slice 4b ([task](tasks/TASK-015-S4B-engagement-safety.md), D-97) is on the
PROGRAM-001 branch, **not on `main`**: close_engagement, conversation
restriction (G-14), viewing protection under a hold, non-destructive photo
restriction; rollback to S4a is a safety barrier.
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
