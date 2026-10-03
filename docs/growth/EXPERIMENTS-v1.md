# EXPERIMENTS-v1 — experiment contract and backlog

Part of [GROWTH-001](GROWTH-001-marketplace-growth-foundation.md).
Classification: assignment seam **BUILD SEAM NOW** (frontend, registry empty) ·
experiments **NEXT PHASE**, each one founder-approved. **No spend is
authorized by this document.**

## 1. Record

`experiment_key · version · title · hypothesis · owner · unit_type
(anonymous_id | user | provider legal party | listing | district | week) ·
eligibility · allocation (variants + weights) · salt · assignment point ·
exposure definition · primary metric (name-vN) · guardrails (name-vN +
threshold) · baseline · minimum practical effect · planned n and horizon ·
contamination and seasonality risk (academic-year peaks in Kraków) · stopping
rule · analysis method · success / failure criteria · next action · cost
ceiling (0 PLN until founder approval) · status (DRAFT → APPROVED → RUNNING →
STOPPED → DECIDED) · causality label · result label (CONFIRMATORY |
DIRECTIONAL)`.

## 2. Rules

* **Sticky deterministic assignment:** `bucket = H(salt ‖ key ‖ unit_id) mod
  10 000`; server-side for logged-in and provider units; anonymous units only
  with consent (others get control and are excluded from analysis).
* **Exposure ≠ assignment:** analysis is intention-to-treat over *exposed*
  units (`experiment_exposed`, first exposure); assigned-but-unexposed units
  are reported.
* **SRM** (randomized): chi-square on exposed counts; p < 0.001 → invalid, no
  outcome reading.
* **Stopping:** a fixed horizon or a pre-registered sequential rule; never
  "run until p < 0.05"; guardrail breaches may stop early.
* **Clustering:** provider and district units; never split one provider's
  listings across arms.
* **Labelling:** CONFIRMATORY only at planned n and α = 0.05; at Kraków
  seeding scale most results are **DIRECTIONAL** and labelled so.

## 3. Backlog (founder-facing contracts; cost ceiling 0 PLN until approved)

| # | Experiment | Unit | Primary metric | Guardrails | Readiness gate |
|---|---|---|---|---|---|
| 1 | concierge landlord onboarding vs self-serve | provider (randomized outreach list) | activation-30d, then QAL per provider | concierge hours per activation; authority-verification failures | concierge log; exclusion table |
| 2 | agency import assistance | organization | QAL added per org in 30 d | duplicate listings (DQ-11); FAKE/DUPLICATE moderation rate | import path (Phase 1.5); agency publish route debt closed |
| 3 | total-cost transparency display | anonymous_id / user | qualified-inquiry rate per listing view | contact-reveal rate; MISLEADING_PRICE reports | client ingestion + consent; monthly total coverage ≥ 80 % of QAL |
| 4 | freshness trust signal ("confirmed N days ago") | anonymous_id / user | L0 rate per listing view | provider reconfirmation rate | client ingestion |
| 5 | Google high-intent Kraków renters | geo/time split (weeks) | qualified seekers per week (HOMIES ATTRIBUTED) | zero-result rate; response-liquidity-24h | cell ≥ LIQUIDITY_TEST; cost CSV; consent |
| 6 | Meta landlord acquisition | time split, campaign holdout | activated owners | CAC per activation; QAL share | cost CSV; landing route; consent; founder spend approval |
| 7 | SEO district pages | district (matched pairs) | organic landing → search in district | indexing errors; thin pages (QAL < k) | indexing enabled by founder; QAL per district ≥ k |
| 8 | landlord referral | provider (referrer) | referred activations per referrer | fraud (EXCL FRAUD); duplicate properties | `referral_code`; incentive legal review |
| 9 | Agency Pro willingness-to-pay (priced pilot) | organization | % accepting a priced offer at P | no revenue claim; disclosure | pricing page; legal review |
| 10 | structured viewing workflow (slots vs free messaging) | provider | TTV p50; viewing-liquidity (b) | NO_SHOW rate; provider retention | viewing facts (built) |
