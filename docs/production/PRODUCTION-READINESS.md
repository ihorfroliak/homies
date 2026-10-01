# Production readiness — baseline (PR-001, repaired in PR-001R and PR-001R2, 2026-09-29)

Status of Homies against production readiness, **measured, not assumed**.
Baseline: accepted Phase-1A SHA `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe`
(TASK-012). TASK-013 is under audit and is not part of this baseline.
**Nothing is deployed. No production environment exists. PRODUCTION READINESS = NOT READY.**
PR-001 → PR-001A → PR-001R → PR-001RA (targeted fix required) → PR-001R2
(candidate, pending PR-001RA2). **PR-001 is not accepted.**

**PR-003 (2026-10-01, candidate on its branch, not merged):** database client deadlines, 503 failure semantics, health isolation (RA-3), worker loop — rows 6, 8, 10 and the database section below. Builder verified, milestone audit deferred (D-88).

Statuses: **READY** (evidence exists) · **PARTIAL** · **MISSING** · **NOT ASSESSED**.
Nothing is READY without evidence named in the row.

## 1. Readiness matrix

| # | Area | Status | Evidence / gap |
|---|---|---|---|
| 1 | Reproducible build | **PARTIAL** | Production image `backend/Dockerfile` (python:3.12-slim) now installs the verified dependency set (`backend/constraints.txt`, PR-001); built locally and checked to carry 24 migrations. Gap: base image by tag, not digest; no image registry / immutable tags; no SBOM |
| 2 | CI green | **PARTIAL** | `.github/workflows/ci.yml`: backend (pinned install proven equal to `constraints.txt`, lint, types, migrate, tests incl. PostGIS and mandatory restore drills, coverage, pip-audit of the pinned set + canary), image (Python 3.12 and `ENV=production` asserted), gitleaks, monitoring, contracts. Runs on `main`, `claude/**`, PRs, manual; `main` keeps every commit's run (PR-001R F10). Gap: no run observed by the builder (no `gh` access); branch protection not verified |
| 3 | Supported runtime | **READY (local evidence)** | Python 3.12.14 (test image `ops/test/Dockerfile.py312`): full SQLite 780 passed / 291 skipped, full PostgreSQL 16.4 / PostGIS 3.4.3 1070 passed / 1 skipped (Stripe live, not requested), ruff, mypy, OpenAPI drift — at `879bf56` with the pinned set. `requires-python >=3.12`; not raised |
| 4 | Migrations | **PARTIAL** | Single Alembic head; every migration declares `schema_transition` / `rollback_to_previous`; the database records its lineage (`schema_lineage`); the migration job `app.scripts.migrate` (migration role, advisory lock, `lock_timeout` 10 s, privilege convergence, post-verify) runs in CI; startup evaluates compatibility instead of requiring the exact head (PR-002 candidate, RELEASE-AND-MIGRATION.md). Gap: no staging/production pipeline runs the job yet |
| 5 | Secrets | **PARTIAL** | Fail-fast validation outside dev (SEC-02): weak/default JWT/webhook secrets, Stripe key/environment mismatch, and (PR-001R F4) a `DATABASE_URL` that is not PostgreSQL, uses the published `homies`/`homies` credentials, or is the loopback dev endpoint `…:5433/homies` — compared on the parsed URL. The image defaults to `ENV=production` (F3). Errors name rules, never values; a percent-encoded password no longer leaks through Alembic. gitleaks in CI. Gap: no secret store chosen; SMTP password not validated; no rotation procedure |
| 6 | Health | **PARTIAL** | `/healthz` liveness (no external checks). `/readyz`: on PostgreSQL a fresh dedicated connection per probe, never the application pool; 503 without DSN; **dependency decision budget 3 s**. PR-003 (candidate, not merged): `/healthz`, `/readyz`, `/metrics` are `async def` and never wait for a thread-pool token; readiness probes on the event loop with one in-flight probe per database and answers at the decision (driver clean-up detached) — under a frozen database saturating 60 requests: `/healthz` 0.02 s, `/metrics` 0.02 s, `/readyz` 503 in 2.0 s (was: `/healthz` up to 75.9 s, `/readyz` client timeouts at 90 s, Phase A S11b). **RA-3 closed by the candidate.** No SQL on the event loop (test guard). Timings are local evidence, not an SLO. Gap: probe settings of a real orchestrator not configured (no environment) |
| 7 | Logs | **PARTIAL** | Process logging at the entry point (text or `LOG_FORMAT=json`, `LOG_LEVEL`). **Request correlation READY (local evidence):** one id on normal, handled-error, 429 and **unhandled-500** responses and on their log records (PR-001R F1: the exception is logged once, under the id, and the client gets a generic 500 with `X-Request-ID`); concurrency-tested. Alembic self-migration no longer wipes logging (F5). Gap: no log shipping/retention; uvicorn access log still plain text |
| 8 | Metrics | **PARTIAL** | Prometheus `/metrics` (HTTP, DB, rate limit, notifications, search, reveals). PR-003 adds, with bounded labels only: client deadlines by operation, 503s by database reason, worker passes / failure streak / next-pass-due, pool connections in use / capacity, thread-pool tokens in use / total. Gap: **`/metrics` is served publicly on the app port** — must be restricted to the internal network at ingress before production (DATA-001 proposal also notes business counters on it) |
| 9 | Errors | **PARTIAL** | Unhandled errors → generic 500, traceback in logs with request id. Gap: no error tracking service (none chosen; none activated) |
| 10 | Monitoring | **PARTIAL** | Prometheus + Alertmanager config and rules, promtool-tested in CI (17 rules). `NotificationBacklogGrowing` counts the database-wide backlog once across replicas (PR-001R F6). PR-003: worker liveness (`WorkerOverdue` — a hung or dead worker stops moving its next-pass-due time; `WorkerFailing`), `DatabaseStoppedAnswering`, `DatabaseWriteOutcomeUnknown`. Gap: several rules watch dormant booking/payment metrics; no rules for backups, restore verification, disk |
| 11 | Alerting | **MISSING** | Alertmanager routes to a local HTTP sink only. No real destination (chat/e-mail/pager) — founder decision |
| 12 | Backup | **PARTIAL** | Scripts (`backend/scripts/backup/`: pg_dump custom → gzip → AES-256 → sha256) refuse the published key. Gap: no scheduled job, no offsite target, no retention, no backup of media files |
| 13 | Restore drill | **PARTIAL** | Mandatory on every CI build (PR-001R F7: `HOMIES_REQUIRE_RESTORE_DRILL=1` turns missing `pg_dump`/`pg_restore`/database into a red run; skips are listed with `-rs`): legacy drill (`test_dr_restore_pg.py`) and Phase-1A drill (`test_dr_restore_phase1_pg.py`). Disposable databases only — see BACKUP-RESTORE.md for what this does not prove |
| 14 | RPO / RTO | **MISSING** | **CANONICAL DECISION REQUIRED** (§4) |
| 15 | Rollback | **PARTIAL** | Explicit per-release rollback declaration and a machine check (PR-002, RELEASE-AND-MIGRATION.md); runbook outline §5. Gap: no image registry, no staging rehearsal; several destructive downgrades |
| 16 | Staging | **MISSING** | No staging environment |
| 17 | Smoke test | **PARTIAL** | Local production-image smoke matrix (PR-001R, §6). Gap: no scripted post-deploy smoke test against an environment |
| 18 | Load / capacity | **NOT ASSESSED** | Only diagnostic EXPLAIN on ~5 000 synthetic listings (TASK-013 branch) |
| 19 | Security | **PARTIAL** | Independent audits of the foundation and each slice; rate limiting; privacy tests; pip-audit; gitleaks. Gap: no external penetration test, no TLS/ingress config, no WAF decision |
| 20 | Incident runbook | **PARTIAL** | `INCIDENT-RUNBOOK.md` (PR-001) + `docs/runbooks/dr-database-recovery.md`. Gap: no on-call, no contacts, never rehearsed |

## 2. Configuration inventory

Read by `app/core/config.py` (pydantic-settings; variable = field name upper-cased;
unknown variables are ignored).

| Variable | Class | Required outside dev | Notes |
|---|---|---|---|
| `ENV` | public | yes | the production image defaults to `production` (PR-001R F3); `local` (config default for a developer shell, announced by a startup warning when implicit; compose sets it explicitly) self-migrates; `test`/`ci` exempt from secret checks; anything else is production-like |
| `DATABASE_URL` | **secret** (password) | **yes** (repository dev configurations refused, PR-001/PR-001R F4) | application role `homies_app` (`backend/app/core/sql/app_role.sql` + `app_grants.sql`), not the owner |
| `ALEMBIC_DATABASE_URL` | **secret** | for the migration job | migration role `homies_migrator` (`backend/app/core/sql/migration_role.sql`); read by `app/scripts/migrate.py` and `alembic/env.py` |
| `DB_CONNECT_TIMEOUT_SECONDS`, `DB_POOL_TIMEOUT_SECONDS`, `DB_LOCK_TIMEOUT_MS`, `DB_STATEMENT_TIMEOUT_MS`, `DB_IDLE_IN_TRANSACTION_TIMEOUT_MS`, `DB_CLIENT_CONNECTION_CHECK_INTERVAL_MS`, `DB_CLIENT_GRACE_SECONDS` | public | no (defaults 3 s, 5 s, 2000, 5000, 60000, 2000, 2 s) | PR-003 deadline policy (D-89); an unworkable combination refuses startup. `client_connection_check_interval` needs a Linux PostgreSQL ≥ 14 (0 disables) |
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

Release and migration compatibility (PR-002, candidate):
[RELEASE-AND-MIGRATION.md](RELEASE-AND-MIGRATION.md).

* `ENV=local`: the app runs the migration job on boot (same locked runner as a
  deploy), then requires the exact head (developer convenience only).
* every other environment: the app **evaluates compatibility** of its release
  manifest and migration graph with the database revision and
  `schema_lineage` — allowed: exact head, a supported older revision (within
  `minimum_schema`), or a newer one reached only through EXPAND/SAFE steps;
  everything else refuses to start. It then refuses an application role that
  can rewrite append-only tables (B5) or change the schema / write
  `alembic_version`, `schema_lineage`, `spatial_ref_sys` (PR-002).
* Migrations are a separate, single deploy step: `python -m
  app.scripts.migrate` from the release image, as the migration role
  (`ALEMBIC_DATABASE_URL`), under a session-level advisory lock held by the
  migrating connection and acquired within a 10 s budget enforced by the job
  (`pg_try_advisory_lock` + monotonic deadline). Existing pre-PR-002 databases
  first need the DBA's one-time `migration_owner.sql`. The image refuses to
  start outside `local/test/ci` without an injected build identity.
  CI runs it on every build. No staging or production pipeline runs it yet.

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
| Application code | Redeploy the previous image — only when the new release's manifest declares `rollback_to_previous = SAFE` **and** the previous image's `release check` against the live database is allowed (PR-002, N−1 only). Images are reproducible from a commit; no registry/tags exist yet | Roll back by image, not by rebuilding |
| Database schema | Never downgraded automatically; forward-fix preferred. Several downgrades destroy data (MIGRATION-ROLLOUT.md). **`git revert` is not a database rollback** | Restore from backup or ship a forward migration |
| Configuration | Environment variables only; no versioned config store | Keep the previous environment set with each release record |

The former blocking interaction (exact-head startup made every rollback and
rolling deploy refuse) is replaced by the PR-002 model. When a release
declares `rollback_to_previous = BLOCKED` — PR-002 itself and TASK-014 do —
restarting the previous image is not a recovery path: forward repair, or a
restore to the recovery point recorded before the migration.

Rollback outline (to rehearse on staging, never yet executed):
1. Freeze deploys; record current image tag, DB revision, env set.
2. `rollback-allowed` on the current image and `release check` with the
   previous image → both exit 0: redeploy the previous image; verify
   `/readyz`, smoke test.
3. Otherwise → forward-fix, or restore (BACKUP-RESTORE.md).
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

## 6a. Evidence from PR-001R (local, disposable)

* Full suites on Python 3.12.14: see the PR-001R report (SQLite and
  PostgreSQL 16.4 / PostGIS 3.4.3, restore drills mandatory).
* Production image `ENV=production` by default; all 37 installed packages at
  exactly their `constraints.txt` pins. Smoke matrix: no `ENV` + no secrets →
  refused; no `ENV` + the dev credentials spelled differently → refused
  (`DATABASE_URL`); a superuser application role → B5 refusal; `homies_app`
  with secrets → started (JSON logs, no secret in the output); explicit
  `ENV=local` on an empty database → migrated and kept logging.
* Real `docker pause` of the database after warming the pool: `/readyz` 503 in
  ~2.04 s (×3), `/healthz` 200, recovery 200; `docker stop`: 503 in ~2.3–2.8 s
  on the builder's machine — PR-001RA measured 3.8–4.0 s (Docker DNS resolving
  a stopped container), recovery 200. A business request on the frozen database still hangs on the
  warm pool (not in PR-001R scope — see known debt).
* A business request with the database stopped: generic 500 carrying the
  caller's `X-Request-ID`, and one ERROR log record with the same id.
* `pip-audit -r constraints.txt --no-deps --disable-pip`: no known
  vulnerabilities; the canary `urllib3==1.26.4` is flagged (9 advisories),
  while an unpinned `urllib3>=1.26.4` resolves to a clean release — the
  failure mode of the old `pip-audit .`.

## 6b. PR-001R2 (after PR-001RA)

* RA-1: the readiness contract is stated as a **decision budget** plus measured,
  finite end-to-end bounds (row 6); no universal wall-clock guarantee is claimed.
  New PostgreSQL regression: the server freezes after the connection is
  established, with the query in flight (and the cancel request frozen too) →
  `/readyz` 503 in 13.0 s; it fails (hangs past its bound) when the decision
  deadline is removed — PR-001RA mutation m12 now killed.
* RA-2: the dependency-audit canary passes only when pip-audit's JSON report
  lists `urllib3==1.26.4` with a PYSEC/GHSA/CVE advisory
  (`backend/scripts/ci/audit_canary.py`); an advisory-lookup failure fails it
  (verified without network: exit 1).
* RA-3 (health endpoints starved by hung business requests): **PR-003 debt, not
  fixed here.**

## 6c. PR-003 — database failure containment (candidate, local, disposable)

Phase A probe kit (production image, `ENV=production`, `homies_app`, a
controllable proxy and direct runs) before and after; fault suite
`tests/test_db_deadlines_pg.py`. What is bounded now, and what is not:

* every application database wait (connect, pool, lock, statement, a server
  that does not answer) — client deadline 7 s, worst case for one request on a
  frozen server ≈ pre-ping 7 s + reconnect 3 s;
* startup and release checks — the bounded engine;
* health, readiness, metrics — independent of the thread pool;
* **not** bounded by PR-003: the migration job's connect/statements (PR-002,
  job-runner timeout required), DNS resolution (OS resolver), the server's own
  work after a client vanished beyond `client_connection_check_interval`.
* An abandoned COMMIT is outcome-unknown; non-idempotent creates can be
  duplicated by a client retry (debt; `DatabaseWriteOutcomeUnknown`).

## 7. Next production tasks (proposed)

PR-002 release and migration compatibility (candidate: manifest, lineage,
migration job, roles); PR-003 database client deadlines / failure containment;
then staging environment + deploy pipeline + smoke test; alerting destination
+ backup scheduling/offsite + restore rehearsal against staging;
PR-005 ingress (TLS, `/metrics` restriction, proxy hops), error tracking;
PR-006 load/capacity baseline.
