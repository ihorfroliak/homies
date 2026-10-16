# AGENT-002 — Delivery operation

The founder's 2026-10-16 HOMIES-DELIVERY-002 section 4 authorizes this bounded
implementation. One additional role, Implementation Orchestrator, is defined for
each vendor. Six specialist definitions remain unchanged. This is a local policy
and an active-session workflow, not a background scheduler or new product authority.

## Run one authorized task

1. Fetch and reconcile remote branches/PRs, exact base SHA, contract, candidate and
   existing worktrees. Read only the task's relevant canonical sections. The parent
   owns `docs/PROJECT-STATUS.md`; delegated writers record task facts only.
2. Build a small JSON backlog from accepted contracts. Fields: `id`, `context`,
   `contract` (repository path), `authorization` (founder decision reference),
   `base_sha` (full SHA), `base_branch`, `branch`, `risk` (R0-R3), `changes` (explicit
   surfaces from ROUTES), `priority` (lower first), `state`, `dependencies`.
   Do not treat a nonempty string as authority without reading its source.
3. Run `python docs/engineering/delivery_policy.py plan backlog.json --root <repo>`.
   Selection is deterministic by priority then task ID, after authorization,
   dependencies, unimplemented status, blockers and ownership. Completed candidates
   are not selected again. Unknown surfaces and states fail instead of guessing.
4. Create/select a clean isolated worktree at the exact base on the named feature
   branch. Run `... claim task.json --root <worktree> --owner <session-id>
   --backlog backlog.json`. The helper checks selection again and creates an
   exclusive claim in the shared Git common directory. Different local worktrees
   of the same repository contend for the same context. Separate clones/hosts do
   **not** share a lock: the top-level owner must reconcile their live ownership
   before dispatch. Do not use time-based automatic lease stealing.
5. Dispatch only the selected writer, then bounded read-only specialists. R0 selects
   zero; R1 up to one; R2/R3 up to two distinct relevant roles in explicit priority
   order. Mandatory governance section 9 independent review is additional, even if
   risk was mislabeled R0. R3 also requires exact-SHA operational evidence.
6. Implement, test, commit; update the task JSON with writer, candidate SHA, evidence,
   blockers and next action. `checkpoint` requires a clean exact HEAD and atomically
   replaces only that task's bounded checkpoint. `resume` checks ownership, path,
   branch, base, contract hash, HEAD/tree and cleanliness; returns saved blockers,
   next step and evidence. It does not rerun an unchanged audit or reimplement work.
7. Run `draft task.json` for a GitHub create-PR payload with `draft: true`. No network
   or credentials are used by the helper. The top-level authorized session checks
   live branch/head/base and sends the payload using available GitHub tooling. It
   may open the Draft to trigger PR-only CI; this is explicitly marked CI pending.
   `CI_GREEN` / `DRAFT_PR_READY` checkpoints require CI PASS at the exact candidate.
   A successful run on a synthetic merge must be attested to its actual PR head and
   include the run URL; verify head/tree identity before recording it.
8. Persist the immutable candidate/evidence receipt in the task contract or handoff
   and return the checkpoint to the owner of PROJECT-STATUS. Once this writer is
   stopped, `release` removes its claim. Continue other authorized tasks; never
   automatically merge or deploy. Founder approval is separately SHA-bound.

The helper accepts trusted operator evidence attestations; it cannot authenticate
GitHub reports or prevent a privileged user bypassing it. Runtime permissions and
GitHub branch protection are separate enforcement. No generic merge command exists.
Its `MERGE_AUTHORIZED` checkpoint requires exact founder SHA/reference; `INTEGRATED`
requires the same authorization plus actual merge evidence. Check both against
GitHub before recording them; a Draft or green CI is never integration.

## Evidence and dependencies

Evidence objects `tests`, `review`, `ci`, `operational` contain `sha`, `result: PASS`
and a durable `reference`. Mandatory review additionally needs `reviewer` different
from `writer` and `separate_context: true`; the operator must verify actual
independence. Changed SHA invalidates evidence automatically. Never fabricate PASS.

Dependencies contain `id`, `mode` (`integrated` or `stacked`), and exact `sha`.
Integrated mode requires the upstream merge identity. Stacked mode requires a
verified upstream Draft, exact upstream candidate as base SHA, and upstream feature
branch as PR base. Such PRs are not independently mergeable into unprepared main.
Remote drift, unavailable contracts and ambiguous ownership require reconciliation.
After a base/head change, refresh actual evidence; never silently copy PASS fields.

States: PLANNED, AUTHORIZED, READY, IN_PROGRESS, BUILDER_VERIFIED, REVIEW_REQUIRED,
REVIEWED, CI_GREEN, DRAFT_PR_READY, MERGE_AUTHORIZED, INTEGRATED, BLOCKED. They describe
attested delivery milestones, not production readiness. BLOCKED retains reasons;
resolving a blocker requires updating its evidence, not merely removing its text.

## Interrupted or failed ownership operations

Do not delete or expire another session's claim. A partial claim or `.busy` marker
fails closed. Reconcile with the previous owner, preserve its work, confirm it has
stopped, and record explicit ownership transfer before repairing the local marker.
Only the same named owner/worktree can release normally. Recoverable local claims
are coordination, not distributed consensus. Export milestone facts repository-wide
before a session ends; the local checkpoint is not the durable repository authority.

## Runtime boundaries and measured context

Codex standalone `.codex/agents/*.toml` uses name, description and
 developer_instructions; no additional project config registration is required.
Installed-runtime verification is recorded in AGENT-002-EVIDENCE. Permissions are
inherited from the parent. In current official Codex documentation, `sandbox_mode`
in custom agent files does not override the parent: existing specialist fields are
preserved for compatibility, not claimed as runtime enforcement. Start independent
review in an actually read-only session and constrain external connector actions.
See [official subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Claude YAML uses project-scoped agent metadata. A Claude subagent cannot orchestrate
recursively; its parent performs dispatch. When Claude authentication is unavailable,
the founder-authorized Codex writer executes the approved program. Configuration
loading and actual model dispatch are distinct evidence. No persistent scheduler,
provider-cache synchronization, automatic shared memory or token savings is claimed.

AGENT-001 context hooks/settings remain unchanged. No default transcript copies or
raw event persistence; archive opt-ins stay bounded and per-task. Checkpoints are
32 KiB max and should contain references, never secrets/transcripts. Record only
observed numeric metrics: compaction_ms, recovery_ms, duplicate_context_reads,
agent_calls, input_tokens/output_tokens where exposed, cycle_ms. Unknown measures
remain NOT MEASURED. Do not clear caches or load complete histories to resume.

Run bounded tests: `python -m unittest discover -s docs/engineering -p test_delivery_policy.py`.
