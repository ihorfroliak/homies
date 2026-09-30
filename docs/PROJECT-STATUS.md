---
id: PROJECT-STATUS
type: status_index
as_of: 2026-09-30
current_baseline:
  id: IBB-001
  name: Integrated Backend Baseline 001
  sha: 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98
  status: accepted
production_ready: false
deployed: false
next_task: PR-002
---

# Project status — orientation index

> **Derived, not canonical.** A fast orientation page for humans and agents.
> It holds no decisions of its own: authority is [00-AUTHORITY](canonical/00-AUTHORITY.md),
> the canon, [IMPLEMENTATION-CONVERGENCE](canonical/IMPLEMENTATION-CONVERGENCE.md)
> and [DECISIONS](DECISIONS.md). If this page disagrees with them, they win —
> fix this page. Nothing is accepted because it is listed here.

**As of:** 2026-09-30 (written by BASELINE-001)

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
MICRO-001                   CANDIDATE evidence / docs / test cleanup (R0/R1) — builder done, CI on the branch
  ↓
PR-002                      PLANNED   release and migration compatibility
  ↓
PR-003                      PLANNED   database client deadlines / failure containment
  ↓
TASK-015 delta review       PLANNED   against IBB-001
  ↓
TASK-015 implementation     PLANNED   reports and moderation
```

Nothing after MICRO-001 is implemented. MICRO-001 scope and closure:
[docs/tasks/MICRO-001-evidence-docs-test-cleanup.md](tasks/MICRO-001-evidence-docs-test-cleanup.md).

**DEFERRED:** Phase-2 transactional renting (payments, ledger), short stay,
dedicated search/message infrastructure — by canonical decision only
([06 — Roadmap](canonical/06-ROADMAP.md)).

## Verification policy after IBB-001

Risk-based (R0 docs → builder + light checks; R1 ordinary → tests + CI;
R2 migrations/authorisation/concurrency/privacy → independent review where
material; R3 payments/production/deployment → independent audit + operational
evidence + founder approval). Details: [AUDIT-HISTORY](reviews/AUDIT-HISTORY.md#governance-change-after-ibb-001--risk-based-verification).

## Production

**NOT_READY · NOT_DEPLOYED.** Readiness matrix and open gaps:
[docs/production/PRODUCTION-READINESS.md](production/PRODUCTION-READINESS.md).
