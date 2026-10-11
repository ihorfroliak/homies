# AGENT-001 — Multi-vendor agent operating model (proposed)

Status: PROPOSED on AGENT-001 branch. Guidance, **not new canonical product authority**. No product roadmap or BP-10 decision changed.

## Authority and roles
Founder decides semantics, merge and release. ChatGPT performs advisory planning/adjudication with repository evidence. Claude Code is the primary single writer implementing approved contracts. Codex independently audits exact SHAs, read-only by default; founder-authorized AGENT-001 branch is a narrow exception, not a standing privilege. Copilot is auxiliary. A Claude subagent or Codex specialist is **not** a second primary developer or replacement for the governance-mandated independent Codex audit.

## Six equivalent specializations, different runtimes

| Decision surface | Claude native `.claude/agents/` | Codex native `.codex/agents/` |
|---|---|---|
| FastAPI/SQLAlchemy/backend | `backend-reviewer` | `backend_reviewer` |
| PostgreSQL/locks/Alembic | `postgres-auditor` | `postgres_auditor` |
| Auth/PII/redaction/security | `security-auditor` | `security_auditor` |
| Next.js/React/BFF/a11y | `frontend-reviewer` | `frontend_reviewer` |
| Fixtures/mutations/test truth | `test-engineer` | `test_engineer` |
| CI/Docker/restore/release | `devops-reviewer` | `devops_reviewer` |

Claude specialists expose only Read, Grep and Glob. Codex specialists request a read-only filesystem sandbox; external connectors are governed separately by the parent runtime. These controls do not restrict a fully privileged parent. Every specialist is prohibited from Git writes, external mutations and deployment, and must ask the authorized writer to execute any required mutating test. Codex project roles load only if the project is trusted and the Codex surface supports them. Claude descriptions enable best-effort automatic delegation; Codex local releases may spawn after an explicit request **or applicable project instruction**. Natural-language routing is nondeterministic: **do not claim a perfect automatic dispatcher**.

## Proportional agent-selection policy

1. Resolve the task, contract, exact base/candidate SHA, changed paths and risk R0–R3.
2. R0/docs: 0 specialists by default. R1: 0–1 where useful. R2/R3: select up to 2 **non-overlapping** specialists for material risk. This is a default cost guideline, not a prohibition on mandatory independent audit.
3. Trigger: database migration/advisory locks ⇒ postgres; auth/private data ⇒ security; API/business logic ⇒ backend; React/BFF ⇒ frontend; test semantics/flakiness ⇒ test-engineer; CI/rollout ⇒ devops. Cross-domain work may warrant two. **Do not auto-spawn all six**.
4. Primary writer runs targeted tests then required regression/CI; read-only reviewers identify falsifiable risks. Unchanged SHA + unchanged evidence should not trigger another review. Findings must have file:line, causality, confidence, minimal remedy; no claim of complete correctness from finite tests.
5. Single active writer per bounded context; separate Git worktrees. Exact SHA and approved task contract are the handoff. Specialists do not merge or deploy.

## Definition of Done (delivery, not audit theater)
One approved vertical slice and bounded diff; tests on accepted invariants; relevant DB/security proof; green CI on exact SHA; documented material risks; independent Codex audit only where canon §9 mandates it; founder merge approval. Do not start an unapproved audit program or roadmap refactor. Track cycle time, agent calls, escaped material defects, repeat review loops and total tokens if measured. Optimize on **observed** benefit, not assumptions.

## Real routing smoke test
Fresh Claude/Codex sessions on **same checked-out AGENT-001 SHA**: (1) row-lock regression -> postgres; (2) Next.js focus regression -> frontend; (3) docs typo -> no specialist. Record actual spawned role, whether tool routing occurred or explicit prompt was necessary, and version/surface. Config presence is NOT proof of runtime invocation. Mandatory reviews must be explicitly requested if model-directed selection does not occur. If the runtime cannot perform a mandatory review, record NOT VERIFIED and keep its gate open; a parent self-review cannot silently replace it.

**Routing disclaimer:** agent descriptions provide heuristic, model-selected routing rather than deterministic dispatch. In Codex, explicit subagent invocation may be required depending on client/runtime. Neither tool context nor provider cache is synchronized cross-vendor. A material mandatory independent Codex audit is always a separate exact-SHA task and is not satisfied by these in-process specialist roles.
