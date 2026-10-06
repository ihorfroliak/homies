# CLAUDE.md — Homies

Homies is a trust-first residential property marketplace — market: Poland;
architecture target: Europe (launch locally, model nationally, architect
internationally). Canon lives in
[docs/canonical](docs/canonical/00-AUTHORITY.md); read `00-AUTHORITY`, `07-PRODUCT-GROWTH-DOCTRINE`,
`02-BUSINESS-LOGIC`, `05-DEVELOPMENT-GOVERNANCE-v1` and
`IMPLEMENTATION-CONVERGENCE` before building. Older strategy, charter and
release-plan documents are historical (banner-marked).

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
Verification is risk-based (R0–R3, see the audit history).

## Your role

**Claude Code is the primary builder.** You implement approved Task Contracts
(`docs/tasks/`): code, migrations, tests, adversarial/concurrency/security
validation, repository docs, evidence. The founder is final authority;
ChatGPT is advisory product/architecture arbiter; Codex is an independent,
read-only-by-default auditor.

## Rules

1. **Hierarchy.** Canonical documents outrank code, old docs and design
   exports. A real domain contradiction is recorded as
   `CANONICAL DECISION REQUIRED` (05 §8) — never resolved silently in code.
2. **No stealth architecture changes.** Stack, database, new infrastructure,
   new dependencies with operational weight, paid providers: founder decision.
3. **One writer per bounded context.** Never write in a dirty checkout you did
   not create; never overwrite or delete another agent's uncommitted work —
   preserve it on a branch and report it.
4. **Task Contract first** for meaningful work; branch
   `claude/TASK-XXX-<name>`; the founder merges to `main`.
5. **Exact-SHA handoff.** Reports end with the full commit SHA to audit and
   `DEPLOYMENT STATUS`. Report only tests actually run; mutation runs need a
   green baseline and count only real test failures.
6. **High-risk changes** (05 §9 list) are not final until Codex audits them.
7. **Legacy dormant.** `booking`, `payments`, `ledger`, the short-stay
   `listings` module, `admin/legacy.py` and `identity/host_payouts.py` are
   `LEGACY_DORMANT — DO NOT EXTEND FOR PHASE 1`. The deployable app is
   `create_phase1_app()` in `app/composition.py`; it must not route or start
   them (`tests/test_phase1_runtime.py`), and Phase-1 code must not import
   them (`tests/test_phase1_boundaries.py`). Legacy tests use
   `tests/legacy_runtime.py` via the `legacy_runtime` marker.
8. **Hard limits.** No deployment, production infrastructure change, paid
   provider activation or production data mutation without explicit founder
   approval for that action.

## Stack (03)

Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 + PostGIS 3.4
(controlled debt) · transactional outbox. One production database. The
TypeScript/Drizzle Schema v1 package is a reference oracle on branch
`reference/ts-drizzle-schema-v1`, never a runtime (as of 2026-10-06 that
branch is not published on `origin` — it exists in a local clone only;
publishing it is a founder decision). Money in integer minor
units. Exact location private; public point only.

## Working agreements

* Communication with the founder: Ukrainian. Code, commits, README: English.
  Conventional commits.
* Local: `make up`, `make test`, `make lint`; backend in `backend/`
  (venv `backend/.venv`). PostgreSQL tests recreate the schema at
  `TEST_DATABASE_URL` — disposable databases only.
* Contracts: `docs/api/openapi.json` generated from FastAPI, drift-tested.
* After meaningful work update `docs/DEVLOG.md` and the relevant task contract.
  When a merge changes current or next work, accepted task state,
  implementation authorisation, production readiness or deployment, the
  same task reconciles `docs/PROJECT-STATUS.md` (05 §14) — without embedding
  the SHA of its own commit (TRACEABILITY, self-reference rule).
* Market or product research goes to `docs/research/` (non-normative,
  independent synthesis, no named commercial competitor as authority; D-106).
