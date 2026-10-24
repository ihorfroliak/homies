# AGENT-002 — Implementation Orchestrator

Authority: founder HOMIES-DELIVERY-002 directive, 2026-10-16, section 4.
Base: `4ed8fe8ab334a8d8e344b80e266da2be3b661aee` (integrated BP-8).
Branch: `codex/AGENT-002-implementation-orchestrator`.
Owner: Codex, explicitly authorized single writer of this bounded context.
Risk: R2 delivery tooling; focused independent review of ownership and evidence gates.
Status: BUILDER_VERIFIED; candidate, not integrated. Focused separate review pending.

## Scope and acceptance

Add exactly one Implementation Orchestrator role per vendor while preserving the
six existing specialists. Implement a small standard-library policy for deterministic
selection, dependency-aware stacked work, exclusive context ownership, exact-SHA
recovery, evidence gating and Draft PR payload preparation. Update operating model,
ChatGPT interoperability and Copilot instructions; an existing contracts-job CI
step runs policy tests on Python 3.12. No application code, database,
production access, provider activation, merge executor or persistent scheduler.

A caller must supply an approved contract, explicit authorization reference, exact
base, named context, task risk and changes. Reject unknown policy inputs; do not infer
product authorization. Required reviews under governance section 9 cannot be removed
by assigning a low risk label. A writer cannot attest its own independent review.
Backlog states remain distinct from integration and production readiness.

Tests cover deterministic routing/selection, unchanged specialist configuration,
exclusive ownership across worktrees, fail-closed interrupted claims, exact-SHA
resume, evidence invalidation, independent review, R3 operational gates, stacked base
identity and Draft-only preparation. Preserve AGENT-001 hooks/settings and archive
privacy. Use synthetic local fixtures only. Native configuration discovery is reported
separately from model invocation, and unavailable runtime behavior is NOT VERIFIED.

The parent program owns docs/PROJECT-STATUS.md. This contract and the task evidence
record are immutable milestone facts, not a second current project index.
New PR remains Draft; founder merge decision is required. Deployment is prohibited.
