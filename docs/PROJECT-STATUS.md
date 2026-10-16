---
id: PROJECT-STATUS
type: status_index
role: single semantic owner of volatile project status (D-106, 05 §14)
as_of: 2026-10-16
reconciled_through:
  code_and_product: BP-8 merge 4ed8fe8ab334a8d8e344b80e266da2be3b661aee (D-112)
  documentation: BP-8 integrated; HOMIES-DELIVERY-002 authorized (D-112)
last_formal_baseline:
  id: IBB-001
  name: Integrated Backend Baseline 001
  sha: 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98
  tag: backend-baseline-001
  status: ACCEPTED
latest_code_bearing_main_state:
  implementation_sha: 24a47e81cfd31948e4de642ff7c2cb2fbe5bf521
  what: BP-8 INTEGRATED; prior BP-5/BP-6 acceptance retained
  merge_sha: 4ed8fe8ab334a8d8e344b80e266da2be3b661aee
  candidate_ci: 38548793363 success 6/6
  main_ci: post-merge verification in progress; result on GitHub
repository_head: resolved from Git (origin/main); intentionally not embedded here
next_task:
  id: HOMIES-DELIVERY-002
  status: AUTHORIZED — AGENT-002 and BP-11/BP-9 in progress on isolated branches; subsequent PRs Draft only
fe003_implementation_authorized: true # conditional on verified backend prerequisites; D-112
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

**As of:** 2026-10-12. **BP-10 and AGENT-001 are INTEGRATED / ACCEPTED
FOR CONTINUED DEVELOPMENT** under D-110. PR #6 merge
`064be3e1827d279890a9e026e9b1a48e476d7dbd` has candidate and post-merge CI
SUCCESS 6/6. PR #5 merge `74a7065e167e6cea8d4251a17138ffe775b02a54`
has exact reconciled-head CI `38152688469` SUCCESS 6/6; its post-merge run
`38217864176` is SUCCESS 6/6. Integrated main tree is
`735e1557a1362c0070f815c4875bab7fa69920f8`. Both original candidates remain
ancestors; both DEVLOG entries and specialist configurations are preserved.

**2026-10-14 — BP-5 and BP-6 INTEGRATED (D-111).** PR #7 normal merge
`38db9c100eae331fbe978432c9197d5ceb893121` preserves accepted candidate
`b400bc9ea8f638e5915c9892b29abe444db7d242` and tree
`225cc074f8358b521bbf79f033b57313ebe7821e`. CI38363820860 SUCCESS6/6,
1983passed/1skip (live Stripe), restore10/10, coverage92.2%.
Postmerge CI: [38546637969](https://github.com/ihorfroliak/homies/actions/runs/38546637969).
[Independent final report](reviews/BP56-independent-review-b400bc9-final.md)
and its two antecedents are archived byte-for-byte; final SHA256
`fe185b69d0a9238a34422bd4b0a038b0dfeab50fd5ef05e4c25c32b9cf0a9d04`.
Founder accepts PASS WITH NONBLOCKING NOTE. BP-9/BB-10 must include provider
notice VERIFIED-root authority filtering before external provider beta.
Migration23e89acb98b4 remains BARRIER / rollback_to_previous BLOCKED;
unprovable historical actors retain sealed NULL legacy exception.
Local Docker clock instability is not a certified application defect.
This historical acceptance is followed by BP-8 integration under D-112; no debt/baseline/deployment change.

**2026-10-16 — BP-8 INTEGRATED (D-112).** PR #9 merge
`4ed8fe8ab334a8d8e344b80e266da2be3b661aee`; exact accepted tree
`b29e0ceac644c026ecaa3d3e5dd01cc625b27f27`. Candidate CI38548793363 SUCCESS6/6;
independent PASS [report](reviews/BP8-independent-review-24a47e8.md) archived
with original SHA256. Post-merge CI is being verified. New program scope and
conditional FE-003 authorization: [D-112](DECISIONS.md),
[full directive](tasks/HOMIES-DELIVERY-002.md). Claude CLI is installed but not
authenticated; Codex is authorized writer. New feature branches remain candidates.

## Three different "current" states

| Concept | Value | How to read it |
|---|---|---|
| **Last formal backend baseline** | Integrated Backend Baseline 001 (`IBB-001`), `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98`, tag `backend-baseline-001`, **ACCEPTED** (CONV-001A) | the last state accepted through the baseline process ([record](baselines/IBB-001.md)). There is no IBB-002 |
| **Historical BP-10 main state** | BP-10 merge `064be3e1827d279890a9e026e9b1a48e476d7dbd`; audited implementation `c385136c93826879b41509f1e30533ef46eee64c` preserved | ACCEPTED FOR CONTINUED DEVELOPMENT (D-110), D-109 dispositions retained; candidate CI `38129196394` SUCCESS 6/6; post-merge CI from GitHub. No successor formal baseline |
| **Repository HEAD** | read it from Git: `git rev-parse origin/main` | this file does not embed the SHA of the commit that contains it ([TRACEABILITY](engineering/TRACEABILITY.md#self-reference-a-file-cannot-name-its-own-commit)). Documentation-only children do not replace the frozen audited implementation identity |

## Flags

```text
BP-10 MERGE AUTHORIZED:              YES  (PR #6 only, D-110)
AGENT-001 MERGE AUTHORIZED:          YES  (PR #5 only, after reconciliation/checks, D-110)
BP-5 / BP-6:                         INTEGRATED (D-111, PR #7)
BP-8:                                INTEGRATED (D-112, PR #9)
FE-003 IMPLEMENTATION AUTHORIZED:     YES, conditional on verified backend prerequisites (D-112)
FE-VIS-001 IMPLEMENTATION AUTHORIZED: NO   (D-104 OD-5; DESIGN-001C handoff §26, §31)
PRODUCTION READY:                     NO   (NOT_READY)
DEPLOYMENT:                           NO   (NOT_DEPLOYED; no production environment exists)
```

## Next work

| Order | Item | Status |
|---|---|---|
| integration 1 | **BP-10** — [PR #6](https://github.com/ihorfroliak/homies/pull/6) | INTEGRATED / ACCEPTED FOR CONTINUED DEVELOPMENT (D-110), merge `064be3e1827d279890a9e026e9b1a48e476d7dbd`, candidate CI `38129196394` SUCCESS 6/6. Audited code `c385136c93826879b41509f1e30533ef46eee64c`, PASS_WITH_NONBLOCKING_NOTES; all four P3 and five NOTEs/debt retained under D-109. [Historical staging receipt](reviews/2026-10-11-bp10-acceptance-staging-receipt.md) |
| integration 2 | **AGENT-001** — [PR #5](https://github.com/ihorfroliak/homies/pull/5) | INTEGRATED / ACCEPTED FOR CONTINUED DEVELOPMENT; merge `74a7065e167e6cea8d4251a17138ffe775b02a54`, exact-head CI `38152688469` SUCCESS 6/6. Six Claude/six Codex specialists preserved. Native dispatch NOT VERIFIED where unavailable is an accepted nonblocking limitation; no shared vendor memory/cache or guaranteed routing |
| integrated | **BP-5 + BP-6** | INTEGRATED / ACCEPTED, D-111, PR #7 merge38db9c1; exact-head CI and independent review accepted |
| integrated | **BP-8** | INTEGRATED, D-112; PR #9 merge4ed8fe8, independent PASS, candidate CI SUCCESS6/6 |
| authorized | AGENT-002; BP-11; BP-9 → BP-3 → BP-4 → FE-003 | D-112; isolated bounded branches and Draft PRs, independent reviews where required. FE-003 conditional on verified prerequisites. MARKET-001 remains separate |

FE-003 is conditionally authorized by D-112; FE-VIS-001 remains unauthorized. Beta blockers BB-1…BB-11
stay open until their own criteria close them. IBB-001 remains the last formal
baseline; no IBB-002. BP-10 release restrictions remain **EXPAND /
rollback_to_previous = BLOCKED / migrate-first / BB-11 all-serving-instances**.
Integration does not certify deployment or external beta. No completed audit
is reopened by this integration; new BP-8 work has its own review gate.

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

## Main protection — 2026-10-16

Active ruleset25221028 applies to refs/heads/main: PR required, six GitHub Actions
checks (backend/web/contracts/monitoring/image/secrets, app15368) required on the
current base, force pushes and deletion blocked, merge commits allowed, no bypass
actors. Zero mandatory formal GitHub approvals preserves the sole-contributor
workflow; canonical independent-review evidence and founder authorization remain
required. Configuration: [main-ruleset.json](engineering/main-ruleset.json).
Repository visibility remains public. Verified by reading back both the ruleset
and effective main rules. No deployment occurred.
