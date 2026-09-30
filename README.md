# Homies

Homies is a Poland-first residential property marketplace, starting with
long-term rentals.

The platform connects renters with property owners and agencies through
structured, current and privacy-aware housing data. Its long-term direction is
to preserve the identity and history of a home across discovery, renting,
selling and property management.

## Current status

```text
Phase 1A marketplace backend core

Status:      in development
Production:  NOT READY
Deployment:  NOT DEPLOYED

Current accepted backend baseline:
Integrated Backend Baseline 001 (IBB-001),
Git SHA 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98 (tag backend-baseline-001)
```

- Current status and next work: [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md)
- Baseline record: [docs/baselines/IBB-001.md](docs/baselines/IBB-001.md)
- How every accepted state was audited: [docs/reviews/AUDIT-HISTORY.md](docs/reviews/AUDIT-HISTORY.md)
- Naming convention (human name, ID, Git SHA): [docs/engineering/TRACEABILITY.md](docs/engineering/TRACEABILITY.md)

"Accepted" means accepted for continued engineering development. It is not a
release and not production readiness.

## Implemented now (Phase 1A backend)

The deployable application is `create_phase1_app()` in
[backend/app/composition.py](backend/app/composition.py). It exposes:

- **Identity and authorization** — accounts, roles, email verification, JWT sessions.
- **Who may offer a home** — LegalParty, organizations and memberships,
  representation mandates, and PropertyAuthority chains checked atomically at
  publication.
- **Property → Space → Listing** — long-term rental listings with temporal
  price components (money in integer minor units) and an optimistic-concurrency
  lifecycle.
- **Structured geography and address** — country → administrative areas →
  locality; source-aware addresses; property classification.
- **Location privacy** — the exact location is private; the public sees only an
  approximate grid point or a district.
- **Freshness and availability** — listings must be reconfirmed; stale listings
  leave public surfaces; availability dates on the UTC calendar.
- **Search and map** — one search model for the list and the map (PostGIS).
- **Saved listings, saved searches and saved-search alerts** — alerts for newly
  public listings, revalidated at send time; in-app inbox, notification
  preferences and single-use unsubscribe links.
- **Messaging, viewings and media foundation** — conversations, viewing
  scheduling, moderated property photos with metadata stripped.
- **Transactional outbox** for domain events and notifications.
- **Operations** — `/healthz`, `/readyz` (bounded database probe),
  request-id correlation, metrics, fail-closed production configuration,
  synthetic backup/restore drills.

Stack: Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 +
PostGIS 3.4 (the one database) · pinned dependencies · GitHub Actions CI
(tests on SQLite and PostgreSQL/PostGIS, image build, dependency audit,
secret scan, monitoring rules, API contracts). API contract:
[docs/api/openapi.json](docs/api/openapi.json).

## Next engineering work (planned)

1. MICRO-001 — evidence, documentation and test cleanup
2. PR-002 — release and migration compatibility
3. PR-003 — database client deadlines and failure containment
4. TASK-015 — reports and moderation
5. rental application funnel
6. web and admin UI expansion

These are planned; none is implemented yet.

## Deferred, dormant or historical — not current product capabilities

The repository still contains earlier or future-facing material. None of it is
part of the running Phase 1A product:

- **Dormant code** (`LEGACY_DORMANT`, not routed or started by the Phase-1
  app): short-stay booking, Phase-2 payments, Stripe Connect payouts, the
  ledger, the short-stay `listings` module.
- **Not built / deferred by canonical decision:** managed-hosting model,
  landlord ERP/CRM, Kubernetes, Helm, Terraform, Kafka/NATS, Meilisearch,
  Redis, an ML or data platform.
- **Historical documents:** the original project charter and early strategy
  and release plans are banner-marked as historical.

## Source of truth

Read in this order:

1. [docs/canonical/00-AUTHORITY.md](docs/canonical/00-AUTHORITY.md) — precedence of documents
2. [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) — current baseline and next work
3. [docs/canonical/01-CONSTITUTION-v2.md](docs/canonical/01-CONSTITUTION-v2.md)
4. [docs/canonical/02-BUSINESS-LOGIC.md](docs/canonical/02-BUSINESS-LOGIC.md)
5. [docs/canonical/03-SYSTEM-ARCHITECTURE-v1.1.md](docs/canonical/03-SYSTEM-ARCHITECTURE-v1.1.md)
6. [docs/canonical/07-PRODUCT-GROWTH-DOCTRINE.md](docs/canonical/07-PRODUCT-GROWTH-DOCTRINE.md)

Also: [IMPLEMENTATION-CONVERGENCE](docs/canonical/IMPLEMENTATION-CONVERGENCE.md)
(status history), [DECISIONS](docs/DECISIONS.md), [task contracts](docs/tasks/),
[production readiness](docs/production/PRODUCTION-READINESS.md),
[DEVLOG](docs/DEVLOG.md) (Ukrainian). Historical context only:
[the original project charter](docs/PROJECT_CHARTER.md).

## Quick start (local)

```bash
make up      # start the local stack (docker compose)
make test    # run backend tests
make down    # stop everything
```

The API is served at `http://localhost:8000` (`GET /healthz`, OpenAPI docs at
`/docs`).

## Repository layout

```
backend/     FastAPI modular monolith (bounded-context modules), Alembic migrations, tests
frontend/    design system and visual reference material
ops/         docker-compose, SQL roles, CI helpers, monitoring configs
docs/        canon, baselines, task contracts, audit archives, API contracts, production docs
```

## License

All rights reserved.
