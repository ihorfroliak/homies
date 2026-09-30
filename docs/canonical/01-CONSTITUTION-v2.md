# 01 — Homies Product & Engineering Constitution v2

> **Source status: incomplete.** The full Constitution v2 was authored outside
> this repository and has not been committed. This file records only the
> principles the founder stated on 2026-09-24 (TASK-000). It does not add to
> them. Replace this file with the full text when available; see
> [00-AUTHORITY](00-AUTHORITY.md).

## What Homies is

**The most transparent way to rent a home in Poland.**

Long-term: a trusted residential-property marketplace and operating system
that maintains a persistent digital identity for a home across discovery,
rental, management and sale.

The product begins with marketplace liquidity and trust — not with short-stay
payments. The earlier "managed hospitality / give us the keys / bookings →
cleaning → payout" strategy is historical: its engineering is valuable, but it
no longer defines Phase-1 product strategy.

## Principles

1. **Value before extraction.** Maximise value to renter, landlord, agent,
   agency, buyer and seller before maximising what the platform takes. Core
   LONG_TERM and SALE listings launch free. No surprise renter fees. Future
   paid functionality corresponds to real operational or transactional value.
2. **Human life and health override liquidity and revenue.** There is no
   universal `property.safe = true`; safety is typed requirements, hazards,
   versioned attestations, evidence and incidents.
3. **Authority is explicit.** A person acts on a property only through a
   valid chain to a legal party holding authority over it. Identity
   verification alone never authorises publication.
4. **Privacy of place.** A property's exact location is private domain data;
   public listings carry a separate public location.
5. **Money is integers.** All authoritative money is integer minor units,
   never floating point.
6. **Analytics is not business truth.** Authoritative domain state produces
   server-side outcome events; analytics consumes them.
7. **One backend is authoritative.** Clients do not carry business logic of
   their own; the API contract is generated from the backend.
8. **Preserve proven engineering, replace obsolete assumptions.** Neither keep
   every line nor rewrite everything: converge on one canonical Homies, and
   make every change reproducible and independently reviewable.
9. **No stealth decisions.** Material business, domain or architecture
   changes are made by the founder, recorded, and never introduced silently
   in code.
