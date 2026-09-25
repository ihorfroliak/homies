# 06 — Roadmap

Order, not dates. Phase scope is defined in [02 §1](02-BUSINESS-LOGIC.md).
Engineering status per area is in
[IMPLEMENTATION-CONVERGENCE](IMPLEMENTATION-CONVERGENCE.md).

## Now

1. ~~TASK-000~~ — canonical governance and convergence. Done.
2. ~~TASK-001~~ — Codex independent audit of `988b31b`: safe to continue with
   blocking fixes in named contexts (P1 ×5, P2 ×4). Done.
3. ~~TASK-002~~ — foundational repair of F-01…F-09
   ([contract](../tasks/TASK-002-foundational-repair.md)); ~~TASK-003~~ Codex
   re-audit accepted eight closures, F-04 partially closed.
4. ~~TASK-004~~ — atomic publication authorisation across all chains
   ([contract](../tasks/TASK-004-atomic-publication-auth.md)); ~~TASK-005~~
   independent re-audit: F-04 CLOSED, `dfa3254` = HOMIES FOUNDATION BASELINE
   001 (C1–C8 accepted for continued Phase 1A development).
5. ~~TASK-006~~ — authority integrity and audit-debt closure, TASK-005 N-01…N-04
   ([contract](../tasks/TASK-006-authority-integrity-cleanup.md)); ~~TASK-007~~
   re-audit: N-02…N-04 closed, N-01 partially closed (N-05). HOMIES FOUNDATION
   BASELINE 002: **candidate, not yet accepted**.
6. ~~TASK-008~~ — final foundation concurrency and invitation hardening
   ([contract](../tasks/TASK-008-final-foundation-hardening.md)); ~~TASK-009~~
   two independent final audits (Codex, Claude Code):
   **HOMIES FOUNDATION BASELINE 002 = `3623184` — ACCEPTED** for continued
   Phase 1A development (not production readiness).
7. **TASK-010** — Poland-wide geography, structured address and property
   classification + Product & Growth Doctrine (07) + TASK-009 audit archive
   ([contract](../tasks/TASK-010-geography-address-property-classification.md)).
   Builder complete; **awaiting adjudication** (targeted audit recommended).
8. Next Phase-1A product vertical slice: chosen by the founder after TASK-010
   is adjudicated.

Carried-forward maintenance (not a task on its own, done when the files are
next touched): E01/E02/E03 PostgreSQL regression tests and mutation-review
wording; replace HTTP-completion-order assertions with database evidence.

Hooks enabled by TASK-010 for later tasks (not scheduled): reference-data
import of the full Polish registers (TERYT/PRG) with release versioning;
address normalisation/geocoding behind a provider seam (no paid provider);
duplicate address/property detection; Building entity; area boundary search;
SEO location routes from slugs; regional liquidity metrics.

## Phase 1A — LONG_TERM marketplace (next build work)

Close the MUST_CLOSE items in the convergence map before the 1A marketplace is
called complete. The order below is **proposed by Claude** (TASK-000) and
awaits founder approval; each item becomes a Task Contract:

1. Audit actor type (USER / SYSTEM / SERVICE) and versioned legal-document
   acceptance — small, cross-cutting, cheaper before more code depends on them.
2. Property authority verification evidence record (trust).
3. **(TASK-010, builder — pending adjudication)** Structured address and geographic areas; property type = APARTMENT | HOUSE
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
