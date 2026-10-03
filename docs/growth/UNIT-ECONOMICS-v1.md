# UNIT-ECONOMICS-v1 — revenue, margin and acquisition cost

Part of [GROWTH-001](GROWTH-001-marketplace-growth-foundation.md).
Classification: DESIGN-SPECIFY NOW. No connector, no data, no spend.

## 1. Never mix these

| Term | In Homies Phase 1A |
|---|---|
| GMV | **none** — rent never passes through Homies (LONG_TERM, no transaction money). "Facilitated rent value" (monthly rent of confirmed lets) may be shown as information, labelled **NOT REVENUE** |
| Revenue | invoiced, recognized amounts from agency/property OS and professional/ancillary products (G-8). Today 0. Renter commission is excluded by decision |
| Contribution margin | revenue − variable payment costs − verification − incentives − support − fraud loss − partner payouts (− concierge labour per unit, messaging/SMS cost per unit) |
| Cash | bank movements — the finance source, not the platform |

The legacy `admin/kpi.py` booking/ledger KPIs are LEGACY_DORMANT and not reused.

## 2. Campaign and acquisition cost contract (manual CSV first)

Template: [`templates/campaign-costs.csv`](templates/campaign-costs.csv). Grain:
date × market cell × channel × campaign × cost type.

| Column | Rule |
|---|---|
| date | ISO local date (Europe/Warsaw) |
| market_cell_id | e.g. `PL:KRK:WHOLE_APT:LONG_TERM`, or `PL:SHARED` |
| side | SUPPLY / DEMAND / SHARED |
| channel_code | as in ATTRIBUTION-v1 (incl. CONCIERGE) |
| campaign_id / campaign_name | platform or internal id; `NONE` for labour |
| cost_type | MEDIA / LABOR / INCENTIVE / TOOLING / CONTENT / OTHER |
| amount_minor | integer ≥ 0 (corrections are new negative rows linked by `source_ref`, never edits) |
| currency | ISO 4217 |
| tax_basis | NET / GROSS |
| source / source_ref | PLATFORM_EXPORT / INVOICE / TIMESHEET / MANUAL + id |
| entered_by / entered_at / notes | provenance |

Unique key: (date, market_cell_id, channel_code, campaign_id, cost_type,
source_ref).

## 3. Side-specific CAC (METRICS-v1 §9)

Supply: per activated owner, per QAL, per outcome. Demand: per qualified
seeker, per qualified inquiry, per outcome. A blended CAC may be shown next
to them, never instead. Concierge labour and incentives count (a 0 PLN
listing is not 0 CAC).

## 4. Monetization hypotheses (documented only — G-8)

Agency/property OS (portfolio, team, import, leads, response analytics,
viewings, mandates); pro tools; optional promotion (later, never fake
urgency); insurance/referrals; verification services; moving/cleaning
referrals; later payments/contracts (Phase 2). None is built because it is
listed here.
