# ATTRIBUTION-v1 — acquisition context and causality

Part of [GROWTH-001](GROWTH-001-marketplace-growth-foundation.md).
Classification: **BUILD SEAM NOW** in the frontend (in-memory capture, consent
gate) · storage **NEXT PHASE**, consent- and legal-gated (G-12).

## 1. Touch record

Stored only with marketing or analytics consent; otherwise it lives in session
memory and is discarded at the end of the session.

`touch_id · anonymous_id · captured_at (server) · channel_code ∈ {PAID_SEARCH,
PAID_SOCIAL, ORGANIC_SEARCH, REFERRAL, PARTNER, CONCIERGE, EMAIL, DIRECT} ·
utm_source · utm_medium · utm_campaign · utm_content · utm_term (allowlisted
values only) · click_id_present + click_id_platform · referrer_domain ·
landing_route_template · cell_id · referral_code (reserved)`

Raw click ids (gclid, fbclid, …) are **not stored** while no ad platform
exists; storing them for offline conversion upload is a later founder- and
legal-gated decision. Marketing context never joins LegalParty,
PropertyAuthority, moderation or identity verification.

## 2. Models (computed at conversion, 30-day lookback — to calibrate)

| Model | Rule |
|---|---|
| first touch | earliest touch of the identity — **never overwritten** |
| last touch | latest touch before the conversion |
| last non-direct | latest touch whose channel ≠ DIRECT, else DIRECT |

Supply units accept CONCIERGE attribution from the concierge log, overriding
digital touches (policy: a concierge-sourced owner is concierge CAC).

## 3. Causality labels — mandatory on every channel claim

| Label | Meaning |
|---|---|
| PLATFORM ATTRIBUTED | the ad platform's own reported conversions — never a CAC denominator |
| HOMIES ATTRIBUTED | a first-party touch joined server-side to a server fact (activation, qualified inquiry, L4, outcome) |
| OBSERVATIONAL | before/after or cross-sectional association |
| INCREMENTAL / CAUSAL | only from a randomized holdout, geo/time split, matched markets or a lift study with a pre-registered contract (EXPERIMENTS-v1) |

Nothing is called "ROAS"; platform figures are never causal.

## 4. Marketing conversions (future, before any is sent to a platform)

Each needs: name, business meaning, authoritative source (a server fact),
dedup id, value, currency, consent eligibility. Ladder: signup < qualified
seeker < qualified inquiry < confirmed viewing (L3) < completed viewing (L4) <
outcome. A channel is judged at the highest rung with n ≥ 20, and the rung is
stated. Optimizing ads on shallow events because algorithms like them is not
allowed. Raw email/phone never goes to a third party unless separately
designed, legally appropriate, founder-approved and technically protected.
