# PR-001A — Independent audit of PR-001 (CI, runtime, production-readiness baseline)

- Audited SHA: `4416e2b14b007ba50aab41cad8e23deea32c4678` (branch `claude/PR-001-ci-runtime-readiness`)
- Base: `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe`. PR-001 = `0d85331` + `4416e2b`.
- HEAD verified exact, working tree clean. Audit ran in a detached worktree
  (`homies-audit-evidence/PR-001A/wt`) on disposable Docker infrastructure
  (`pr001a-*` images, network `pr001a-net`, DBs `pr001a-db`, `pr001a-db2`).
- No source modified, no commit, no push, no deploy, no production access.
- Evidence: `homies-audit-evidence/PR-001A/evidence/`; probes: `.../probes/`.

## Verdicts

```
PYTHON_312                 = ACCEPTED
DEPENDENCY_REPRODUCIBILITY = ACCEPTED
CI                         = NEEDS_FIX   (F2; P3 F7, F10)
DOCKER                     = NEEDS_FIX   (F3 — no ENV default; P3 F8)
STARTUP_SECURITY           = NEEDS_FIX   (F3; P3 F4)
REQUEST_ID                 = NEEDS_FIX   (F1)
LOGGING                    = ACCEPTED    (P3 F5; NOTE N2, N3)
HEALTH_READINESS           = NEEDS_FIX   (F11 — pre-existing, but "bounded" is false and row 6 says READY)
RESTORE_DRILL              = ACCEPTED    (local restore drill accepted; production DR NOT proven)
ALERT_RULES                = ACCEPTED    (P3 F6)
INFRA_CLEANUP              = ACCEPTED    (NOTE N5)
DOMAIN_REGRESSION          = ACCEPTED
```

**PR_001_REQUIRES_TARGETED_FIXES**

PRODUCTION READINESS: **NOT READY**
DEPLOYMENT: **NOT DEPLOYED**

No P0 and no P1. Four P2s. F1, F2 and F3 are small and inside PR-001's own scope: its claims, its Dockerfile, its pinning.
F11 is pre-existing. The minimum acceptable action is to fix it or downgrade matrix row 6 to PARTIAL with recorded debt;
that choice belongs to the founder.

## Tests actually run (all on disposable infrastructure, Python 3.12.14)

| Gate | Result | Evidence |
|---|---|---|
| Image builds (`--no-cache --pull`), test + production | both exit 0 | `build-*.log` |
| Installed set vs `constraints.txt` | test 70/70 exact; prod 37 runtime exact, no dev deps | `test-image-freeze-compare.txt`, `prod-image.txt` |
| `alembic heads` single-head gate | `heads=1` | `gates-sqlite.log` |
| ruff 0.15.22 | All checks passed | `gates-sqlite.log` |
| mypy 2.3.0 | Success, 88 files | `gates-sqlite.log` |
| OpenAPI drift | up to date | `gates-sqlite.log` |
| Full SQLite suite (no `TEST_DATABASE_URL`) | **787 passed, 292 skipped** | `gates-sqlite.log` |
| CI-equivalent migrate base→head + PG16/PostGIS asserts | PG 16.4, PostGIS 3.4.3, head `b8d0f2a4c6e8` | `gates-pg.log` |
| Full PostgreSQL/PostGIS suite, run #1 (coverage) | 3 failed / 1075 passed / 1 skipped, branch coverage 91.4% — **discarded**: it ran concurrently with my `ALTER ROLE homies_app` and a drill matrix on the same server, and my `tail` cut the failure names | `gates-pg.log` |
| Full PostgreSQL/PostGIS suite, run #2 (fresh DB server, quiet) | **1078 passed, 1 skipped** (Stripe live not requested) | `gates-pg-rerun.log` |
| Both restore drills, verbose | pass | `gates-pg.log` |
| Drill instrumentation + 7-sabotage matrix | 7/7 killed, baseline passes | `drill-mutations.log` |
| promtool config / rules / unit tests; amtool | SUCCESS (13 rules) | `promtool.txt` |
| Extra promtool semantics (scratch) | SUCCESS | `promtool-pr001a-extra.txt` |
| Startup security matrix (11 container runs) | see Startup detail | `rt-cases-1.txt`, `rt-*.log`, `probe-config.txt` |
| Request-id ASGI + real-HTTP + concurrency | see Request-id detail | `probe-rid-*.txt`, `rt-probeapp*` |
| Health fault injection (pause/stop, cold and warm pool) | see F11 | `health-probes*.txt` |
| pip-audit `.` and `-r constraints.txt` | both "No known vulnerabilities" today | `pip-audit.txt` |
| GitHub Actions | run 36395679602 exists, success (metadata only; logs 403) | `gha-run.json`, `gha-jobs.json` |

## Findings

### P0 — none
### P1 — none

### P2

**F1 — Unhandled 500s lose the request id (response and traceback); the readiness matrix says the opposite.**
`backend/app/core/request_id.py:50-58`, `docs/production/PRODUCTION-READINESS.md` §1 row 9.
The middleware sets the header only after `call_next` returns. An unhandled exception propagates through it
(the `finally` resets the contextvar first), so Starlette's `ServerErrorMiddleware` sends a 500 **without
`X-Request-ID`**. uvicorn logs the traceback on `uvicorn.error` in plain text, which is outside the context
and outside the JSON handler, so the traceback carries **no request id**.
Evidence: ASGI probe `boom: status=500 x-request-id-on-response=[]`; real uvicorn `boom status=500 x-request-id=None`;
`rt-probeapp.log` shows the app's own pre-failure log line with `request_id: boom-http-000001` but the
`Exception in ASGI application` traceback as plain text with no id. Row 9 claims "traceback in logs with request id".
This is the failure class correlation exists for. It is not a regression: 500s had no id before. But PR-001 claims the capability.
Repair: in the middleware, catch `Exception`, `log.exception(...)` while the id is still set, and return a generic 500
that carries the header. Or keep the id in `scope["state"]` and add an `Exception` handler. Add a test for the 500 path.
Correct row 9. No canonical decision required.

**F2 — The CI dependency audit does not audit the pinned set that CI and the images install.**
`.github/workflows/ci.yml` step "Dependency audit" runs `python -m pip_audit .`. pip-audit's project source
(`pip_audit/_dependency_source/pyproject.py:92-97`) writes the `pyproject` dependencies into a temporary requirements
file and installs them into a **fresh venv without `constraints.txt`**. So it audits the newest resolvable versions.
Today these equal the pins, and both `pip-audit .` and `pip-audit -r constraints.txt` report "No known vulnerabilities".
The first upstream security release breaks the equality. At that point the audit checks the fixed version and passes,
while the images keep shipping the vulnerable pin. Pinning was introduced by PR-001, so PR-001 created this gap.
Repair: audit the shipped set with `pip-audit -r constraints.txt`, or `pip-audit -l` in the installed environment,
in addition to or instead of `.`.

**F3 — Absent `ENV` fails open. The production image sets no `ENV`, so a container started without it runs as `local`.**
`backend/app/core/config.py:12` (`env = "local"`), `:203` (dev no-op), `backend/app/core/schema.py:69,106`, `backend/Dockerfile`.
With `ENV` unset, `Settings().env == 'local'`. That skips SEC-02 secret validation, skips PR-001's new
`DATABASE_URL` guard and skips the B5 ledger-privilege check, and the app self-migrates.
Evidence:
- `c5b`: no `ENV`, owner role, repository dev JWT/webhook secrets → **started and served** (`/healthz` → `{"env":"local"}`, `/v1/classifieds` 200).
- `c5a`: no `ENV`, no `DATABASE_URL` → it tried to self-migrate the repository dev URL (`localhost:5433`). That is the exact thing the PR-001 guard exists to refuse.
- `ENV=''` (set but empty) is correctly refused.
The default is pre-existing (not a PR-001 regression). But it bypasses PR-001's own claim that a
"production-like env refuses the development `DATABASE_URL`", and the Docker item "the container does not silently use a development DB".
PRODUCTION-READINESS §2 lists `ENV` as "required outside dev" but nothing enforces that.
Impact if deployed this way: forgeable tokens (published dev JWT secret), owner role, self-migration.
Repair (targeted): `ENV ENV=production` in `backend/Dockerfile` (compose and dev set `ENV=local` explicitly already),
and/or refuse to start when `ENV` is not explicitly set. Plus a test.

**F11 — `/readyz` is not bounded against a hung database when idle pooled connections exist. The readiness matrix rates Health READY.**
`backend/app/core/health.py:66-82`, `backend/app/core/db.py:30-34` (`pool_pre_ping=True`), `PRODUCTION-READINESS.md` §1 row 6.
Setup: private DB, notification worker disabled, pool warmed to 5 connections, DB container paused (TCP accepted, no response).
Result: **3 of 3 `/readyz` calls hung until the 60 s client cap** (`health-probes-warm-pool.txt`). They recovered instantly on unpause.
Why: `pool_pre_ping` pings an established pooled connection with no client-side timeout. `connect_timeout=3` bounds only new
connections, and `SET LOCAL statement_timeout` is server-side, so a frozen server or a network partition never enforces it.
The first run looked bounded (~3 s) only because the worker thread held the single pooled connection, so the probe opened a
fresh connection bounded by `connect_timeout` (`health-probes.txt`). A stopped DB → 503 in ~3.9 s. `/healthz` stays 200 throughout.
The body carries the class name only, never the DSN.
Pre-existing: `health.py` and `db.py` are unchanged by PR-001. But PR-001 marks row 6 READY on evidence that does not cover this case,
and the module promises the probe "must fail fast" so it cannot exhaust the pool. Here each hung probe holds a pool connection and a worker thread.
Repair: give the probe a dedicated `NullPool` engine (fresh connect bounded by `connect_timeout` + `statement_timeout`), and/or set
libpq `tcp_user_timeout` and keepalives in `_connect_args` so every pooled read is bounded. Or, at minimum, downgrade row 6 to
PARTIAL and record the debt.

### P3

**F4 — The `DATABASE_URL` guard is a literal string compare.** `config.py:225`. It refuses only the exact default. These all
pass validation: `127.0.0.1` instead of `localhost`, `LOCALHOST`, `?connect_timeout=5`, a trailing `?`, an upper-case
scheme, the compose URL `homies:homies@db:5432/homies`, the CI URL, and a %-encoded user. The last five carry the
published password `homies`. `c7` shows `127.0.0.1:5433` passing validation and proceeding to connect. Leading or
trailing whitespace also passes the check but then fails parsing or connecting (fail-closed in effect). It meets the stated
intent (catch "unset"). It is not a general dev-URL refusal. Repair: parse with `make_url`, refuse the published dev
password or loopback/compose hosts outside dev, and word the docs accordingly.

**F5 — `ENV=local` self-migration wipes PR-001 logging, and startup errors become silent.** `alembic/env.py`
`fileConfig(alembic.ini)` uses `disable_existing_loggers=True`. After `ensure_schema()` the root logger is WARNING with a plain
formatter, the JSON handler is gone, and `homies.*` and `uvicorn.*` are disabled (`probe-local-logging.txt`). `c5a` exited
with code 3 and **printed no traceback**. Local only, but it compounds F3.
Repair: `fileConfig(..., disable_existing_loggers=False)`, and skip `fileConfig` when invoked programmatically.

**F6 — `NotificationBacklogGrowing` semantics.** Metric names, label values (`pending|failed`, lower-case, match `worker.py`),
the strict `> 100`, and `for: 15m` are all correct. Scratch promtool tests confirm: 100 never fires, 101 fires at 15m (not 14m),
processing/dead/delivered are excluded, and `sum()` drops labels so there is no cardinality risk. Two issues:
(a) the gauge is refreshed only inside the worker loop (`worker.py:133`). A **stopped** worker freezes it, and a disabled worker
never creates the series. The rule comment "A stopped ... worker shows up here" is wrong. The runbook correctly says
"no worker heartbeat metric".
(b) Every API replica runs its own worker and publishes the **DB-wide** count, so `sum()` multiplies by the replica count.
A promtool test proves 2 replicas × 60 real rows fires as "120 notifications waiting".
Repair: `sum(max by (status) (homies_notification_queue_depth{status=~"pending|failed"})) > 100`, a freshness or heartbeat rule, and corrected comment wording.

**F7 — CI could be green with both restore drills skipped.** If `pg_dump` is not on the runner, the "Runtime versions" step
only echoes a message, the drills `skipif`, and `pytest -q` does not print skip reasons. A real run exists
(GHA run 36395679602, push, `4416e2b`, all 5 jobs success). Job logs return HTTP 403 (admin only), so whether the drills ran or
skipped there is **UNKNOWN**. "Executed on every CI build" is therefore unproven.
Repair: fail when `CI=true` and the PG client tools are missing, or add `-rs` plus a guard.

**F8 — Build reproducibility residue.** Build-isolation `setuptools` and `pip` are unconstrained (`-c` does not reach build
isolation). Base images are by tag (documented). The test image's `postgresql-client-16` minor is unpinned. Dependabot's docker
ecosystem already proposes `python:3.14-slim` (remote branch `dependabot/docker/backend/python-3.14-slim`), and the `image` CI
job does not assert that the image's Python is 3.12. Merging that PR would silently move production off the tested runtime.
Repair: a dependabot `ignore` for Python major/minor bumps plus an image-job assert of `python -V`.

**F9 — Canonical document damage.** `docs/canonical/IMPLEMENTATION-CONVERGENCE.md`: the diff **replaced** the heading
`## TASK-012 → TASK-012A → TASK-012R — UTC temporal repair (2026-09-27)` with the PR-001 heading. The TASK-012A/012R
history ("History: TASK-012 candidate …", the finding table) now sits under the PR-001 section. Repair: restore the heading.

**F10 — CI concurrency on `main`.** `group: ci-${{ github.ref }}` with `cancel-in-progress: true`. Groups are per ref, so
unrelated branches cannot cancel each other and a PR (`refs/pull/N/merge`) never cancels its branch push. But a newer push to
`main` cancels the older `main` run, which leaves that commit without a CI record. Repair: `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`.

### NOTE
- N1 `request_id.py:22` uses `re.match` with `$`, which accepts a trailing `\n` (ASGI probe: `abcdefgh\n` is kept and echoed).
  The real uvicorn/httptools parser rejects bare LF/CR/NUL/obs-fold with 400, so it is not exploitable today. Use `fullmatch` or `\Z`.
- N2 uvicorn's own lines (startup, access log, ASGI tracebacks) stay plain text and carry no request id under `LOG_FORMAT=json`.
  A JSON shipper gets a mixed stream. The access log part is documented; the traceback part is F1.
- N3 `LOG_LEVEL=VERBOSE` or an empty `LOG_LEVEL` crashes at import with `ValueError: Unknown level` (exit 1, fail-closed,
  undocumented). An unknown `LOG_FORMAT` silently falls back to text.
- N4 Drill: the guard assertions pin the constraint name only for precision. Status, hierarchy and one-address accept any
  `IntegrityError`/`DBAPIError`. My inspection shows today they hit `ck_classified_offers_status`, `ck_admin_areas_hierarchy`
  and `uq_properties_address_id`. The hierarchy guard exercises "cannot change the level of an area that has children", not
  cycle detection as documented. The "public search" check evaluates `freshness.public_clause`, not the HTTP search endpoint.
- N5 `README.md:14-15` still presents Redis, Meilisearch and NATS as the stack.
- N6 The production image runs as root and carries `build/` and `*.egg-info` leftovers (pre-existing).
- N7 `test_errors_and_rate_limited_responses_carry_the_id_too` never exercises a 429. The probe shows 429s do carry the id.
- N8 The CI service health check uses `pg_isready` over the Unix socket, which can pass during the PostGIS init temp server.
  This is harmless because the first DB use comes minutes later.

## Area verdicts (detail)

- **Python 3.12.** `requires-python >=3.12` is unchanged, and ruff and mypy target 3.12. Both images I built without cache
  (`--no-cache --pull`, base `python:3.12-slim@sha256:f77ac9e4…`) run **Python 3.12.14**. CI uses `setup-python 3.12`. No installed
  distribution declares a `Requires-Python` above 3.12. The distinct specs present top out at `>=3.12`.
- **Dependencies.** Test image: installed set == `constraints.txt` (70/70, 0 version mismatches, nothing unconstrained).
  Production image: 37 runtime distributions, all at the pinned versions. Dev tools (pytest, ruff, mypy, coverage, pip-audit, httpx)
  are **absent**. Key versions actually used: SQLAlchemy 2.1.1, Alembic 1.20.0, psycopg 3.3.6 (binary 3.3.6), FastAPI 0.141.1,
  Starlette 1.7.0, pydantic 2.13.5, pydantic-settings 2.15.0, uvicorn 0.54.0, Pillow 12.3.0, PyJWT 2.15.0, pytest 9.1.1, ruff 0.15.22,
  mypy 2.3.0, pip 25.0.1. SQLAlchemy 2.1.1 + Alembic 1.20.0 + psycopg 3.3.6 worked together: migrations ran base → head on PG 16.4 /
  PostGIS 3.4.3, `MigrationContext`/`ScriptDirectory` verification passed, and the full suites ran. `pip check` is clean.
  `constraints.txt` has CRLF endings in a Windows checkout; pip is indifferent to that.
- **CI.** Static review plus a real run. GitHub Actions run **36395679602** (push, `claude/PR-001-ci-runtime-readiness`,
  `4416e2b`, `success`, jobs backend/image/secrets/monitoring/contracts all success). So `claude/**` matches in practice. The job
  logs are admin-only (403), so step output is not visible to me. `pull_request` and `main` triggers are unchanged. Concurrency is
  per-ref, so it cannot cancel unrelated branches or a PR's merge ref. On `main` it does cancel superseded runs (F10). The PostGIS
  service is digest-pinned and health-gated; Alembic upgrade happens before tests. The single-head gate logic works locally
  (`heads=1`, and it fails on 0 or ≥2). `cache: pip` caches downloads keyed on pyproject **and** constraints, and resolution is still
  enforced by `-c`, so a stale cache cannot substitute a different environment. No `secrets.*` are referenced. Only the
  disposable service password is present. Open items: F2, F7.
- **Docker.** The production image carries `app/`, `alembic/` (24 revisions) and `alembic.ini`. There is no `tests/`, `scripts/`
  or `pg_dump`. `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000`. There is no `ENV` default (F3), and it runs as root (N6). The
  test image `ops/test/Dockerfile.py312` gives 3.12.14 + pg_dump/pg_restore 16.15.
- **Startup/security** (production image against disposable PostGIS):
  - `ENV=production` with no secrets → exit 3, message names fields only.
  - Default `DATABASE_URL` → exit 3 "DATABASE_URL is the repository's local-development default".
  - `ENV=staging` as the owner role → `LedgerPrivilegeError` (B5) listing `audit_log, domain_events, journal_entries, journal_lines`.
  - `ENV=staging` as a restricted role (`ops/sql/app_role.sql` applied) → "schema verified at head b8d0f2a4c6e8", "ledger
    privileges verified", worker started, `/readyz` 200.
  - Across 11 startup logs, no secret value, no password and no `homies:homies` appears.
  - `ENV` spellings: `Production`, ` production`, `production `, `prod`, `staging`, `dev`, `development` and `''` are all strict.
    Only `local`, `test` and `ci` (any case) are exempt.
  - Whitespace-padded secrets are caught.
  - Malformed URLs do not leak the password (`ArgumentError: Could not parse SQLAlchemy URL from given URL string`, int-port `ValueError`, `NoSuchModuleError`).
  - Bypasses: absent `ENV` (F3); equivalent URL spellings (F4).
- **Request id.**
  - Generated ids are 32-hex. A sane caller id (8–64 chars of `[A-Za-z0-9._-]`) is kept.
  - Rejected and regenerated: <8, >64, space, TAB, NUL, CR, CR/LF + injected header, latin-1/UTF-8 high bytes, JSON quote, `%0a`, empty.
  - Duplicate headers: the first wins.
  - The real parser rejects bare LF/CR/NUL/obs-fold with 400. CRLF only ever produces a separate header, never an echoed one.
  - Concurrency: 600 in-process requests (400 async + 200 sync) and 300 real-HTTP requests → **0 header mismatches**. 1000 and
    450 log records → **0 cross-request leaks**. The contextvar is `None` afterwards.
  - 429s carry the id.
  - Gaps: F1 (500s), N1.
- **Logging.** Under `LOG_FORMAT=json` every `homies.*` and `alembic.*` line is valid JSON with `request_id`. INFO is emitted
  ("schema verified…", "ledger privileges verified…", "notification worker started"), and before PR-001 it was dropped. No DSN or
  secret appears. The handler is installed once (the root `_homies_configured` guard). Under `ENV=test` pytest keeps capture.
  Bad `LOG_LEVEL` crashes at import; bad `LOG_FORMAT` falls back to text (N3). uvicorn lines are plain (N2). Gaps: F1 traceback, F5 local wipe.
- **Health/readiness.** `/healthz` is 200 with the DB paused or stopped (no DB dependency). `/readyz` gives 200 when healthy,
  503 in ~2.9 s from a fresh connection to a paused DB, and 503 in ~3.9 s with the DB stopped; it recovers to 200. The body carries
  the class name only, and `homies_database_up` is set to 0. **Unbounded with warm idle pooled connections (F11).**
  `/metrics` is public: PRODUCTION-READINESS row 8 and §7 (PR-005) record it as a **gap to close before production**, not as
  accepted design.
- **Restore drill** (`test_dr_restore_phase1_pg.py`). The unmodified drill passes (13.6 s).
  - Instrumented: all 16 compared tables are non-empty in the source (countries 1, geo_sources 6, admin_areas 8, localities 3,
    geo_areas 1, geo_external_refs 11, addresses 3, properties 3, spaces 3, classified_offers 3, listing_price_components 6,
    legal_parties 1, person_legal_parties 1, property_authorities 3, property_authority_scopes 15, attribute_definitions 22).
  - `exact_geog` and `public_geog` are non-null `GENERATED ALWAYS` columns.
  - The restore target is a new database from template1. `alembic_version` equals the source head and the script head.
  - Each guard trips its intended constraint or trigger.
  - Sabotage matrix, applied to the restored copy: **7/7 killed**. Skip restore → `alembic_version` missing. Drop the hierarchy
    trigger, the status CHECK, the unique address, the precision CHECK or the GiST index → the drill fails. Delete
    `property_authority_scopes` → row mismatch.
  - No false-positive path found. Weaknesses are recorded as N4.
  - **Local restore drill accepted. Production DR is NOT proven**: no scheduled backup, no offsite copy, no PITR, no
    production-volume timing, no media, no roles or grants. BACKUP-RESTORE.md states this correctly.
- **Alert rules.** `promtool check config`: SUCCESS. `check rules`: 13 rules, SUCCESS. `test rules homies.rules.test.yml`: SUCCESS.
  `amtool check-config`: SUCCESS (prom/prometheus v2.55.1, alertmanager v0.27.0). The scratch extra tests pass (boundary, duration,
  exclusions, replica sum, absent series). Semantic issues: F6.
- **Redis/Meilisearch/NATS.** No reference remains in `backend/app`, `alembic`, `ops/` (compose, monitoring), `pyproject`,
  constraints, the Makefile, Dockerfiles or CI, apart from the removal comments. Two historical sentences in `ratelimit.py` are
  comments only. The Settings fields are removed. Unknown env vars `REDIS_URL`, `MEILI_URL`, `MEILI_MASTER_KEY` and `NATS_URL` are
  ignored at startup (verified). Remaining mentions are historical or deferred-architecture docs (charter, reviews, ADRs, canon 03/04,
  convergence) and `README.md` (N5). Removal is acceptable.
- **Scope protection.** PR-001 changes 5 files under `backend/app`: `composition.py` (+middleware), `core/config.py` (−4 unused
  fields, +DATABASE_URL check), `core/logging_config.py` (new), `core/request_id.py` (new) and `main.py` (+configure_logging).
  `app/modules/**`, `alembic/**`, `health.py`, `db.py` and `schema.py` are unchanged, so there is no change to authentication, payments,
  Property/Space/Listing, public privacy or pricing. The test changes only add tests; `test_sec02` `_cfg` gains a non-default
  `database_url`. The OpenAPI drift check is clean.

## CHATGPT HANDOFF

- **SHA audited:** `4416e2b14b007ba50aab41cad8e23deea32c4678` (branch `claude/PR-001-ci-runtime-readiness`; base `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe`). Exact HEAD, clean tree, detached worktree. Nothing modified, committed, pushed or deployed. No production access.
- **Result:** `PR_001_REQUIRES_TARGETED_FIXES`. PRODUCTION READINESS: NOT READY. DEPLOYMENT: NOT DEPLOYED.
- **P0:** none. **P1:** none.
- **P2:**
  - F1: unhandled 500 → no `X-Request-ID` on the response, and the traceback is logged by `uvicorn.error` in plain text without the id. The readiness matrix row 9 claims the opposite.
  - F2: CI `pip-audit .` re-resolves unconstrained latest versions, not the pinned `constraints.txt` that CI and the images ship.
  - F3: absent `ENV` → `local`. Secret, `DATABASE_URL` and B5 checks are skipped and the app self-migrates. The production Dockerfile sets no `ENV`. Pre-existing default, but it bypasses PR-001's own guard.
  - F11: `/readyz` hangs (≥60 s) when the DB is frozen and idle pooled connections exist, because `pool_pre_ping` has no client timeout. Pre-existing; the matrix row 6 says READY.
- **P3:**
  - F4: the `DATABASE_URL` guard is a literal compare (127.0.0.1, query string, compose and CI URLs pass).
  - F5: `ENV=local` self-migration (`alembic fileConfig`) wipes PR-001 logging and silences startup errors.
  - F6: the notification alert is blind to a stopped worker (gauge refreshed only by the worker) and `sum()` multiplies across replicas.
  - F7: CI can go green with the drills skipped (no `pg_dump` → skip; logs unverifiable).
  - F8: setuptools, pip and base-image residue; Dependabot proposes `python:3.14-slim`; the image job does not assert Python 3.12.
  - F9: `IMPLEMENTATION-CONVERGENCE.md` lost the TASK-012→012A→012R heading.
  - F10: `cancel-in-progress` also cancels superseded `main` runs.
- **NOTE:** N1 request-id regex `$` accepts a trailing `\n` (ASGI only; the real parser rejects it). N2 uvicorn lines are plain text. N3 a bad `LOG_LEVEL` crashes. N4 drill guards are not name-pinned; "public search" is the visibility predicate only. N5 README still lists Redis/Meili/NATS. N6 the image runs as root. N7 the request-id test named "rate_limited" never sends a 429. N8 the CI `pg_isready` runs over the Unix socket.
- **Accepted:**
  - Python 3.12.14 runtime.
  - Constraints exact (SQLAlchemy 2.1.1 / Alembic 1.20.0 / psycopg 3.3.6 compatible).
  - Request-id isolation under concurrency: 900 requests, 1450 log records, 0 leaks.
  - JSON logging with no secrets.
  - Startup refusals with named fields and no values; restricted role starts; owner role refused (B5).
  - Restore drill genuine (7/7 sabotages killed) — **local restore drill accepted; production DR NOT proven**.
  - promtool green; Redis/Meili/NATS removal complete in runtime paths.
  - No domain changes (auth, payments, Property/Space/Listing, privacy, pricing untouched).
- **Tests actually run:**
  - SQLite: 787 passed / 292 skipped.
  - PostgreSQL 16.4 / PostGIS 3.4.3: 1078 passed / 1 skipped (clean rerun); run #1 was contaminated by my own concurrent role changes and is discarded.
  - ruff, mypy, OpenAPI drift, and the single-head gate all pass.
  - promtool/amtool pass, plus the scratch semantics tests.
  - 11 production-image startup runs; request-id ASGI, real-HTTP and concurrency probes; health fault injection; drill sabotage matrix; pip-audit ×2.
  - GitHub Actions run 36395679602 exists (success), but its logs were not readable (403).
- **Known debt (unchanged by this audit):**
  - `/metrics` is public (a gap to close before production).
  - No alert destination, no scheduled or offsite backup, no PITR, no RPO/RTO decision.
  - The exact-head startup check blocks rollback and rolling deploys (a decision is required).
  - No staging, no deploy or migration job, no error tracking, no load baseline, base images by tag, image runs as root.
- **Re-audit scope after fixes:** F1, F2, F3, and F11 (fixed or row 6 downgraded), plus any P3s taken. Probes in `homies-audit-evidence/PR-001A/probes/` are reusable. Isolate `homies_app` from concurrent suites; use `pr001a_role.sql` (a renamed role) for runtime probes.
