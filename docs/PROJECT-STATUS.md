---
id: PROJECT-STATUS
type: status_index
role: single semantic owner of volatile project status (D-106, 05 §14)
as_of: 2026-10-06
reconciled_through:
  code_and_product: BP-12 merge a7756e16c5ae2888776bf02a022b44b0221c0f7a
  documentation: TASK-016 source-of-truth reconciliation
last_formal_baseline:
  id: IBB-001
  name: Integrated Backend Baseline 001
  sha: 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98
  tag: backend-baseline-001
  status: ACCEPTED
latest_code_bearing_main_state:
  sha: a7756e16c5ae2888776bf02a022b44b0221c0f7a
  what: BP-12 merge (IBB-001 plus builder-verified increments)
  main_ci: 37417946174 success
repository_head: resolved from Git (origin/main); intentionally not embedded here
next_task:
  id: BP-10
  status: NOT_STARTED
fe003_implementation_authorized: false
fe_vis_001_implementation_authorized: false
production_ready: false
deployed: false
---

# Project status — orientation index

> **Single owner of volatile status, not of decisions.** This page owns the
> answer to "where is Homies now?" (05 §14, D-106): baseline, `main` state,
> candidates, next work, authorisation flags and production state. It holds no
> decisions of its own: authority is [00-AUTHORITY](canonical/00-AUTHORITY.md),
> the canon, [IMPLEMENTATION-CONVERGENCE](canonical/IMPLEMENTATION-CONVERGENCE.md)
> and [DECISIONS](DECISIONS.md). If this page disagrees with them, they win —
> fix this page. Nothing is accepted because it is listed here.

**As of:** 2026-10-06. Code and product state reconciled through the BP-12
merge; documentation reconciled by TASK-016.

## Three different "current" states

| Concept | Value | How to read it |
|---|---|---|
| **Last formal backend baseline** | Integrated Backend Baseline 001 (`IBB-001`), `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98`, tag `backend-baseline-001`, **ACCEPTED** (CONV-001A) | the last state accepted through the baseline process ([record](baselines/IBB-001.md)). There is no IBB-002 |
| **Latest code-bearing `main` state** | `a7756e16c5ae2888776bf02a022b44b0221c0f7a` — BP-12 merge, main CI `37417946174` success (backend, web, image, contracts, monitoring, secrets) | IBB-001 plus the merged increments listed below. Verification and review status is recorded per increment in the table: several R1 increments received founder/GPT review, while the R2 increments marked MILESTONE AUDIT DEFERRED still await the D-88 milestone review. Founder/GPT review is not the D-88 milestone audit, and neither is formal baseline acceptance: no post-IBB increment has been promoted to a formal successor backend baseline, so no IBB-002 exists |
| **Repository HEAD** | read it from Git: `git rev-parse origin/main` | this file does not embed the SHA of the commit that contains it ([TRACEABILITY](engineering/TRACEABILITY.md#self-reference-a-file-cannot-name-its-own-commit)). Documentation-only merges after `a7756e1` (such as TASK-016) do not change the code-bearing state |

## Flags

```text
FE-003 IMPLEMENTATION AUTHORIZED:     NO   (contract approved, D-104/D-105)
FE-VIS-001 IMPLEMENTATION AUTHORIZED: NO   (D-104 OD-5; DESIGN-001C handoff §26, §31)
PRODUCTION READY:                     NO   (NOT_READY)
DEPLOYMENT:                           NO   (NOT_DEPLOYED; no production environment exists)
```

## Next work

| Order | Item | Status |
|---|---|---|
| next | **BP-10** — idempotent conversation start / message append (FE-003 §10.1; beta blocker BB-11) | **NOT STARTED** — a separate bounded task |
| then | BP-5 + BP-6, BP-8 → BP-11, BP-9 (security review) → BP-3, BP-4 | NOT STARTED — order from [FE-003 §10.3](tasks/FE-003-save-conversation-viewing-DRAFT.md) |
| later | MARKET-001 residential rental market research ([research family](research/README.md)) | NOT STARTED — separate task, non-normative |

FE-003 slices start only with a separate founder authorisation per slice
(FE-003 §13); beta blockers BB-1…BB-11 stay open until their own tasks close
them.

## Integrated on `main` since IBB-001

Status words: [TRACEABILITY](engineering/TRACEABILITY.md#status-vocabulary).
Risk classes: R0–R3 ([AUDIT-HISTORY](reviews/AUDIT-HISTORY.md#governance-change-after-ibb-001--risk-based-verification)).

| # | Item | Risk class | Status | `main` merge (candidate) |
|---|---|---|---|---|
| 1 | [MICRO-001](tasks/MICRO-001-evidence-docs-test-cleanup.md) — evidence, docs, test cleanup | R0/R1 | DONE | `dacbe9e3` (direct commit) |
| 2 | [PR-002](tasks/PR-002-release-migration-compatibility.md) — release and migration compatibility | R2 | BUILDER VERIFIED · MILESTONE AUDIT DEFERRED (D-88) | `13a92ef7` (`be26fcb8`) |
| 3 | [PR-003](tasks/PR-003-db-failure-containment.md) — database deadlines, failure containment | R2 | BUILDER VERIFIED · MILESTONE AUDIT DEFERRED | `451b7e56` (`e54b3eec`) |
| 4 | [TASK-015 Phase A](tasks/TASK-015-reports-moderation-phase-a.md) — moderation contract | docs-only | DONE (contract; founder D-1…D-9 approved, D-92) | `985db7ae` (`2d4064b0`) |
| 5 | [TASK-015 S1](tasks/TASK-015-S1-moderation-core.md) — decision chain, publication hold (D-93) | R2 | BUILDER VERIFIED · MILESTONE AUDIT DEFERRED | `1a65d381` (`1ccf1a18`) |
| 6 | [TASK-015 S2+S3](tasks/TASK-015-S23-listing-report-moderation-loop.md) — listing reports, moderator loop (D-94) | R2 | BUILDER VERIFIED · MILESTONE AUDIT DEFERRED | `4bf66108` (`7a51236d`) |
| 7 | [TASK-015 S5](tasks/TASK-015-S5-moderation-review-requests.md) — review requests (D-95) | R2 | BUILDER VERIFIED · MILESTONE AUDIT DEFERRED | `1de34bf5` (`3146fed3`) |
| 8 | [TASK-015 S4a](tasks/TASK-015-S4A-message-moderation.md) — message reports, redaction (D-96) | R2 | BUILDER VERIFIED · MILESTONE AUDIT DEFERRED; externally reviewed (GPT-5.6 Sol) | `03268432` (`ff433303`) |
| 9 | PROGRAM-001 — [TASK-015 S4b](tasks/TASK-015-S4B-engagement-safety.md) (D-97) + TASK-015 closure, [GROWTH-001](growth/GROWTH-001-marketplace-growth-foundation.md), [DESIGN-001](product/DESIGN-001-product-ui-foundation.md), [FE-001](frontend/FE-001-foundation.md), [FE-002](frontend/FE-002-seeker-search-detail.md), canon changes, security repairs | R1/R2 | externally reviewed (GPT-5.6 Sol: accepted for merge with conditions), founder-approved; S4b BUILDER VERIFIED · MILESTONE AUDIT DEFERRED; the other parts BUILDER VERIFIED (no deferral recorded). TASK-015 complete for Phase 1A | `c32ac63f` (`779b30fe`) |
| 10 | PROGRAM-001 integration decisions — F6 enforcement, D-102, D-103 | not recorded | merged after branch CI `37163365720` | `995b05fe` (`cde91fa9`) |
| 11 | [FE-003 contract](tasks/FE-003-save-conversation-viewing-DRAFT.md) (D-104, D-105) | docs-only | APPROVED — implementation NOT authorised | `c87616ad` (`2162676e`) |
| 12 | [P-0 DESIGN-001C handoff](design/DESIGN-001C-HANDOFF.md) (D-107) | docs-only | APPROVED — implementation binding ready for FE-003 | `673b61e0` (`2ed544bb`) |
| 13 | HM-1 Home-map amendment (handoff §31, D-107) | docs-only | recorded; owner FE-VIS-001 (not authorised) | `dc74da3f` (`50d1074f`) |
| 14 | [BP-1](tasks/BP-1-stable-api-codes.md) — stable API refusal codes | R1 | merged; founder/GPT reviewed | `6be148b6` (`fa5612e6`) |
| 15 | [BP-2 + BP-7](tasks/BP-2-BP-7-viewing-api-contract.md) — typed viewing slots + timezone; no cancel after start (DB clock) | R1 | merged; founder/GPT reviewed | `6adca78c` (`caf38383`) |
| 16 | [BP-12](tasks/BP-12-message-report-verification-exception.md) — MESSAGE reports without verified contact (D-105 OD-7) | R1 | merged; founder/GPT reviewed (BP-12: PASS) | `a7756e16` (`0d45583a`; implementation `434c0956`; CI `37413458869`) |

Before IBB-001 the accepted line was Foundation Baselines 001/002 → TASK-010,
TASK-012, TASK-013, TASK-014 + PR-001 → CONV-001 → IBB-001
([AUDIT-HISTORY](reviews/AUDIT-HISTORY.md)).

## Deferred milestone audit (D-88)

Items recorded above as MILESTONE AUDIT DEFERRED wait for one comprehensive
milestone / production-readiness review (D-88; list in
[AUDIT-HISTORY §8](reviews/AUDIT-HISTORY.md#8-after-ibb-001--integrated-without-independent-acceptance-d-88)).
**CANONICAL DECISION REQUIRED:** the milestone's trigger, scope, acceptance
threshold and whether it yields a successor baseline are not defined in the
repository. Nothing here defines them.

## Open knowledge gaps (05 §14)

01 Constitution v2, 02 Business Logic and 03 System Architecture v1.1 are
incomplete derived representations of founder texts authored outside the
repository ([00 — source status](canonical/00-AUTHORITY.md#source-status-of-levels-24));
the concrete 1C visual values live only in the inaccessible DESIGN-001C
artifact (handoff §27, U-1) and are needed before an FE-VIS-001 contract.
Full list: [TASK-016 §10](tasks/TASK-016-source-of-truth-documentation-reconciliation.md#10-recorded-not-resolved-here).

## Not now

**DEFERRED** by canonical decision: Phase-2 transactional renting (payments,
ledger), short stay, dedicated search/message infrastructure
([06 — Roadmap](canonical/06-ROADMAP.md)). Legacy modules are
`LEGACY_DORMANT`.

## Verification policy after IBB-001

Risk-based: R0 docs → builder + light checks; R1 ordinary → tests + CI; R2
migrations/authorisation/concurrency/privacy → independent review where
material, from PR-002 on deferred into the milestone audit (D-88); R3
payments/production/deployment → independent audit + operational evidence +
founder approval.

## Production

**NOT_READY · NOT_DEPLOYED.** Readiness matrix and open gaps:
[PRODUCTION-READINESS](production/PRODUCTION-READINESS.md).
