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

## 18. Listing freshness — derived dates, one visibility rule

Decisions D-59–D-62, D-65 (TASK-012). The only stored freshness fact is
`last_confirmed_available_at` (04 §43): when someone with authority last
confirmed the offer is still current. Publication counts as confirmation. 04
§43's `reconfirm_at` and `stale_at` are **derived, not stored**:
`reconfirm_at = last + CONFIRMATION_VALID_FOR`, `stale_at = last +
AUTO_PAUSE_AFTER`, evaluated at the database decision time, with the policy
(Phase 1A: 14 days, +7 grace = 21) kept in one mutable place. 04 §127's
search rule therefore reads `status = active AND last_confirmed_available_at >
now − AUTO_PAUSE_AFTER`, and the same rule gates every public path. The
`stale` status (04 §43 STALE) is written only by the freshness maintenance
sweep; `stale → active` only through an authorised confirmation or
publication with every publication check; `archived` is terminal. "Confirmed
current" is not identity or property verification and is never labelled so.

## 19. Move-in availability — unknown is unknown

Decision D-64 (TASK-012). `available_from = NULL` means the move-in date was
not given — **never** "available now". Such a listing may appear in the
general board, is shown as unknown, is recommended to add a date, and is not
matched by an explicit `available_by` filter. No date is inferred or
migrated in. Whether a known date means "now" is derived on the database's
UTC date, never stored.

## 20. Time: instants, elapsed durations, UTC dates

Decision D-67 (TASK-012R, after TASK-012A F12A-01). The same stored instant
and the same decision instant must produce the same business result whatever
TimeZone a PostgreSQL session uses. Policy windows expressed in days (the
freshness 14/21 days of §18) are **elapsed durations** — 14 × 24 h, 21 × 24 h
— and are never computed by calendar-day arithmetic, so a DST change cannot
move them. Application code treats every instant as UTC before subtracting,
adding, taking a date or building an identity from it; "today", where a rule
needs one (move-in, §19), is the UTC date of the database decision instant;
an identity derived from an instant (an event's dedup key) uses one canonical
UTC spelling. The database clock remains the authority; forcing sessions to
UTC is defence in depth, never the reason a rule is correct.

## 21. Discovery — one query, the public point, honest money

Decisions D-68–D-74 (TASK-013). Public search and the public map answer one
canonical query (`SearchQuery`): dimensions combine with AND, repeated values
of one dimension with OR; contradictions are validation errors, unlikely
combinations empty results. Every result satisfies the single
public-visibility rule of §18. Anonymous spatial discovery (viewport,
radius) uses **only the public, privacy-reduced point** — never the exact
residential point (§16). The map is a lighter projection of the list's own
result set and says how many matching listings have no public point. Money
filters name their money — base rent, stated monthly total, move-in total —
and the response says whether utilities are included, estimated or not
stated. Every sort ends on the listing id; the search state is the canonical
URL query. 04 §127's search rule is implemented by this model.

**Input contract (D-76, TASK-013R).** A discovery query is validated before any SQL: finite numbers inside documented bounds, NUL-free bounded text and ids, catalogue values for controlled vocabularies, bounded repetition and a bounded canonical query. Invalid is 422; valid and unmatched is an empty 200. The canonical query is deterministic: empty optional values are absent, repeated values de-duplicated and sorted, −0.0 written as 0.0, text kept as given. The map's `total`, `with_point` and `without_point` come from one aggregate and always add up.

## 22. Saved Listing, Saved Search and alerts (TASK-014)

Decisions D-78…D-82. Founder / Product-Arbiter decision, TASK-014 Phase B
(2026-09-28).

**Saved Listing — deliberate supersession.** For Phase 1A a renter saves the
**Listing** — the marketplace offer they saw — `SavedListing (user_id,
listing_id)`, unique per pair. This **supersedes** 04 §51
`engagement.saved_properties (user_id, property_id)` ("Save Property rather
than transient Listing") and 04 §81 invariant 20 ("Saved Property targets
Property, not transient Listing") **for Phase 1A**. Those texts are kept as
written in 04; this clarification ranks with 04 and wins for Phase 1A. A save
never follows later Listings of the same Property; *Follow Property / Follow
Home* may become a separate, later concept. A save outlives the listing's
public life: once the listing is not public the save answers a tombstone
(`saved_id`, `listing_id`, `saved_at`, `availability_status =
NO_LONGER_AVAILABLE`) — no cached title, price, media, place, owner or
contact. `saved_at` is the database instant.

**Saved Search — one search language.** A saved search stores exactly the
TASK-013 canonical query (`SearchQuery.canonical()`, D-72/D-76) with a
`query_schema_version` and `query_fingerprint = SHA-256(version, canonical
query)`, unique per user (the duplicate rule). 04 §52's versioned `criteria
jsonb` is realised as this versioned canonical string: there is no second
criteria format. Stored queries are re-validated through the live
validation; one that no longer validates (a place retired or gone, a
catalogue value withdrawn, an unsupported schema version, an unknown
parameter) is **INVALID** — explicit, never matched, never silently
broadened. A search with zero current results is a first-class save.

**Alert scope (TASK-014).** A saved-search alert means exactly: *a listing
became publicly eligible in a NEW public generation, after the search's
baseline, and currently matches the search.* The baseline is the database
instant of saving (or of changing the query): listings already matching then
are shown, never notified — no initial flood, no backfill. `public_generation`
counts public-eligibility episodes by the §18 rule (not the status label):
0 never public; +1 on every not-public → public transition (first
publication, republication after pause, stale → active, confirmation after
silent freshness expiry); never on public → public. **Deferred alert
families** (not TASK-014): price change, availability-date change, attribute
or media edits while continuously public; following a Property.

**Notification category PRODUCT.** Saved-search alerts are user-requested,
optional and unsubscribable — classified **PRODUCT**. This is Homies
**product policy, not a legal conclusion**, and PRODUCT is **not** marketing
consent. Preferences (04 §71) default PRODUCT on for IN_APP and EMAIL; any
channel can be turned off without deleting a search. PRODUCT email goes only
to a **verified** email address, resolved at send time; transactional account
email resolves the account's current address at send time (no verification
requirement stated by the identity canon). A queued alert is not authority to
send: it is re-validated at send time and otherwise ends `suppressed`.
Unsubscribe is a bearer capability (256 bits, only its hash stored, generic
response). TASK-014R: the capability of one delivery and scope is derived with a
server key (HMAC-SHA256), committed **before** the email is sent and identical on
every retry of that delivery; its effect is **single-use** — the first valid use
applies it, a replay (like an unknown or expired token) changes nothing and gets
the same generic answer, so an old link cannot switch off alerts turned back on
later. Email transport is **at-least-once** (D-09): a crash between the
provider's acceptance and the delivery's commit can send a second copy, and
every copy carries the same working links. A stored saved search whose text is
not its own canonical form, or whose fingerprint does not match, is INVALID —
never repaired or run broader.

**Account status limitation.** Phase 1A has no account deletion/status
model; for alerts "account valid" means *the user exists* (plus a verified
email for EMAIL). No parallel account lifecycle is introduced.

## 23. Reports and moderation in Phase 1A (TASK-015, founder D-1 … D-9, 2026-10-01)

Refines 04 §64 (`trust.reports`) and §65 (`trust.moderation_decisions`); it
does not replace them. Contract: `docs/tasks/TASK-015-reports-moderation-phase-a.md`.

* **Report targets in Phase 1A:** LISTING and MESSAGE. The stored `target_type`
  keeps the canonical set; USER, MEDIA and PROPERTY are not offered to users
  in 1A (moderators act on media in a listing's context).
* **Report lifecycle in 1A:** OPEN → IN_REVIEW → RESOLVED. TRIAGED and CLOSED
  remain canonical values and are unused in 1A (severity is derived at
  creation; RESOLVED is terminal). Categories are the canonical codes;
  `MISLEADING_PRICE` covers "price or key details misleading" in the 1A UI; no
  PRIVACY category is added.
* **Reports never mutate targets** (04 invariant 23). Only the application of a
  moderation decision has cross-domain effects.
* **Decisions are immutable** (§65) and form one **chain per target**: a later
  decision names the one it supersedes (`supersedes_decision_id`). The chain
  cannot fork (a decision is superseded at most once; a target has at most one
  first decision; a decision supersedes only a decision on the same target).
  The **head** — the decision nobody supersedes — is the target's current
  moderation state.
* **No ModerationCase entity** in 1A: reports are grouped by target in the
  moderator queue; the chain head and a compare-and-set on it replace a case.
* **No separate hold table or flag.** A listing is **held** while its chain
  head is `CONTENT_EDIT_REQUIRED` or `VISIBILITY_LIMITED`. Applying a hold
  moves the listing to the existing `paused` status; the public-visibility rule
  (§18) is unchanged. While held, no transition into `active` is possible
  (the single public-transition seam refuses it). A later `NO_ACTION` decision
  that supersedes the hold **releases** it; release never republishes — the
  owner republishes through the normal publication, which opens a new public
  episode (§22) and may alert saved searches (D-5).
* **Refinement columns** (additive to §64/§65): reports — `listing_id`,
  `conversation_id`, `snapshot`, `listing_public_generation_at_report`,
  `first_reviewed_at`, `resolution_decision_id`; decisions —
  `supersedes_decision_id`, `listing_id`, `reclassified_category`,
  `close_engagement`, `listing_public_generation_at_decision`; reason codes =
  the report categories plus `NOT_A_VIOLATION`, `REINSTATED_REMEDIED`,
  `REINSTATED_DECISION_ERROR`.
* **Review request seam:** `moderation_review_requests` (one open request per
  decision) is the 1A reconsideration path implied by `appeal_eligible`; it is
  not a formal appeal state machine.
* **Out of 1A:** account status and suspension (§22's limitation stands; the
  `ACCOUNT_*` actions are not used), user block, property-level holds, incidents
  (§66, safety foundation), evidence uploads.

## 24. Seeker surfaces: public facts, totals, address disclosure, re-contact (PROGRAM-001 adjudication, founder + GPT-5.6 Sol, 2026-10-04)

Recorded as D-102. Refines §16 (public location), §21 (honest money) and §23
(moderation); it replaces none of them.

* **Public floor facts (D-101).** A public Listing may show the property's
  `floor`. It does **not** show the building's total floors (`floors_total`)
  for now: together with the privacy-reduced public point (§16) and the
  subtype it raises re-identification risk. The owner-facing record keeps it.
* **Parking in the monthly total (G4).** Parking is part of the
  authoritative monthly total **only** when it is a mandatory, non-separable
  recurring payment required for that Listing; optional parking is shown
  separately and never added. Totals are never adjusted heuristically: where
  the stored price does not say whether a parking charge is mandatory, it is a
  modelling gap to close (owner input must state it), not a guess. Today the
  only parking input is a fee the owner states, stored as a mandatory monthly
  component — the gap is recorded in the roadmap, not resolved by changing
  totals.
* **Exact address and meeting details (G9).** The exact address, or meeting
  instructions (the provider may choose a meeting point instead of the flat's
  address), may be disclosed **only** after a Viewing reaches `CONFIRMED`,
  **only** to the parties of that Viewing, and **only** through an explicitly
  privacy-safe participant surface. They never enter the public Listing DTO,
  public SEO, analytics events, attribution or generic logs. Until a
  participant-only delivery model exists, nothing is disclosed (FE-003/API
  work).
* **Re-contact after a restriction (F6, extends G-14).** A requester whose
  conversation Homies restricted (`FEATURE_RESTRICTED`) can neither open a new
  conversation **nor request a Viewing** on that Listing for the same public
  generation (`listing_public_generation_at_decision`); a later legitimate
  publication generation may engage again under the normal rules. Both
  refusals carry the stable code `RECONTACT_BLOCKED`.

**FE-003 contract review (D-104 and final review D-105, founder + GPT-5.6
Sol, 2026-10-04)** — decided; implementation pending as bounded backend tasks:

* **Existing-engagement safety cleanup ≠ future-engagement generation
  gate.** When G-14 is applied, the restriction **cancels every currently
  existing** Viewing of the restricted requester on that Listing that is
  REQUESTED or CONFIRMED and starts after the moderation decision's instant,
  in the decision's transaction, with neutral notices to both sides and an
  explicit immutable cancellation source (HOMIES). This cleanup does **not**
  infer which publication generation created a Viewing (Viewings carry no
  such field). Past and terminal Viewings are untouched. Separately, the F6 /
  G-14 gate stays **generation-scoped** for **new** engagement: same
  restricted generation → `RECONTACT_BLOCKED`; a later legitimate generation
  → allowed under the normal rules. Generation-specific cancellation would
  need a durable publication-generation identifier on Viewing (or another
  provable episode binding) — not introduced.
* **G-14 and contact reveal.** The restricted requester cannot obtain a
  **new or repeat** contact reveal for that Listing in the restricted
  publication generation (`RECONTACT_BLOCKED`, checked before any
  repeat-reveal path): Homies does not reveal a number again, return an
  updated one, or act as a continuing phone channel. A number disclosed
  earlier cannot be made unknown.
* **Message reports without verified contact.** An authenticated user who is
  a current side of a conversation may report another participant's USER
  message without a verified e-mail or phone. Narrow exception: in-context
  MESSAGE reports only; LISTING reports keep the verified-contact
  requirement (TASK-015). Participation, own/SYSTEM refusal, quotas and the
  one-live-report rule remain.
* **Requester identity for providers.** A server-side projection of first
  name and surname initial only; never e-mail or phone; never presented as
  verified without a separate verified identity fact.
* **Public derived viewing slots.** For a PUBLIC Listing (§18) the derived
  offered slot instants may be read without an account; viewing settings,
  windows, blackouts and capacity stay private; requesting a Viewing
  requires an account; the read is rate-limited; no exact address (§16).
  Subject to the security review of that backend change.
* **Viewing cancellation after start** is refused by the backend for both
  sides (stable code).
* **Private engagement requires a VERIFIED PropertyAuthority (security
  rule).** For every MANAGE_MESSAGES / MANAGE_VIEWINGS private read and
  write: the authority chain is in force (§2 of 02: person, active membership
  or valid representation mandate, with their own rules); the
  PropertyAuthority at its root has `verification_state = VERIFIED`; the
  actor holds the required effective scope through ownership, membership role
  or mandate. An unverified PropertyAuthority grants no access to requester
  messages, requester notes, requester projected identity, provider
  conversation actions or provider viewing reads/actions. Guards that refuse
  self-dealing or conflicts of interest keep evaluating any in-force
  authority. The legacy `host` role is never authority. Current routes do not
  yet enforce this; it remains a beta/security prerequisite until implemented
  and verified.
* **Open debt:** a REQUESTED Viewing whose start has passed stays REQUESTED;
  explicit expiry semantics are a later product/backend decision. Clients may
  show a derived "no answer — time passed" label without changing the state.
