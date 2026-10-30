# System passport — Homies (DEVOPS-FOUNDATION-001 Gate B)

A source-linked inventory of what the repository actually contains and what a
deployment of it needs. **Documentation only: nothing here is deployed,
provisioned or certified.** Production state: **NOT READY / NOT DEPLOYED**.

* Volatile status (`main`, CI, authorisations): [PROJECT-STATUS](../PROJECT-STATUS.md) — this page does not repeat it.
* Authority and phases: [00-AUTHORITY](../canonical/00-AUTHORITY.md), [02-BUSINESS-LOGIC](../canonical/02-BUSINESS-LOGIC.md), [03-SYSTEM-ARCHITECTURE](../canonical/03-SYSTEM-ARCHITECTURE-v1.1.md).
* Readiness gaps: [PRODUCTION-READINESS](PRODUCTION-READINESS.md). Release policy: [RELEASE-AND-MIGRATION](RELEASE-AND-MIGRATION.md).

Evidence markers: **VERIFIED** — read in the source at the inventory SHA;
**PROPOSED** — a design recommendation, not implemented; **UNKNOWN** — must be
established before relying on it. VERIFIED source is not a running system.

Inventory SHA: `4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4` (2026-10-30).

## 1. What runs in Phase 1A

Long-term residential rental marketplace (02): search and map, listing,
saved listings and searches, conversation, viewing request, provider
confirm/decline, reports and moderation, freshness. No money is collected in
Phase 1A. Booking, payments, ledger and the short-stay `listings` module are
`LEGACY_DORMANT` and are not routed or started by `create_phase1_app()`
([composition.py](../../backend/app/composition.py)).

## 2. Components

| Component | Source | Runtime | Evidence |
|---|---|---|---|
| Public web + BFF | [frontend/web](../../frontend/web) — Next.js 16.3.8, React 19.3.0, Node `>=24 <27` (`.nvmrc` 24) | `next build` / `next start`; server-rendered, not static files | VERIFIED [package.json](../../frontend/web/package.json) |
| API | [backend/app](../../backend/app) — Python 3.12, FastAPI, SQLAlchemy 2, uvicorn | `uvicorn app.main:app --no-proxy-headers` on port 8000 | VERIFIED [backend/Dockerfile](../../backend/Dockerfile) |
| Background workers | notification (outbox), saved-search alerts, listing freshness | **Inside the API process**, started by the FastAPI lifespan when their flag is on. No standalone worker executable exists | VERIFIED [composition.py](../../backend/app/composition.py) `phase1_workers()` / `lifespan` |
| Database | PostgreSQL 16 + PostGIS 3.4 (+ `btree_gist`), Alembic | one operational database (03) | VERIFIED CI image `postgis/postgis:16-3.4` |
| Migration job | `python -m app.scripts.migrate [--plan] [--allow-barrier]` | one-off process from the release image, as `homies_migrator` | VERIFIED [migrate.py](../../backend/app/scripts/migrate.py) |
| Release identity | [release.json](../../backend/app/release.json), build arg `GIT_SHA` → `HOMIES_BUILD_SHA` | `python -m app.scripts.release manifest\|check\|rollback-allowed` | VERIFIED |
| Media | `GET /v1/media/{id}` (public, no auth, `Cache-Control: public, max-age=300`); bytes under `MEDIA_ROOT` (local disk) | API | VERIFIED [media/router.py](../../backend/app/modules/media/router.py), [media/storage.py](../../backend/app/modules/media/storage.py) |
| Health | API `/healthz` (liveness, no DB), `/readyz` (DB readiness, 503 on failure); web `/healthz` (process only) | | VERIFIED |
| Metrics | API `GET /metrics` (Prometheus), **unauthenticated on the application port** | must be private at ingress | VERIFIED [composition.py](../../backend/app/composition.py) |
| Monitoring config | [ops/monitoring](../../ops/monitoring) — Prometheus, Alertmanager (local sink only), rules tested in CI | | VERIFIED; no real alert destination |
| Backup tooling | [backend/scripts/backup](../../backend/scripts/backup) — `backup.sh`, `restore.sh`, `dr_drill.sh` | scripts; not scheduled anywhere | VERIFIED; see [BACKUP-RESTORE](BACKUP-RESTORE.md) |
| Local stack | [ops/docker-compose.yml](../../ops/docker-compose.yml) — `ENV=local`, published development credentials | developer machine only | VERIFIED; **not a deployment template** |
| CI | [.github/workflows/ci.yml](../../.github/workflows/ci.yml) — `backend`, `image`, `secrets`, `monitoring`, `contracts`, `web` | GitHub Actions; builds the API image but **does not publish it** | VERIFIED |
| Mobile, admin web | canon 03 §3 direction (Expo app; separate admin Next.js app) | **not built** | VERIFIED absence |

Not present (VERIFIED): a web Dockerfile, an image registry, a deploy job,
infrastructure-as-code, Kubernetes manifests (03 §8 keeps Kubernetes deferred).

## 3. Process model

* One API process = HTTP server **plus** whichever workers its flags enable.
  Defaults: `NOTIFICATION_WORKER_ENABLED=true`, `SAVED_SEARCH_WORKER_ENABLED=true`,
  `LISTING_FRESHNESS_WORKER_ENABLED=false` ([config.py](../../backend/app/core/config.py)).
  So every API replica started with defaults runs two workers.
* All three claim work with `FOR UPDATE SKIP LOCKED` (worker docstrings), so
  duplicate workers do not duplicate delivery; they waste polling and make
  behaviour harder to reason about. PROPOSED placement: workers off on serving
  replicas, on in exactly one non-ingress instance of the same image
  ([STAGING-ARCHITECTURE §4](STAGING-ARCHITECTURE.md#4-worker-placement)).
* The lifespan validates configuration and the schema **before** starting
  workers; a worker instance needs no inbound HTTP request to start.

## 4. Environments

| | Local | Private alpha (PROPOSED) | Future staging (PROPOSED) | Production |
|---|---|---|---|---|
| Purpose | development | founder tests the real app in a browser | production-like release rehearsal | real users |
| Data | throwaway | **synthetic only** | synthetic | real |
| Hosting | developer machine | one EU VPS, Docker Compose, Caddy | EU container hosting, private networking, managed PostgreSQL | not designed |
| Status | exists | design only | design only | **does not exist** |

Detail: [STAGING-ARCHITECTURE](STAGING-ARCHITECTURE.md). Variables:
[ENVIRONMENT-MATRIX](ENVIRONMENT-MATRIX.md). Procedure:
[STAGING-RUNBOOK](STAGING-RUNBOOK.md). Gates:
[DEPLOYMENT-CHECKLIST](DEPLOYMENT-CHECKLIST.md).

## 5. Schema and release facts at the inventory SHA

* 30 Alembic revisions, one head `23e89acb98b4`; 7 steps are BARRIER (6
  historical in [lineage_registry.py](../../backend/app/core/lineage_registry.py), plus `23e89acb98b4`).
* Release manifest: BP-5, `schema_transition = BARRIER`,
  `rollback_to_previous = BLOCKED` — recovery is forward repair only.
* A fresh production-like database therefore needs `--allow-barrier`
  ([RELEASE-AND-MIGRATION §8](RELEASE-AND-MIGRATION.md#8-deployment-patterns-with-homies-examples); CI does the same).

## 6. Security-relevant facts

* Sessions: BFF keeps the token pair in `__Host-hm_at` / `__Host-hm_rt`
  httpOnly Secure cookies; CSRF on every mutating BFF route; `/bff/v1/*` is
  an allowlisted proxy ([frontend/web/src/server](../../frontend/web/src/server)).
* Known session gaps (VERIFIED; Task Contract SEC-SESSION-001 is prepared on
  its own branch, `docs/tasks/SEC-SESSION-001-session-lifecycle.md`, and is
  not part of this change):
  no backend logout or revocation; refresh rotation without reuse detection;
  per-process refresh single-flight, so several web replicas need sticky
  sessions or a grace window.
* Client IP: backend trusts `X-Forwarded-For` only from a socket peer inside
  `TRUSTED_PROXY_CIDRS` **and** only for `TRUST_PROXY_HOPS` hops
  ([ratelimit.py `client_ip`](../../backend/app/core/ratelimit.py)); trust chain in
  [request-flow-and-proxy-trust](../diagrams/request-flow-and-proxy-trust.md).
* Startup refuses weak secrets, the published development database
  credentials and live Stripe keys outside `ENV=production`
  ([config.py](../../backend/app/core/config.py)). Outside `local/test/ci` the
  image refuses to start without a build identity.
* Exact address and coordinates never leave the private boundary; a leak is a
  release blocker (02).

## 7. Diagrams

* [request-flow-and-proxy-trust](../diagrams/request-flow-and-proxy-trust.md)
* [database-and-worker-topology](../diagrams/database-and-worker-topology.md)
* [release-and-migration-sequence](../diagrams/release-and-migration-sequence.md)
* [backup-restore-and-dependencies](../diagrams/backup-restore-and-dependencies.md)

## 8. Cross-project practices (register)

Practices considered from other founder projects. Method transfers; data,
domains, credentials and business rules never do.

| ID | Practice | Homies state | Decision |
|---|---|---|---|
| XP-01 | Logout revokes server-side; refresh reuse revokes the family | missing | SEC-SESSION-001 (contract) |
| XP-02 | Long-lived streams end with their token | no streams exist | rule for future real-time work |
| XP-03 | Idle and absolute session limits | sliding 30-day refresh | founder decision (SEC-SESSION-001) |
| XP-04 | Indexing and analytics off unless explicitly enabled | present (`INDEXING_ENABLED`, empty consent) | keep |
| XP-05 | Sitemap gated by the indexing switch | no sitemap | candidate small PR |
| XP-06 | Status timeline with the next action per role | not present | candidate after private alpha feedback |
| XP-07 | Outcome metrics counted server-side | client events only | candidate |
