# BP-10 — independent final Codex audit

Date: 2026-10-11. Role: independent read-only reviewer; this session did not implement BP-10.

**Verdict: PASS_WITH_NONBLOCKING_NOTES.** P0 CRITICAL: 0; P1 HIGH: 0; P2 MEDIUM: 0; P3 LOW: 4; NOTE: 5. The tested idempotency and transaction requirements pass. The literal no-echo claim, inherited input/access races and permanent mutation-test cleanup need the qualifications below. No blocking regression was established.

**READY FOR FOUNDER/GPT MERGE DECISION** on this immutable candidate, with the nonblocking findings explicitly presented for disposition. This is not acceptance or merge permission. Before acceptance, governance 05 §14 requires this report/receipt and binding scope decisions to become repository-readable. Draft receipt is provided outside the frozen branch.

The SHA256 of this exact file is in `BP-10-PHASE-CODEX-AUDIT.sha256` and in the accompanying draft receipt; it is deliberately not embedded in the file whose bytes it hashes.

## 1. Identity and authorized scope

| Item | Independently resolved value |
|---|---|
| Repository | ihorfroliak/homies |
| Candidate branch | claude/BP-10-idempotent-message-send |
| Candidate SHA | c385136c93826879b41509f1e30533ef46eee64c |
| Candidate tree | 15c26d7aedd525e2b5ea4beef8383e313a1473fd |
| Baseline SHA | be150da11b9838409fcf8ee2d8ca4bd8b0311307 |
| Candidate parent | 234851e6c9c755700f4b6f7c9770c4d438332c55 |
| Alembic head / parent | 11d778ab87a3 / a3c5e7f9b1d4; actual graph has one head |
| Exact-head CI | [run 38047352161](https://github.com/ihorfroliak/homies/actions/runs/38047352161), six successful jobs |
| Reviewed worktree | C:/Users/ihorf/.codex/worktrees/bp10-final-audit/homies |
| Evidence root | C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/BP10-c385136-audit |

Git objects and GitHub commit/run metadata agree. Baseline is an ancestor, not the direct parent: there are three candidate commits from baseline. The shared checkout was and remains at 5cad442f07264ab25b3024c96fc691ad9c7a75fa; it was never substituted as the target. Both checkouts have empty porcelain status at completion.

Read authority: AGENTS.md, canon 00-AUTHORITY, 05 governance (including §14), applicable 04 §73 / 04a §6, D-108 / FD-1…FD-9, BP-10 contract, FE-003 gate and convergence/port dispositions. D-108 approves the message-local equivalent unique key; this audit does not demand an unapproved platform.idempotency_keys implementation.

The 35-file baseline-to-candidate manifest is `changed-files.txt` and Appendix A. Review addressed runtime diffs, test oracles, migration/release semantics, changed documents and generated contract consistency. The full Phase-B scope includes the original Phase-A proposal plus these **six extensions explicitly authorized in the founder's current audit prompt**:

- backend/app/core/business_metrics.py
- backend/tests/test_obs02_03_metrics.py
- backend/tests/test_moderation_core.py
- backend/tests/test_schema_compat.py
- backend/tests/test_release_pg.py
- docs/production/RELEASE-AND-MIGRATION.md

All changed paths are covered. The proposal's optional task002 mutant-anchor / TRACEABILITY changes were not necessary and are not in this diff. No frontend runtime, access/authority helper, core error/deadline machinery, deployment workflow, dormant module or canon 00–05 changes were found. A missing older transcript quote is not an unauthorized-change finding. Durability is addressed by CX-N5.

No source edits, commits, pushes, PRs, merge, deployment, production connection or paid-provider activation occurred. Probes and mutation copies stayed outside the reviewed worktree. Only the audit's local synthetic databases were recreated.

## 2. HSEP-1 independence and evidence chronology

Before runtime tracing or separate conclusions, a hypothesis/evidence plan was written:
`00-HYPOTHESIS-EVIDENCE-PLAN.md`, SHA256
`192016e470316bcf349d8a5b46804b35e4ef17b5e1efffb4414d5f655ff85ac0`.

Before opening builder, combined, C1 or C2 reports, findings were frozen:
`01-PRELIMINARY-FINDINGS-FROZEN.md`, SHA256
`19b9cb03f8cfb01d151e4cb07e50c43e193a3913aa3f9e714c4e1181adf35892`.
Both hashes were rechecked unchanged at completion.

Blindness limitation: the user's prompt already supplied C1/C2 summaries, and reading the required contract incidentally exposed builder test counts. This was disclosed in the plan. Separate conclusions were not used to construct the initial probes. GitHub executable logs are evidence, not another reviewer's conclusion.

After freezing, the accessible secondary reports were read and their hashes verified. Additional HTTP T22, PostgreSQL new-thread rollback, stranger-key and Unicode-cause probes were designed/executed afterward; they are corroboration, not retrospectively blinded evidence. The preliminary report was not edited. Its statement that both NUL and surrogate “pass validation” is corrected here: only NUL does; surrogate fails validation and then breaks error-response encoding.

## 3. Environment and actually executed checks

Source mounts were read-only; test runtime had read-only root filesystem and writable temporary/evidence paths. Disposable container `bp10-codex-c385136` was bound to 127.0.0.1:55510, label `homies.audit=BP10-CODEX-c385136`. Databases: homies_bp10_test, homies_bp10_probes, homies_bp10_mutants. All data was synthetic.

| Component | Actual local version |
|---|---|
| Python | 3.12.15 |
| OS | Linux 6.6.87.2-microsoft-standard-WSL2, glibc 2.41 |
| PostgreSQL / PostGIS | 16.4 / 3.4.3 |
| pg_dump / pg_restore | 16.15, Debian 16.15-1.pgdg13+2 |
| pytest / ruff / mypy | 9.1.1 / 0.15.22 / 2.3.0 |
| Alembic / SQLAlchemy / psycopg | 1.20.0 / 2.1.1 / 3.3.6 |
| FastAPI / Pydantic / HTTPX | 0.141.1 / 2.13.5 / 0.28.1 |
| Host Git | 2.54.0.windows.1 |

The cached Python tool image was bp10c-test:c385136, image ID sha256:86026a4e11a8589ddbd331ff5ddbf8491bebe398c38b76c812ebf5cc981cb23a. It supplied tools, not reviewed source; the exact worktree was mounted. 70/70 pinned dependencies match candidate constraints, zero mismatches. PG image digest sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5 matches CI.

A 35-second paired wall/monotonic sample showed no backward step; maximum observed difference was ~6.39ms. This does not certify permanent Docker clock stability.

| Run | Actual result / retained evidence |
|---|---|
| Candidate BP-10 unit/PG + OpenAPI + release manifest + schema compatibility + migration tests | Initial 157 passed, 5 failed because the first runner omitted /docs mount. targeted.log/xml retained. |
| Corrected OpenAPI rerun | 6 passed, openapi.log/xml. The five missing-file failures are resolved; one passing test overlaps the initial run. |
| Ruff app/tests/alembic/scripts | Clean, ruff.log |
| Mypy app | Clean, 126 source files, mypy.log |
| Metrics + moderation head pin + release PG | 42 passed, metrics_release.log/xml |
| Initial independent probes | 11 passed, 1 failed: the strict 422 no-echo hypothesis was false. probes.log/xml retained as finding evidence. |
| Independent observations | 6 passed, observations.log/xml |
| Own semantic lock mutant | Green baseline 4 passed; lock removed 4 failed on actual 409 false refusals. semantic-*.log/xml |
| Post-freeze HTTP T22 + migration-lock deadline + PG new-thread loser | 10 passed, final-probes.log/xml |
| Post-freeze stranger-key / Unicode-cause clarification | Final 2 passed, clarifications.log/xml. Initial 1 passed/1 failed was a probe expectation error: request middleware catches the encoding exception, so TestClient does not raise it. clarifications-initial.* retained. |
| Selected original mutation harness | Nine individually green baselines, nine reported kills, with qualifications in §6; all 316 copied files SHA-restored |
| Actual Alembic graph | One head, 11d778ab87a3 |

No aggregate inflated total: reruns overlap; expected mutation failures and falsified audit hypotheses are not passing product tests.

Independent GitHub retrieval verified:
- Backend job 114199445661 checked out the exact candidate; hosted Ubuntu 24.04.5, Python 3.12.15, PG16.4/PostGIS3.4.3.
- Full backend suite: **1964 passed, 1 skipped, 164 warnings**. The skipped test is live Stripe. These are CI results, not a local full-suite rerun.
- DR assertion: **10 passed, 0 skipped, 0 failed**; client tools 16.15. Local audit did not replay the restore drill.
- Web job 114199445480: `npm run check:api` explicitly says schema.d.ts matches docs/api/openapi.json; 83 unit tests and 44 browser cases passed.
- Contracts job 114199445596: OpenAPI lint zero errors / 49 warnings.
- All six job conclusions are success. No run-level downloadable artifacts were returned; preserved full job logs and metadata are the evidence.

Saved GitHub files: github-commit.json, github-run.json, github-jobs.json, github-backend-job.log, github-web-job.log, github-contracts-job.log, github-artifacts.json.

## 4. Claims to proof

| Accepted claim | Source trace and falsification evidence | Assessment |
|---|---|---|
| At most one message per sender/key | Nullable varchar(36) + partial UNIQUE; both routes use canonical UUID4 and sender scope; unit/PG backstop tests, raw-writer loser and T22 final counts | Supported |
| Both routes require UUIDv4; same namespace | MessageIn UUID4, no nullable write path; route tests, positive/negative signed keys, cross-route cases | Supported; OpenAPI format uuid uses description for v4 rather than a pattern |
| First execution/replay 201; mismatch 409 | _replay_start/_replay_append compare stored body and binding; same/different route tests, actual HTTP T22 | Supported |
| A key is not an access capability | Append _load precedes advisory/key lookup; stranger's victim/unknown keys both identical404, no message/conversation/audit changes; revoked-provider subsequent404 | Supported at initial access check; mid-wait temporal debt CX-02 |
| Replay writes nothing, current redaction | MessageOut applies current moderation projection and omits key; permanent redaction/no-write tests; own post-revoke replay snapshot unchanged | Supported; metrics may increment, not a domain write |
| No false refusal when closure overtakes a delivered send | Actual three-party original→queued moderator→retry ordering, PID-specific pg_blocking_pids proof, four route combinations with/without advisory | Supported causally |
| Transaction-scoped lock and fresh lookup | two CAST integer parameters, domain-separated signed SHA256 prefix, top-level guard, separate populated READ COMMITTED _keyed; T27/T28 real PG | Supported |
| Failed new-thread write rolls back everything | Full rollback outside IntegrityError handler; synthetic raw winner bypasses advisory and forces PG unique loser after new conversation/participants/audit creation; 409 with zero orphan rows | Supported |
| COMMIT outcome unknown is retry-safe for same key | Permanent T10/T12 use actual proxy commit-window alternatives; own injected HTTP503 verifies handler wording/header; subsequent same-key resolution tests | Supported within those scenarios; wording CX-N1 |
| Error privacy | Sanitized SQLSTATE/constraint only, no original exception chaining; hide_parameters for application PG engines; B18/B19 semantic kills, key omitted from participant schemas | Supported for intended successful/caught-integrity paths; 422/server logs exceptions CX-01/CX-N2 |
| Migration/release safety | Populated upgrade/roundtrip, real DDL timeout rollback, lock-mode proof, API2s deadline, actual old manifest lineage rejection, CI restore10 | Supported under EXPAND/BLOCKED and BB-11; no live rollout/load certification |

Implementation ordering: _serialise_send is acquired before write-row locks and refusals, never inside a savepoint. Its two-int advisory namespace is 0x42503130 plus the signed first four bytes of SHA256(domain + sender + NUL + canonical key). Hash collisions serialize unrelated sends but cannot merge database identities. The distinct post-wait lookup is critical: the original commit becomes visible under READ COMMITTED. Start then uses listing SHARE, sender NO KEY UPDATE, conversation UPDATE and the existing nested insertion recovery; append locks conversation after replay lookup. Original authority/access helpers are unchanged.

## 5. Causal concurrency, provider revocation and migration

**T22:** Own pre-freeze probes exercised original start/append × retry start/append × advisory enabled/removed (eight cases), including original start continuing an existing thread. Exact waiter/blocker PIDs were observed, not inferred from sleeps or database-wide blocked counts. With lock: four original-message replays. Without lock, unique index retained: four actual409 false refusals after the queued moderator closure. One keyed message and no new deadlocks in each case. An additional forced-expect-replay semantic mutation produced four actual assertion failures after all threads were joined.

Post-freeze HTTP probes repeated all eight route/lock combinations with actual application-session lock_timeout=2s and returned201/409 as predicted. Permanent T4 covers same-key new-thread races; the separate PG bypass-writer probe covers full new-thread rollback. The permanent T22's original route remains append only; this coverage limitation is real even though audit probes close the current-candidate uncertainty.

**Provider authority timing:** The candidate can pass _load, wait on the new advisory lock, have its sole proof revoked by a raw synthetic transaction, and still commit that in-flight provider message. Candidate conversation-row wait and verbatim baseline send-function control reproduce the same stale-access write; next request returns404. The baseline function was extracted from the exact baseline and run with unchanged helpers plus a nullable-key _post adapter, not a complete old-build boot certification. This establishes inherited row-wait behavior and a newly added advisory waiting opportunity. It does **not** prove equal exposure frequency or absence of amplification. A raw holder / rolled-back original can leave a fresh-send path after the new wait. Own replay variant returns only the provider's prior message, with zero domain writes after revoke.

FD-6/contract explicitly checks access before the advisory wait; this is pre-existing temporal authorization debt with another bounded waiting context, not an established new blocking breach of transaction-atomic authorization. No strict commit-time messaging authority guarantee was invented from publication-only D47. Finding CX-02 preserves this limitation.

**Migration:** A real populated parent database with 10001 synthetic legacy rows preserved its fingerprint and all NULL keys after upgrade. A held AccessShare lock and an audit-only 350ms DDL budget caused SQLSTATE55P03; migration stayed at the parent with no partial column. Pausing real Alembic between column addition and index creation proved AccessExclusiveLock remains held; an identified concurrent reader blocked. A separate same-lock-mode API probe hit default2s timeout in ~2.03s, returned503 + Retry-After5, stored no key, and succeeded201 on same-key retry after release. This combines real migration lock evidence and a controlled API lock simulation; it is not a production runner/load test.

Dev-only downgrade/upgrade preserved message rows (including a subsequent old-style NULL-key insert). Physical old SQL works, but the exact previous manifest/graph against the actual new lineage returns TOO_NEW. EXPAND therefore does not certify old-instance admission. Rollback BLOCKED and the all-serving-instances BB-11 gate remain mandatory. No inference from C1's one-million-row timing to production is accepted.

## 6. Mutation quality

Selected original harness IDs: B01, B04, B05, B07, B08, B15, B18, B19, B22. Each baseline passed; nine mutants were reported killed. The mutation copy alone was edited; restoration checked all 316 files byte-for-byte.

- B15 is a domain-state replay-write kill; B18/B19 are privacy-output kills; B22 fails the concurrent replay oracle.
- B07 observes lock ownership/savepoint scope on actual PG. T27 also passed unmutated.
- B08 fails the signed known-answer/range unit test before its PG test because the runner uses -x; positive and negative actual bindings passed unmutated T28.
- B01 stops at a waiting/backstop mechanism assertion before the intended final23505 assertion.
- B04/B05 initially detect missing wait, then cleanup closes the paused original Session before its worker finishes; final failure is IllegalStateChangeError. These are not clean final-result semantic kills.
- B09 was inspected, not selected for replay; literal SQL-call inventory is structural evidence.

Consequently, **“28/28 semantic mutants killed” is not certified**. Builder's harness count is secondary evidence, not a substitute for the quality distinction. Own four-case semantic no-lock mutant and eight HTTP controls independently establish the advisory mechanism's current behavioral necessity. Permanent regression debt remains CX-04.

Files: mutation-results.json, mutation-test-01…18.log, mutation-original-hashes.json, mutation-restoration.json; semantic_mutation_run.py and semantic-*.log/xml.

## 7. Findings and dispositions

All source references below are relative to the exact worktree in §1. These are nonblocking for BP-10 acceptance review; “accepted debt” is a proposed disposition requiring founder adjudication, not silently granted by the auditor.

| ID | Severity / classification | Location | Accepted rule, observation, impact, expected behavior, smallest correction |
|---|---|---|---|
| CX-01 | P3 LOW; inherited handler + new-field contract coverage gap; high confidence | backend/app/composition.py:159; backend/app/modules/engagement/router.py:124; docs/tasks/BP-10-idempotent-message-send.md:62 / INV-12 | Absolute “key never echoed” is false for422: client_message_id=[UUID4] echoes that UUID in detail[].input to the submitting account. No stored/other-user data or capability exposure observed. Expect detail[] without sensitive input under literal contract. Omit rejected key/body input on send errors; alternatively obtain an explicit exception to the approved no-echo wording. Canonical decision: NO for conforming sanitization; founder/contract decision YES if weakening the promise. Builder already lists this residual; that acknowledgment is not approval. |
| CX-02 | P3 LOW; pre-existing access race + new waiting opportunity; high observed / limited amplification confidence | backend/app/modules/engagement/router.py:224,635–648; unchanged engagement/access.py | FD-6 current access is assessed before wait. Revoked-during-wait fresh send still commits; own-message replay has no writes. Baseline row-wait control reproduces the write. Expected temporal semantics need precision: a post-wait current-side check narrows stale access; strict commit-time guarantees require synchronized proof rows. Small correction: recheck side after wait before replay/write. Canonical decision: no for preserving existing chains; YES if extending publication-only locked-proof guarantees to messaging. No claim of quantified baseline equivalence. |
| CX-03 | P3 LOW; pre-existing malformed-input defect; high confidence | backend/app/modules/engagement/router.py:125–133; backend/app/composition.py:159–162; backend/app/core/request_id.py:69 | NUL passes body validation then PG rejects it; unpaired surrogate gives Pydantic string_unicode but echo in422 cannot UTF-8 encode. Both actualHTTP500, zero keyed rows. Generic exception logging can contain the rejected malformed input. Expected422 without encoding failure and ordinary Unicode preserved. Reject NUL early and make error rendering Unicode-safe without echoing private values. Canonical decision: NO. The frozen preliminary's surrogate-validation wording is corrected, not hidden. |
| CX-04 | P3 LOW; permanent regression/mutation-test gap; high confidence | backend/tests/test_bp10_message_idempotency_pg.py:480–545, especially530–532; backend/scripts/mutation/bp10_mutants.py:85,93 | HSEP/test-quality requirement: a kill should falsify an invariant. B04/B05 cleanup can mask the semantic result with Session IllegalStateChangeError; original route is append only. Expected release/join all worker threads before Session close and assertions on final outcome in the mutated path. Small correction: safe finally cleanup plus original-start parametrization and final replay oracle. Canonical decision: NO. Audit probes support current behavior; permanent test quality remains debt. |
| CX-N1 | NOTE; inherited generic wording; high confidence | backend/app/core/db_failures.py:69–71; send OpenAPI503 | Actual commit_unknown says “Check before repeating it”; keyed retry documentation is more specific. Own injected HTTP503 verifies Retry-After5; actual network alternatives tested by T10/T12. Expected client guidance eventually names same-key retry. Optional route-specific wording; no dedup failure or canonical decision. |
| CX-N2 | NOTE; explicit application/server logging boundary; high confidence for key DETAIL | backend/app/core/db.py:121; engagement/router.py:375–394; server settings in disposable-pg-settings.txt | hide_parameters hides bound rendering, not raw psycopg/PG unique DETAIL containing sender/key. Own driver exception and disposable server log confirm this despite log_parameter_max_length_on_error=0. Routes sanitize caught integrity errors. C1's synthetic added CHECK/body-log result is secondary, not reproduced here. Expect no blanket all-logs privacy certification; production logging policy must be separately verified before launch. No production configuration reviewed; canonical decision only if changing retention policy. |
| CX-N3 | NOTE; release documentation precision; high confidence | backend/alembic/versions/11d778ab87a3_bp10_message_client_id.py:23; backend/app/release.json | “Previous release still runs” means physical SQL compatibility; actual old startup compatibility policy is TOO_NEW. Expected wording distinguishes the two and preserves EXPAND/BLOCKED/BB-11. Small documentation clarification, no policy change or canonical decision. |
| CX-N4 | NOTE; mutation evidence limits; high confidence | backend/scripts/mutation/bp10_mutants.py:153; tests/test_bp10_message_idempotency.py signed/cast tests | B09 structural oracle and B08 early unit failure do not establish all-mutant PG behavioral kills. Expected evidence labels mechanism/unit/semantic outcomes separately. Small harness/report clarification; no canonical decision. |
| CX-N5 | NOTE; repository durability prerequisite; high confidence | docs/canonical/05-DEVELOPMENT-GOVERNANCE-v1.md:148–179; BP-10 external reports/scope evidence | §14 requires repository-readable audit/decision semantics before acceptance. Reports are currently external; draft receipt is provided, not committed. Founder/builder must archive report or complete binding handoff with identities/hashes, six scope authorizations, findings/dispositions and status reconciliation before merge acceptance. No new permission needed for this audit; founder acceptance is not inferred. Canonical decision: NO. |

No new P0/P1/P2, no mandatory evidence blocked by a safeguard or missing runtime. Optional improvements above are separate from verified mandatory behavior; no broad repair/re-audit cycle is recommended.

## 8. Secondary report reconciliation

Verified actual SHA256 values:

| Artifact | SHA256 |
|---|---|
| Builder Phase B | 181b18ffea3128895671e78b839376728db10d82bd454c2265d47875846aeccd |
| Combined Phase C handoff | 3e44ca7fff73904253a179a4f97376c0704502846cefee6215d6f498bd99b3e2 |
| C1 preliminary | 07a0e7c50a322478443be0e84a2becb5a4d51794237826b72a084f49647fbd7e |
| C1 final | 71f19c9eb7dfc66e7ac76d4bfc87f20a2718bb319548fb1da50836405da8cdf4 |
| C2 preliminary | 0b0133230168b0b57a8b5f4b8676f9b464d6e04f98ed06cd6bafa293ce129feb |
| C2 final | f24909828cbde82fff86f095945aebd1c5a49eba3463871ad8f9176f78ff4528 |

Paths/provenance in secondary-report-hashes.json: builder under C:/Users/ihorf/Projects; C1/C2 under C:/Users/ihorf/Projects/homies-audit-evidence/BP-10-PHASE-C. Their declared separate Claude contexts are secondary provenance, not independently verified model histories. Neither is this Codex session.

**Builder:** Exact candidate/full-suite claim is corroborated by fetched CI, not accepted from its prose. Nine selected kills corroborate parts of the claimed28 but expose the cleanup/structural distinction. Reported422/input/server-detail residuals are real boundaries.

**C1:** Own T22 matrix confirms its causal with-lock/without-lock observation without adding its15/24 runs to our counts. Post-wait provider replay and PG new-thread lost-race gaps are independently tested here. Its lock-duration/old-build observations agree with our semantic evidence; timing is not a production bound. C1 synthetic CHECK body log remains secondary only.

**C2:** Own controls corroborate its pre-existing malformed-input and row-wait access findings. “Not materially amplified” is not promoted to proof: the new advisory opportunity is identified, quantitative impact remains unmeasured. Its allowlist missing-quote question is resolved by the current explicit founder authorization, with §14 durability still pending. Its exact-head full-suite / frontend-check gaps are closed by direct CI logs. Actual503 wording and stranger victim-key denial were independently exercised.

Preliminary P3/NOTE classifications are retained; only the Unicode causal explanation was corrected with a direct validator/error-handler probe. Agreement between reports did not replace own evidence.

## 9. Residual limits, lifecycle and delivery

Not verified as production facts: continuous long-term host clock stability, large/live-table migration duration, live rollout/mixed-instance admission, production logging retention, quantitative authority-race amplification, all28 semantic mutant kills. These are outside or qualified within the approved contract; no production-readiness claim follows.

The full1964 suite and restore10 are verified **from exact-SHA CI**, not locally rerun. C1/C2 extra cases are clearly secondary. Original failed harness/mount/hypothesis outputs remain available. No general audit, AGENT-001 or FE-003 implementation was started.

After all local probes, the exact owned container ID e148832bfaa21653f4d221ff2fcec2c3ba57c02bbac5a12ef48aa046c8e60f3a and label were verified, synthetic server evidence saved, and that container/anonymous volumes removed. cleanup-receipt.json records success. Other containers were untouched. The exact clean worktree remains for review.

Deliverables: this report, its SHA256 sidecar, BP-10-AUDIT-RECEIPT-DRAFT.md, evidence manifest, frozen plan/preliminary and executable probe/log bundle. To accept later: preserve repository-readable binding evidence and dispositions, reconcile PROJECT-STATUS as governance requires, and obtain the founder/GPT merge decision. This session performs none of those repository writes or merge actions.

## Appendix A — changed-file scope (35)

```text
backend/alembic/versions/11d778ab87a3_bp10_message_client_id.py
backend/app/core/business_metrics.py
backend/app/core/db.py
backend/app/modules/engagement/models.py
backend/app/modules/engagement/router.py
backend/app/release.json
backend/scripts/mutation/bp10_mutants.py
backend/tests/test_bp10_message_idempotency.py
backend/tests/test_bp10_message_idempotency_pg.py
backend/tests/test_concurrency_r4_pg.py
backend/tests/test_conversations.py
backend/tests/test_dr_restore_phase1_pg.py
backend/tests/test_engagement_safety.py
backend/tests/test_engagement_safety_pg.py
backend/tests/test_listing_freshness.py
backend/tests/test_listing_freshness_tz_pg.py
backend/tests/test_message_moderation.py
backend/tests/test_message_moderation_pg.py
backend/tests/test_moderation_core.py
backend/tests/test_obs02_03_metrics.py
backend/tests/test_release_manifest.py
backend/tests/test_release_pg.py
backend/tests/test_schema_compat.py
backend/tests/test_tst01_openapi_contract.py
docs/DECISIONS.md
docs/DEVLOG.md
docs/PROJECT-STATUS.md
docs/api/openapi.json
docs/canonical/IMPLEMENTATION-CONVERGENCE.md
docs/database/SCHEMA-v1-PORT.md
docs/production/RELEASE-AND-MIGRATION.md
docs/tasks/BP-1-stable-api-codes.md
docs/tasks/BP-10-idempotent-message-send.md
docs/tasks/FE-003-save-conversation-viewing-DRAFT.md
frontend/web/src/api/schema.d.ts
```

## Appendix B — actual command families

Host: PowerShell; source inspection through rg, Get-Content and exact-object git commands; worktree created/attached through Codex worktree tools. Windows standard exec sandbox initialization failed; require_escalated execution was approved. No auto-review action rejection remained.

Docker command base (actual final mounts; initial targeted attempt omitted /docs):
```powershell
docker run --rm --label homies.audit=BP10-CODEX-c385136 --read-only --tmpfs /tmp -v 'C:/Users/ihorf/.codex/worktrees/bp10-final-audit/homies/backend:/src:ro' -v 'C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/BP10-c385136-audit:/audit' -v 'C:/Users/ihorf/.codex/worktrees/bp10-final-audit/homies/docs:/docs:ro' -v 'C:/Users/ihorf/.codex/worktrees/bp10-final-audit/homies/frontend:/frontend:ro' -v 'C:/Users/ihorf/.codex/worktrees/bp10-final-audit/homies:/repo:ro' -w /repo/backend -e PYTHONPATH=/repo/backend -e DATABASE_URL=sqlite:// -e TEST_DATABASE_URL=postgresql+psycopg://bp10_audit:synthetic-bp10-only@host.docker.internal:55510/homies_bp10_test --entrypoint python bp10c-test:c385136 /audit/audit_run.py targeted
```
The password above is disposable synthetic fixture material. Probe/mutation runs change only the database suffix to homies_bp10_probes / homies_bp10_mutants and external runner name.

Actual inner commands, exact arguments retained in runner files:
```text
python -m pytest tests/test_bp10_message_idempotency.py tests/test_bp10_message_idempotency_pg.py tests/test_tst01_openapi_contract.py tests/test_release_manifest.py tests/test_schema_compat.py tests/test_td01_migrations.py -q -rs -p no:cacheprovider --basetemp=/audit/pytest-targeted --junitxml=/audit/targeted.xml
python /audit/supplemental_run.py
  python -m pytest tests/test_tst01_openapi_contract.py -q -p no:cacheprovider --basetemp=/audit/pytest-openapi --junitxml=/audit/openapi.xml
  python -m ruff check app tests alembic scripts --no-cache
  python -m mypy app --cache-dir=/tmp/mypy-cache
  python -m pytest tests/test_obs02_03_metrics.py tests/test_moderation_core.py::test_one_migration_head_and_it_is_the_release_head tests/test_release_pg.py -q -rs -p no:cacheprovider --basetemp=/audit/pytest-extra --junitxml=/audit/metrics_release.xml
python /audit/audit_run.py probes
  python -m pytest -p tests.conftest /audit/independent_probes.py -q -s -p no:cacheprovider --basetemp=/audit/pytest-probes --junitxml=/audit/probes.xml
python -m pytest -p tests.conftest /audit/observations.py -q -s -p no:cacheprovider --basetemp=/audit/pytest-observations --junitxml=/audit/observations.xml
python /audit/mutation_run.py
python /audit/semantic_mutation_run.py
python -m pytest -p tests.conftest /audit/final_probes.py -q -s -p no:cacheprovider --basetemp=/audit/pytest-final-probes --junitxml=/audit/final-probes.xml
python -m pytest -p tests.conftest /audit/clarifications.py -q -s -p no:cacheprovider --basetemp=/audit/pytest-clarifications --junitxml=/audit/clarifications.xml
```
Source for all external runners is retained. Migration observations invoke real Alembic command.upgrade/downgrade against the disposable database with selected barriers; exact code is in observations.py. GitHub retrieval used read-only connector commit/workflow-run/jobs/job-logs/artifact APIs. No CI run was triggered by this session.

MERGE AUTHORIZED: NO
FE-003 IMPLEMENTATION AUTHORIZED: NO
PRODUCTION READY: NO
DEPLOYMENT: NO

