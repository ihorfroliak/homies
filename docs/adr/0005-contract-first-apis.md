# ADR-0005: Contract-first APIs with OpenAPI 3.1, AsyncAPI 3.0, and Spectral linting

- **Status:** Accepted
- **Date:** 2026-07-05
- **Context chat:** 01 — System Design & Contracts

## Context

Multiple surfaces (web client, back-office, 3 mobile apps) consume the same backend. Writing contracts before code keeps frontend and backend work parallelizable and forces explicit domain decisions.

## Decision

- REST contracts are authored in **OpenAPI 3.1** under `docs/api/` (auth, listings, booking first) — the spec is the source of truth; handlers are implemented against it.
- Event contracts in **AsyncAPI 3.0** (`docs/api/events.asyncapi.yaml`).
- All specs are linted with **Spectral** (`.spectral.yaml`) in CI. Rule deviations are allowed only via a documented, justified override in the config — disabling a rule with a written rationale is an engineering decision, not a shortcut.

## Consequences

- **Positive:** zero-drift documentation; client SDKs and mock servers can be generated; API review happens before implementation cost is sunk.
- **Negative:** small upfront overhead per endpoint; mitigated by only contracting stable, externally consumed APIs (internal module interfaces stay in code).
