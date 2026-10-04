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
   → TASK-011 (targeted fixes) → TASK-010R → TASK-011R: **ACCEPTED** at
   `ed9cf1b` (Phase-1A slice; not production readiness).
8. **TASK-012** — listing freshness, long-term availability, owner quality
   guidance ([contract](../tasks/TASK-012-listing-freshness-availability-quality.md))
   → TASK-012A → TASK-012R → TASK-012RA: **ACCEPTED** at `879bf56`.
9. **TASK-013** — search, map & marketplace discovery
   ([contract](../tasks/TASK-013-search-map-marketplace-discovery.md))
   → TASK-013A → TASK-013R: **ACCEPTED** at `3f324b6` (D-77).
10. **TASK-014** — saved listings, saved search & alerts
    ([contract](../tasks/TASK-014-saved-listings-saved-search-alerts.md))
    → TASK-014R: **ACCEPTED** at `7ffb4f5` (TASK-014RA); integrated with
    PR-001 into **IBB-001** = `5abfd7b` (CONV-001, accepted for continued
    development; production NOT READY).
11. **PR-002, PR-003** — release/migration compatibility and database client
    deadlines: builder verified, on `main`, milestone audit deferred (D-88).
12. **TASK-015** — reports & moderation basics: **complete for Phase 1A**
    on `main` (Slices 1, 2+3, 5, 4a, 4b and the closure; S6 absorbed;
    milestone audit deferred, D-88). F6 (viewings covered by G-14) added by
    D-102.
13. **PROGRAM-001** — reviewed by GPT-5.6 Sol and founder-approved; merged to
    `main` at `c32ac63` (2026-10-04): GROWTH-001, DESIGN-001, FE-001, FE-002
    (search → results → map/list → listing detail). Adjudications D-102.
14. **DESIGN-001C** — 1C Dzielnica product convergence (Claude Design):
    approved at design-contract level (D-103/D-104); implementation needs a
    repository-readable handoff (`docs/design/DESIGN-001C-HANDOFF.md`). The
    1C visual/token rollout is a separate task **FE-VIS-001**.
15. **FE-003** — save → conversation → viewing: contract final candidate r2
    ([contract](../tasks/FE-003-save-conversation-viewing-DRAFT.md)), founder
    decisions D-104; backend prerequisites BP-1…BP-11; **implementation not
    authorised** until final contract approval.

**Beta prerequisites (before FE-003 matures or any external beta):**
BG-1 backend logout/refresh revocation; BG-5 refresh reuse/grace semantics
(the FE's 120 s rotation memory is a mitigation, not the design);
authority-correct supply routes (remove the legacy `host` role gate where
PropertyAuthority must decide — agency supply, concierge/import, Property OS);
G9 participant-only address/meeting delivery; G4 mandatory/optional parking
input; an explicit immutable viewing cancellation source (REQUESTER /
PROVIDER / HOMIES) before disputes or UI depend on it; first-party analytics
ingestion, consent evidence and retention (legal-gated, G-12); the D-104
G-14 extensions (viewing cancellation, contact reveal) implemented;
**security:** private-engagement authority verification decided and enforced
before provider-side beta (FE-003 BP-9); idempotent conversation/message
writes (FE-003 BP-10).

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
3. **(TASK-010 — accepted)** Structured address and geographic areas; property type = APARTMENT | HOUSE
   + subtype; deprecate `properties.owner_id`.
4. Listing aggregate convergence: Listing terminology in the public API,
   listing texts, rental terms, status history, ~~freshness
   (reconfirm/stale)~~ (TASK-012; expiry not built), publication eligibility
   service.
5. ~~Saved property, saved search.~~ Saved **listing** (04a §22 supersedes Saved Property
   for Phase 1A) and saved search with alerts — TASK-014 (accepted, in IBB-001).
6. ~~Reports and moderation basics~~ — TASK-015 (complete for Phase 1A as a
   candidate; see Now 12); **incidents** not built.
7. Safety foundation: safety profile, typed requirements, hazards, versioned
   attestations.
8. Media derivatives and a vetted processing path (after the C8 audit).
9. Server-side outcome events for analytics via the outbox — measurement
   facts for listing status, viewings and lead stages in GROWTH-001
   (candidate); the housing-outcome capture (G-15) is designed and belongs
   to the owner-flow slice.
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
