---
id: PROJECT-STATUS
type: status_index
role: single semantic owner of volatile project status (D-106, 05 §14)
as_of: 2026-10-11
reconciled_through:
  code_and_product: BP-10 merge 064be3e1827d279890a9e026e9b1a48e476d7dbd (D-110)
  documentation: BP-10 integrated; AGENT-001 configuration integrated when PR 5 reaches main (D-110)
last_formal_baseline:
  id: IBB-001
  name: Integrated Backend Baseline 001
  sha: 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98
  tag: backend-baseline-001
  status: ACCEPTED
latest_code_bearing_main_state:
  implementation_sha: c385136c93826879b41509f1e30533ef46eee64c
  what: BP-10 INTEGRATED / ACCEPTED FOR CONTINUED DEVELOPMENT
  merge_sha: 064be3e1827d279890a9e026e9b1a48e476d7dbd
  candidate_ci: 38129196394 success 6/6
  main_ci: resolve actual post-merge run from GitHub
repository_head: resolved from Git (origin/main); intentionally not embedded here
next_task:
  id: BP-5 + BP-6
  status: AUTHORIZED — begins immediately after PR 5 integration
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

**As of:** 2026-10-11. **BP-10 is INTEGRATED / ACCEPTED FOR CONTINUED
DEVELOPMENT** via PR #6, merge `064be3e1827d279890a9e026e9b1a48e476d7dbd`;
exact-head CI `38129196394` SUCCESS 6/6. AGENT-001 is accepted under D-110:
this branch is the reconciled PR #5 candidate until merge; **when this record
lands on main through PR #5, AGENT-001 is INTEGRATED / ACCEPTED FOR CONTINUED
DEVELOPMENT** and BP-5/BP-6 implementation begins. Actual PR #5 merge SHA and
post-merge CI come from Git/GitHub, never a predicted self-reference.

## Three different "current" states

| Concept | Value | How to read it |
|---|---|---|
| **Last formal backend baseline** | Integrated Backend Baseline 001 (`IBB-001`), `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98`, tag `backend-baseline-001`, **ACCEPTED** (CONV-001A) | the last state accepted through the baseline process ([record](baselines/IBB-001.md)). There is no IBB-002 |
| **Latest code-bearing `main` state** | BP-10 merge `064be3e1827d279890a9e026e9b1a48e476d7dbd`; audited implementation `c385136c93826879b41509f1e30533ef46eee64c` preserved | ACCEPTED FOR CONTINUED DEVELOPMENT (D-110), D-109 dispositions retained; candidate CI `38129196394` SUCCESS 6/6; post-merge CI from GitHub. No successor formal baseline |
| **Repository HEAD** | read it from Git: `git rev-parse origin/main` | this file does not embed the SHA of the commit that contains it ([TRACEABILITY](engineering/TRACEABILITY.md#self-reference-a-file-cannot-name-its-own-commit)). Documentation-only children do not replace the frozen audited implementation identity |

## Flags

```text
BP-10 MERGE AUTHORIZED:              YES  (PR #6 only, D-110)
AGENT-001 MERGE AUTHORIZED:          YES  (PR #5 only, after reconciliation/checks, D-110)
BP-5 / BP-6 IMPLEMENTATION AUTHORIZED: YES  (after both integrations; new PR merge NOT authorized)
FE-003 IMPLEMENTATION AUTHORIZED:     NO   (contract approved, D-104/D-105)
FE-VIS-001 IMPLEMENTATION AUTHORIZED: NO   (D-104 OD-5; DESIGN-001C handoff §26, §31)
PRODUCTION READY:                     NO   (NOT_READY)
DEPLOYMENT:                           NO   (NOT_DEPLOYED; no production environment exists)
```

## Next work

| Order | Item | Status |
|---|---|---|
| integration 1 | **BP-10** — [PR #6](https://github.com/ihorfroliak/homies/pull/6) | INTEGRATED / ACCEPTED FOR CONTINUED DEVELOPMENT (D-110), merge `064be3e1827d279890a9e026e9b1a48e476d7dbd`, candidate CI `38129196394` SUCCESS 6/6. Audited code `c385136c93826879b41509f1e30533ef46eee64c`, PASS_WITH_NONBLOCKING_NOTES; all four P3 and five NOTEs/debt retained under D-109. [Historical staging receipt](reviews/2026-10-11-bp10-acceptance-staging-receipt.md) |
| integration 2 | **AGENT-001** — [PR #5](https://github.com/ihorfroliak/homies/pull/5) | ACCEPTED FOR CONTINUED DEVELOPMENT; INTEGRATED when reconciled PR #5 lands on main after green checks. Six Claude/six Codex specialists preserved. Native dispatch NOT VERIFIED where unavailable is an accepted nonblocking limitation; no shared vendor memory/cache or guaranteed routing |
| immediately after both merges | **BP-5 + BP-6** | IMPLEMENTATION AUTHORIZED (D-110), Codex temporary sole bounded writer in a dedicated worktree/feature branch. BP-5 first, BP-6 second; real PostgreSQL, migrations/API/types/release checks, CI and separate exact-SHA R2 review; Draft PR, subsequent founder merge authorization required |
| later, separately authorized | BP-8 → BP-11, BP-9 → BP-3, BP-4; MARKET-001 | Existing [FE-003 sequencing](tasks/FE-003-save-conversation-viewing-DRAFT.md); no authorization added here |

FE-003 frontend and FE-VIS-001 remain unauthorized. Beta blockers BB-1…BB-11
stay open until their own criteria close them. IBB-001 remains the last formal
baseline; no IBB-002. BP-10 release restrictions remain **EXPAND /
rollback_to_previous = BLOCKED / migrate-first / BB-11 all-serving-instances**.
Integration does not certify deployment or external beta. No completed audit
is reopened by this integration; new BP-5/BP-6 work has its own review gate.

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
