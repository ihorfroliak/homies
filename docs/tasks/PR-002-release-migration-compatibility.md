# PR-002 — Release & Migration Compatibility

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88). Integrated into `main` for continued development after green CI; not independently verified; **production NOT READY · NOT DEPLOYED** |
| Risk class | **R2** (migrations, database roles, startup gate) |
| Owner (writer) | Claude Code |
| Baseline | `main` `dacbe9e3bb2b6a05a87946c860b8c9b942d36cf8` (IBB-001 + BASELINE-001 + MICRO-001) |
| Branch | `claude/PR-002-release-migration-compatibility` |
| Design | PR-002 Phase A (read-only, 2026-09-28, at PR-001R `70be78b`) — accepted decisions; delta-reviewed against `dacbe9e` |
| Policy document | [RELEASE-AND-MIGRATION.md](../production/RELEASE-AND-MIGRATION.md) |
| Decisions | D-83 … D-87; verification governance D-88 |

## Goal

Replace "database revision must equal the application head" with an explicit,
machine-verifiable and fail-closed compatibility model, so rolling deploys,
blue/green and N−1 rollback become possible where — and only where — they are
declared safe.

## What was built

| Area | Where |
|---|---|
| Release compatibility policy (strict, cross-checked with the migrations; no commit id) | `backend/app/release.json`, `app/core/release.py` |
| Runtime release identity = policy + injected build identity (required outside local/test/ci) | `release.RuntimeReleaseIdentity`, `app/scripts/release.py manifest` |
| Per-migration declarations (`schema_transition`, `rollback_to_previous`); fail-closed template | `alembic/script.py.mako`; historical registry `app/core/lineage_registry.py` |
| `schema_lineage` + backfill + on_version_apply recorder | migration `0c4e6a8b2d91`, `alembic/env.py` |
| Graph-aware compatibility decision (pure; lineage boundaries; missing/mismatched lineage refused) | `release.evaluate` |
| Startup: compatibility instead of exact head; schema-privilege refusal | `app/core/schema.py`, `app/composition.py` |
| Migration job (role check; session advisory lock on the migrating connection, try-lock with 10 s runner-side deadline, ownership re-check; plan; BARRIER flag; grant convergence; post-verify incl. privileges on every table/sequence) | `app/scripts/migrate.py` |
| Deploy-tooling CLI (`manifest`, `check`, `rollback-allowed`) | `app/scripts/release.py` |
| Roles: migration role; application role split into role + grants; one-time ownership transfer for pre-PR-002 databases | `app/core/sql/{migration_role,app_role,app_grants,migration_owner}.sql` |
| Build identity (build arg without default → env + OCI label; runtime identity, logs — not public metrics; CI proves refusal without it) | `backend/Dockerfile`, CI image job |

## Phase A delta review (against `dacbe9e`)

| Since Phase A | Effect on PR-002 |
|---|---|
| TASK-013 `d0f2b4c6e8a1` (discovery indexes) | EXPAND / SAFE — index only |
| TASK-014 `f3b5d7e9a1c2` | **EXPAND / BLOCKED** — additive, but the previous release bypasses the publicity seam (missed alerts, generation drift) and lacks the unsubscribe endpoint for emailed links |
| PR-001 / PR-001R / PR-001R2 | F-A1 (`%` in URL) and F-A2 (logging) already fixed; `ENV=production` image default kept; readiness untouched |
| CONV-001 | one line; the lineage migration re-parented onto `f3b5d7e9a1c2` (Phase A's parent collision resolved) |
| MICRO-001 | no schema impact; restore drill now also carries `schema_lineage` |
| Phase A F-A3 (app role writes `alembic_version` / `spatial_ref_sys`), F-A4 (default privileges bind only their creator), F-A5 (no lock) | **closed by builder** (D-85, D-86) |

## Out of scope (unchanged)

PR-003 (warm-pool business-request hang, request DB deadlines, health
isolation), TASK-015, applications, frontend, payments, deployment. No
production database, role or pipeline was touched.

## Evidence (builder, local — 2026-10-01)

Builder evidence only (D-88). The candidate commit SHA and the CI run cannot be
written into the commit they describe; they are recorded in the builder
handoff and in the next task's status update. Environment: test image Python
3.12.14; disposable PostgreSQL 16.4 / PostGIS 3.4.3 containers.

| Gate | Result |
|---|---|
| Full SQLite suite | 1160 passed, 409 skipped (PostgreSQL-only), 4 failed + 1 error — all five JWT "Invalid or expired token" / `KeyError 'id'` during Docker VM wall-clock backward steps (~0.5 s every 30 s, recorded by a clock watcher); rerun individually with the previous run's four other clock failures: **9 passed** |
| Full PostgreSQL/PostGIS suite (`HOMIES_REQUIRE_RESTORE_DRILL=1`) | 1567 passed, **1 skipped** (Stripe live suite, opt-in), 5 failed + 1 error — same clock signature; rerun: **23 passed** (all parameter cases). Restore drills ran, **0 skipped** |
| Targeted PG (release, privileges, TD-01, restore drill) | 69 passed, 0 skipped |
| Mutation / fault probes | **22 / 22 killed** — [report](../reviews/2026-10-01-pr002-mutation.md) |
| ruff · mypy · Alembic heads | clean · clean (109 files) · 1 head `0c4e6a8b2d91` |
| OpenAPI | `docs/api/openapi.json` unchanged; drift test passes; Spectral 0 errors |
| AsyncAPI | 0 errors |
| Image | built with `GIT_SHA`: runtime identity carries it; blank or missing identity → exit 1 |

Authoritative full-suite and secrets evidence for the merge is the GitHub CI
run on the candidate (backend, image, secrets, monitoring, contracts).

Real-PostgreSQL scenarios covered (test_release_pg, test_db_privileges_pg):
fresh install (base → head, lineage recorded, second run no-op); IBB-001
`f3b5d7e9a1c2` → head as the migration role (fails with the database unchanged
without the ownership transfer; after `migration_owner.sql` migrates, backfills
lineage, converges grants, application role starts); application-role Phase-1
DML; application-role DDL and protected-metadata writes refused with `42501`;
future table + serial sequence + standalone sequence created by the migration
role get the application grants only through convergence; a table owned by
another role fails the job (exit 3); lock held by the migrating backend for the
whole migration while a second runner times out and changes nothing; bounded
10 s wait and a 1 s budget independent of `lock_timeout`; two concurrent
runners migrate exactly once; startup EXACT / AHEAD_COMPATIBLE / TOO_OLD /
TOO_NEW (BARRIER and BLOCKED) / UNKNOWN_SCHEMA / LINEAGE_MISSING /
LINEAGE_MISMATCH; backup/restore carries `schema_lineage`.

Runtime product behaviour outside release/migration infrastructure: unchanged
(no public API change).
