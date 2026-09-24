# 03 — System Architecture v1.1

> **Source status: derived summary** of the founder instruction of 2026-09-24
> (TASK-000), which reconciled System Architecture v1 with the existing
> implementation. See [00-AUTHORITY](00-AUTHORITY.md).

## 1. What changed from v1

System Architecture v1 proposed a TypeScript / Fastify / Drizzle backend.
After auditing the existing implementation the **runtime technology** is
reconciled to Python. The **domain** in Domain Schema v1 is unchanged: when
the schema specifies an invariant, port the invariant — not necessarily the
library.

## 2. Canonical runtime backend v1

Python 3.12+ · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · PostGIS.

The existing Python implementation is the production implementation path.
One production operational database. No dual writes, no two authoritative
databases.

## 3. Clients

| Client | Direction |
|---|---|
| Public web | Next.js + TypeScript |
| Mobile | Expo / React Native + TypeScript — one app for renter, owner and agent capabilities |
| Admin | Separate secure Next.js web app; no native admin app initially |

Clients are generated from, or strongly typed against, the API contract. No
business logic lives separately in a client.

## 4. API

Contract-first through OpenAPI generated from the backend
(`docs/api/openapi.json`, drift-guarded in CI). The backend is authoritative.

## 5. Async and events

PostgreSQL + transactional outbox + worker. Kafka, NATS or Redpanda are not
introduced merely because an earlier architecture planned them. No new
dependency without a real requirement.

## 6. Search

Phase 1: PostgreSQL + PostGIS + indexes, `pg_trgm`/native search where
justified. Meilisearch is not a launch dependency unless measured evidence
requires it.

## 7. Redis

Not a Phase-1 requirement. Introduced only when a concrete problem justifies
it.

## 8. Infrastructure status

Kubernetes, Helm, ArgoCD, NATS, Airflow, data warehouse, ML: **LEGACY /
DEFERRED / REUSABLE REFERENCE** unless a canonical Task Contract activates
them. Useful historical work is kept; none is required for Phase 1.

## 9. The TypeScript/Drizzle Schema v1 candidate

**REFERENCE IMPLEMENTATION / PARITY ORACLE**, preserved on branch
`reference/ts-drizzle-schema-v1`. Used to compare constraints, relationships,
PostGIS behaviour, privacy boundaries, invariants, indexes and benchmark
expectations. Never a second runtime; never connected to the live API.

## 10. Database version

PostgreSQL 16 / PostGIS 3.4 is **controlled debt**, not a reason to rewrite.
Upgrade is evaluated as its own task, never mixed with domain convergence or
frontend integration. Revisit trigger (proposed by Claude in TASK-000; the
founder may change it): the first of (a) a feature needing
`uuidv7()` or another PG≥17 capability, (b) PG16 entering its final year of
community support, (c) the production database being provisioned — upgrade
before real data, not after.

## 11. Engineering preserved from the earlier implementation

Modular-monolith discipline; PostgreSQL/PostGIS; SQLAlchemy/Alembic; OpenAPI;
test harnesses incl. real-PostgreSQL integration tests, mutation testing and
concurrency tests; backup + restore drills; append-only protection; database
privilege isolation; money in minor units; public/private DTO separation;
audit infrastructure; rate limiting; provider seams; design-system assets.
