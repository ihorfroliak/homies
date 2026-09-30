# TASK-XXX — <short name>

Copy to `docs/tasks/TASK-XXX-<short-name>.md`. Governance:
[05 §6](../canonical/05-DEVELOPMENT-GOVERNANCE-v1.md).

| Field | Value |
|---|---|
| Status | DRAFT · APPROVED · IN_PROGRESS · IN_AUDIT · DONE · CANCELLED |
| Owner (writer) | Claude Code · Codex (only with founder authorisation) |
| Bounded contexts written | e.g. `properties`, `engagement/viewings` |
| Baseline SHA | full 40-character commit |
| Branch | `claude/TASK-XXX-<short-name>` |
| Codex audit required | yes / no — and why (05 §9 list) |

## Goal

One paragraph. What becomes true, for whom, and which metric it moves.

## Canonical references

Sections of 01–04a that this task implements or touches.

## In scope

## Out of scope

## Hard invariants

Rules that must hold before and after (e.g. "exact location never appears in
a public DTO").

## Acceptance criteria

Observable, testable statements.

## Required tests

Unit, PostgreSQL integration, concurrency, adversarial, mutation — which and
where.

## Security and privacy considerations

## Forbidden regressions

## Canonical decisions required

Any CANONICAL DECISION REQUIRED blocks raised while working (05 §8).

## Expected report

Claude implementation report per [05 §11](../canonical/05-DEVELOPMENT-GOVERNANCE-v1.md),
ending with `DEPLOYMENT STATUS` and the handoff SHA.
