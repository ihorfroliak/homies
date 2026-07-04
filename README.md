# Homies — Rental Housing Platform (Poland)

> Portfolio flagship project demonstrating **DevOps · Data Analytics · Data Engineering · Business Analysis** skills end-to-end, built solo.

Homies is a two-sided marketplace for flexible-term apartment rentals across Poland (daily → yearly). Tenants search and book homes; landlords and property managers run their operations through a back-office (ERP + CRM) and mobile apps. The platform earns via marketplace commission, landlord SaaS subscriptions, featured listings, and ancillary services.

## Status

🚧 **Phase 0 — Walking Skeleton.** Repo structure, architecture decisions (ADRs), API contracts, and local dev environment. See [docs/DEVLOG.md](docs/DEVLOG.md) for progress.

## Architecture at a glance

- **Modular monolith** (FastAPI, Python) organized by DDD bounded contexts — not 11 microservices ([ADR-0001](docs/adr/0001-modular-monolith.md)). Notifications and ML-serving are the only separately deployed processes.
- **PostgreSQL + PostGIS** for the core domain and geo-search, **Redis** for cache/queues, **Meilisearch** for listing search.
- **Event-driven integration** between contexts via a domain event bus (Kafka-compatible; NATS/Redpanda locally).
- **Kubernetes + Helm + Terraform + ArgoCD (GitOps)** for the deployment story; Docker Compose for one-command local dev.
- **Data platform**: events → S3 lake → DWH → dbt → BI dashboards; ML for dynamic pricing, demand forecasting, and recommendations.

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
backend/     FastAPI modular monolith (bounded-context modules)
apps/        Web client, back-office, mobile apps (later phases)
data/        Airflow DAGs, dbt models, ML training
infra/       Terraform, Helm charts, k8s manifests, ArgoCD
ops/         docker-compose, scripts, monitoring configs
docs/        Charter, ADRs, API contracts, diagrams, runbooks
```

## License

Portfolio project. All rights reserved.
