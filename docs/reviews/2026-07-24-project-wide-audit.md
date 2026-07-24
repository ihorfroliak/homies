# Project-wide Audit — Homies (baseline for long-term development)

**Date:** 2026-07-24 · **Commit audited:** `0f2f8a1` (main, clean tree) ·
**Mode:** AUDIT ONLY — no implementation. Evidence gathered by running commands,
not from memory. Supersedes [AUDIT-01](2026-07-23-full-system-audit.md) as the
current baseline; the earlier report's P0s are re-checked below.

State docs remain: [PROJECT_STATE](../PROJECT_STATE.md) (live state),
[BUILD_HISTORY](../BUILD_HISTORY.md), [DECISIONS](../DECISIONS.md) (30 ADR-lite
entries). **Deliberately NOT creating SECURITY_STATE/QUALITY_STATE/…** — that
would duplicate PROJECT_STATE and violate the brief's own anti-bloat rule.
PROJECT_STATE stays the single live status doc; this report is the periodic
baseline.

## What was actually inspected (evidence)

| Check | Command / source | Result |
|---|---|---|
| Full test suite on real Postgres | `TEST_DATABASE_URL=… pytest -q` | **148 passed, 1 skipped, ~47s** |
| Lint | `ruff check app tests alembic scripts` | clean (ruff pinned 0.15.22) |
| Typecheck | `mypy --version` | **not installed** (CI-04 open) |
| CI workflow | `.github/workflows/ci.yml` | backend (postgres:16 svc, migrate, lint, test) + contracts (Spectral 0 err, AsyncAPI) |
| CI scanning | grep workflow | **no dependency/secret/SAST scan, no coverage gate** |
| Observability | grep `Counter/Gauge/Histogram`, healthz body | metrics for notif/rate-limit/expiry only; **healthz returns static `{status,env}` — no DB check**; no tracing/Sentry/structured logs |
| Frontend | `find apps -type f` | **apps/ EMPTY**; `frontend/design-system/` = showcase only |
| Product B | grep `free_listing/marketplace` in app | only a comment (future policy names) — **0% code** |
| SEO | `find sitemap/robots` | **none** |
| Branch protection | GitHub API `/branches/main/protection` | **HTTP 401 — UNVERIFIED** (needs authenticated check) |
| Dependabot | `.github/dependabot.yml` | **absent** |

## Executive summary

Since AUDIT-01 (2026-07-23) eight micro-cycles closed the perimeter and the
schema/CI foundations: **rate limiting, fail-fast secrets, real-SDK webhook +
payment-environment model, unpaid-booking expiry + scheduler, generated OpenAPI
+ drift guard, Alembic single schema source, and a real-Postgres CI with true
concurrency tests.** The transactional + financial core is now strong and
concurrency is validated on real Postgres (not SQLite theatre).

The gap has shifted decisively from **backend correctness** to **product surface
and operations**: there is **no production frontend** (`apps/` empty), **no
Product B**, **no observability worth the name** (blind health check, no HTTP/
business metrics, no tracing/error tracking), and **no CI security scanning**.
Nothing is architecturally blocked — the modular monolith has clean seams for
all of it.

## Current architecture (verified)

```
backend/ FastAPI modular monolith (3,436 app LOC · 2,864 test LOC · 141 tests)
  core: config (fail-fast secrets + payment-env model), db, security (JWT/scrypt/RBAC),
        ratelimit (token bucket), schema (Alembic ensure/verify), audit
  modules: identity · listings · booking (TTL expiry + scheduler) · payments
           (Stripe Connect, real-SDK webhook) · ledger (double-entry, append-only
           triggers) · events (outbox + notification worker) · admin
  alembic/ single migration = schema source of truth (image ships it)
PostgreSQL 16 (PostGIS in compose; schema needs only btree_gist)
frontend/design-system/ runnable showcase (NOT production) · apps/ EMPTY
.github/workflows/ci.yml: backend (pg16 service) + contracts
docs/ charter, strategy, business arch, 7 ADRs, 14 design, 8 reviews, live state
ops/ compose (api, PostGIS, Redis, Meilisearch, NATS — last three UNUSED by code)
```

## Product state (verified)

| Capability | Product A | Evidence |
|---|---|---|
| Register/login/RBAC, host onboarding (Stripe sim) | ✅ | tests |
| Listing CRUD + publish + calendar blocks | ✅ (no photos, no geo, flat price) | code |
| Search by city (paged) | ⚠️ minimal | code |
| Booking lifecycle incl. expiry | ✅ | BK-01 |
| Payment→ledger→payout, reconciliation | ✅ (sim provider) | tests |
| Cancellation + refund | ✅ (full only) | tests |
| Notifications (outbox, retry, DEAD) | ✅ | OAT-03 |
| Reviews / messaging / disputes | ❌ (reviews modelled, no UI/flow; messaging & disputes absent) | code |
| **Any frontend (web/mobile)** | ❌ `apps/` empty | filesystem |
| **Product B (free listings)** | ❌ 0% | grep |

Guest journey: search→book→pay→confirm→expire/cancel works at the API level;
**no UI**. Host journey: onboard→list→payout works at the API level; **no
dashboard endpoint or UI**. Admin: read-only surface + incidents exist; no
moderation queue.

## Maturity (evidence-based; Low/Med/High with basis — no fabricated numbers)

| Area | Rating | Basis |
|---|---|---|
| Backend correctness | **High** | 148 tests, financial invariants, real-Postgres concurrency proven |
| Financial integrity | **High (sim) / Med (real)** | double-entry, append-only triggers, reconciliation=0 — but provider is simulation; real Stripe UNVERIFIED (no keys) |
| Concurrency/reliability | **High** | exclusion constraint, FOR UPDATE, expiry race — validated on real Postgres in CI |
| Test maturity | **Med-High** | unit+integration+concurrency+security+contract; **no E2E, no load** |
| Security (object-level) | **High** | 12/12 IDOR probes; rate limiting; fail-fast secrets; webhook signature |
| Security (perimeter/supply-chain) | **Low-Med** | no MFA, no email verification, **no dependency/secret/SAST scanning**, branch protection UNVERIFIED |
| CI/CD | **Med** | pg service + migration-first + lint + contract; **no typecheck/scan/coverage/deploy** |
| Infrastructure | **Low** | one compose; **no backups schedule, no deploy, nothing deployed**; DR drill manual only |
| Observability | **Low** | notification/rate-limit/expiry metrics only; **blind healthz; no HTTP/business metrics, tracing, error tracking, structured logs** |
| Frontend | **Showcase only** | design-system runnable; **no production app** |
| Analytics | **Design only** | taxonomy doc; no pipeline/consent/sink |
| SEO | **None** | no sitemap/robots/structured data; Product B (the SEO engine) absent |
| Documentation | **High but heavy** | thorough + drift-guarded (OpenAPI); AsyncAPI still drifted; docs > code |

## Critical risks

### P0 — none newly critical
The AUDIT-01 P0s are resolved or credential-blocked:
- ~~no rate limiting~~ closed (SEC-01) · ~~fail-open secrets~~ closed (SEC-02) ·
  ~~ghost booking~~ closed (BK-01) · ~~dual schema path~~ closed (TD-01).
- **FIN-01 (real Stripe Test Mode)** — **BLOCKED** on `sk_test_` credentials;
  adapter + webhook signature proven against the real SDK, API-call scenarios
  written and gated. Not a code gap.

### P1 (production readiness)
| ID | Risk | Evidence |
|---|---|---|
| OBS-01 | `/healthz` never checks the DB — reports healthy while the database is down | code |
| OBS-02 | No HTTP metrics (latency/status/throughput), no business metrics (bookings, GMV, conversion) — the KPI framework has no data source | grep |
| OBS-03 | No error tracking, no structured/JSON logs, no request/correlation id, no tracing | grep |
| CI-02 | No dependency scanning (pip-audit), secret scanning (gitleaks), or SAST | workflow |
| CI-01 | Branch protection on `main` UNVERIFIED (API 401); no dependabot | API |
| CI-04 | No static typechecker (mypy/pyright) | env |
| FIN-02/03 | Only full refunds; no chargeback/`dispute.*` handling or clawback (refund-after-payout → 409) | code |
| REC-01 | No external Stripe reconciliation (orphaned payments / missing webhooks / payout mismatch undetectable) | code |
| SEC-03/05 | No email verification, no admin MFA | code |

### P2
Listing media (photos), geo search, reviews/messaging surfaces, disputes engine,
AsyncAPI alignment, load/E2E tests, D-14 per-process rate-limit counters,
consent-mode analytics.

## Technical debt

TD-03 payment provider defaults to simulation · TD-06 **dead infra** (Redis,
Meilisearch, NATS run in compose, used by zero code) · AsyncAPI catalog drifted
from emitted events · docs-to-code ratio inverted · single initial migration
(fine pre-deploy; future changes must be new migrations).

## Missing capabilities (product)

Production web + mobile frontend · Product B free-listings marketplace + its
anti-abuse/moderation/SEO safeguards · listing photos & media pipeline · geo/
faceted search · reviews & messaging UX · disputes/resolution engine · analytics
pipeline + consent · SEO (sitemap, robots, structured data, location/listing
pages) · email verification & MFA · scheduled offsite backups + deploy target.

## Dependency map (what unblocks what)

```
Backend contracts (OpenAPI, generated + guarded) ──┬─▶ Frontend integration ──▶ E2E
Design-system tokens/components (exist) ───────────┘
Rate limiting + moderation infra ──▶ Product B free listings ──▶ SEO surfaces
Observability (health/metrics/logs) ──▶ safe deploy ──▶ staging/prod ──▶ load tests
Real Stripe test keys ──▶ FIN-01 close ──▶ chargeback/clawback ──▶ external reconciliation
```

## Parallelization

**Can run in parallel now (independent):**
- CORE: chargeback/clawback + external reconciliation (P1 financial).
- DEVOPS: observability (health/DB check, HTTP+business metrics, structured logs)
  and CI security (pip-audit + gitleaks + branch protection) — independent.
- SECURITY/QA: dependency/secret scanning wiring; E2E harness scaffolding.
- FRONTEND: pick the framework and stand up the web app skeleton from the
  existing design-system contract — does not touch backend.

**Must be sequential:**
- Frontend production flows ← stable OpenAPI (already generated/guarded) → then E2E.
- Product B ← rate limiting (done) + a moderation service + trust signals, THEN
  SEO surfaces (never index unmoderated content).
- Real Stripe (needs keys) → chargeback/dispute handling → external reconciliation.

## Recommended micro-cycle roadmap (grouped by context)

### CORE / BACKEND
- `CORE-1` chargeback/`charge.dispute.*` handling + refund-after-payout clawback (FIN-02/03).
- `CORE-2` external Stripe reconciliation job (REC-01) — needs keys to run live; logic + gated test now.
- `CORE-3` listing media model (photos) + geo fields (PostGIS already available).

### FRONTEND / MOBILE
- `FE-1` choose framework (Next.js recommended — SSR/SEO), stand up web skeleton consuming `docs/api/openapi.json`, wire one real flow (search→listing→booking) against the API.

### SECURITY / QA
- `SEC-3` email verification; `SEC-5` admin MFA.
- `QA-1` E2E harness (Playwright) for the guest booking flow once FE-1 lands.
- `SUP-1` dependency + secret scanning in CI (pip-audit, gitleaks) + dependabot.

### DEVOPS / SRE
- `OBS-1` **real health/readiness (DB check) + HTTP metrics middleware + business metrics + structured JSON logs + request id** — highest-leverage ops cycle.
- `CI-4` static typecheck (mypy, incremental) + `CI-1` branch protection + required checks.
- `INFRA-1` scheduled offsite backups + a deploy target (staging).

### PRODUCT / DATA / SEO
- `PB-1` Product B design + moderation/anti-abuse architecture (design pass; no unmoderated indexing).
- `SEO-1` sitemap/robots/structured-data scaffolding (after FE-1).
- `AN-1` analytics pipeline + consent (after FE-1 emits events).

## What changed during this audit

Only this report was added. No code, no config, no behaviour changed.

## What must NOT change yet

The financial core, the schema/migration path, the generated-OpenAPI contract,
and the design-system visual direction — all recently stabilised and guarded.
Do not refactor them without a specific evidence-backed reason.

## Recommended next micro-cycle

**`OBS-1` — observability foundation** (DEVOPS/SRE):
real `/healthz` + `/readyz` that check the database, an HTTP metrics middleware
(latency/status/throughput), core business counters (bookings created/confirmed/
expired, payments, refunds), structured JSON logging with a request/correlation
id, and no secrets/PII in logs.

**Why highest value:** the platform is functionally strong but **operationally
blind** — a blind health check means an outage is invisible, and there is no
data source for the KPI framework or for incident response. It is a P1 that
unblocks safe deployment (INFRA-1) and every growth/analytics decision, it is
low-risk (additive, no financial-logic change), and it is independent of the
frontend and of Stripe credentials.

**Parallel while OBS-1 runs:** SECURITY/QA can wire CI dependency+secret scanning
(`SUP-1`); CORE can start chargeback/clawback (`CORE-1`); FRONTEND can pick the
framework and scaffold the web app (`FE-1`). None of these touch the same files.

**Evidence that will define OBS-1 done:** `/healthz` returns unhealthy when the
DB is down (test); `/metrics` exposes HTTP + business series (probe);
structured logs carry a request id and no secrets (test); full suite + CI green;
PROJECT_STATE/BUILD_HISTORY updated.
