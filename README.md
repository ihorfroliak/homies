# Homies — Rental Housing Platform (Poland)

> Portfolio flagship project demonstrating **DevOps · Data Analytics · Data Engineering · Business Analysis** skills end-to-end, built solo.

Homies is a two-sided marketplace for flexible-term apartment rentals across Poland (daily → yearly). Tenants search and book homes; landlords and property managers run their operations through a back-office (ERP + CRM) and mobile apps. The platform earns via marketplace commission, landlord SaaS subscriptions, featured listings, and ancillary services.

## Status

🚧 **Phase 1A — long-term residential marketplace, in development; not deployed.** Current state, accepted baselines and open audits: [IMPLEMENTATION-CONVERGENCE](docs/canonical/IMPLEMENTATION-CONVERGENCE.md) and [docs/DEVLOG.md](docs/DEVLOG.md).

## Architecture at a glance

- **Modular monolith** (FastAPI, Python) organized by DDD bounded contexts — not 11 microservices ([ADR-0001](docs/adr/0001-modular-monolith.md)). One deployable application process; its background workers (notifications, listing freshness) run in-process. No ML serving exists.
- **Runtime today** (canon: [03 — System Architecture](docs/canonical/03-SYSTEM-ARCHITECTURE-v1.1.md)): Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · **PostgreSQL 16 + PostGIS 3.4** as the one database — domain, geo-search and listing search — and a **transactional outbox** in PostgreSQL for events and notifications. No Redis, Meilisearch or NATS: they were never used by the code and were removed from the local stack (PR-001).
- *Deferred, not built:* a message broker, a dedicated search engine, Kubernetes/Helm/Terraform/ArgoCD and the data platform (lake → DWH → dbt → BI, ML) are target-architecture ideas from the original charter (historical), adopted only by a future canonical decision. Docker Compose is the local dev stack.

Full architecture, roadmap, and business plan: [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) (working language: Ukrainian). API contracts: [docs/api/](docs/api/). Decisions: [docs/adr/](docs/adr/).

## Quick start (local)

```bash
make up      # start the full local stack (docker compose)
make test    # run backend tests
make down    # stop everything
```

The API is served at `http://localhost:8000` (health check: `GET /healthz`, OpenAPI docs: `/docs`).

## Repository layout

```
backend/     FastAPI modular monolith (bounded-context modules), Alembic migrations, tests
frontend/    design system and visual reference material
ops/         docker-compose, SQL roles, CI helpers, monitoring configs
docs/        canon, task contracts, audit archives, API contracts, production docs
```

## License

Portfolio project. All rights reserved.
