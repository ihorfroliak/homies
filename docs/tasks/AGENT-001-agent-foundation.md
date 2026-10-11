# AGENT-001 — Multi-vendor specialist foundation

| Field | Value |
|---|---|
| Status | ACCEPTED FOR CONTINUED DEVELOPMENT (D-110); INTEGRATED effective upon reconciled PR #5 merge. Before merge this branch is a candidate |
| Owner | Codex, bounded Session B exception to read-only auditor role |
| Baseline | `be150da11b9838409fcf8ee2d8ca4bd8b0311307` (fetched and remote-verified origin/main) |
| Branch | `codex/AGENT-001-agent-foundation` |
| Authority | Original founder Session B instruction, then final founder integration authorization D-110 (2026-10-11); 00-AUTHORITY; 05 sections 3–7 and 14; D-106 |
| Review | Bounded configuration/runtime validation and Claude same-SHA parity; no new independent audit program |
| Merge / deployment | PR #5 normal merge AUTHORIZED (D-110) after reconciliation and required exact-head CI; deployment NOT AUTHORIZED |

## Final integration disposition (D-110)

Reconciled with BP-10 main merge `064be3e1827d279890a9e026e9b1a48e476d7dbd`.
Both historical DEVLOG entries and every specialist configuration/permission
are retained. Native dispatch NOT VERIFIED where runtime was unavailable is
an accepted nonblocking operational limitation; STATIC VERIFIED and actually
observed RUNTIME VERIFIED evidence retain their original scope. No audit or
hook test is repeated on unchanged configuration. Actual PR #5 merge identity
is recorded by Git/GitHub; [PROJECT-STATUS](../PROJECT-STATUS.md) owns current state.
The scope and prohibitions below describe the original Session B implementation;
D-110 adds only the named reconciliation and normal PR #5 merge authorization.
It does not grant standing product-writing permission or deployment authority.

## Original Session B goal and authorization (historical)

Install six permanent project-scoped Claude specialists and corresponding Codex roles,
best-effort routing with mandatory-review escalation, Copilot instructions, compatible
skills, and private context recovery. The founder explicitly authorizes a separate
worktree and feature branch, bounded edits, validation, commits, push of this branch
only, and a Draft PR to main. This exception ends with the Draft PR and handoff;
it grants no standing product-writing permission. Claude remains the primary product
builder and must not concurrently write this AGENT-001 context.

Session A is complete per the founder: BP-10 audit PASS_WITH_NONBLOCKING_NOTES on
`c385136c93826879b41509f1e30533ef46eee64c`; report SHA256
`5b289d02391b7f049df65c71c2e4e6cb4a2fa6d48241100e4520d36678a9461a`.
No P0/P1/P2 established; four P3 and five NOTES await founder disposition. This is
recorded provenance supplied by the founder, not a repeated audit or reverified
report hash. BP-10 merge authorization remains NO.

## In scope / changed-path allowlist

- `.claude/agents/{backend-reviewer,postgres-auditor,security-auditor,frontend-reviewer,test-engineer,devops-reviewer}.md`
- `.codex/agents/` with the six matching TOML files; `.codex/config.toml`
- `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`
- `.claude/skills/micro-cycle/SKILL.md`, `.claude/skills/security-probe/SKILL.md`
- `.claude/hooks/context-pre-compact.ps1`, `.claude/hooks/context-post-compact.ps1`
- `docs/engineering/{AGENT-001-AUDIT,AGENT-OPERATING-MODEL,CHATGPT-COPILOT-INTEROP,CONTEXT-AND-CACHE}.md`
- `docs/engineering/agent001_checks.py` (bounded reproducible configuration/hook checks)
- This contract and the AGENT-001 entry in `docs/DEVLOG.md`.

Package v3 is proposed implementation subordinate to current authority. The ZIP,
installer, manifest and history are not repository deliverables. Necessary
compatibility corrections within these paths are part of implementation.

## Out of scope / forbidden regressions

No BP-10 changes, product code, migrations, API contracts, canonical decisions,
roadmap changes, CI workflow edits, live service operations, main writes, merges,
deployment, paid-provider activation or another agent's worktree edits. Preserve
unrelated settings, all existing hook wiring, the 80% compaction setting,
SessionStart hook, context-survival rule and money-invariants skill.

## Acceptance and required checks

1. Six Claude YAML definitions and six Codex TOML roles parse; scopes correspond.
2. Specialists are read-only; mandatory reviews are explicitly invoked or marked
   NOT VERIFIED with their gate open. Docs-only work defaults to zero reviewers.
3. Root instructions agree with governance; Copilot has auxiliary-only authority.
4. Skills use feature branches, approved test paths and disposable databases;
   they never grant writes to read-only specialists.
5. Windows synthetic hook tests: no transcript copy/hash or summary/raw hook
   payload by default; explicit opt-ins cap transcript copies at 20 MiB and
   summaries at 16,384 characters. Recovery returns the synthetic HEAD/checkpoint.
6. Native runtime discovery and bounded synthetic routing where supported;
   distinguish actual delegation from explicit invocation and unverified behavior.
7. Declared diff only; syntax/frontmatter, preserved-file identities and
   `git diff --check` pass. Record only checks actually executed.
8. Push only this branch, open Draft PR, return exact commit/tree and Claude
   read-only parity instructions. No second general audit.

## Security, privacy and shared state

Use synthetic transcripts and disposable local Git fixtures only. No raw user
transcripts, credentials or private archives enter Git. No archive deletion or
provider-cache reset. Shared state means the same Git SHA, canonical contracts,
accepted decisions and documented evidence; vendor memory and prompt caches are
independent. A filesystem sandbox does not govern external connectors or a fully
privileged parent. Native enforcement and provider savings require measured evidence.

## Evidence and disposition

See [AGENT-001-AUDIT](../engineering/AGENT-001-AUDIT.md) for STATIC VERIFIED,
RUNTIME VERIFIED and NOT VERIFIED results. Exact final identity is in the external
handoff/PR, not a self-referential SHA in this file. No canonical product decision
is changed by AGENT-001 configuration. Original Session B next action was Claude
parity and founder disposition; D-110 supplies the final acceptance and specific
PR #5 merge authorization. New BP-5/BP-6 implementation is a separate bounded
authorization with its own independent exact-SHA review and later merge decision.
