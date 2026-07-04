# ADR-0006: Monorepo with trunk-based development

- **Status:** Accepted
- **Date:** 2026-07-05
- **Context chat:** 01 — System Design & Contracts

## Context

The project spans backend, several frontends, data pipelines, ML, and infrastructure. Split repos would multiply CI setup, cross-repo contract synchronization, and cognitive load for a solo developer — while a recruiter should see the whole system in one place.

## Decision

A single **monorepo** (`homies/`) holds all code and docs (layout in charter §7, adjusted for the modular monolith: `backend/` instead of `services/*`). Workflow:

- **Trunk-based development**: short-lived branches merged to `main` via PR (even solo — review discipline is part of the portfolio signal).
- **Conventional commits** (`feat:`, `fix:`, `docs:`, `chore:`…) enabling semantic releases later.
- CI paths-filtering keeps pipelines fast (backend changes don't rebuild mobile apps).

## Consequences

- **Positive:** one clone shows the entire system; atomic cross-cutting changes (contract + server + client in one PR); single issue tracker and project board.
- **Negative:** repo grows large over time; mitigated by paths-filtered CI and clear top-level layout.
