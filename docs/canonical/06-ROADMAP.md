# 06 — Roadmap

Order, not dates. Phase scope is defined in [02 §1](02-BUSINESS-LOGIC.md).
Engineering status per area is in
[IMPLEMENTATION-CONVERGENCE](IMPLEMENTATION-CONVERGENCE.md).

## Now

1. **TASK-000** — canonical governance and convergence (this baseline).
2. **TASK-001 — Codex independent audit** of the C1–C8 port at an exact SHA,
   with the C8 media sanitiser as a security focus
   ([draft contract](../tasks/TASK-001-codex-convergence-audit.md)).

## Phase 1A — LONG_TERM marketplace (next build work)

Close the MUST_CLOSE items in the convergence map before the 1A marketplace is
called complete. The order below is **proposed by Claude** (TASK-000) and
awaits founder approval; each item becomes a Task Contract:

1. Audit actor type (USER / SYSTEM / SERVICE) and versioned legal-document
   acceptance — small, cross-cutting, cheaper before more code depends on them.
2. Property authority verification evidence record (trust).
3. Structured address and geographic areas; property type = APARTMENT | HOUSE
   + subtype; deprecate `properties.owner_id`.
4. Listing aggregate convergence: Listing terminology in the public API,
   listing texts, rental terms, status history, freshness
   (reconfirm/stale/expiry), publication eligibility service.
5. Saved property, saved search.
6. Reports and moderation basics; incidents.
7. Safety foundation: safety profile, typed requirements, hazards, versioned
   attestations.
8. Media derivatives and a vetted processing path (after the C8 audit).
9. Server-side outcome events for analytics via the outbox.
10. Organization ↔ LegalParty multi-relationship with one active primary.

## Phase 1B — SALE classifieds

Sale terms, SALE_ASKING_PRICE entry, sale-specific publication rules. No money.

## Phase 1.5 — Property / Agency OS

Applications, Housing Passport, lead inbox, agency imports, condition and
handover basics, owner/agency analytics.

## Phase 2 — MONTHLY transactional rental

Behind legal and payment gates. Legacy payment/ledger code audited
KEEP / ADAPT / REWRITE before any reuse.

## Phase 3 — SHORT_STAY

Behind the gates in 02 §1. Legacy short-stay authorisation (`listings.host_id`)
must move to PropertyAuthority first.

## Not scheduled

PostgreSQL major upgrade — its own task at the trigger in
[03 §10](03-SYSTEM-ARCHITECTURE-v1.1.md). Kubernetes, NATS, Airflow, DWH,
Meilisearch, Redis — only on a concrete requirement.
