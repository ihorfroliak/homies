# ADR-0003: PostgreSQL + PostGIS as the primary datastore

- **Status:** Accepted
- **Date:** 2026-07-05
- **Context chat:** 01 — System Design & Contracts

## Context

The platform needs transactional integrity for bookings and payments, geospatial queries for "listings near me" and map search, and a mature migration/tooling story a solo developer can operate.

## Decision

**PostgreSQL 16 with the PostGIS extension** is the single primary datastore. Each bounded context owns its own schema. Supporting stores with clearly scoped roles:

- **Redis** — cache, rate limiting, lightweight queues.
- **Meilisearch** — full-text/faceted listing search, fed by domain events; never a source of truth.
- **S3 → DWH** — analytics replicas fed by the event pipeline; OLTP database is never queried by BI directly.

## Consequences

- **Positive:** ACID transactions for the booking/payment core; PostGIS covers geo-search without a separate geo-service; one engine to back up, monitor, and tune.
- **Positive:** RDS PostgreSQL in `eu-central-1` satisfies EU data-residency (RODO/GDPR).
- **Negative:** search index and DWH are eventually consistent with the OLTP source — acceptable, since both are read-optimized projections.
