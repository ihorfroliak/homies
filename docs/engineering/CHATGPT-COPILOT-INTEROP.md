# AGENT-001 â€” ChatGPT and GitHub Copilot interoperability

ChatGPT is the **advisory planning/architecture/adjudication layer**, not a native agent automatically installed by `.claude/agents/*.md` or `.codex/agents/*.toml`. For consequential planning, it must read the canonical repository contract and exact SHA through its available GitHub connector/Work tools; it should distinguish source evidence, founder decisions, hypotheses and gaps. Its sessions are not a trusted durable source of code or project status.

Copilot loads repo-specific instructions from `.github/copilot-instructions.md` (supported surfaces), with role boundaries/authority linked from `AGENTS.md`. Copilot does not automatically acquire six native Claude/Codex specialist roles. Check the effective instructions in the chosen Copilot surface; no implicit memory sharing is promised.

All vendors use the same Git commit/branch and a compact handoff (task, contract, exact SHA, scope, evidence, decision, next). Only GitHub accepted state is shared. An unmerged branch is an unaccepted candidate, even when all agents agree. No credentials, raw transcripts or opaque cache dumps in Git. Read `docs/engineering/CONTEXT-AND-CACHE.md` and the AGENT-001 operating model.

## AGENT-002 delivery handoff

ChatGPT retains architecture, product decisions, contract refinement, founder-facing
assessment and independent strategic synthesis. It is not a hidden background
worker or automatically shared-memory agent. The orchestrator supplies a compact
contract/base/head/tree/owner/evidence/blockers/next handoff.

Copilot follows the same approved contract, context claim and exact-SHA review
gates in [AGENT-002-DELIVERY](AGENT-002-DELIVERY.md). It may assist only the assigned
writer and does not gain independent authority to merge, deploy or redefine canon.
Draft completion, acceptance, integration and production readiness remain separate.
