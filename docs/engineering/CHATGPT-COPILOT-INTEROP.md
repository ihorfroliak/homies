# AGENT-001 — ChatGPT and GitHub Copilot interoperability

ChatGPT is the **advisory planning/architecture/adjudication layer**, not a native agent automatically installed by `.claude/agents/*.md` or `.codex/agents/*.toml`. For consequential planning, it must read the canonical repository contract and exact SHA through its available GitHub connector/Work tools; it should distinguish source evidence, founder decisions, hypotheses and gaps. Its sessions are not a trusted durable source of code or project status.

Copilot loads repo-specific instructions from `.github/copilot-instructions.md` (supported surfaces), with role boundaries/authority linked from `AGENTS.md`. Copilot does not automatically acquire six native Claude/Codex specialist roles. Check the effective instructions in the chosen Copilot surface; no implicit memory sharing is promised.

All vendors use the same Git commit/branch and a compact handoff (task, contract, exact SHA, scope, evidence, decision, next). Only GitHub accepted state is shared. An unmerged branch is an unaccepted candidate, even when all agents agree. No credentials, raw transcripts or opaque cache dumps in Git. Read `docs/engineering/CONTEXT-AND-CACHE.md` and the AGENT-001 operating model.
