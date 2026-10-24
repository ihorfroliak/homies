# FE-003 final focused independent client closure — 46b187e

**Disposition: PASS for the bounded client closure.** The remaining CLIENT-2 and CLIENT-3 findings are closed. Together with the prior focused closure, all five original client findings are closed. No new established P0/P1/P2/P3 defect was found in this bounded delta. This is not a new whole-system audit, production-readiness statement, merge approval or deployment authorization.

## Exact identities and preserved evidence

- Runtime/source reviewed and tested: **`46b187e4846706a9162ab30ecb7079c191cfbb9f`**.
- Tree: **`b5a801eceeb9fc4bc61495dbf764f552674b2db1`**.
- Own detached worktree: `C:/Users/ihorf/.codex/worktrees/fe003-client-final-review/homies`; exact identity and clean status verified.
- Delta base: `c3b68a5896f9fb8f91a169a4ff9e19836fb82df6`.
- Original immutable review: `FE003-client-review-ec2bfa9.md`, SHA256 `ab9c8eaf3ef62391ff487fdc0e9e1e80268643157a1d5320d6368c6b26f63bbe`.
- Prior immutable focused review: `FE003-client-repair-review-c3b68a5.md`, SHA256 `05ddf35ac2f3cbd9bf332fd482acf66e8ae4683fc6df5412d4e44a3fab14af09`.
- Original and intermediate failing probes/output remain preserved. This report supersedes their open disposition only for the repaired code identity above.

Scope was limited to the remaining saved-operation generation/lock lifetime, restored eligible report intent, directly affected source/tests, and the final follow-up's equivalence. Earlier authority/contract reading and unchanged client review evidence are reused. No BFF/backend/seed re-audit, database use, shared runtime mutation, source edits, commit, push or deployment was performed.

## Findings closed

### CLIENT-2 — P2 MEDIUM: saved operation generation and busy ownership — CLOSED

**Repair:** `frontend/web/src/engagement/saved.tsx:16`, `:43`, `:48`, `:69`.

Every committed identity transition increments a generation, including A → anonymous → A. The layout effect establishes the current account/generation and initial-read promise before continuation. Reads, state, operation ownership and busy display are generation-scoped. The stable toggle captures its generation, checks it before retries and reconciliation, rejects obsolete results, and returns false for abandoned work so the initiating button does not emit a false success event.

In-flight keys include generation plus listing id. An old finally block deletes only its own key and does not update the new generation's busy set. Returning to the same user id cannot revive the invalidated operation.

**Executed evidence:** The retained causal A → anonymous → A probe now passes with exactly one POST. The new lock-isolation test starts A's deferred save, switches to B, verifies B can start its own same-listing operation, rejects A's old response, and verifies B stays busy until B's response succeeds. Existing saved regressions also pass, covering same-session idempotent transport retry, uncertain-outcome re-read, late account responses, initial-read recovery, confirmed state changes, tombstones and saved-search state/version behavior.

**Expected invariant achieved:** FE-003 sections 3.1 and 3.7 account-bound continuation; old operations neither issue automatic writes under a later generation nor lock/unlock that generation's work.

**CANONICAL DECISION REQUIRED: No.**

### CLIENT-3 — P2 MEDIUM: restored authorized report intent — CLOSED

**Repair:** `frontend/web/src/engagement/conversations.tsx:182` and `:191`.

Thread consumes a restored report intent only after fresh authorized thread data is available with the expected side. It finds the referenced message in that thread and applies the existing `mayReport` eligibility rule before opening ReportDialog. The safe intent is consumed; private report text is not restored; opening the form does not submit anything. Own, removed and SYSTEM messages do not open the dialog.

**Executed evidence:** The formerly failing restored eligible intent probe now passes. The assertion correctly waits for the post-response effect to open the dialog, rather than demanding synchronous rendering. The other assertions are preserved, including zero automatic report POSTs. New own/removed/SYSTEM cases pass. Existing report and conversation regressions pass, including unverified-participant reporting, own/other-side filtering, neutral refusals and removal of private thread/report UI after denied reads. The live 401 → same-account login control still retains the memory-only draft and requires another explicit send.

**Expected invariant achieved:** FE-003 section 3.7, AC-A1/AC-A6 and OD-7: restore the safe report intent through authentication, retain backend/current-thread authority, add no verification wall, and require deliberate submission.

**CANONICAL DECISION REQUIRED: No.**

## Tests actually executed

Disposable network-disabled Docker `node:24`, observed **Node v24.21.0**, **Vitest 5.0.3**, existing jsdom configuration. The pinned source and Linux dependency volume were mounted read-only and copied into private ephemeral container files. Container execution completed with exit 0.

| Test file | Executed result |
|---|---|
| `src/engagement/closure.test.tsx` | **12/12 PASS** |
| `src/engagement/saved.test.tsx` | **18/18 PASS** |
| `src/engagement/conversations.test.tsx` | **32/32 PASS** |
| Total | **62/62 PASS**, 3 files, reported duration **7.52 s** |

The twelve closure tests include the eight earlier independent causal/positive probes plus busy-lock isolation and three ineligible report cases. They also retain guest slot/auth/deliberate-confirmation, guest save after account initialization, late viewing-result rejection, and component modal wrapping controls. Modal methods and geometry are stubbed in jsdom; this does not independently certify native-browser keyboard behavior.

Evidence: adjacent `FE003-client-final-probes-46b187e/run.sh` and `test-output.txt`. The tested source/test files are pinned by the commit above. There were no startup/collection failures in this run. The existing non-failing Vite notice about future native-config support was unchanged.

The previous 183-test baseline and prior 25+8 focused runs were not repeated as a new broad suite. No independent full 206-test run, lint, typecheck, production build, API generation, browser/E2E/axe, screen-reader/mobile overlap, PostgreSQL or backend execution occurred here.

## Carry-forward to final follow-up 04cab95

A read-only Git object comparison verified:

- Follow-up SHA: **`04cab95a905f37e5a64d265e8dad22a529103449`**.
- Follow-up tree: **`300d7ee84415076fe7edefe995d16c1a9bad89bb`**.
- Entire delta from 46b187e: exactly **two files**, 6 insertions / 1 deletion:
  - `frontend/web/e2e/engagement-boundaries.spec.ts` waits for the preceding document's authenticated UI before inserting the simulated persisted intent and navigating.
  - `docs/tasks/FE-003-execution.md` records the browser results and preserves the failed-run explanation.
- All product source, dependency and configuration files are identical. The inspected browser change retains the substantive assertions: authorized report dialog appears, free text is empty, safe intent is removed, and no report POST occurs. It corrects fixture-insertion timing without changing product behavior.

**This bounded product-code closure carries to 04cab95 by verified source equivalence.** The 62 runtime tests were executed at 46b187e; they are not misreported as a separate execution at 04cab95.

The builder reports real-API guest-save/search/logout stress **10/10** and restored-report browser flow **2/2** passing on this unchanged repaired product source. The builder preserves the earlier report-browser **1/2** setup failure and attributes it to injecting storage before the preceding document completed its initial session probe. These are attributed builder results and an inspected test-definition change, not browser execution by this reviewer.

Likewise, the documented full-unit history remains **205/206 initially**, an unchanged growth test exceeding its existing timeout during concurrent build, followed by **12/12 growth tests** passing unchanged. No blanket independent full-suite PASS is inferred from those builder results.

## Limits and disposition

CLIENT-1, CLIENT-4 and CLIENT-5 retain their closed disposition from the c3b68a5 review because their production paths are unchanged by this repair. The shared Modal/post-commit continuation assessment and its stated browser limitations remain inherited. The parent's BFF boundary equivalence and separate backend/fixture reviews are not expanded by this report.

No optional architecture work or canonical decision is required for these repairs. All original client findings are closed on the reviewed source, with the exact carry-forward above. Final composed CI, founder acceptance/merge, outstanding beta blockers, and any later dependency/product changes remain separately governed.

