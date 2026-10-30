---
id: PROJECT-STATUS
type: status_index
role: single semantic owner of volatile project status (D-106, 05 §14)
as_of: 2026-10-25
reconciled_through:
  code_and_product: FE-003 merge 98ad3cc09b418784500452a62907be2dd46f9e81 (D-114)
  documentation: HOMIES-DELIVERY-002 integrated package and immutable review archive (D-114)
last_formal_baseline:
  id: IBB-001
  name: Integrated Backend Baseline 001
  sha: 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98
  tag: backend-baseline-001
  status: ACCEPTED
latest_code_bearing_main_state:
  implementation_sha: 3f1a3fdbac303edbf09bf5e95678356d96dcc15d
  what: DEP-001, BP-3, BP-11, BP-9, AGENT-002, BP-4 and FE-003 INTEGRATED
  merge_sha: 98ad3cc09b418784500452a62907be2dd46f9e81
  candidate_ci: 40140692791 success 6/6
  main_ci: 40174564874 (exact merge SHA; post-merge acceptance gate)
repository_head: resolved from Git (origin/main); intentionally not embedded here
next_task:
  id: HOMIES-DELIVERY-002
  status: IMPLEMENTATION INTEGRATED — D-114; documentation/archive reconciliation effective with PR10 merge
fe003_implementation_authorized: true # prerequisites satisfied; implementation integrated under D-114
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

## Delivery integration — 2026-10-25

**D-114: the founder-approved implementation package is INTEGRATED.** Normal
GitHub merge commits preserve every original reviewed candidate. Each refreshed
candidate passed all six required checks on its current main base. Changes
during refresh were mechanical composition and complete DEVLOG unions; reviewed
application semantics were preserved. No protection bypass or deployment.

| Task | Original reviewed candidate | Refreshed candidate | PR / actual merge | Exact candidate CI |
|---|---|---|---|---|
| DEP-001 | `289b816d76757ced905bc565e548170bd461d830` | `289b816d76757ced905bc565e548170bd461d830` | [#18](https://github.com/ihorfroliak/homies/pull/18) / `211fd249cda1906d74ca15ceb18d7e25348d76ea` | [40090487615](https://github.com/ihorfroliak/homies/actions/runs/40090487615) SUCCESS 6/6 |
| BP-3 | `55c9d43d218b9fa749789348adeccc59306fe9ea` | `c158df1d226323b3fb729e0f3154adffe93784e6` | [#11](https://github.com/ihorfroliak/homies/pull/11) / `6bccb427cabefcde5c359c9bd5f9df8bbb5b8b38` | [40127816560](https://github.com/ihorfroliak/homies/actions/runs/40127816560) SUCCESS 6/6 |
| BP-11 | `e3841a638b4cc54bba10b2caed29569aaffd54e5` | `ffea83d37c91c24dda699997e4be88f23f3f4250` | [#14](https://github.com/ihorfroliak/homies/pull/14) / `51874d521d364bccd8fb6071384e7ed00711f323` | [40129162428](https://github.com/ihorfroliak/homies/actions/runs/40129162428) SUCCESS 6/6 |
| BP-9 | `fb5b3e57a6e4881ab14ad378a15e15f49475e682` | `566dec6fd3bf1d00a120092515b9888db42b6901` | [#13](https://github.com/ihorfroliak/homies/pull/13) / `485ee1688c8d35cd305da5862fa68074b5ee4f3f` | [40136125477](https://github.com/ihorfroliak/homies/actions/runs/40136125477) SUCCESS 6/6 |
| AGENT-002 | `ff972255587d4737604073993dd88278e1af1c07` | `be14f95dd9c9da44c07bafebdeeeb874a6ebe7b2` | [#12](https://github.com/ihorfroliak/homies/pull/12) / `4aabbd8f2a33dcee54686d6a9f39e5ac2fcc6dd9` | [40137662406](https://github.com/ihorfroliak/homies/actions/runs/40137662406) SUCCESS 6/6 |
| BP-4 | `2fc30a28939c7d8b8a5b6f62a71a920ad444d693` | `25406c0e99f1fd4821b794f45738bb178a0c390d` | [#15](https://github.com/ihorfroliak/homies/pull/15) / `6e75c7d68fe9c6119f4d2faeb5d6c410c881a05f` | [40139200433](https://github.com/ihorfroliak/homies/actions/runs/40139200433) SUCCESS 6/6 |
| FE-003 | `c831ea616a6fe022b08b4fba106761a9d4c6cdd1` | `3f1a3fdbac303edbf09bf5e95678356d96dcc15d` | [#17](https://github.com/ihorfroliak/homies/pull/17) / `98ad3cc09b418784500452a62907be2dd46f9e81` | [40140692791](https://github.com/ihorfroliak/homies/actions/runs/40140692791) SUCCESS 6/6 |

PR16's reviewed composition `ee19b3affc9f33d560c7624ebc6b562276c56000`
is an ancestor of main through FE-003. Its backend source, tests and generated
API matched the integrated individual prerequisites. PR16 is closed as incorporated,
not recorded as a separate merge; no artificial empty merge was created. PR10 contains this final status reconciliation and the byte-exact
independent report archive. Its merge identity is resolved from Git/GitHub,
not embedded in a file that would have to name its own containing commit.
See the [authorized integration contract](tasks/HOMIES-DELIVERY-002-integration.md).
All independent reviews, focused closures and accepted nonblocking notes remain
valid for the unchanged sources and are retained below.

The refreshed FE-003 run `40140692791` passed all six CI jobs:
2099 backend tests, 206 unit tests, 98 desktop/mobile browser scenarios and
10 restore drills; coverage 90.3%, mypy 128 files, no known dependency
vulnerabilities. Two explicit backend skips remain: live Stripe and the opt-in
PostgreSQL benchmark.

The first final documentation candidate `e3dc48b08dac613995d8b033ca2b740eab9c77e6`
encountered a frontend unit-test synchronization failure in CI `40174842047`
(205/206 passed). The report401 regression helper advanced its mock frame queue
before React's passive authentication-completion effect necessarily registered
that frame. A controlled 200 ms registration delay reproduced the same missing
send-button failure with the original helper; waiting for the actual frame made
that probe pass. The R1 repair changes only that helper, retaining every original
privacy/no-auto-send assertion, timeout and product source. Host unit tests then
passed 206/206; typecheck and lint passed. Host Node 24.14 retains the previously
noted transitive engine warnings; supported Linux CI remains the acceptance gate.
The original failing run remains recorded; this repair requires fresh exact-head
CI and is not covered by a historical green verdict.

 Post-merge run `40174564874` belongs to exact main
`98ad3cc09b418784500452a62907be2dd46f9e81`; final documentation integration
requires that run and the documentation candidate to pass all six checks.

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

**Incorporated dependency [PR16](https://github.com/ihorfroliak/homies/pull/16) — original composition evidence:**
`ee19b3affc9f33d560c7624ebc6b562276c56000`, tree
`18a6c794d3d37c4eca63a57d4cb910c18c7048a8`, base BP-4 PR15; preserves BP-9,
BP-3 and BP-11 ancestry. No product-code conflicts; combined schema generation
matches. Combined regressions:200 passed +1 fixture setup error; unchanged
single-case rerun1 passed7.93s. Ruff/mypy127/API/types pass. [Composition-only independent review](reviews/FE003-composition-review-ee19b3a.md) PASS;36 tests and41 shared definitions verified. Exact composed CI39112216176 SUCCESS6/6. FE-003 implementation entry released after independent feature/composition verification; frontend, conversation and synthetic-fixture writers use separate bounded contexts and isolated worktrees derived from this exact base. This historical evidence is now incorporated through the D-114 integration above; it does not certify deployment.

**FE-003 INTEGRATED — original independent candidate evidence:**
[PR #17](https://github.com/ihorfroliak/homies/pull/17), branch
`codex/FE-003-engagement-journey`, originally based on PR #16. Reviewed combined candidate
`c831ea616a6fe022b08b4fba106761a9d4c6cdd1`, tree
`9bc245c62028fb9144cc35e88b6f49d3a88a6c09`. Founder reconfirmed bounded
fixes, tests, commit/push and Draft PR on 2026-10-21, then authorized the
verified dependency repair's inclusion on 2026-10-23/24. D-114 subsequently authorized its protected main integration. Deployment and paid-provider activation remain unauthorized.

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
frontend source/configuration is unchanged. That was feature-branch composition evidence; the subsequent founder-authorized main integration is recorded above.

Historical evidence is retained: local final units were 205/206 with one
unchanged growth-test timeout, followed by an unchanged focused 12/12 pass;
subsequent GitHub runs passed all 206. Local full browser tests passed 96/96,
plus 10 fresh-account save journeys and two restored-report journeys. Earlier
CI 40019368887 and 40090323202 passed web and four other jobs but failed the
backend dependency audit. These failures are not erased or reported as green.

**DEP-001 dependency repair — INTEGRATED, original review evidence:**
[PR #18](https://github.com/ihorfroliak/homies/pull/18), candidate
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
in the FE-003 feature candidate above and was subsequently integrated under D-114.

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

**Retained release limits and historical CI evidence:** DEP-001 resolved the
old pinned-dependency blockers. Historical documentation runs 39651483013 and
40113823558 failed dependency audit before that repair reached the docs branch;
those failures remain historical failures, not green evidence. Every current
combined candidate requires its own exact-SHA checks. Integration preserves all
reviewed limitations and does not create a successor formal baseline.
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
FE-003:                              INTEGRATED (D-114); backend prerequisites integrated
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
| integrated | DEP-001; AGENT-002; BP-11; BP-9; BP-3; BP-4; FE-003 | D-114; exact reviewed ancestry and current-base CI preserved. MARKET-001 remains separate |

FE-003 is integrated under D-114; FE-VIS-001 remains unauthorized. Beta blockers BB-1…BB-11
stay open until their own criteria close them. IBB-001 remains the last formal
baseline; no IBB-002. BP-10 release restrictions remain **EXPAND /
rollback_to_previous = BLOCKED / migrate-first / BB-11 all-serving-instances**.
Integration does not certify deployment or external beta. No completed audit
is reopened by this integration; no new product scope is authorized here.

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

## 2026-10-30 — DESIGN-001C local presentation candidate

Founder supplied the latest design package and explicitly requested preservation and integration/improvement. Codex owns the bounded web presentation candidate in `codex/design-001c-integration`, based on `4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4`. [Contract](tasks/DESIGN-001C-integration.md), [preserved originals and convergence](design/001c/README.md), [verification](design/001c/VERIFICATION.md).

Archive and neutral presentation integration are locally verified, not merged or accepted as the complete FE-VIS-001 rollout. Source geography/boundaries, district palette and font proposals remain deferred. Candidate CI and founder visual acceptance are pending. Existing main status, IBB-001 and debt remain unchanged; production is NOT READY / NOT DEPLOYED.
