# 02 — Canonical Business Logic

> **Source status: derived summary** of the founder instruction of 2026-09-24
> (TASK-000). Where the founder's full business-logic text exists, it
> supersedes this file. See [00-AUTHORITY](00-AUTHORITY.md).

## 1. Phasing

| Phase | Scope | Money handled by Homies |
|---|---|---|
| **1A** | LONG_TERM residential marketplace: User, LegalParty, Organization basics, Representation, PropertyAuthority, Property, Space, Listing, media, transparent pricing, search and map, freshness, saved search, saved property, messaging, viewing, report and moderation basics, safety foundation, analytics instrumentation | None |
| **1B** | SALE secondary-market classifieds | None. No purchase money, no mortgage brokerage, no escrow, no notary replacement, no brokerage/representation without a separate legal decision |
| **1.5** | Property / Agency OS: applications, reusable Housing Passport, lead inbox, agency imports, condition/handover basics, richer owner and agency analytics | None implied |
| **2** | MONTHLY transactional rental: contracts, tenancy legal regimes, payments, deposits, double-entry ledger, reconciliation, invoicing, KSeF, disputes, move-in acceptance window, condition reports, protection providers | Yes — behind new legal and payment gates. Existing payment architecture is **not** assumed to satisfy Phase 2 |
| **3** | SHORT_STAY | Only after payment architecture, booking/availability, calendar sync, rebooking, safety operations, check-in/access, STR compliance, DAC7 applicability, cancellation/refund and support readiness |

Existing short-stay, booking, payment and ledger code is historical reusable
engineering, not Phase-1 authority.

## 2. Domain invariants (frozen unless the founder changes them)

**Identity.** User ≠ LegalParty. Organization ≠ LegalParty. Identity
verification ≠ property authority. Organization membership ≠ universal legal
representation.

**Property.** Property → Space (WHOLE_PROPERTY | ROOM) → Listing. Property is
persistent; a Listing is temporary. A room is a Space, never a separate
Property.

**Listing.** The domain term is **Listing**. New business-domain use of
"Offer" is not introduced; legacy physical names may remain until migrated
safely, but public API and domain language converge on Listing.
`ListingIntent` = RENT | SALE. For RENT, `RentalMode` = SHORT_STAY | MONTHLY |
LONG_TERM. The rental mode does **not** determine the jurisdiction-specific
tenancy legal regime.

**Authority.** A user acts on a property only through an explicit valid chain:

```text
User → PERSON LegalParty → PropertyAuthority
User → ACTIVE OrganizationMembership → Organization → LegalParty → PropertyAuthority
User → valid RepresentationMandate → LegalParty → PropertyAuthority
```

**Money.** Integer minor units, never float.

**Address.** Exact internal location and public location are distinct; the
exact address never leaks through a public listing, and neither does the
exact coordinate — public location is privacy-reduced only, with no owner
opt-in exception (04a §16, D-58).

**Safety.** No universal `safe` flag: PropertySafetyProfile, typed
requirements, hazards, versioned attestations, evidence, incidents.

**Analytics.** Not business truth; consumes server-side outcome events.

## 3. Value doctrine and fees

Core LONG_TERM and SALE listings launch free. No surprise renter fees. Paid
functionality later corresponds to real operational or transactional value.

## 4. Competitive strategy

Not merely another classifieds board. The stack: fresh verified inventory +
transparent total cost + Property Passport + verified Housing Passport +
reusable Application + Viewing workflow + Owner OS + Agency OS + Safety +
demand intelligence + fair fees + property lifecycle. The persistent Property
is the core long-term moat.
