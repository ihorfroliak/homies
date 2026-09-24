# 04a — Domain Schema v1: approved clarifications

Additions to [04-DOMAIN-SCHEMA-v1](04-DOMAIN-SCHEMA-v1.md) stated by the
founder on 2026-09-24 (TASK-000 §20–§21). They rank with 04. Where they
tighten 04, they win over any implementation that follows 04's looser text.

## 1. Organization ↔ LegalParty

Not a global 1:1 forever. An Organization may relate to several LegalParties
where required, with **at most one active primary** relationship.

## 2. Versioned legal documents

Never `termsAccepted = true`. Record acceptance or acknowledgment of an exact
document version:

* document type; version; effective date;
* immutable identifier or content hash;
* locale where relevant;
* the User's acceptance/acknowledgment event with timestamp.

No CMS is required for this.

## 3. Marketing consent

Separate from notification preferences. Opting out of marketing never
disables security or required transactional messages.

## 4. Safety attestations

Versioned. Not reducible to `last_attested_at`: record who attested, what,
under which policy version, and when.

## 5. Audit actor

Audit distinguishes **USER**, **SYSTEM** and **SERVICE** actors. An automated
action is not recorded as `actor_user_id = NULL` (nor as a free-text
placeholder).

## 6. Idempotency minimisation

Idempotency records do not store arbitrary sensitive response bodies. Prefer a
result reference, a safe status, a hash, or an explicitly safe snapshot only
where necessary.

## 7. Property type

`PropertyType = APARTMENT | HOUSE` plus a subtype where classification is
useful. ROOM never returns as a property type. `aparthotel_unit` must not pull
hospitality inventory into Phase 1 scope.

## 8. Structured address

The free-text address + exact point is not the final model. Before
marketplace, search and geography design is complete, a structured address
exists — country, region, city, district, street, building, unit, postcode,
exact geolocation, and a geographic-area hierarchy or equivalent — keeping the
exact/public privacy split already implemented.

## 9. Property authority verification

`verification_state` plus an audit entry is not enough for mature,
evidence-backed authority verification. An explicit verification/evidence
record is required before this is production-complete.

## 10. `properties.owner_id`

Not authorisation truth. Its meaning is deprecated; prefer migrating to
`created_by_user_id` (or equivalent creator semantics) if still useful.

## 11. Media

Public marketplace performance needs safe derivatives (thumbnail, card,
gallery, web-large). Serving originals forever is not the target. Untrusted
binary processing needs independent security review; prefer a well-maintained
decoding/processing library or an isolated processing path unless a custom
implementation is rigorously justified and independently validated.
