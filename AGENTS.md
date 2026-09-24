# AGENTS.md — instructions for Codex

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
a CANONICAL DECISION is required. Separate canonical violations from optional
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
