# FE-003 focused independent client repair review — c3b68a5

Finalized 2026-10-24 after resuming the existing review. **Disposition: CHANGES REQUIRED — CLIENT-2 and CLIENT-3 remain partially open.** CLIENT-1, CLIENT-4 and CLIENT-5 are closed for this checkpoint. No new broad audit was performed.

## Exact identity and scope

- SHA: `c3b68a5896f9fb8f91a169a4ff9e19836fb82df6`.
- Tree: `0e20efde949d11cfb776fb1560d8edaf313ba58f`.
- Compared against original reviewed SHA `ec2bfa9ed8857eccc9551feaa30daa889d6c282c`.
- Own read-only worktree: `C:/Users/ihorf/.codex/worktrees/fe003-client-repair-review/homies`; clean at identity checks.
- Original immutable report: `FE003-client-review-ec2bfa9.md`, SHA256 `ab9c8eaf3ef62391ff487fdc0e9e1e80268643157a1d5320d6368c6b26f63bbe`. Its findings and failed evidence are preserved.
- Delta: 11 files, 192 insertions / 11 deletions. Reviewed production changes in viewing/session/saved/report/detail/modal/copy, retained independent probes, and added browser regression definitions.
- Authority and original source assessment are reused. The parent verified the BFF/server/proxy/config/dependency boundary unchanged; no repeat BFF/backend/seed review was performed. No source writes, commits, push, deployment, database, shared runtime or production mutation.

## Closure results

| Original item | Disposition at this SHA | Evidence |
|---|---|---|
| CLIENT-1 P1 viewing account privacy | **Closed** | Picker remount generation resets private state when leaving an authenticated identity; active-instance checks reject delayed success/failure/reconciliation. Original anonymous/B note and late-success probes pass. Additional late failure and reconciliation probes pass. Anonymous-to-auth preserves the selected public instant and requires explicit submission. |
| CLIENT-2 P2 automatic save retry ownership | **Partially repaired; remains open** | Original A-to-B retry probe passes. Guard compares user id only; an A-to-anonymous-to-A transition revives the old operation. Busy/lock state is also unscoped. See remaining finding below. |
| CLIENT-3 P2 report authentication/resume | **Partially repaired; remains open** | 401 now opens AuthInterrupt. Same-account login retains memory-only text and requires another explicit press. Restored safe report intent still has no consumer and never opens the dialog. See remaining finding below. |
| CLIENT-4 P2 terminal thread entry point | **Closed** | Detail continuation now selects ACTIVE tenant threads only. Both retained terminal-only fixtures pass and offer the start action. |
| CLIENT-5 P3 other-cost exclusion label | **Closed** | Polish label explicitly says “nie wliczone w sumy”; retained rendering probe passes. Totals are unchanged. |

### Remaining CLIENT-2 — P2 MEDIUM: operation ownership is not invalidated across a same-user session cycle

**Location:** `frontend/web/src/engagement/saved.tsx:38` onward, particularly the id-only retry guard at line 48; in-flight/busy setup at lines 17–18 and final cleanup at line 59.

**Invariant:** Original CLIENT-2, FE-003 section 3.7 account-bound continuation and section 3.1 per-user saves. A previously invalidated operation must not silently resume merely because the same user id is observed later. The original repair recommendation explicitly required logout/login transitions, including return to the same id.

**Executed evidence:** A starts a save whose response is deferred; authoritative refresh returns anonymous; another authoritative refresh returns A; the original request then rejects with a transport error. The implementation issues a second POST. The independent assertion expected one POST and observed **two**. This is a runtime causal failure, not a startup issue. The normal same-session idempotent retry control continues to pass.

**Related source evidence:** `inFlight` and `busy` remain keyed only by listing id and are neither scoped nor invalidated on account changes. Consequently an old outstanding operation disables the new identity's same-listing SaveButton until the old operation settles. This related lock-lifetime behavior was source-inspected; it was not separately reproduced in a browser in this review. Any repair must avoid an old operation's finally block clearing a newer generation's lock.

**Expected / suggested repair:** Use a monotonic ownership generation that advances when authoritative identity is lost or changes. Bind attempts, pending locks, retries, re-reads and completion to that generation. No automatic retry survives an invalidated generation, even if the same account logs back in. Scope busy state so B can act independently of an unresolved A operation. Preserve ordinary same-session retry and explicitly authorized authentication continuation.

**CANONICAL DECISION REQUIRED: No.**

### Remaining CLIENT-3 — P2 MEDIUM: restored report intent is never consumed by the authorized thread

**Location:** `frontend/web/src/engagement/conversations.tsx:182` onward (Thread's report state/rendering); the newly changed 401 catch at line 132 fixes only the live-dialog path.

**Invariant:** FE-003 section 3.7, **AC-A1**, and the original CLIENT-3 repair scope: the safe report intent is mirrored to sessionStorage and, when valid authentication resumes it, the report dialog reopens without automatic submission. Private report text is not persisted.

**Executed evidence:** The independent probe placed a valid, unexpired `report` intent with a message id in sessionStorage, established account A, and rendered its authorized thread with an eligible other-participant USER message. The thread and message loaded; no report POST occurred; **no report dialog opened**. EngagementProvider restores `resumed`, but Workspace/Thread never consumes that report intent. This also applies to reloading during the report authentication interruption.

**Expected / suggested repair:** Consume the restored report intent only after the current authorized thread/message data establishes report eligibility; reopen the dialog with empty private text and require deliberate send. Clear ineligible, unavailable or abandoned intents without leaking prior private state or inventing an authorized target. Retain passing same-account live 401 behavior and test expired intent, removed/own/SYSTEM message, denied thread and account-change cases as appropriate to the bounded consumer.

**CANONICAL DECISION REQUIRED: No.**

## Changed shared behavior

**Post-commit authentication continuation:** `session.tsx` now schedules completion from a passive effect, rather than scheduling a frame directly within finish. The retained 14 session tests pass. The independent actual guest-save probe deliberately holds the newly authenticated account's initial saved-set read: no write happens before it resolves; exactly one save is then submitted and displayed. The guest-viewing probe preserves the exact chosen instant through login and submits nothing until confirmation. These validate the consequential ordering and intent behavior, not just the presence of a frame callback.

**Modal Tab wrap:** `ui.tsx` explicitly wraps Tab from the last visible eligible element to the first and Shift+Tab in the reverse direction. An independent component probe passes both boundaries and opener restoration. jsdom has no layout/native focus trap: this probe stubs dialog methods and element rectangles, so it is **not a browser keyboard certification**. The added browser test definition exercises auth email focus, both Tab boundaries, Escape, opener restoration and abandoned saved intent. The builder subsequently reported a full 96/96 browser run at this SHA; this reviewer did not execute or independently inspect the browser runtime/output for that claim. The parent owns that evidence gate.

## Tests actually executed

Network-disabled disposable Docker container, observed **Node v24.21.0**, **Vitest 5.0.3**. Exact source and shared Linux dependency volume mounted read-only and copied into private ephemeral files. Source checkout remained untouched.

- Retained `account-boundary.test.tsx`: **5/5 PASS**.
- Retained `controls-and-presentation.test.tsx`: **6/6 PASS**.
- Existing `session.test.tsx`: **14/14 PASS**.
- Focused total: **25/25 PASS**, reported duration **27.88 s**, exit 0.
- New independent `closure.test.tsx`: **8 executed, 6 PASS / 2 FAIL**, duration **8.63 s**, exit 1.

Independent passing probes cover guest viewing/auth/exact instant/deliberate submit, guest save after committed account initialization, live report 401/same-account deliberate retry, rejection of late viewing failures before a B-owned private read, rejection of late reconciliation results, and explicit modal wrapping/opener restoration. The two failures are the remaining findings above.

Evidence: adjacent `FE003-client-repair-probes-c3b68a5/closure.test.tsx`, `run.sh`, `test-output.txt`. The output records both commands, their results and exit markers. Original baseline 183 tests were **not rerun**. No test startup/collection failure occurred in this focused run; the existing future-Vite-config notice was non-failing.

No independent full 194-test run, typecheck, lint, build, API generation, E2E/axe, screen-reader/mobile overlap, database test or backend review was executed here. Builder results are not relabelled as reviewer execution.

## Next closure boundary

Only the remaining saved operation generation/lock behavior and restored report intent consumer, their causal tests, and any directly affected shared behavior need another exact-SHA closure. Preserve this report and failed output. No canonical decision or broader architectural change is needed. This checkpoint is not a complete client PASS, beta authorization or merge approval.

