# AGENT-002 — bounded evidence (2026-10-16)

Base: 4ed8fe8ab334a8d8e344b80e266da2be3b661aee.
Contract: docs/tasks/AGENT-002-implementation-orchestrator.md.
Final candidate identity is recorded in the immutable Git/PR receipt, not a self-hash.

Executed: `python -m unittest discover -s docs/engineering -p test_delivery_policy.py`:
21 passed in 16.492s on host Python 3.14. Existing backend venv Ruff on the two new
Python files: PASS. All tests use synthetic local Git fixtures. They cover routing,
exclusive ownership across worktrees, task-isolated recovery, stale evidence,
independence, operational/merge gates, stacks and CLI Draft preparation. Inherited
12 specialist blobs, project config and AGENT-001 hooks/settings/check script match
base. Initial run found 3 Windows open-handle deletion errors and 1 routing-order
failure; corrected, then 20 and 21 pass. Default Python lacked Ruff; reused the
existing project venv. No installs, product tests or repeated AGENT-001 hook runs.
The existing contracts CI job now runs these tests under Python 3.12.

Claude Code 2.1.228 native init enumerated all seven project roles including the
orchestrator. Synthetic read-only tools, hooks disabled, no persisted session,
USD0.10 cap. Actual model turn failed: OAuth expired and could not be refreshed.
Native discovery VERIFIED; actual role invocation/delegation NOT VERIFIED.

Codex CLI0.162.0-alpha.17.2 protocol schema generated locally. Private stdio
app-server initialized with --strict-config and config/read returned enabled
project layer, agents.enabled=true, concurrency2, no disabled reason/error.
Process terminated; no model request or global config change. debug prompt-input
also returned0 but did not expose the new role. Strict-config is unsupported by
debug (one rejected invocation, replaced by supported app-server config/read).
Manifest uses only name, description, developer_instructions per current schema.
Actual native role invocation remains NOT VERIFIED; top-level orchestration is
an explicit fallback, not claimed native named-role dispatch.

[Official custom-agent schema](https://learn.chatgpt.com/docs/agent-configuration/subagents)
states permissions are inherited; custom sandbox_mode does not override the parent.
Existing specialist definitions are preserved, while guidance now requires an
actually read-only independent-review session and separately constrained connectors.

Limits: shared-Git claims coordinate cooperating worktrees on one host, not separate
clones or malicious privileged operators. Evidence is trusted operator attestation;
actual GitHub identity/CI and reviewer independence must be checked before recording.
No network, merge or deployment executor exists. A Draft can trigger PR-only CI,
but CI_GREEN/DRAFT_PR_READY require exact-candidate CI evidence. Interrupted claims
never expire automatically; reconcile stopped ownership explicitly. Checkpoints
are per-task, bounded32KiB, preserve blockers and measured numeric metrics only.
No transcript copying, cache clearing or shared provider-cache claims. Compaction,
context savings, token savings and cycle improvement NOT MEASURED. The test time
is one fixture observation. Separate review/CI receipts follow for the exact head.
New PR is Draft; no founder merge authorization or production-readiness claim.
