# FE-003 independent client review — ec2bfa9

Review executed 2026-10-21; original report finalized 2026-10-23 after the session pause. Independent read-only Codex reviewer.

**Disposition: CHANGES REQUIRED.** Five established contract defects: **1 P1 HIGH, 3 P2 MEDIUM, 1 P3 LOW**. No P0 finding. The passing repository suite does not cover the failing cases below. This report is immutable evidence for the frozen original checkpoint; later repairs require a separately identified closure report.

## Identity, authority and scope

- Audited SHA: `ec2bfa9ed8857eccc9551feaa30daa889d6c282c`.
- Audited tree: `1e913787609d98871013a0ce154fe61aba147944`.
- Comparison base: `ee19b3affc9f33d560c7624ebc6b562276c56000`.
- Own pinned worktree: `C:/Users/ihorf/.codex/worktrees/fe003-client-independent-review/homies`.
- Initial and concluding managed Git checks: clean worktree, exact SHA/tree above. The initial unprivileged status check could not treat the managed directory as a worktree; the approved normal escalation succeeded. This was a tooling restriction, not a source defect or test result.
- No source edits, commits, pushes, shared-runtime mutations, backend/seed re-audit, database use, production work or deployment.
- Independent probes and reports reside only in the external evidence directory. Test copies were disposable container files, never edits to the pinned checkout.

Authority read: AGENTS.md; canonical 00; governance 05 sections 9–10; approved FE-003 contract including client flows, sections 9 and 11; FE-003-execution acceptance evidence map; approved DESIGN-001C repository handoff; relevant implementation-convergence dispositions. Current founder authorization supersedes historical implementation-NO labels. The review does not grant merge, beta, deployment or paid-provider authorization.

Scope: auth interruption and session/account transitions; saved listings/searches; conversations/reports; contact disclosure; viewing request/lifecycle/provider UI; authority-derived navigation; client privacy, analytics, totals, accessible responsive implementation and test quality. The separately accepted BFF review at `dbf06681a78c128c27bfcf3a2ae94f485dec6cb2` is not repeated. The parent verified the BFF/server/config boundary unchanged at this checkpoint. Seed/backend acceptance is inherited, not claimed as this review's execution.

## Contract findings

### CLIENT-1 — P1 HIGH: viewing private state and responses survive an authoritative account change

**Locations:** `frontend/web/src/engagement/viewings.tsx:14`, `:29`, `:34`; mounting site `frontend/web/src/engagement/detail.tsx:40`.

**Invariant:** FE-003 sections 3.7 and 3.8, authenticated private engagement, and the approved handoff privacy/auth boundaries. A requester's private note and request outcome belong to that account; an authoritative logout/account switch must revoke their display and prevent old asynchronous results from becoming the new account's state.

**Evidence:** Real EngagementProvider plus ViewingPicker probes entered a private note as A, then resolved an explicit session refresh to anonymous or B. The note remained rendered in both cases. A third probe started A's viewing POST, changed the authoritative session to B, then resolved A's response: B's dialog displayed “Oglądanie potwierdzone”. All three assertions failed for the observed elements, not collection/setup errors. The component stores note/confirm/result without an owner and directly accepts asynchronous success/reconciliation; the public-detail mounting site supplies no account boundary. The retained confirmation form can also submit the old note with the current cookie session.

**Expected:** Clear private note, confirmation, result and errors on authoritative account loss/change; discard pending results and uncertainty reconciliation from the previous identity. Preserve the safe anonymous slot-selection/auth-resume flow without exposing an old authenticated account's private fields.

**Suggested repair:** Bind the private picker state and in-flight work to an account/session generation, clear or remount on authoritative changes, and check ownership before applying every response or follow-up read/write. A safe public selection may be carried separately through guest authentication. Add both anonymous and A-to-B transitions, delayed success and delayed uncertainty reconciliation as regressions.

**CANONICAL DECISION REQUIRED: No.**

### CLIENT-2 — P2 MEDIUM: automatic save retry can mutate the next account

**Location:** `frontend/web/src/engagement/saved.tsx:49` (toggle retry; original write at line 46).

**Invariant:** FE-003 section 3.7 binds continuation to the established session and its loaded saved set; section 3.1 scopes saves to the authenticated user. An automatic retry of A's intent cannot become B's action.

**Evidence:** With the real provider and SaveButton, A started a save whose response remained pending. An explicit session refresh established B. Rejecting A's first transport request then caused a second automatic POST. The synthetic transport recorded owners **[A, B]**, while the assertion required only [A]. The account check before the first write and before updating the UI does not protect the retry. The positive control confirmed that same-account transport retry still succeeds.

**Expected:** Once the originating session/account is invalidated, no automatic follow-up write should execute under another account, and no old result should update that account's saved set. A deliberate new action by B is separate.

**Suggested repair:** Capture an account/session generation for the operation; recheck it immediately before retry/reconciliation and on completion. Do not rely solely on final UI suppression. Test A-to-B, A-to-anonymous, and logout/login transitions—including return to the same user id—so an invalidated operation is not silently revived. Preserve supported same-session idempotent retry and explicit authorized continuation after authentication.

**CANONICAL DECISION REQUIRED: No.**

### CLIENT-3 — P2 MEDIUM: expired message reporting does not invoke AuthInterrupt

**Location:** `frontend/web/src/engagement/conversations.tsx:132` (ReportDialog catch).

**Invariant:** FE-003 section 3.7 and **AC-A6**: a write returning 401 opens AuthInterrupt with the same intent; a report resumes as a dialog requiring deliberate submission. OD-7 permits unverified current participants to report without a verification wall.

**Evidence:** A real EngagementProvider/ReportDialog probe established a signed-in account and returned 401 from the report POST. It displayed the generic login-required text but no auth dialog/e-mail field. The catch handles 403/404 access loss only; `ensure` is called only when the pre-request session already has no user. A positive control confirmed a 201 report succeeds for a participant with neither contact verification flag.

**Expected:** Open authentication on report 401; keep private text only in memory where the same authorized account can safely resume, revalidate eligibility, reopen the report UI, and require the user's own send. Cancel/discard correctly and clear private state on an account switch. Persisted safe report intent must also have an actual consumer if restored.

**Suggested repair:** Add the forced report intent on 401, with safe suspended/resume handling and account/participant checks. Add expired-session, successful same-account resume, abandonment and different-account regressions. Never automatically submit the report after login.

**CANONICAL DECISION REQUIRED: No.**

### CLIENT-4 — P2 MEDIUM: a terminal conversation hides the new-message entry point

**Location:** `frontend/web/src/engagement/detail.tsx:19` (thread selection; CTA at line 30).

**Invariant:** FE-003 section 3.2 says “Napisz” opens an existing **ACTIVE** tenant thread; CLOSED/ARCHIVED threads remain read-only. A historical terminal thread does not itself establish a current generation's recontact restriction.

**Evidence:** Independent detail-component probes supplied a public listing and a sole tenant thread with ARCHIVED or CLOSED status. Both rendered only “Kontynuuj rozmowę” targeting the terminal thread; neither offered the new-message button. The predicate checks listing and side but not status. A legitimately republished listing may permit new engagement while its historical closed thread still exists, yet this UI keeps routing the requester to the read-only thread.

**Expected:** Use an existing ACTIVE thread for continuation. With no ACTIVE thread, offer the normal explicit start flow unless a current backend restriction forbids it; keep historical threads accessible from the inbox.

**Suggested repair:** Filter continuation by ACTIVE status, retain backend RECONTACT_BLOCKED as the authority for refusals, and test terminal-only and mixed terminal/active inboxes. No client inference of publication-generation authority is needed.

**CANONICAL DECISION REQUIRED: No.**

### CLIENT-5 — P3 LOW: other-cost prose lacks its required exclusion label

**Locations:** `frontend/web/src/engagement/cost-breakdown.tsx:25`; `frontend/web/src/i18n/pl.ts:171`.

**Invariant:** FE-003 section 3.4 and DESIGN-001C section 15: owner `other_costs` prose is verbatim and explicitly labelled **not included in totals**.

**Evidence:** The rendering probe received “Inne koszty (opis właściciela): Synthetic description”; the required exclusion wording was absent. Totals themselves remain authoritative—the non-additive fixture passes—so this is a bounded disclosure/copy defect, not arithmetic corruption.

**Expected / repair:** Include the approved “Opis właściciela — nie wliczone w sumy” meaning adjacent to the prose. Keep the text unparsed and totals unchanged; retain a small presentation regression.

**CANONICAL DECISION REQUIRED: No.**

## Tests actually executed

Environment: disposable Docker `node:24`, observed **Node v24.21.0**, **Vitest 5.0.3**, existing jsdom configuration; **network disabled**. Pinned source and the existing Linux `homies-fe-nm` dependency volume were mounted read-only and copied into private ephemeral storage. Containers were removed after execution.

1. Full unchanged repository Vitest suite: **183/183 PASS**, 19 files, reported duration **38.75 s**, exit 0. This includes the existing auth/session, saved, conversation/report, contact, viewing-model, non-additive pricing, analytics, OpenAPI refusal/limit parity and common error tests. Server/BFF tests included by the suite also passed; this is not a separate new boundary audit.
2. Independent `account-boundary.test.tsx`: **5 tests executed, 5 expected-invariant assertions FAILED**, duration **6.59 s**, exit 1. Three failures support CLIENT-1; one each supports CLIENT-2 and CLIENT-3.
3. Independent `controls-and-presentation.test.tsx`: **6 executed, 3 PASS / 3 FAIL**, duration **5.42 s**, exit 1. Passing controls: ordinary current-account viewing, same-account idempotent save retry, unverified participant report success. Two failures support CLIENT-4; one supports CLIENT-5.

Thus **11 independent probes executed: 3 passed, 8 exposed contract failures**. Failures were runtime assertions showing retained DOM/state or an extra write, not test collection or startup errors. The non-failing Vite notice concerns future native-config support for the existing `__dirname` usage. No failed dependency startup occurred in these client runs. The previous BFF review's separate startup history is not this review's execution.

Evidence directory: `FE003-client-probes-ec2bfa9/` adjacent to this report:
- `account-boundary.test.tsx`, `run.sh`, `test-output.txt`.
- `controls-and-presentation.test.tsx`, `run-controls.sh`, `controls-output.txt`.

The probes use real pinned client/provider/API error code with synthetic fetch responses. Native dialog methods are stubbed in jsdom. They prove the stated client transitions, not cookie transport, real backend authority or browser focus behavior.

## Other assessed areas and limits

- Source and passing tests support safe intent field reconstruction/30-minute expiry, no stored free-text drafts, registration field minimization, committed auth continuation, transient session failure versus authoritative identity change, and stale probe ordering. These do not cancel the account-boundary failures above.
- Existing saved tests exercise confirmed writes, uncertainty reconciliation, tombstones, INVALID-query suppression, safe duplicate references and expected-version changes. CLIENT-2 exposes the missing automatic retry transition.
- Existing conversation tests exercise immutable body/UUID retry for transient errors, final refusals, CLOSED/ARCHIVED read-only, redaction/system text, report eligibility and provider-data removal on denied reads. CLIENT-3/4 are uncovered branches.
- Contact source keys the reveal surface by account/listing, limits the number to the reveal element, and invalidates disclosure on blur/visibility changes; three executed tests cover refusal clearing and delayed responses after lost focus. Full real verification/reveal/navigation flows are **NOT VERIFIED by this reviewer**.
- Viewing model tests cover exact returned instants, response timezone/DST grouping, historical UTC fallback, final-state actions and passed REQUESTED. Source uses response statuses and explicit uncertainty reconciliation. Client request ownership fails as documented.
- Provider access/navigation is derived from authority-backed scoped endpoints/my_side, not role. Tenant/private projections and denial handling have exercised component coverage. Real backend chain enforcement was inherited, not re-audited.
- API totals and currency are rendered without summing components; consent-gated closed analytics payloads and route-template minimization have executed tests. No deliberate exact-address/identity enrichment was found in the changed client paths. CLIENT-5 remains a required disclosure omission.
- Responsive source uses semantic tokens, the 1024px rail/dock split and native modal presentation. **Browser/E2E, axe, keyboard trap/focus restoration, screen-reader behavior, actual mobile keyboard/dock overlap and visual layout are NOT VERIFIED by this reviewer.** The builder separately reported a real-browser Tab/Shift+Tab boundary escape in the shared Modal and is preparing a repair. That is a required focused closure target; it is not claimed here as an independently executed finding.
- No independent typecheck, lint, production build, API regeneration, pytest, PostgreSQL/PostGIS, seeded HTTP/browser flow or deployment was run. Builder-reported results remain attributed builder evidence.

## Optional improvements and closure

No optional architecture program is proposed. Regression coverage for the concrete failures is part of their repair, not a substitute for fixing them. This report does not assert complete FE-003 acceptance or external-beta readiness.

Closure must identify a new exact SHA/tree, inspect the bounded production/test delta, rerun the causal probes against that SHA, and confirm that same-account uncertain operations and guest slot/auth continuation still work. Shared Modal focus changes require actual browser keyboard evidence as well as code inspection. Preserve this original report and its failing logs; append a new closure report rather than rewriting historical findings. The remaining browser acceptance matrix and existing beta blockers remain open until separately evidenced.

