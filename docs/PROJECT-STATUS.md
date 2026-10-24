---
id: PROJECT-STATUS
type: status_index
role: single semantic owner of volatile project status (D-106, 05 §14)
as_of: 2026-10-24
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
  main_ci: 38859368831 success (exact merge SHA verified)
repository_head: resolved from Git (origin/main); intentionally not embedded here
next_task:
  id: HOMIES-DELIVERY-002
  status: INTEGRATION AUTHORIZED — D-114, package PRs 10–18; protected merge execution in progress
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

**Historical integration record — 2026-10-12.** **BP-10 and AGENT-001 are INTEGRATED / ACCEPTED
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
with original SHA256. Post-merge CI38859368831 is SUCCESS. New program scope and
conditional FE-003 authorization: [D-112](DECISIONS.md),
[full directive](tasks/HOMIES-DELIVERY-002.md). Claude CLI is installed but not
authenticated; Codex is authorized writer. New feature branches remain candidates.

## Delivery checkpoint — 2026-10-24

**D-114: founder now authorizes integration of PRs #10–18.** The prior Draft-only
statements below describe the delivered candidates before this decision. Follow
[the bounded integration contract](tasks/HOMIES-DELIVERY-002-integration.md);
no integration is claimed until its actual merge is recorded. No deployment.


All candidates below are implemented, pushed and **unmerged Draft PRs**.
No new merge authorization is inferred. BP-4 is stacked on BP-9; the other
listed candidates start at integrated BP-8 main. FE-003 is implemented on the independently verified dependency chain. Backend CI results below are historical exact-candidate evidence; they do not exempt current dependency scans. FE-003 and its dependency repair now have independent closure and exact combined CI green; founder acceptance and main integration remain separate decisions.

| Task | Exact candidate | Verification and review | CI run | Draft PR |
|---|---|---|---|---|
| AGENT-002 | `ff972255587d4737604073993dd88278e1af1c07` | 26 synthetic tests + Ruff; both original P2 findings repaired, independent repair addendum PASS, both P2 closed; native runtime invocation limitations retained | 39029912878 SUCCESS | [#12](https://github.com/ihorfroliak/homies/pull/12) |
| BP-11 | `e3841a638b4cc54bba10b2caed29569aaffd54e5` | Builder benchmark: all 10 outputs identical; largest fixture SQL 2488 to 8, median 7415 to 126 ms; independent PASS_WITH_NONBLOCKING_NOTES, 135 cases +120 differential comparisons | 39007470216 SUCCESS | [#14](https://github.com/ihorfroliak/homies/pull/14) |
| BP-9 | `fb5b3e57a6e4881ab14ad378a15e15f49475e682` | Independent PASS_WITH_NONBLOCKING_NOTES; 121 repository tests + 7 independent probes, Ruff/mypy/OpenAPI clean; no P0-P3 findings | 38941516780 SUCCESS | [#13](https://github.com/ihorfroliak/homies/pull/13) |
| BP-3 | `55c9d43d218b9fa749789348adeccc59306fe9ea` | Original CI direct-handler default regression repaired; 20 focused tests including PostgreSQL regression + API drift; independent repair addendum PASS (19 tests + Ruff) | 39029843865 SUCCESS | [#11](https://github.com/ihorfroliak/homies/pull/11) |
| BP-4 | `2fc30a28939c7d8b8a5b6f62a71a920ad444d693` | Unicode P3 repaired; independent addendum closes finding, 4 independent probes pass; initial fixture errors retained transparently | 39060137761 SUCCESS | [#15](https://github.com/ihorfroliak/homies/pull/15), base BP-9 |

[BP-9 independent report](reviews/2026-10-17-bp9-independent-review-fb5b3e57.md)
is archived byte-for-byte, SHA256
`2d8b1b750d78fc83757a1a1eedbfcfc25bfcfa84cdcb23c8e3e4abd4ce5299bf`.
Its two nonblocking notes retain the bounded temporal authorization guarantee
and optionally promote the independent probes; no strict commit-time guarantee
or production certification is asserted. Original reviews and their focused addenda are archived below.


Independent evidence archived unchanged (each full SHA256 verified before copy):

- [BP-3 original](reviews/BP-3-independent-review.md) and [repair PASS](reviews/BP-3-repair-addendum-55c9d43.md).
- [AGENT-002 original](reviews/AGENT-002-independent-review.md) and [repair PASS](reviews/AGENT-002-repair-addendum-ff97225.md).
- [BP-11 PASS with notes](reviews/BP11-independent-review-e3841a6.md).
- [BP-4 original P3](reviews/2026-10-17-bp4-independent-review-d138fadf.md) and [repair closure](reviews/2026-10-17-bp4-repair-addendum-2fc30a28.md).

**Explicit dependency Draft [PR16](https://github.com/ihorfroliak/homies/pull/16):**
`ee19b3affc9f33d560c7624ebc6b562276c56000`, tree
`18a6c794d3d37c4eca63a57d4cb910c18c7048a8`, base BP-4 PR15; preserves BP-9,
BP-3 and BP-11 ancestry. No product-code conflicts; combined schema generation
matches. Combined regressions:200 passed +1 fixture setup error; unchanged
single-case rerun1 passed7.93s. Ruff/mypy127/API/types pass. [Composition-only independent review](reviews/FE003-composition-review-ee19b3a.md) PASS;36 tests and41 shared definitions verified. Exact composed CI39112216176 SUCCESS6/6. FE-003 implementation entry released after independent feature/composition verification; frontend, conversation and synthetic-fixture writers use separate bounded contexts and isolated worktrees derived from this exact base. This branch is
not main and does not authorize any merge or deployment.

**FE-003 implemented, independently reviewed and combined CI green:**
Draft [PR #17](https://github.com/ihorfroliak/homies/pull/17), branch
`codex/FE-003-engagement-journey`, base PR #16. Combined candidate
`c831ea616a6fe022b08b4fba106761a9d4c6cdd1`, tree
`9bc245c62028fb9144cc35e88b6f49d3a88a6c09`. Founder reconfirmed bounded
fixes, tests, commit/push and Draft PR on 2026-10-21, then authorized the
verified dependency repair's inclusion on 2026-10-23/24. No main merge,
deployment or paid-provider activation is authorized.

Implemented journeys: authentication and safe intent continuation, saved
listings/searches, conversations and reporting, contact verification/reveal,
viewing requests and requester/provider actions. All five original independent
client findings are closed: account-transition privacy, stale save retries,
report authentication/resume, terminal-thread selection and ancillary-cost wording.
The [original report](reviews/FE003-client-review-ec2bfa9.md),
[intermediate repair report](reviews/FE003-client-repair-review-c3b68a5.md) and
[final closure](reviews/FE003-client-final-review-46b187e.md) are archived
byte-for-byte. Final report SHA256:
`8eff39f6c93f831332be8ae70dde85ff2c3593645d24d401b3df000fceaf19fe`.
The reviewer independently ran 62/62 targeted tests at
`46b187e4846706a9162ab30ecb7079c191cfbb9f` and verified identical product
source/configuration/dependencies in the frontend checkpoint
`04cab95a905f37e5a64d265e8dad22a529103449` (tree
`300d7ee84415076fe7edefe995d16c1a9bad89bb`). Its only follow-up changes were
browser setup and evidence documentation.

Combined [CI 40112245745](https://github.com/ihorfroliak/homies/actions/runs/40112245745)
is **SUCCESS 6/6** at this exact candidate: **2099 backend tests passed,
206 unit tests passed, 98 desktop/mobile browser scenarios passed, and 10
restore checks passed**. Two backend skips are explicit: live Stripe and the
opt-in PostgreSQL benchmark. Coverage is 90.3%; mypy passed 128 files; the
dependency scan found no known vulnerabilities. Typecheck, lint, generated API
equality and production build passed.
The normal merge preserves both reviewed parents (04cab95 and DEP-001
289b816); only three dependency/contract files changed from 04cab95. All
frontend source/configuration is unchanged. This is feature-branch integration,
not a merge to main or final founder acceptance.

Historical evidence is retained: local final units were 205/206 with one
unchanged growth-test timeout, followed by an unchanged focused 12/12 pass;
subsequent GitHub runs passed all 206. Local full browser tests passed 96/96,
plus 10 fresh-account save journeys and two restored-report journeys. Earlier
CI 40019368887 and 40090323202 passed web and four other jobs but failed the
backend dependency audit. These failures are not erased or reported as green.

**DEP-001 dependency repair — reviewed, CI green:**
Draft [PR #18](https://github.com/ihorfroliak/homies/pull/18), candidate
`289b816d76757ced905bc565e548170bd461d830`, tree
`e832526908e56b9d2060aee90ee8ae527bac17d9`, base integrated main.
Founder authorized certifi 2026.10.19/Pillow 13.0.0 on 23 October, then
filelock 4.2.1 on 24 October. No other pins, application code, migrations or
audit suppressions change. [Exact CI 40090487615](https://github.com/ihorfroliak/homies/actions/runs/40090487615)
is **SUCCESS 6/6**: 1992 backend tests passed, one live-Stripe skip, 10 restore
checks passed, and no known dependency vulnerabilities. The rebuilt supported
Python 3.12.15 runtime matches all 70 pins and passes pip check.

The [original review](reviews/DEP001-independent-review-47b1be5.md) and
[focused addendum](reviews/DEP001-independent-addendum-289b816.md) found no
introduced P0-P3 defects. Independent lock contention/release, CacheControl,
pin matching, dependency audit and vulnerable-package detection canary passed.
Final addendum SHA256:
`d8ff45eefd531b8e88448a60da204299c4a502244b47f3ad8609c401b20c22e3`.
Retained NOTE: the original media run passed 80 tests with one fixture setup
error; the unchanged isolated case then passed. Cause remains unknown.
Predecessor CI 40069367584 passed its tests but failed three filelock advisory
rows; the final update resolves that audit failure. DEP-001 is now included
in the FE-003 feature candidate above; no main merge is authorized.

The [bounded BFF review](reviews/FE003-bff-review-dbf0668.md) independently
passed105/105 tests at `dbf06681a78c128c27bfcf3a2ae94f485dec6cb2`, with no
P0-P3 findings and one optional regression-retention NOTE. SHA256:
`4d3a45197e75f9a7bbaecf901d0249cb056cb5e66d0c9a4f93af210e5b2fde2a`.
Report and supporting synthetic probes/output/blob identities are archived
byte-for-byte. At the final frontend checkpoint the complete BFF/server boundary,
proxy, package/lockfile and Next/TypeScript config diff is empty against that
review SHA, including the combined c831ea6 candidate (comparison verified). This narrow
result does not certify client privacy, full FE-003 or external beta.

Synthetic seed `b44e7bdbff4bf5da6b8e904bec29cc57bd16818f` independently
passed 13 targeted tests. [Original review](reviews/FE003-seed-review-b44e7bd.md)
found one P3 fixture-state validation gap, with no P0-P2 findings. Repair
`81ef509837eb3f1a113455f6e17343d2877f4d24` closes it: the
[independent addendum](reviews/FE003-seed-repair-review-81ef509.md) verifies
four rejected mode/role mutations, no silent repair and unchanged replay;
one focused PostgreSQL test PASS (218.60 s). Both reports are archived
byte-for-byte. Original SHA256:
`64fafb0fedbccbf14774e58661b75c06e77e3a6675cb4731cb3f17bcdbb75d91`;
addendum SHA256:
`d678aac1923b72a8774a81e1232731767dd1ce90de3d9edd1381c5ee0ac04ffd`.
The original 12 fixtures remain intact; desktop/mobile engagement data is
separate. No product authorization defect was found in this narrow seed review.

**Remaining integration and release limits:** all new PRs remain Draft and
unmerged. The documentation branch retains main's old dependency pins; its
previous CI 39651483013 failed dependency audit, and its documentation-only
archive update does not claim to repair those pins. Merge DEP-001 through the
normal founder-approved flow and refresh affected branches/checks before main
integration. Do not copy the combined FE-003 CI verdict onto another SHA.
External beta still requires the existing refresh/logout, participant address,
parking-input, authority-correct supply, SMS-provider and analytics-legal gates.
AGENT-002's native vendor invocation remains NOT VERIFIED. Existing independent
nonblocking notes and prior unknown-cause fixture errors remain visible.

Main ruleset **25221028 ACTIVE**: PRs and six current-base CI checks required,
force-push/deletion blocked, merge commits only, no bypass actors. IBB-001,
BARRIER/rollback BLOCKED, BP-10 EXPAND/BB-11 and all existing debt remain.
FE-VIS-001 unauthorized; production NOT READY / NOT DEPLOYED.
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
