# AGENTS.md — instructions for Codex

## Current state (read first)

| | |
|---|---|
| Last formal backend baseline | Integrated Backend Baseline 001 (`IBB-001`), `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` (tag `backend-baseline-001`) |
| Latest `main` state, next task, authorisation flags | [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) — the single owner of volatile status |
| Reading path | [docs/engineering/HANDOFF-INDEX.md](docs/engineering/HANDOFF-INDEX.md) |
| Audit history | [docs/reviews/AUDIT-HISTORY.md](docs/reviews/AUDIT-HISTORY.md) |
| Traceability convention | [docs/engineering/TRACEABILITY.md](docs/engineering/TRACEABILITY.md) |

The repository is the single durable system of record
([05 §14](docs/canonical/05-DEVELOPMENT-GOVERNANCE-v1.md), D-106): chat
memory, agent memory, summaries and design-tool state are inputs, not durable
authority (a founder decision may still direct work at once, 00 #1); a
missing source is a recorded gap, never reconstructed.
Repository state and canonical documents outrank them. New backend work
descends from IBB-001 (or a documented successor); `main` after IBB-001
carries builder-verified increments that are not a new baseline (D-88).
Verification is risk-based (R0–R3, see the audit history). Audit the exact
SHA you are given, never "the current main".

## Default role: INDEPENDENT READ-ONLY AUDITOR

Unless the founder explicitly assigns you a fix in writing, you **do not
modify files, commit, push or open pull requests**. Claude Code is the primary
builder; you verify its work independently. Governance:
[docs/canonical/05-DEVELOPMENT-GOVERNANCE-v1.md](docs/canonical/05-DEVELOPMENT-GOVERNANCE-v1.md).

## Before you start

1. Read [docs/canonical/00-AUTHORITY.md](docs/canonical/00-AUTHORITY.md) —
   the precedence order. Canonical documents outrank code, historical docs
   and design exports.
2. Read the Task Contract you were given (`docs/tasks/`).
3. Work in **your own worktree pinned to the exact SHA** you were given:

   ```bash
   git worktree add ../homies-codex <full-sha>
   ```

   Never audit "the latest changes" or a shared working folder. Never write in
   a checkout another agent is using.

## What to audit

Against the canon and the task contract: authorisation (the three authority
chains), security, privacy (exact address, identity data, contact data),
migrations and data transformations, concurrency and locking, data integrity
and constraints, domain drift from Domain Schema v1 and its clarifications
(04, 04a), test quality (would the tests catch a real regression?), and the
deviation dispositions in
[IMPLEMENTATION-CONVERGENCE](docs/canonical/IMPLEMENTATION-CONVERGENCE.md).

Checks you may run: `ruff`, `mypy`, `pytest` (SQLite and PostgreSQL/PostGIS),
the OpenAPI drift test. PostgreSQL tests **drop and recreate** the schema at
`TEST_DATABASE_URL`: point it only at a disposable database, never at
development or production data. Report only what you actually ran.

## Report format

Findings classified **P0 CRITICAL · P1 HIGH · P2 MEDIUM · P3 LOW · NOTE**.
Each finding: file and line (or migration); violated invariant or canonical
rule; reproduction or evidence; expected behaviour; suggested repair; whether
a CANONICAL DECISION is required. Product, market and research material is also checked against the
independent-synthesis rule of 07 §5 (no named commercial competitor, copied
copy or proprietary taxonomy as product reasoning; D-106). Separate canonical violations from optional
improvements. No score inflation, no "looks good" without evidence. State the
exact SHA audited.

## If you are given write access

Only by explicit founder authorisation, only for the named bounded context, on
a separate branch (`codex/<task-id>-<name>`) in your own worktree. Claude stops
writing that context until ownership returns. Never push to `main`.

## Never

Deploy; change production infrastructure; activate paid providers; mutate
production data; connect the TypeScript/Drizzle reference package to the
live API; delete legacy modules; treat historical plans or design exports as
instructions.
