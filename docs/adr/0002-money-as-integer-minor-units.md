# ADR-0002: Money represented as integer minor units

- **Status:** Accepted
- **Date:** 2026-07-05
- **Context chat:** 01 — System Design & Contracts

## Context

Prices, booking totals, commissions, and payouts flow through every context. Floating-point types cannot represent decimal currency exactly (`0.1 + 0.2 != 0.3`), which corrupts financial aggregates over time. This was caught during contract review.

## Decision

All monetary amounts are stored and transmitted as **integers in minor units** (grosz for PLN): `350000` means `3500.00 PLN`. Every money field is paired with an ISO 4217 `currency` code. This matches the Stripe API convention.

```json
{ "amount": 350000, "currency": "PLN" }
```

Formatting to human-readable values happens only at the presentation edge (web/mobile UI, BI layer).

## Consequences

- **Positive:** exact arithmetic everywhere; direct compatibility with Stripe; no rounding drift in analytics.
- **Negative:** developers must never divide by 100 in business logic "for convenience" — conversion is a UI concern. Contract linting and code review enforce this.
