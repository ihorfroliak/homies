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

---

Founder decisions of 2026-09-24 carried by TASK-002 (§23, §24, §25, §44).
They rank with 04a.

## 12. LONG_TERM and MONTHLY

LONG_TERM is the **non-transactional residential-rental marketplace mode**. It
is not defined by a mandatory six-month minimum: a LONG_TERM listing is
open-ended or states a minimum term of at least one month. MONTHLY remains the
future **transactional** product (Phase 2) and is not activated by this;
nothing in Phase 1A may tell a user that shorter stays are "booked through
Homies".

## 13. APARTHOTEL_UNIT

`PropertyType = APARTMENT | HOUSE`; `APARTHOTEL_UNIT` is an APARTMENT
**subtype** and the information is preserved. The subtype does not pull
hospitality or short-stay behaviour into Phase 1. Publication of such a unit
**fails closed** until an explicit residential-use eligibility policy exists.
**LEGAL/POLICY REVIEW REQUIRED** before that policy is written; Homies does not
invent Polish legal eligibility rules. ROOM is never a property type.

## 14. Viewing times across daylight-saving changes

A Phase-1 viewing slot maps **one local wall time to exactly one UTC
instant**. Nonexistent (spring-forward) wall times are not offered.
Ambiguous (fall-back) wall times are not offered in Phase 1 until the domain
and UI explicitly support choosing the occurrence. Correctness is preferred
over one extra slot a year.

## 15. Media processing

The media trust boundary is a **maintained decoding library** (decision
`REPLACE_WITH_MAINTAINED_LIBRARY`, from the TASK-001 audit): images are
decoded, bounded, re-encoded without original metadata, and verified; the
upload as received is never published. Isolated processing follows when
derivatives or scale justify it.

## 16. Public location precision — no public EXACT

Decision D-58 (product arbiter, TASK-010R, after the TASK-011 audit). **Exact
location is private.** The exact residential coordinate is private /
authorized data, stored on the Property. A public listing never exposes it:
public residential location is a privacy-reduced representation only —
APPROXIMATE (the deterministic grid cell's centre) or DISTRICT (no point).
**There is no owner opt-in exception** for anonymous/public exact coordinates.
The `EXACT` value of the location-precision enum in 04 is withdrawn for
public use: a new request for it is refused (422), the database refuses to
store it, and any stored EXACT offer was converted to APPROXIMATE with its
public point recomputed (the private point untouched). This supersedes the
opt-in EXACT behaviour implemented since C5.

## 17. Structured geography vs legacy location mirrors

Decision D-57 (TASK-010R, closing TASK-011 GEO-02/GEO-03). For a
**STRUCTURED** record the reference entities — Country, AdministrativeArea,
Locality, GeoArea — are authoritative: public display, owner display and the
city/district compatibility filters read their **current** names. For an
**UNSTRUCTURED / LEGACY_BACKFILL** record, or for any part an address does not
reference, the legacy free-text mirror (`properties.city`, `district`, and
the typed text on the address) is the fallback. A referenced name is never
copied into a mirror (mirrors hold "" for it), so no copy can go stale on a
rename or overflow a narrower column; a mirror that still holds a copied name
is never read while the reference exists. A locality-bound GeoArea must lie
inside every place the address names (its locality, or the chosen
administrative area's subtree); a GeoArea bound to no locality is
country-wide by its own meaning. The same rule governs the eventual removal
of the mirrors.
