# PRIVACY-CONSENT-v1 — consent categories, forbidden data, retention classes

Part of [GROWTH-001](GROWTH-001-marketplace-growth-foundation.md). No legal
claim is made here; every period and every user-facing wording is
**LEGAL-GATED** (founder G-12: storage, retention and consent must pass
privacy/legal review before external beta).

## 1. Consent categories

| Category | Covers | Default |
|---|---|---|
| STRICTLY_NECESSARY | session, security, rate limiting, fraud screening | always on; never used for analytics |
| FUNCTIONAL | locale, remembered filters | opt-in |
| ANALYTICS_FIRST_PARTY | anonymous_id, client events, identity link | opt-in |
| MARKETING_ATTRIBUTION | touch persistence beyond the session, future click ids | opt-in |
| PRODUCT_COMMUNICATIONS | existing PRODUCT notification preferences (alerts) | already separate; never merged with analytics |

The consent UI is a seam (state store + gate + component); it is shown only
once a non-essential category actually exists. Marketing trackers are never
turned on automatically. The consent evidence record (policy version,
categories, instant, actor) is server-side and distinct from the
`consent_updated` analytics event.

## 2. Never in analytics, attribution, ads, logs, error monitoring or events

Private messages · report descriptions · moderation explanations · identity
documents · exact private addresses or coordinates · viewing and tenant notes
· raw e-mail or phone · form contents · free text · auth tokens · full URLs
with query strings. Vendor tracking stays behind one controlled boundary (the
frontend `analytics` module); no SDK is called from components. No vendor is
installed (G-12).

## 3. Retention classes (periods LEGAL-GATED — none invented)

| Class | Contents |
|---|---|
| R-OPS | operational business tables (04 §75–76 governs) |
| R-AUDIT | `audit_log`, `domain_events` (append-only) |
| R-ANALYTICS-RAW | client events with pseudonymous ids — the shortest class |
| R-IDENTITY-LINK | anonymous ↔ user links — until consent withdrawal or account deletion |
| R-ATTRIBUTION | touch records |
| R-ANALYTICS-AGG | aggregates without identifiers (snapshots) |
| R-CONSENT-EVIDENCE | consent records |
| R-FINANCE | cost CSV, invoices (statutory; accountant to set) |
| R-OBS | Prometheus, logs (operational) |

Identifiers are designed for deletion: analytics rows keyed by anonymous_id or
user_id can be deleted or anonymized per subject. Incident data never enters
product analytics (04 §66).
