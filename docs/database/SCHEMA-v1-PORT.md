# Domain Schema v1 — port into the existing stack

The founder's Domain Schema v1 (2026-09-23) specifies Drizzle, Fastify and
PostgreSQL 18. On 2026-09-23 the founder chose to **port its domain model into
the existing FastAPI / SQLAlchemy / Alembic backend** rather than rebuild in
TypeScript. The model is authoritative; the stack is not. This file records
what has landed, and every place the port departs from the text, with the
reason, the impact, and whether domain semantics changed (spec §131).

## Cycles

| Cycle | Scope | State |
|---|---|---|
| C1 | Money columns → `bigint`; public listing stops exposing `owner_id` | `c3ab28c` |
| C2 | `legal_parties`, `person_legal_parties`, `property_authorities`, scopes; one authorization service; publish requires a VERIFIED authority; revocation takes listings down | `49641c0` |
| C3 | `spaces` (WHOLE_PROPERTY / ROOM); offers point at a space through a composite key; archiving takes listings down; search filters and sorts on the listed area | `903312c` |
| C4 | Temporal price components with contiguous history; stored summaries (headline, monthly, move-in) recomputed in the same transaction; optimistic concurrency on price edits; flat price columns dropped | `dba093a` |
| C5 | PostGIS; exact location private (`properties.exact_geog`); listings get a public point at the owner's precision (EXACT / APPROXIMATE grid cell / DISTRICT); viewport and geodesic radius search on a GiST index; public shape gains city and district | this commit |
| C6 | Organizations, memberships, representation mandates (agency chain) | next |
| C7 | Conversations, messages, viewings | |
| C8 | Files and media | |

## Deviations

| # | Spec | Port | Why | Impact | Semantics changed? |
|---|---|---|---|---|---|
| 1 | Drizzle + Fastify + node-postgres (header) | FastAPI + SQLAlchemy + Alembic | Founder decision 2026-09-23: keep ~430 tests and the ledger, payments, verification and DR guarantees already proven | Implementation language only | No |
| 2 | One PostgreSQL schema per domain (§11) | Single `public` schema; ownership by code module | Moving ~30 existing tables changes no behaviour and touches every query. Revisit when per-domain database roles are needed | Logical ownership lives in `app/modules/*`, not in the catalogue | No |
| 3 | `uuid` columns, `uuidv7()` defaults (§4) | `varchar(36)` holding uuid4 | CI runs PostgreSQL 16 (no `uuidv7()`), and every existing foreign key is `varchar(36)`; changing the type ripples through all of them | Loses v7 index locality; ids are equally opaque | No |
| 4 | PostgreSQL 18 + PostGIS 3.6 (§1, §9) | PostgreSQL 16 + PostGIS 3.4 (`postgis/postgis:16-3.4`, pinned by digest in CI) | Same major version as the existing app; 18 is a separate upgrade | No `uuidv7()` (see 3) | No |
| 5 | `legal_first_name` / `legal_last_name` NOT NULL (§17) | Nullable; required before an authority can be VERIFIED | Registration never collected legal names; inventing them from a display name would record as *legal* a name nobody gave as legal | A claim cannot be verified without one; once verified, the name is locked | No — the requirement moves to the point that depends on it |
| 6 | `trust.authority_verifications` (§63) | Verification recorded as `verification_state` + an audit event | The decision is a human one against evidence; the evidence record (land-register number, document) lands with the trust cycle | Who verified and when is in `audit_log`; what they looked at is not yet stored | No |
| 7 | No triggers by default (§84) | Append-only triggers kept on ledger, audit and domain events (D-04), plus role privileges (D-43) | Spec §84 allows small technical-integrity triggers; §68 itself requires audit to be append-only | Defence in depth | No |
| 8 | SHORT_STAY bookings deferred to Phase 3 (§97) | Existing short-stay listings, bookings, payments and ledger retained | Already built and tested; not on the Phase-1 path | Short-stay listings are still authorised by `listings.host_id`, not by property authority — **open gap, to close before short-stay is reactivated** | Yes, for short-stay only |
| 9 | UPPER_CASE status values (§7) | New tables UPPER_CASE; pre-existing tables keep lower-case values | Rewriting existing status values is churn with a migration risk and no behavioural gain | Two casings coexist until a table is next reworked | No |
| 10 | No `owner_id` on Property (§110) | `properties.owner_id` kept as the *creating account* | Removing it means rewriting the short-stay path in the same cycle | Not used for authorisation on the board; authority is | No |
| 11 | `property_type` is APARTMENT or HOUSE (§26) | Existing six lower-case types kept (apartment, studio, house, townhouse, loft, aparthotel_unit); `room` refused for new properties | Narrowing the vocabulary rewrites existing rows and the filter API for no behavioural gain; `room` is the one value that contradicts the model, and it is closed | A richer type list than the spec | No — the frozen rule (room is a Space) holds |
| 12 | `properties.area_m2 numeric(10,2)` (§26) | `properties.area_m2` stays integer; `spaces.area_m2` is `numeric(10,2)` | Changing the property column touches every filter and existing value for no user-visible gain yet; rooms are where fractional areas matter | Whole-flat areas are whole square metres | No |
| 13 | `marketplace.listings` is the listing aggregate (§42) | `classified_offers` plays that role; `listing_price_components.listing_id` references it | The board's offer table already carries status, space, terms and contact rules; renaming it is churn with no behavioural gain | Name only | No |
| 14 | Price composed of any component types (§46) | The API writes rent, building fee, utilities, parking and deposit; the other types (agency, cleaning, Homies fee, sale price) are accepted by the schema but no endpoint writes them yet | Nothing on the board charges them today; SALE and agency listings arrive later | Those components cannot yet be entered | No |
| 15 | Structured `addresses` table with `geo_areas` hierarchy, `exact_geog` on the address (§23–§24) | Address stays text on the property; `exact_geog` is a generated column on `properties`; no `geo_areas` yet | The address table and area hierarchy need a geocoder and seeded boundaries; the privacy rule does not | District search is by name, not by polygon | No — exact location is private either way |
| 16 | Public location precision on the listing (§42) | Same, plus a rule the spec leaves open: APPROXIMATE is the centre of a fixed ~550 m grid cell, not a random offset | A fresh random offset per publication can be averaged back to the flat; a grid cell cannot | Flats sharing a cell share a point | No |

## What C2 changed in behaviour

* Registering a property records an ACTIVE, **UNVERIFIED** OWNER authority held
  by the registrant's PERSON legal party.
* An unverified claim can prepare listings and take them down. **It cannot
  publish** — `POST /v1/classifieds/{id}/publish` answers 403 until an admin
  verifies the claim (`POST /v1/admin/property-authorities/{id}/verify`).
* Verification requires a legal name (`PUT /v1/me/legal-identity`); the name
  locks once a claim is verified.
* Revoking an authority pauses the property's live listings unless another
  verified right still backs them.
* Existing properties were backfilled as UNVERIFIED; listings already on the
  board were left as they are.
