---
name: micro-cycle
description: "Use for a bounded Homies code change: contract, minimal implementation, targeted tests, required verification, feature-branch CI and handoff. Never self-merge."
---
# Homies development micro-cycle (AGENT-001 compatible)

## PLAN
Read `CLAUDE.md`, current task contract, exact base commit, full approved allowlist, risk R0-R3, acceptance tests and forbidden regressions. Do not create a new task for already approved in-scope debugging.

## IMPLEMENT
Only the founder-authorized primary writer implements. A read-only reviewer reports suggested repairs without editing or running mutating probes. Use the smallest behavior-preserving delta. Preserve other agents' dirty work and frozen audit candidates. No new architectural or paid-provider dependencies without founder authorization.

## VERIFY
First run targeted tests that distinguish the failure hypothesis. Then run the contract-required full SQLite/PostgreSQL suites, migration/restore/security/mutation checks as dictated by risk, and lint/API checks. Record exact commands and result totals. PostgreSQL tests must point **only at disposable test databases**. Do not invoke legacy live payment/warfare harnesses for unrelated phase-1 messaging.

## REVIEW
For R0/doc-only use no specialist; R1 usually zero or one; R2/R3 up to two non-overlapping read-only specialists by default, unless a canonical or explicitly assigned review requires more. They must provide falsifiable evidence and not replace mandatory independent Codex audit. Escalate unresolved material disagreements with evidence; do not repeat a review of unchanged evidence.

## DOCUMENT / GIT
Update the approved task contract and `docs/DEVLOG.md`; only update `docs/PROJECT-STATUS.md` when the task's state change requires it under 05 §14. Never write obsolete `PROJECT_STATE.md` or `BUILD_HISTORY.md` merely because an old skill said so. Conventional commits; push **only the named feature branch**, verify CI tied to exact SHA. **Founder alone authorizes merge to main**. No deployment.
