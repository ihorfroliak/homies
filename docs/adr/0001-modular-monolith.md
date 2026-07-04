# ADR-0001: Modular monolith instead of 11 microservices

- **Status:** Accepted
- **Date:** 2026-07-05
- **Context chat:** 01 — System Design & Contracts

## Context

The domain model defines 11 bounded contexts (identity, listings, search, booking, pricing, payments, reviews, notifications, CRM, operations/ERP, marketing). The charter originally sketched one microservice per context. A solo developer on a learning budget must weigh AWS cost, operational overhead (11 pipelines, 11 deployments, distributed debugging), and the portfolio goal of demonstrating DevOps skills.

## Decision

Build a **modular monolith**: one FastAPI process containing all bounded contexts as isolated Python modules under `backend/app/modules/`. Only two capabilities run as separate processes:

1. **Notifications** — naturally asynchronous, no shared transactional state.
2. **ML serving** (pricing/recommendations) — different runtime profile and release cadence.

Module isolation rules:
- Modules never import each other directly.
- Cross-context integration happens via **domain events** (ADR-0004) or explicit application-layer service interfaces.
- Each module owns its own database schema (namespace) inside the shared PostgreSQL instance.

## Consequences

- **Positive:** one deployable, one CI pipeline, one database to operate; drastically lower cloud cost; refactoring across contexts stays cheap while the domain model is still stabilizing.
- **Positive:** the DevOps portfolio story (Kubernetes, Helm, GitOps, observability) is fully achievable with a monolith — bounded contexts ≠ deployment units.
- **Negative:** requires discipline to keep module boundaries clean; enforced by import rules and event-based integration.
- **Escape hatch:** any module with clean boundaries can later be extracted into its own service without redesign.
