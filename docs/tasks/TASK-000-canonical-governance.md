# TASK-000 — Canonical synchronization, governance and convergence bootstrap

| Field | Value |
|---|---|
| Status | IN_AUDIT (handoff to founder; Codex audit is TASK-001) |
| Owner (writer) | Claude Code |
| Bounded contexts written | docs only, plus legacy markers and one boundary test |
| Baseline SHA | `782c833f100f1bf2e86888b664c9b30b27cbc1dd` |
| Branch | `claude/TASK-000-canonical-governance` |
| Codex audit required | Not for this task on its own; the C1–C8 port it inventories is |

## Goal

Make the repository reflect the founder's 2026-09-24 canon: one authority
hierarchy, one runtime backend, one writer per context, and a clear map of
what existing code is active, adapted, dormant or reference-only — so the
next build work starts from agreed ground and no agent's work is lost.

## Canonical references

Founder instruction of 2026-09-24 (TASK-000), captured in
[docs/canonical](../canonical/00-AUTHORITY.md).

## In scope

* Preserve all uncommitted foreign work losslessly; leave no mixed dirty tree.
* `docs/canonical/00`–`06`, `04a`, `IMPLEMENTATION-CONVERGENCE.md`.
* Concise `CLAUDE.md`; `AGENTS.md` for Codex; this task-contract system.
* Classification of every area; disposition of the 22 port deviations.
* C8 sanitiser flagged REQUIRES_CODEX_SECURITY_AUDIT.
* LEGACY_DORMANT markers on booking, payments, ledger and short-stay listings;
  a test that Phase-1 modules do not import them.
* Historical banners on superseded strategy/plan documents.
* Test baseline.

## Out of scope

C9 or any product feature; deployment; production infrastructure; paid
providers; Gate 2; stack rewrite; Python → TypeScript; deleting legacy code;
connecting Drizzle to the API; dual writes; pushing to `main`.

## Hard invariants

* No foreign change deleted or overwritten without a verified preserved copy.
* No behaviour change in the running API.
* Historical documents are banner-marked, not rewritten.

## Acceptance criteria

* Preservation branches verified blob-for-blob against disk.
* `git status` clean on the task branch after commit.
* ruff, mypy, full pytest (SQLite and PostGIS), OpenAPI drift: results
  reported, failures classed PRE-EXISTING or INTRODUCED.

## Canonical decisions required

Recorded in [IMPLEMENTATION-CONVERGENCE §7](../canonical/IMPLEMENTATION-CONVERGENCE.md):
LONG_TERM minimum term vs MONTHLY; subtype for `aparthotel_unit`.

## Expected report

The TASK-000 final report format given by the founder, ending with
`DEPLOYMENT STATUS: NOT DEPLOYED` and TASK-001 (Codex audit) as the single
next task.
