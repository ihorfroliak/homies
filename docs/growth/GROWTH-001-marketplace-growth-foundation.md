# GROWTH-001 — Marketplace Growth & Measurement Foundation

| Field | Value |
|---|---|
| Status | **FOUNDATION (builder) — PROGRAM-001**, on the program branch, not on `main` |
| Authority | subordinate to [07 Product & Growth Doctrine](../canonical/07-PRODUCT-GROWTH-DOCTRINE.md) and the canon; founder decisions **D-98** (G-1…G-15) |
| Family | this document · [METRICS-v1](METRICS-v1.md) · [EVENTS-v1](EVENTS-v1.md) · [ATTRIBUTION-v1](ATTRIBUTION-v1.md) · [EXPERIMENTS-v1](EXPERIMENTS-v1.md) · [DATA-QUALITY-v1](DATA-QUALITY-v1.md) · [UNIT-ECONOMICS-v1](UNIT-ECONOMICS-v1.md) · [PRIVACY-CONSENT-v1](PRIVACY-CONSENT-v1.md) |
| Supersedes | `docs/design/ANALYTICS_EVENTS.md` (booking-era) |
| Built now | the outbox measurement facts (`app/modules/events/facts.py`, EVENTS-v1 §4) — nothing else: no ingestion, no vendor, no dashboard, no spend |

This is not a marketing plan. It fixes, before material traffic exists, what
Homies measures, how, from which source, and which seams are needed — so the
first beta produces numbers that mean something.

## 1. Accepted founder decisions (D-98, 2026-10-03)

| # | Decision | Status |
|---|---|---|
| G-1 | Kraków is the first market | ACCEPTED |
| G-2 | LONG_TERM first | ACCEPTED |
| G-3 | first liquidity cell: whole apartments; rooms later, as a separate cell | ACCEPTED |
| G-4 | 0 PLN listing + concierge/import assistance — a launch acquisition policy, not permanent pricing | ACCEPTED |
| G-5 | seekers free | ACCEPTED |
| G-6 | supply-led cold start | ACCEPTED |
| G-7 | North Star = Successful Housing Outcomes; proxies stay labelled until a real confirmation mechanism exists | ACCEPTED |
| G-8 | monetization discovery: agency/property OS + professional/ancillary products, not renter commission (direction only — nothing built) | ACCEPTED |
| G-9 | prove Kraków liquidity before Warsaw | ACCEPTED |
| G-10 | SHORT_STAY later | ACCEPTED |
| G-11 | map provider-agnostic; development-only source now; beta/production provider is a later external-service decision | ACCEPTED |
| G-12 | analytics vendor-neutral; no external analytics/ad SDK in PROGRAM-001; prepare first-party ingestion; storage, retention and consent legal-gated before external beta | ACCEPTED WITH CONSTRAINTS |
| G-13 | Polish launch language; i18n architecture from the start; EN/UK ready, not active | ACCEPTED |
| G-14 | after FEATURE_RESTRICTED, the requester cannot reopen a conversation on the same listing publication generation | ACCEPTED (implemented in TASK-015 S4b) |
| G-15 | housing-outcome capture seam designed now, built in the owner-flow slice; never inferred from a listing disappearing | ACCEPTED (designed: EVENTS-v1 §5) |

## 2. Growth hierarchy

liquidity → trust → matching efficiency → supply retention → demand retention
→ unit economics → monetization → geographic expansion → mode/product
expansion. Never "traffic → signup → scale ads": broad demand acquisition does
not scale into an empty cell.

## 3. Four planes, never merged

| Plane | What | Where | Never |
|---|---|---|---|
| operational observability | logs, Prometheus, traces | `/metrics` (operational only) | campaign, UTM, user or listing labels; business KPIs |
| domain events | business facts | outbox `domain_events` (ids, codes, DB instants) | bodies, notes, addresses, contacts |
| product analytics | behaviour, funnels | first-party ingestion — **not built**, legal-gated (G-12) | anything without consent |
| marketing attribution | acquisition context | touch records — **not built**, consent-gated | joined to LegalParty, PropertyAuthority, moderation or verification |

**Failure principle:** marketplace correctness > analytics delivery. Client
analytics is fire-and-forget (bounded queue, drop on failure, drop counter)
and never blocks search, listing, conversation, viewing, moderation or
publication. Domain facts stay transactional because they *are* domain truth.
No Kafka, no warehouse, no CDP.

## 4. Market cells and cold start

Liquidity is local. A cell = country × market area × inventory type ×
rental mode × intent; the first is `PL : Kraków : WHOLE_PROPERTY/APARTMENT :
LONG_TERM : RENT`. Cells are coarsened until data supports a split
(district later). Never judge Homies by national totals.

Analytical maturity states (not a domain enum). Every threshold is
**PROPOSED — TO CALIBRATE**; a state is entered after 4 consecutive weeks at
or above, demoted after 3 below.

| State | Entry (Kraków whole-apartment LONG_TERM) | Allowed |
|---|---|---|
| DISCOVERY | default | research, concierge pilots; 0 spend |
| SEEDING | founder go; concierge pipeline running; QAL ≥ 25 | supply-led acquisition only (G-6) |
| LIQUIDITY_TEST | QAL ≥ 150 and ≥ ⅓ of districts with QAL ≥ 5; response-liquidity-24h ≥ 70 %; outcome-unrecorded ≤ 30 % | small capped demand tests |
| LIQUID | QAL ≥ 400; coverage(10) ≥ 70 %; zero-result ≤ 10 %; listing-liquidity-7d ≥ 60 %; TTFR p50 ≤ 6 h; viewing-liquidity (completed) ≥ 25 %; supply retention m2 ≥ 60 % | sustained demand acquisition |
| SCALE_ELIGIBLE | LIQUID 8 weeks **and** SHO measurable (`ListingOutcomeReported` live) **and** CAC per outcome HOMIES ATTRIBUTED with n ≥ 20 **and** a contribution-margin plan | **founder decision** to open Warsaw (G-9) |

Paid scale follows readiness, never a calendar date.

## 5. Acquisition (hypotheses, not authorization)

**Supply (first):** 0 PLN listing + concierge/import (G-4); private landlords,
agencies, property managers, relocation companies, partner sources. A future
internal supply view needs: source, entity (owner/agency), assigned outreach
owner, stage, contacted_at, cost, activation, first inquiry, outcome — a
concierge log first (CSV), never a CRM now. Agencies scale supply: the
architecture never assumes one account = one private owner (Organization,
PropertyAuthority, mandates already exist); agency publishing still runs into
the host-only route debt (BETA BLOCKER).

**Demand (after liquidity):** SEO → partnerships/communities → Google Search
→ sharing/referrals → remarketing → broad paid social. Meta possibly earlier
for owner acquisition. Order is a hypothesis.

**Loops (designed, not built):** seeker shares a listing/search; landlord
refers landlord; agency imports a portfolio; SEO (inventory → visibility →
seekers → inquiries → supply value → inventory); trust (outcome → verified
review later → conversion). No reward incentives before abuse economics are
understood. Reviews only after credible outcomes (double-blind later), kept
apart from badges, moderation and enforcement; no opaque score from reports.

**Partnerships (source model only):** agencies, property managers,
relocation, employers, universities, landlord communities, insurance, tenant
verification, moving, utilities, cleaning. No partner portal.

## 6. Admin / BI requirements (future; nothing built)

Executive (SHO proxy ladder, QAL, active seekers, zero-result, listing /
response / viewing liquidity, time-to-match) · supply (acquisition,
activation, QAL, inquiries, response, retention, agency performance) · demand
(sessions, searches, views, contacts, conversations, viewings, outcomes) ·
geography (city, district, type, price) · growth (source, channel, campaign,
spend, attributed conversions, CAC with measurement-type label) · data quality
(missing attribution, duplicates, unknown events, anomalies, ingestion
delay). Commercially sensitive (CAC, spend, agency performance, moderator
internals) → least privilege, never a public schema. No vanity-only views.

## 7. What is deliberately not built

Kafka · warehouse at scale · CDP · multi-touch attribution · MMM · automated
ad optimizer · CRM · nationwide programmatic SEO · AI content · recommendation
AI · opaque trust score · billing engine · partner portal · referral reward
engine · reputation system · SHORT_STAY marketing · multi-country growth ·
mobile apps · any vendor tracking SDK · any spend.

## 8. Seams — built now vs next

| Seam | Classification | State |
|---|---|---|
| outbox measurement facts (status changes, viewing transitions incl. who cancelled, outcome, lead stage) | **BUILD SEAM NOW** | built (`events/facts.py`, tests `test_measurement_facts.py`) |
| `analytics_account_exclusions` (internal/test/seed/fraud accounts) | DESIGN-SPECIFY NOW | needed before the first metric report |
| `listing_status_history` table (canon 04 §49) | DESIGN-SPECIFY NOW | the `ListingStatusChanged` fact covers the measurement need until the table lands |
| `metric_snapshots` (daily aggregates; QAL history) | NEXT PHASE | |
| first-party client ingestion with consent | NEXT PHASE — legal-gated (G-12) | the frontend sinks are noop/memory/console |
| cost CSV + concierge log | DESIGN-SPECIFY NOW | schema in UNIT-ECONOMICS-v1 |
| `ListingOutcomeReported` (G-15) | DESIGN-SPECIFY NOW → owner-flow slice | EVENTS-v1 §5 |
