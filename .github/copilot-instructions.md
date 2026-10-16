# Homies — GitHub Copilot shared repository instructions

Read `AGENTS.md`, `CLAUDE.md` (Claude-only parts as relevant), `docs/canonical/00-AUTHORITY.md`, the approved task contract and `docs/engineering/AGENT-OPERATING-MODEL.md`. GitHub is the durable source of truth; the founder is final authority. Do not invent accepted decisions from chat summaries. Respect one writer per bounded context, assigned branch/allowlist and exact SHA handoffs. Copilot is an auxiliary assistant and not automatically a primary writer or independent Codex auditor. No unattended merges, force pushes, production access, paid-provider activation or deployment. Verify actual tests run. For material changes, choose a focused specialist only when the changed scope warrants it; do not run a six-agent review for a documentation typo. Report blockers with reproducible evidence and a minimal suggested correction. Project status belongs only to `docs/PROJECT-STATUS.md`.

AGENT-002: follow docs/engineering/AGENT-002-DELIVERY.md and delivery_policy.py for
explicit task selection, shared-Git context ownership and exact-SHA checkpoint
recovery. Claim one authorized writer; never become a second writer implicitly.
Mandatory independent review remains separate from your own implementation. Prepare
Draft PRs only; neither green CI nor a ready Draft authorizes merge or deployment.
No authority to redefine canonical semantics. Use top-level orchestration when
native delegation is unavailable; do not claim hidden background execution.
