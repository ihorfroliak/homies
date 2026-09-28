# Production readiness — baseline (PR-001, 2026-09-28)

Status of Homies against production readiness, **measured, not assumed**.
Baseline: accepted Phase-1A SHA `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe`
(TASK-012). TASK-013 is under audit and is not part of this baseline.
**Nothing is deployed. No production environment exists.**

Statuses: **READY** (evidence exists) · **PARTIAL** · **MISSING** · **NOT ASSESSED**.
Nothing is READY without evidence named in the row.

## 1. Readiness matrix

| # | Area | Status | Evidence / gap |
|---|---|---|---|
| 1 | Reproducible build | **PARTIAL** | Production image `backend/Dockerfile` (python:3.12-slim) now installs the verified dependency set (`backend/constraints.txt`, PR-001); built locally and checked to carry 24 migrations. Gap: base image by tag, not digest; no image registry / immutable tags; no SBOM |
| 2 | CI green | **PARTIAL** | `.github/workflows/ci.yml` has backend (lint, types, migrate, tests incl. PostGIS, coverage, pip-audit), image, gitleaks, monitoring and contract jobs. **Before PR-001 it triggered only on `main` and PRs; task branches are pushed without PRs, so no Phase-1A commit has a CI record.** PR-001 adds `claude/**` pushes and `workflow_dispatch`. Gap: no run observed yet (no `gh` access from the builder); branch protection not verified |
| 3 | Supported runtime | **READY (local evidence)** | Python 3.12.14 (test image `ops/test/Dockerfile.py312`): full SQLite 780 passed / 291 skipped, full PostgreSQL 16.4 / PostGIS 3.4.3 1070 passed / 1 skipped (Stripe live, not requested), ruff, mypy, OpenAPI drift — at `879bf56` with the pinned set. `requires-python >=3.12`; not raised |
| 4 | Migrations | **PARTIAL** | Single Alembic head (CI gate added); empty → head verified in CI and in the image smoke test; startup never migrates outside `ENV=local`, only verifies head (`app/core/schema.py`). Gap: see §5 — app refuses any DB not at its exact head, which blocks code rollback after a migration and rolling deploys; no documented migration job/runner for staging/prod |
| 5 | Secrets | **PARTIAL** | Fail-fast validation outside dev (SEC-02): weak/default JWT/webhook secrets, Stripe key/environment mismatch, and now (PR-001) the repository's default `DATABASE_URL`. Errors name fields, never values. gitleaks in CI. Gap: no secret store chosen; SMTP password not validated; no rotation procedure |
| 6 | Health | **READY (local evidence)** | `/healthz` liveness (no external checks, by design), `/readyz` readiness (bounded `SELECT 1`, 2 s statement timeout, 503 without DSN leakage), `homies_database_up` gauge + freshness timestamp. Smoke-tested on the production image |
| 7 | Logs | **PARTIAL** | PR-001: process logging configured at the entry point (text or `LOG_FORMAT=json`, `LOG_LEVEL`), request id on every record and `X-Request-ID` on every response. Before, `homies.*` INFO logs were dropped. Gap: no log shipping/retention; uvicorn access log still plain text |
| 8 | Metrics | **PARTIAL** | Prometheus `/metrics` (HTTP, DB, rate limit, notifications, search, reveals). Gap: **`/metrics` is served publicly on the app port** — must be restricted to the internal network at ingress before production |
| 9 | Errors | **PARTIAL** | Unhandled errors → generic 500, traceback in logs with request id. Gap: no error tracking service (none chosen; none activated) |
| 10 | Monitoring | **PARTIAL** | Prometheus + Alertmanager config and rules, promtool-tested in CI (13 rules). Gap: several rules watch dormant booking/payment metrics; no rules for backups, restore verification, disk, worker liveness |
| 11 | Alerting | **MISSING** | Alertmanager routes to a local HTTP sink only. No real destination (chat/e-mail/pager) — founder decision |
| 12 | Backup | **PARTIAL** | Scripts (`backend/scripts/backup/`: pg_dump custom → gzip → AES-256 → sha256) refuse the published key. Gap: no scheduled job, no offsite target, no retention, no backup of media files |
| 13 | Restore drill | **PARTIAL** | Executed on every CI build: legacy drill (`test_dr_restore_pg.py`) and, new in PR-001, the Phase-1A drill (`test_dr_restore_phase1_pg.py`). Disposable databases only — see BACKUP-RESTORE.md for what this does not prove |
| 14 | RPO / RTO | **MISSING** | **CANONICAL DECISION REQUIRED** (§4) |
| 15 | Rollback | **PARTIAL** | Runbook outline §5. Gap: exact-head startup check (above); several destructive downgrades; no staging rehearsal |
| 16 | Staging | **MISSING** | No staging environment |
| 17 | Smoke test | **PARTIAL** | Local image smoke test (PR-001, §6). Gap: no scripted post-deploy smoke test against an environment |
| 18 | Load / capacity | **NOT ASSESSED** | Only diagnostic EXPLAIN on ~5 000 synthetic listings (TASK-013 branch) |
| 19 | Security | **PARTIAL** | Independent audits of the foundation and each slice; rate limiting; privacy tests; pip-audit; gitleaks. Gap: no external penetration test, no TLS/ingress config, no WAF decision |
| 20 | Incident runbook | **PARTIAL** | `INCIDENT-RUNBOOK.md` (PR-001) + `docs/runbooks/dr-database-recovery.md`. Gap: no on-call, no contacts, never rehearsed |

## 2. Configuration inventory

Read by `app/core/config.py` (pydantic-settings; variable = field name upper-cased;
unknown variables are ignored).

| Variable | Class | Required outside dev | Notes |
|---|---|---|---|
| `ENV` | public | yes | `local` self-migrates; `test`/`ci` exempt from secret checks; anything else is production-like |
| `DATABASE_URL` | **secret** (password) | **yes** (PR-001: default refused) | application role `homies_app` (`ops/sql/app_role.sql`), not the owner |
| `ALEMBIC_DATABASE_URL` | **secret** | for the migration job | owner/migration role; read by `alembic/env.py` first |
| `JWT_SECRET` | **secret** | yes (≥ 32 chars, not a default) | |
| `WEBHOOK_SECRET` | **secret** | yes (≥ 16) | legacy simulated webhook |
| `PAYMENT_PROVIDER`, `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` | secret (Stripe) | no (dormant) | live keys refused outside `production` |
| `EMAIL_PROVIDER`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_FROM` | public | no | `stub` by default; no provider activated |
| `SMTP_PASSWORD` | **secret** | only with SMTP | not validated (gap) |
| `RATE_LIMIT_ENABLED`, `TRUST_PROXY_HOPS` | public | yes (decide per ingress) | `TRUST_PROXY_HOPS` must equal the real proxy depth |
| `NOTIFICATION_*`, `LISTING_FRESHNESS_*` | public | no | worker switches and tuning |
| `CONTACT_REVEAL_DAILY_QUOTA`, `CONVERSATION_DAILY_QUOTA` | public | no | abuse bounds |
| `MEDIA_ROOT`, `MEDIA_MAX_BYTES`, `MEDIA_PROCESSING_*` | public | yes (storage) | local disk until an object store is chosen |
| `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_DAYS` | public | no | |
| `BOOKING_*`, `PLATFORM_FEE_BPS` | public | no | dormant |
| `DEFAULT_CURRENCY` | public | no | |
| `LOG_FORMAT`, `LOG_LEVEL` | public | no | PR-001 |
| `BACKUP_KEY` | **secret** | for backups | scripts only; published default refused |
| `TEST_DATABASE_URL`, `PG_BIN` | test only | — | never set in an application environment |

Removed in PR-001 (no code read them; canon 03 §5–§7): `REDIS_URL`, `MEILI_URL`,
`MEILI_MASTER_KEY`, `NATS_URL`, and the Redis/Meilisearch/NATS compose services.

No production secret is committed (gitleaks in CI; PR-001 checked the
workflow, compose and config: only published development defaults, all
refused outside dev).

## 3. Startup and migrations

* `ENV=local`: the app runs `alembic upgrade head` on boot (developer
  convenience only).
* every other environment: the app **verifies** the database is at the
  migration head and refuses to start otherwise (D-35), then verifies the
  application role cannot rewrite append-only tables (B5). Replicas therefore
  never race each other running Alembic.
* Migrations in staging/production must be a separate, single deploy step run
  with the migration role (`ALEMBIC_DATABASE_URL`) before new app instances
  start. Nothing in the repository runs that step yet.
* **Risk:** the exact-head check means an app version older than the schema
  refuses to boot. See §5.

## 4. RPO / RTO — CANONICAL DECISION REQUIRED

Nothing here is a commitment; Homies has no production database.

| | Candidate A (minimal) | Candidate B (recommended for a public launch) |
|---|---|---|
| RPO (data loss tolerated) | ≤ 24 h — nightly encrypted `pg_dump` offsite | ≤ 15 min — managed PostgreSQL with WAL archiving / point-in-time recovery |
| RTO (time to restore service) | ≤ 8 h | ≤ 4 h |
| Needs | scheduler + offsite bucket + key custody | a managed PostgreSQL provider (a paid provider — founder decision) + restore rehearsal |
| Media files | separate backup of `MEDIA_ROOT` / object store — not covered by pg_dump | object store with versioning |

Phase 1A holds no money, but it holds identities, authority claims,
conversations and listings owners rely on. **Founder decision required:** the
RPO/RTO targets, the database hosting model, and who holds backup keys.

## 5. Rollback

| Layer | Current capability | Rule |
|---|---|---|
| Application code | Redeploy the previous image. Images are now reproducible from a commit (pinned dependencies). No registry/tags exist yet | Roll back by image, not by rebuilding |
| Database schema | Forward-fix preferred. Several downgrades destroy data (MIGRATION-ROLLOUT.md). **`git revert` is not a database rollback**: reverting code does not undo an applied migration | Restore from backup or ship a forward migration |
| Configuration | Environment variables only; no versioned config store | Keep the previous environment set with each release record |

**Blocking interaction:** because startup requires `DB revision == app head`,
rolling back the application after a migration makes the old version refuse
to start, and a rolling deploy restarts old replicas into a refusal. Before
production, decide one of: (a) app accepts a DB **ahead** of its head when the
migration is declared backward-compatible (expand/contract discipline), or
(b) every migration ships with a tested downgrade and rollback always
downgrades first. **Decision required** (deployment design; not changed here).

Rollback outline (to rehearse on staging, never yet executed):
1. Freeze deploys; record current image tag, DB revision, env set.
2. Code-only release → redeploy previous image; verify `/readyz`, smoke test.
3. Release with migration → if backward-compatible (future rule a), redeploy
   previous image; else restore (BACKUP-RESTORE.md) or forward-fix.
4. Verify: `/readyz`, error rate, a public search, a login.
5. Write the incident record.

## 6. Evidence from PR-001 (local, disposable)

* Python 3.12.14 test image; PostgreSQL 16.4 / PostGIS 3.4.3 container;
  pg_dump 16.15. Verified package set in `backend/constraints.txt`
  (SQLAlchemy 2.1.1, FastAPI 0.141.1, Alembic 1.20.0, psycopg 3.3.6,
  pydantic 2.13.5, Pillow 12.3.0, uvicorn 0.54.0).
* Production image smoke test: `ENV=local` on an empty database migrated to
  head and served `/healthz` 200, `/readyz` 200, `/v1/classifieds` 200,
  `/metrics`; `ENV=production` without secrets refused to start;
  `ENV=staging` as the owner role refused (B5); as `homies_app` with real
  secrets it verified the schema and started, logging in JSON with no secret
  in the output.

## 7. Next production tasks (proposed)

PR-002 staging environment + deploy/migration job + smoke test; PR-003
alerting destination + backup scheduling/offsite + restore rehearsal against
staging; PR-004 schema-compatibility policy for rollback/rolling deploys;
PR-005 ingress (TLS, `/metrics` restriction, proxy hops), error tracking;
PR-006 load/capacity baseline.
