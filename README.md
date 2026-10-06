# Homies

Homies is a Poland-first, trust-first residential property marketplace,
starting with long-term rentals (launch locally, model nationally, architect
internationally).

The platform connects renters with property owners and agencies through
structured, current and privacy-aware housing data. Its long-term direction is
to preserve the identity and history of a home across discovery, renting,
selling and property management.

## Development status

```text
Phase 1A long-term rental marketplace — in development

Production:  NOT READY
Deployment:  NOT DEPLOYED (no production environment exists)
```

Exact, current project status — the last formal baseline, the latest
code-bearing `main` state, the next task and every authorisation flag — lives
in one place: **[docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md)**. This README
deliberately repeats none of it.

"Accepted" means accepted for continued engineering development. It is not a
release and not production readiness
([traceability convention](docs/engineering/TRACEABILITY.md)).

## Broad scope

- **Built (Phase 1A backend):** identity and authorisation; who may offer a
  home (legal parties, organisations, mandates, PropertyAuthority chains);
  Property → Space → Listing with temporal prices in integer minor units;
  structured geography and address with private exact location; freshness
  and availability; one search model for list and map; saved listings,
  saved searches and alerts; conversations, viewings and moderated photos;
  reports and moderation; transactional outbox; operations endpoints and
  synthetic backup/restore drills.
- **Built (public web):** the Next.js seeker web app in `frontend/web`
  (search → results → map/list → listing detail).
- **Approved, not authorised for implementation:** the next frontend slices
  (save → conversation → viewing) and the 1C visual rollout.
- **Later phases, by canonical roadmap:** sale classifieds (1B), property /
  agency operating system (1.5), monthly transactional rental with payments
  (2), short stay (3) — see [06 — Roadmap](docs/canonical/06-ROADMAP.md) and
  [02 §1](docs/canonical/02-BUSINESS-LOGIC.md).
- **Dormant code:** short-stay booking, payments, payouts, ledger and the
  short-stay listings module are `LEGACY_DORMANT` and not routed by the
  Phase-1 application (`create_phase1_app()` in
  [backend/app/composition.py](backend/app/composition.py)).

## Where authority lives

The repository is Homies' single durable system of record; conversations and
external tools are inputs, not authority
([05 §14](docs/canonical/05-DEVELOPMENT-GOVERNANCE-v1.md)). Which document wins
is decided by **[00-AUTHORITY](docs/canonical/00-AUTHORITY.md)**. Core canon:

- [01 — Constitution v2](docs/canonical/01-CONSTITUTION-v2.md)
- [02 — Business Logic](docs/canonical/02-BUSINESS-LOGIC.md)
- [03 — System Architecture v1.1](docs/canonical/03-SYSTEM-ARCHITECTURE-v1.1.md)
- [04 — Domain Schema v1](docs/canonical/04-DOMAIN-SCHEMA-v1.md) and
  [04a — clarifications](docs/canonical/04a-DOMAIN-SCHEMA-v1-CLARIFICATIONS.md)
- [05 — Development Governance](docs/canonical/05-DEVELOPMENT-GOVERNANCE-v1.md)
- [06 — Roadmap](docs/canonical/06-ROADMAP.md)
- [07 — Product & Growth Doctrine](docs/canonical/07-PRODUCT-GROWTH-DOCTRINE.md)
- [Implementation convergence](docs/canonical/IMPLEMENTATION-CONVERGENCE.md)
  (status history) and [decision log](docs/DECISIONS.md)

## New to Homies?

Follow **[docs/engineering/HANDOFF-INDEX.md](docs/engineering/HANDOFF-INDEX.md)**
— a 30–60 minute reading path from what Homies is to how work is executed,
using only this repository and its Git history.

## Quick start (local)

```bash
make up      # start the local stack (docker compose)
make test    # run backend tests
make down    # stop everything
```

The API is served at `http://localhost:8000` (`GET /healthz`, OpenAPI docs at
`/docs`). API contract: [docs/api/openapi.json](docs/api/openapi.json)
(generated from FastAPI, drift-tested).

Stack: Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 +
PostGIS 3.4 (the one database) · Next.js + TypeScript public web · GitHub
Actions CI (backend tests on SQLite and PostgreSQL/PostGIS, web, image,
contracts, monitoring rules, secret scan).

## Repository layout

```
backend/     FastAPI modular monolith (bounded-context modules), Alembic migrations, tests
frontend/    web/ — Next.js public web app; design-system/ — tokens and a legacy showcase
ops/         docker-compose, SQL roles, CI helpers, monitoring configs
docs/        canon, status, baselines, task contracts, audit archives, API contracts, production docs
```

## License

All rights reserved.
