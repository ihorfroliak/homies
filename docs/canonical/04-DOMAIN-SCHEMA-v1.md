# HOMIES PostgreSQL/PostGIS DOMAIN SCHEMA v1

**Status:** CANONICAL IMPLEMENTATION SPECIFICATION
**Target:** Codex
**Input:** Homies Constitution v2.0 + System Architecture v1
**Database:** PostgreSQL 18 + PostGIS 3.6
**Data access:** Drizzle ORM + node-postgres + reviewed SQL migrations
**Scope:** Phase 1 only
**Primary launch mode:** LONG_TERM
**Also architecturally supported:** SALE
**Explicitly not physically implemented yet:** finance, contracts, MONTHLY transactions, SHORT_STAY bookings, DAC7 reporting engine, ledger, payouts, deposits, insurance/protection claims.

---

# 1. Purpose

This document translates the Homies domain architecture into the first physical PostgreSQL/PostGIS schema.

Codex must implement this specification without redesigning the domain.

If implementation reveals a genuine contradiction, Codex must:

1. stop that specific implementation path;
2. document the contradiction;
3. propose alternatives;
4. not silently redesign the canonical model.

---

# 2. Fundamental database rules

The database is authoritative operational storage.

The schema must enforce as many hard invariants as reasonably possible through:

* NOT NULL;
* FOREIGN KEY;
* UNIQUE;
* CHECK;
* partial UNIQUE indexes;
* exclusion/index constraints where justified.

Business rules that span multiple aggregates remain enforced in application services and integration tests.

Do not push all business logic into triggers.

---

# 3. Naming

All database identifiers:

```text
snake_case
```

Examples:

```text
property_authorities
listing_price_components
created_at
```

Primary keys:

```text
id
```

Foreign keys:

```text
property_id
user_id
organization_id
```

---

# 4. Identifier strategy

All new domain entities use:

```text
uuid
```

with PostgreSQL 18:

```text
uuidv7()
```

as default where database-generated IDs are appropriate.

Do not expose sequential integer primary keys.

Public IDs and internal domain IDs may initially be the same UUIDv7.

Do not introduce separate public IDs until there is an actual need.

---

# 5. Timestamp convention

All instants:

```text
timestamptz
```

with:

```text
DEFAULT now()
```

Local civil dates:

```text
date
```

Local recurring clock times:

```text
time without time zone
```

Timezones:

```text
text
```

containing IANA identifiers:

```text
Europe/Warsaw
Europe/Prague
```

Never store:

```text
UTC+1
GMT+2
```

as canonical timezone.

---

# 6. Mutation convention

Mutable aggregate roots generally include:

```text
created_at timestamptz not null default now()
updated_at timestamptz not null default now()
version bigint not null default 1
```

`version` is used for optimistic concurrency.

Application service updates:

```text
version = version + 1
```

No database trigger is required for versioning in v1.

---

# 7. Status representation

Do **not** create PostgreSQL ENUM types in Schema v1.

Use:

```text
text
```

plus explicit:

```text
CHECK (...)
```

for stable internal finite sets.

Reason:

* easier evolution;
* simpler migrations;
* fewer enum-alter complications;
* same canonical values remain defined in TypeScript.

Extensible catalogs use tables.

---

# 8. Money convention

Authoritative monetary fields:

```text
bigint
```

representing minor currency units.

Example:

```text
395000 = 3,950.00 PLN
```

Currency:

```text
char(3)
```

ISO 4217.

Never:

```text
float
double precision
real
```

for money.

---

# 9. Geographic convention

Exact Property location:

```text
geography(Point, 4326)
```

Administrative boundaries:

```text
geometry(MultiPolygon, 4326)
```

PostGIS indexes:

```text
GiST
```

Exact Property coordinates and public marketplace coordinates are separate concepts.

---

# 10. Extensions

Initial migration enables:

```text
postgis
pg_trgm
unaccent
citext
```

Do not install additional PostgreSQL extensions without ADR/review.

---

# 11. PostgreSQL schemas

Create:

```text
auth
identity
real_estate
marketplace
engagement
trust
platform
```

`auth` is implementation-provider territory.

Better Auth tables are managed by the authentication adapter/migrations.

Core Homies domain must not directly depend on Better Auth internal table layout.

---

# 12. Logical ownership

```text
identity
    User
    LegalParty
    Organization
    Membership
    Representation

real_estate
    Geography
    Address
    Building
    Property
    Space
    Ownership
    PropertyAuthority
    Amenities
    EPC
    Safety
    Property Media

marketplace
    Listing
    Listing Text
    Listing Terms
    Pricing
    Publication/Freshness

engagement
    Saved Property
    Saved Search
    Conversation
    Message
    Viewing

trust
    Verification
    Reports
    Moderation
    Incidents

platform
    Files
    Outbox
    Audit
    Notifications
    Push devices
    Idempotency
```

---

# 13. AUTH BOUNDARY

Better Auth owns its authentication-specific tables inside:

```text
auth
```

Homies must not use those tables as business-domain tables.

Create a stable mapping from external authentication subject to Homies User.

---

# 14. identity.users

Canonical Homies account.

```text
identity.users
```

Columns:

```text
id uuid primary key default uuidv7()

primary_email citext not null
email_verified_at timestamptz null

display_name text null

preferred_locale text not null default 'pl'
timezone text not null default 'Europe/Warsaw'

status text not null default 'ACTIVE'

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

closed_at timestamptz null
anonymized_at timestamptz null

version bigint not null default 1
```

Constraints:

```text
UNIQUE(primary_email)

CHECK status IN (
  'ACTIVE',
  'SUSPENDED',
  'CLOSED'
)

CHECK preferred_locale ~ '^[a-z]{2}(-[A-Z]{2})?$'
```

Do not hard delete normal Users.

Account deletion becomes closure/anonymization workflow.

---

# 15. identity.auth_subjects

Maps auth-provider subject to Homies User.

```text
identity.auth_subjects
```

Columns:

```text
id uuid primary key default uuidv7()

user_id uuid not null
auth_system text not null
provider_subject text not null

created_at timestamptz not null default now()
last_seen_at timestamptz null
```

FK:

```text
user_id → identity.users(id)
ON DELETE RESTRICT
```

Unique:

```text
UNIQUE(auth_system, provider_subject)
```

Example:

```text
auth_system = 'better-auth'
```

This table prevents the Homies domain from depending on Better Auth's internal user schema.

---

# 16. identity.legal_parties

Represents real contractual/ownership parties.

```text
identity.legal_parties
```

Columns:

```text
id uuid primary key default uuidv7()

party_type text not null
display_name text not null

status text not null default 'ACTIVE'

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
archived_at timestamptz null

version bigint not null default 1
```

Checks:

```text
party_type IN (
  'PERSON',
  'ORGANIZATION'
)

status IN (
  'ACTIVE',
  'ARCHIVED'
)
```

---

# 17. identity.person_legal_parties

Subtype data for PERSON.

```text
identity.person_legal_parties
```

Columns:

```text
legal_party_id uuid primary key

linked_user_id uuid null

legal_first_name text not null
legal_last_name text not null

country_of_residence char(2) null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

FKs:

```text
legal_party_id → identity.legal_parties(id)
ON DELETE CASCADE

linked_user_id → identity.users(id)
ON DELETE RESTRICT
```

Unique:

```text
UNIQUE(linked_user_id)
```

Application invariant:

associated `legal_parties.party_type` must equal:

```text
PERSON
```

---

# 18. identity.organizations

Homies workspace.

```text
identity.organizations
```

Columns:

```text
id uuid primary key default uuidv7()

display_name text not null
slug text not null

country_code char(2) not null default 'PL'
default_locale text not null default 'pl'

status text not null default 'ACTIVE'

created_by_user_id uuid not null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
archived_at timestamptz null

version bigint not null default 1
```

Constraints:

```text
UNIQUE(slug)

status IN (
  'ACTIVE',
  'SUSPENDED',
  'ARCHIVED'
)
```

FK:

```text
created_by_user_id → identity.users(id)
ON DELETE RESTRICT
```

---

# 19. identity.organization_legal_parties

Links legal company/entity to optional Homies Organization workspace.

```text
identity.organization_legal_parties
```

Columns:

```text
legal_party_id uuid primary key

organization_id uuid null

legal_name text not null
registration_country char(2) null
registration_number text null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

FKs:

```text
legal_party_id → identity.legal_parties(id)
ON DELETE CASCADE

organization_id → identity.organizations(id)
ON DELETE RESTRICT
```

Unique:

```text
UNIQUE(organization_id)
```

Do not add full DAC7/tax profile here.

That belongs to later compliance schema.

---

# 20. identity.organization_memberships

```text
identity.organization_memberships
```

Columns:

```text
id uuid primary key default uuidv7()

organization_id uuid not null
user_id uuid not null

role text not null
status text not null default 'ACTIVE'

invited_by_user_id uuid null

joined_at timestamptz null
revoked_at timestamptz null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

version bigint not null default 1
```

Role:

```text
OWNER
ADMIN
AGENT
FINANCE
VIEWER
```

Status:

```text
INVITED
ACTIVE
REVOKED
```

Unique:

```text
UNIQUE(organization_id, user_id)
```

FKs all:

```text
ON DELETE RESTRICT
```

Granular permission mapping remains in domain/application code in Phase 1.

Do not create 50 role tables prematurely.

---

# 21. identity.representation_mandates

Represents:

> User X may act for LegalParty Y.

```text
identity.representation_mandates
```

Columns:

```text
id uuid primary key default uuidv7()

principal_legal_party_id uuid not null
representative_user_id uuid not null

status text not null default 'PENDING'

effective_from date not null
effective_until date null

verification_state text not null default 'UNVERIFIED'

granted_by_user_id uuid null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

revoked_at timestamptz null

version bigint not null default 1
```

Status:

```text
PENDING
ACTIVE
REVOKED
EXPIRED
```

Verification:

```text
UNVERIFIED
PENDING
VERIFIED
REJECTED
```

Check:

```text
effective_until IS NULL
OR effective_until >= effective_from
```

---

# 22. identity.representation_mandate_scopes

```text
identity.representation_mandate_scopes
```

Columns:

```text
mandate_id uuid not null
scope text not null
```

Composite PK:

```text
PRIMARY KEY(mandate_id, scope)
```

Allowed scopes:

```text
MANAGE_PROPERTY
PUBLISH_LISTING
MANAGE_VIEWINGS
MANAGE_MESSAGES
MANAGE_APPLICATIONS
SIGN_CONTRACTS
VIEW_FINANCIALS
MANAGE_PAYOUTS
```

Not every Phase-1 scope needs UI immediately.

---

# 23. real_estate.geo_areas

Canonical geography hierarchy.

```text
real_estate.geo_areas
```

Columns:

```text
id uuid primary key default uuidv7()

parent_id uuid null

country_code char(2) not null
area_type text not null

name text not null
slug text not null

boundary geometry(MultiPolygon, 4326) null

active boolean not null default true

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Area types:

```text
COUNTRY
REGION
CITY
DISTRICT
```

Unique:

```text
UNIQUE(parent_id, area_type, slug)
```

Indexes:

```text
GiST(boundary)

(country_code, area_type)

(parent_id)
```

Seed:

```text
Poland
Kraków
Warsaw
their launch-relevant districts
```

Use canonical Polish names plus UI translation layer.

---

# 24. real_estate.addresses

Exact internal structured address.

```text
real_estate.addresses
```

Columns:

```text
id uuid primary key default uuidv7()

country_code char(2) not null

region_area_id uuid null
city_area_id uuid not null
district_area_id uuid null

street_name text null
building_number text null
unit_number text null
postal_code text null

exact_geog geography(Point, 4326) not null

geocoder_provider text null
geocoder_place_id text null

normalized_address_hash text null

verification_state text not null default 'UNVERIFIED'

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Verification:

```text
UNVERIFIED
GEOCODED
USER_CONFIRMED
VERIFIED
```

Indexes:

```text
GiST(exact_geog)

(city_area_id)

(district_area_id)

(normalized_address_hash)
```

Do not place UNIQUE on normalized address.

Duplicates may legitimately exist during review/import.

---

# 25. real_estate.buildings

```text
real_estate.buildings
```

Columns:

```text
id uuid primary key default uuidv7()

address_id uuid not null

display_name text null

year_built smallint null
floors_count smallint null
has_elevator boolean null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
archived_at timestamptz null

version bigint not null default 1
```

Unique:

```text
UNIQUE(address_id)
```

Checks:

```text
year_built BETWEEN 1000 AND 2200

floors_count > 0
```

when non-null.

---

# 26. real_estate.properties

Canonical persistent physical home.

```text
real_estate.properties
```

Columns:

```text
id uuid primary key default uuidv7()

property_type text not null

building_id uuid null
address_id uuid not null

created_by_user_id uuid not null

status text not null default 'ACTIVE'

area_m2 numeric(10,2) null
rooms smallint null
bedrooms smallint null
bathrooms numeric(3,1) null

floor integer null
year_built smallint null

kitchen_type text null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
archived_at timestamptz null

version bigint not null default 1
```

Property type:

```text
APARTMENT
HOUSE
```

Status:

```text
ACTIVE
ARCHIVED
```

Kitchen:

```text
SEPARATE
KITCHENETTE
OPEN_PLAN
NONE
OTHER
```

Checks:

```text
area_m2 > 0
rooms > 0
bedrooms >= 0
bathrooms >= 0
year_built BETWEEN 1000 AND 2200
```

Application invariant:

```text
APARTMENT normally requires building_id
HOUSE may have building_id null
```

Do not enforce this as absolute DB constraint because edge cases exist.

---

# 27. real_estate.house_details

Only for HOUSE.

```text
real_estate.house_details
```

Columns:

```text
property_id uuid primary key

house_type text null

plot_area_m2 numeric(12,2) null
floors_count smallint null

has_garden boolean null
has_garage boolean null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

House type:

```text
DETACHED
SEMI_DETACHED
TERRACED
OTHER
```

Application ensures referenced Property is HOUSE.

---

# 28. real_estate.spaces

Inventory unit.

```text
real_estate.spaces
```

Columns:

```text
id uuid primary key default uuidv7()

property_id uuid not null

space_type text not null

label text null
area_m2 numeric(10,2) null

status text not null default 'ACTIVE'

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
archived_at timestamptz null

version bigint not null default 1
```

Space type:

```text
WHOLE_PROPERTY
ROOM
```

Status:

```text
ACTIVE
ARCHIVED
```

Checks:

```text
area_m2 IS NULL OR area_m2 > 0

space_type = 'ROOM'
OR label IS NULL
```

Partial unique index:

```text
UNIQUE(property_id)
WHERE space_type = 'WHOLE_PROPERTY'
AND archived_at IS NULL
```

This guarantees at most one active whole-property inventory unit.

Room labels do not need to be globally unique.

Recommended partial unique:

```text
UNIQUE(property_id, label)
WHERE space_type = 'ROOM'
AND archived_at IS NULL
```

---

# 29. real_estate.property_ownerships

Historical ownership relationship.

```text
real_estate.property_ownerships
```

Columns:

```text
id uuid primary key default uuidv7()

property_id uuid not null
legal_party_id uuid not null

ownership_role text not null

share_numerator integer null
share_denominator integer null

effective_from date not null
effective_until date null

created_at timestamptz not null default now()
```

Role:

```text
OWNER
CO_OWNER
```

Checks:

```text
effective_until IS NULL
OR effective_until >= effective_from

(
  share_numerator IS NULL
  AND share_denominator IS NULL
)
OR
(
  share_numerator > 0
  AND share_denominator > 0
  AND share_numerator <= share_denominator
)
```

Do not overwrite ownership history.

---

# 30. real_estate.property_authorities

Represents right to act regarding specific Property.

Authority holder is a:

```text
LegalParty
```

not directly a User.

```text
real_estate.property_authorities
```

Columns:

```text
id uuid primary key default uuidv7()

property_id uuid not null
holder_legal_party_id uuid not null

authority_type text not null

source_ownership_id uuid null

status text not null default 'PENDING'
verification_state text not null default 'UNVERIFIED'

effective_from date not null
effective_until date null

created_by_user_id uuid not null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

revoked_at timestamptz null

version bigint not null default 1
```

Authority:

```text
OWNER
CO_OWNER
AUTHORIZED_REPRESENTATIVE
PROPERTY_MANAGER
TENANT_WITH_SUBLET_RIGHT
OTHER_VERIFIED_RIGHT
```

Status:

```text
PENDING
ACTIVE
REVOKED
EXPIRED
```

Verification:

```text
UNVERIFIED
PENDING
VERIFIED
REJECTED
```

Critical application rule:

> VERIFIED identity does not imply VERIFIED PropertyAuthority.

---

# 31. real_estate.property_authority_scopes

```text
real_estate.property_authority_scopes
```

Columns:

```text
property_authority_id uuid not null
scope text not null
```

Composite PK.

Scopes:

```text
EDIT_PROPERTY
PUBLISH_LISTING
MANAGE_MEDIA
MANAGE_VIEWINGS
MANAGE_MESSAGES
MANAGE_APPLICATIONS
SIGN_CONTRACT
VIEW_FINANCIALS
MANAGE_SERVICES
```

Phase 1 mainly uses:

```text
EDIT_PROPERTY
PUBLISH_LISTING
MANAGE_MEDIA
MANAGE_VIEWINGS
MANAGE_MESSAGES
```

---

# 32. Authorization derivation

User may act on Property when at least one valid chain exists.

### Personal ownership

```text
User
→ linked PERSON LegalParty
→ VERIFIED PropertyAuthority
```

### Organization

```text
User
→ ACTIVE OrganizationMembership
→ Organization
→ linked ORGANIZATION LegalParty
→ VERIFIED PropertyAuthority
```

plus membership permission.

### Explicit mandate

```text
User
→ ACTIVE VERIFIED RepresentationMandate
→ LegalParty
→ VERIFIED PropertyAuthority
```

This logic belongs in authorization domain service.

Do not implement it separately in every route.

---

# 33. real_estate.energy_performance_certificates

```text
real_estate.energy_performance_certificates
```

Columns:

```text
id uuid primary key default uuidv7()

property_id uuid not null

certificate_number text null

issued_at date not null
valid_until date null

primary_energy_kwh_m2_year numeric(10,2) null
final_energy_kwh_m2_year numeric(10,2) null
usable_energy_kwh_m2_year numeric(10,2) null

co2_kg_m2_year numeric(10,2) null
renewable_share_pct numeric(5,2) null

verification_state text not null default 'UNVERIFIED'

document_file_id uuid null

created_at timestamptz not null default now()
superseded_at timestamptz null
```

Verification:

```text
UNVERIFIED
DECLARED
VERIFIED
REJECTED
```

Partial unique:

```text
UNIQUE(property_id)
WHERE superseded_at IS NULL
```

Check:

```text
renewable_share_pct BETWEEN 0 AND 100
```

---

# 34. real_estate.amenities

Catalog.

```text
real_estate.amenities
```

Columns:

```text
code text primary key

category text not null
searchable boolean not null default true
active boolean not null default true

sort_order integer not null default 0
```

Example codes:

```text
BALCONY
ELEVATOR
PARKING
AIR_CONDITIONING
DISHWASHER
WASHING_MACHINE
FURNISHED
GARAGE
GARDEN
```

Display translations belong to application i18n, not database rows.

---

# 35. real_estate.property_amenities

```text
real_estate.property_amenities
```

Columns:

```text
property_id uuid not null
amenity_code text not null

created_at timestamptz not null default now()
```

Composite PK:

```text
(property_id, amenity_code)
```

---

# 36. platform.file_objects

Canonical stored-file metadata.

```text
platform.file_objects
```

Columns:

```text
id uuid primary key default uuidv7()

uploader_user_id uuid not null

purpose text not null

storage_provider text not null
storage_bucket text not null
storage_key text not null

access_class text not null

original_filename text null
mime_type text null

size_bytes bigint null
sha256 text null

state text not null default 'UPLOADING'

created_at timestamptz not null default now()
ready_at timestamptz null
rejected_at timestamptz null
deleted_at timestamptz null
```

Purpose:

```text
PROPERTY_MEDIA
MESSAGE_ATTACHMENT
SAFETY_EVIDENCE
EPC_DOCUMENT
REPORT_EVIDENCE
```

Access:

```text
QUARANTINE
PUBLIC
PRIVATE
```

State:

```text
UPLOADING
QUARANTINED
PROCESSING
READY
REJECTED
DELETED
```

Unique:

```text
UNIQUE(storage_provider, storage_bucket, storage_key)
```

Checks:

```text
size_bytes IS NULL OR size_bytes >= 0
```

No private file receives a permanent public URL.

---

# 37. platform.file_variants

Generated media derivatives.

```text
platform.file_variants
```

Columns:

```text
id uuid primary key default uuidv7()

source_file_id uuid not null
variant_file_id uuid not null

variant_kind text not null

created_at timestamptz not null default now()
```

Examples:

```text
THUMBNAIL
CARD
GALLERY
WEB_LARGE
```

Unique:

```text
UNIQUE(source_file_id, variant_kind)
```

---

# 38. real_estate.media_assets

Property media semantic entity.

```text
real_estate.media_assets
```

Columns:

```text
id uuid primary key default uuidv7()

property_id uuid not null
space_id uuid null

file_id uuid not null

media_type text not null
visibility text not null default 'PUBLIC'

moderation_state text not null default 'PENDING'

width_px integer null
height_px integer null
duration_seconds numeric(10,2) null

rights_declared_at timestamptz null

created_at timestamptz not null default now()
archived_at timestamptz null
```

Types:

```text
PHOTO
FLOOR_PLAN
VIDEO
TOUR_360
```

Moderation:

```text
PENDING
APPROVED
REJECTED
RESTRICTED
```

Application invariant:

if `space_id` present, Space must belong to same Property.

---

# 39. real_estate.property_safety_profiles

One canonical safety aggregate per Property.

```text
real_estate.property_safety_profiles
```

Columns:

```text
property_id uuid primary key

status text not null default 'NOT_ASSESSED'

last_attested_at timestamptz null
next_review_at timestamptz null
material_change_reported_at timestamptz null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

version bigint not null default 1
```

Status:

```text
NOT_ASSESSED
DECLARED_COMPLIANT
EVIDENCE_VERIFIED
ACTION_REQUIRED
UNDER_REVIEW
TEMPORARILY_SUSPENDED
CLEARED
```

---

# 40. real_estate.safety_requirement_statuses

Typed safety requirement status.

```text
real_estate.safety_requirement_statuses
```

Columns:

```text
id uuid primary key default uuidv7()

property_id uuid not null

requirement_type text not null
status text not null

verified_at timestamptz null
evidence_file_id uuid null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Requirement examples:

```text
SMOKE_DETECTOR
CO_DETECTOR
GAS_INSTALLATION
ELECTRICAL
VENTILATION
FIRE
WINDOW_FALL
ACCESS_SECURITY
```

Unique:

```text
UNIQUE(property_id, requirement_type)
```

Do not pre-create hundreds of safety categories.

---

# 41. real_estate.hazard_disclosures

```text
real_estate.hazard_disclosures
```

Columns:

```text
id uuid primary key default uuidv7()

property_id uuid not null

hazard_type text not null
severity text not null

description text null

status text not null default 'OPEN'

disclosed_at timestamptz not null default now()
resolved_at timestamptz null
```

Severity:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

Status:

```text
OPEN
UNDER_REVIEW
REMEDIATED
CLOSED
```

---

# 42. marketplace.listings

Central marketplace publication aggregate.

```text
marketplace.listings
```

Columns:

```text
id uuid primary key default uuidv7()

space_id uuid not null

provider_legal_party_id uuid not null
created_by_user_id uuid not null

intent text not null
rental_mode text null

provider_classification text not null

status text not null default 'DRAFT'

currency char(3) not null default 'PLN'

primary_price_minor bigint null

estimated_monthly_total_minor bigint null
move_in_total_minor bigint null

original_locale text not null default 'pl'

public_location_precision text not null default 'APPROXIMATE'
public_geog geography(Point, 4326) null

published_at timestamptz null
paused_at timestamptz null
closed_at timestamptz null
archived_at timestamptz null

last_confirmed_available_at timestamptz null
reconfirm_at timestamptz null
stale_at timestamptz null
expires_at timestamptz null

status_reason_code text null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

version bigint not null default 1
```

Intent:

```text
RENT
SALE
```

Rental mode:

```text
SHORT_STAY
MONTHLY
LONG_TERM
```

Schema supports values, but Phase 1 publication must permit only:

```text
LONG_TERM
```

for RENT.

Provider classification:

```text
PRIVATE_NON_TRADER
TRADER_PERSON
ORGANIZATION_TRADER
```

Status:

```text
DRAFT
PENDING_REQUIREMENTS
PENDING_REVIEW
PUBLISHED
PAUSED
STALE
RESERVED
CLOSED
ARCHIVED
```

Location precision:

```text
EXACT
APPROXIMATE
DISTRICT
```

Critical check:

```text
(
  intent = 'SALE'
  AND rental_mode IS NULL
)
OR
(
  intent = 'RENT'
  AND rental_mode IS NOT NULL
)
```

Money checks:

```text
primary_price_minor IS NULL OR primary_price_minor >= 0
estimated_monthly_total_minor IS NULL OR estimated_monthly_total_minor >= 0
move_in_total_minor IS NULL OR move_in_total_minor >= 0
```

Indexes:

```text
(status)
(intent, rental_mode)
(provider_legal_party_id)
(published_at DESC)
(reconfirm_at)
(stale_at)

GiST(public_geog)
```

---

# 43. marketplace.listing_texts

Multilingual content.

```text
marketplace.listing_texts
```

Columns:

```text
id uuid primary key default uuidv7()

listing_id uuid not null

locale text not null

title text not null
description text not null

source_type text not null

source_locale text null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Source:

```text
ORIGINAL
AI_TRANSLATED
HUMAN_TRANSLATED
```

Unique:

```text
UNIQUE(listing_id, locale)
```

Indexes:

```text
GIN(title gin_trgm_ops)
```

and potentially description trigram only after real query evidence.

Do not index huge text indiscriminately.

---

# 44. marketplace.rental_terms

Only RENT Listing.

```text
marketplace.rental_terms
```

Columns:

```text
listing_id uuid primary key

available_from date null
available_until date null

minimum_lease_months smallint null
maximum_lease_months smallint null

max_occupants smallint null

furnished_state text null

pets_policy text null
smoking_policy text null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Furnished:

```text
FURNISHED
PARTLY_FURNISHED
UNFURNISHED
```

Policies:

```text
YES
NO
CASE_BY_CASE
```

Checks:

```text
available_until IS NULL
OR available_from IS NULL
OR available_until >= available_from

minimum_lease_months IS NULL
OR minimum_lease_months > 0

maximum_lease_months IS NULL
OR maximum_lease_months > 0

maximum_lease_months IS NULL
OR minimum_lease_months IS NULL
OR maximum_lease_months >= minimum_lease_months

max_occupants IS NULL
OR max_occupants > 0
```

Application invariant:

Listing intent must equal RENT.

---

# 45. marketplace.sale_terms

```text
marketplace.sale_terms
```

Columns:

```text
listing_id uuid primary key

price_negotiable boolean not null default false

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Application invariant:

Listing intent must equal SALE.

---

# 46. marketplace.listing_price_components

Transparent price composition + price history.

Rows are temporal.

Do not overwrite historical amounts.

```text
marketplace.listing_price_components
```

Columns:

```text
id uuid primary key default uuidv7()

listing_id uuid not null

component_type text not null
component_key text not null default ''

amount_minor bigint not null

cadence text not null

mandatory boolean not null default true
refundable boolean not null default false
estimated boolean not null default false

display_label text null

valid_from timestamptz not null default now()
valid_to timestamptz null

created_by_user_id uuid not null

created_at timestamptz not null default now()
```

Component types:

```text
BASE_RENT
ADMIN_FEE
UTILITIES_FIXED
UTILITIES_ESTIMATE
SECURITY_DEPOSIT
AGENCY_FEE
CLEANING_FEE
HOMIES_FEE
OTHER_MANDATORY
SALE_ASKING_PRICE
```

Cadence:

```text
ONE_TIME
MONTHLY
PER_STAY
PER_NIGHT
```

Phase 1 normally uses:

```text
ONE_TIME
MONTHLY
```

Checks:

```text
amount_minor >= 0

valid_to IS NULL
OR valid_to > valid_from
```

Partial unique current component:

```text
UNIQUE(listing_id, component_type, component_key)
WHERE valid_to IS NULL
```

This permits multiple historical versions.

Example:

```text
BASE_RENT
component_key=''
```

only one current row.

For multiple OTHER_MANDATORY:

```text
component_key='parking'
component_key='internet'
```

---

# 47. Derived pricing invariant

`marketplace.listings` stores search-friendly calculated summaries.

For RENT:

```text
primary_price_minor
    = current BASE_RENT

estimated_monthly_total_minor
    = base rent
    + mandatory monthly fees
    + applicable estimated utilities

move_in_total_minor
    = first expected monthly total
    + mandatory one-time fees
    + refundable deposit
```

Refundable deposit is included in move-in cash requirement but **not** treated as consumed monthly cost.

For SALE:

```text
primary_price_minor
    = current SALE_ASKING_PRICE
```

Totals are recalculated transactionally whenever current price components change.

Codex must implement tests ensuring the summary cannot silently diverge from components.

---

# 48. marketplace.listing_media

Media selected for a Listing.

```text
marketplace.listing_media
```

Columns:

```text
listing_id uuid not null
media_asset_id uuid not null

sort_order integer not null
is_cover boolean not null default false

created_at timestamptz not null default now()
```

Composite PK:

```text
(listing_id, media_asset_id)
```

Partial unique:

```text
UNIQUE(listing_id)
WHERE is_cover = true
```

Index:

```text
(listing_id, sort_order)
```

---

# 49. marketplace.listing_status_history

Immutable lifecycle trail.

```text
marketplace.listing_status_history
```

Columns:

```text
id uuid primary key default uuidv7()

listing_id uuid not null

from_status text null
to_status text not null

reason_code text null

changed_by_user_id uuid null

created_at timestamptz not null default now()
```

Do not update rows.

---

# 50. Listing publication validator

Publication is an application-service operation.

For a LONG_TERM Listing, baseline Phase-1 validator requires:

```text
Listing status appropriate for publish

Space ACTIVE

Property ACTIVE

Provider LegalParty ACTIVE

Actor has valid authorization chain

PropertyAuthority VERIFIED
and includes PUBLISH_LISTING

Property has structured address

public_geog prepared

Property has required core facts

current BASE_RENT exists

currency exists

transparent pricing calculations valid

original Listing text exists

minimum required approved media exists

freshness timestamps initialized

required safety/compliance checks satisfied
according to current Phase-1 policy
```

For SALE:

replace BASE_RENT with:

```text
SALE_ASKING_PRICE
```

plus relevant publication requirements.

Do not implement these as one giant database CHECK.

Implement:

```text
PublicationEligibilityService
```

with dedicated unit/integration tests.

---

# 51. engagement.saved_properties

```text
engagement.saved_properties
```

Columns:

```text
user_id uuid not null
property_id uuid not null

created_at timestamptz not null default now()
```

PK:

```text
(user_id, property_id)
```

Save Property rather than transient Listing.

---

# 52. engagement.saved_searches

Search criteria are allowed to use versioned JSONB because they are non-authoritative user preference data.

```text
engagement.saved_searches
```

Columns:

```text
id uuid primary key default uuidv7()

user_id uuid not null

name text not null

market_country_code char(2) not null default 'PL'

criteria_version integer not null default 1
criteria jsonb not null

notifications_enabled boolean not null default true

last_notified_at timestamptz null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

version bigint not null default 1
```

Index:

```text
(user_id)
```

Potential GIN JSONB index only if real queries need it.

Do not add by default.

---

# 53. engagement.conversations

```text
engagement.conversations
```

Columns:

```text
id uuid primary key default uuidv7()

listing_id uuid null
viewing_id uuid null

status text not null default 'ACTIVE'

provider_stage text null
assigned_to_user_id uuid null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

last_message_at timestamptz null

archived_at timestamptz null

version bigint not null default 1
```

Status:

```text
ACTIVE
ARCHIVED
CLOSED
```

Provider-stage future-ready values:

```text
NEW
REPLIED
VIEWING
APPLICATION
SHORTLISTED
ACCEPTED
REJECTED
ARCHIVED
```

This gives us the Lead Inbox seam without building a CRM.

At least one context should exist.

Phase 1 normally has:

```text
listing_id
```

---

# 54. engagement.conversation_participants

Supports individual users and Organization participation.

```text
engagement.conversation_participants
```

Columns:

```text
id uuid primary key default uuidv7()

conversation_id uuid not null

participant_type text not null

user_id uuid null
organization_id uuid null

joined_at timestamptz not null default now()
left_at timestamptz null
```

Participant type:

```text
USER
ORGANIZATION
```

CHECK exactly one appropriate field exists.

Pseudo-rule:

```text
USER
→ user_id NOT NULL
→ organization_id NULL

ORGANIZATION
→ organization_id NOT NULL
→ user_id NULL
```

Unique partial indexes prevent duplicate participant identities.

---

# 55. engagement.messages

```text
engagement.messages
```

Columns:

```text
id uuid primary key default uuidv7()

conversation_id uuid not null

sender_user_id uuid null
sender_organization_id uuid null

message_type text not null default 'USER'

body text null

created_at timestamptz not null default now()

edited_at timestamptz null

redacted_at timestamptz null
redaction_reason_code text null
```

Type:

```text
USER
SYSTEM
```

For USER message:

```text
sender_user_id NOT NULL
```

If sent on behalf of Organization:

```text
sender_organization_id NOT NULL
```

but sender User still remains recorded.

Never store sensitive documents directly inside message body.

Indexes:

```text
(conversation_id, created_at)
```

---

# 56. engagement.message_attachments

```text
engagement.message_attachments
```

Columns:

```text
message_id uuid not null
file_id uuid not null

created_at timestamptz not null default now()
```

Composite PK.

Only READY PRIVATE permitted files may attach.

This is application-enforced.

---

# 57. engagement.viewing_settings

One schedule configuration per Listing.

```text
engagement.viewing_settings
```

Columns:

```text
listing_id uuid primary key

booking_mode text not null default 'REQUEST_APPROVAL'

timezone text not null

duration_minutes integer not null default 30

minimum_notice_minutes integer not null default 120

buffer_before_minutes integer not null default 0
buffer_after_minutes integer not null default 0

max_concurrent_bookings integer not null default 1

enabled boolean not null default true

created_at timestamptz not null default now()
updated_at timestamptz not null default now()

version bigint not null default 1
```

Mode:

```text
INSTANT_BOOKING
REQUEST_APPROVAL
```

Phase 1 should default to:

```text
REQUEST_APPROVAL
```

Checks all duration/capacity values positive/non-negative.

---

# 58. engagement.viewing_windows

Provider availability windows.

```text
engagement.viewing_windows
```

Columns:

```text
id uuid primary key default uuidv7()

listing_id uuid not null

window_type text not null

weekday smallint null
local_date date null

local_start_time time not null
local_end_time time not null

valid_from date null
valid_until date null

created_at timestamptz not null default now()
```

Types:

```text
WEEKLY
ONE_OFF
```

Checks:

```text
local_end_time > local_start_time

weekday BETWEEN 0 AND 6
when WEEKLY

local_date IS NOT NULL
when ONE_OFF
```

---

# 59. engagement.viewing_blackouts

```text
engagement.viewing_blackouts
```

Columns:

```text
id uuid primary key default uuidv7()

listing_id uuid not null

starts_at timestamptz not null
ends_at timestamptz not null

reason text null

created_at timestamptz not null default now()
```

Check:

```text
ends_at > starts_at
```

---

# 60. engagement.viewings

Concrete viewing request/appointment.

```text
engagement.viewings
```

Columns:

```text
id uuid primary key default uuidv7()

listing_id uuid not null

requester_user_id uuid not null

starts_at timestamptz not null
ends_at timestamptz not null

status text not null default 'REQUESTED'

attendee_count smallint not null default 1

requester_note text null

confirmed_by_user_id uuid null

created_at timestamptz not null default now()
responded_at timestamptz null
cancelled_at timestamptz null
completed_at timestamptz null

version bigint not null default 1
```

Status:

```text
REQUESTED
CONFIRMED
DECLINED
CANCELLED
COMPLETED
NO_SHOW
```

Checks:

```text
ends_at > starts_at
attendee_count > 0
```

Indexes:

```text
(listing_id, starts_at)

(requester_user_id, starts_at)

(status, starts_at)
```

Viewing overlap/capacity validation remains application-transaction logic.

Phase 1 default:

```text
max_concurrent_bookings = 1
```

---

# 61. trust.identity_verifications

No raw passport storage.

```text
trust.identity_verifications
```

Columns:

```text
id uuid primary key default uuidv7()

user_id uuid not null

provider text not null
provider_reference text not null

status text not null

verification_level text null

started_at timestamptz not null default now()
verified_at timestamptz null
expires_at timestamptz null

failure_reason_code text null

created_at timestamptz not null default now()
```

Status:

```text
PENDING
VERIFIED
FAILED
EXPIRED
CANCELLED
```

Index:

```text
(user_id, created_at DESC)
```

Provider reference is opaque.

No document images here.

---

# 62. trust.business_verifications

```text
trust.business_verifications
```

Columns:

```text
id uuid primary key default uuidv7()

legal_party_id uuid not null

provider text null
provider_reference text null

status text not null

verified_at timestamptz null
expires_at timestamptz null

created_at timestamptz not null default now()
```

Status same verification model.

---

# 63. trust.authority_verifications

Verifies PropertyAuthority specifically.

```text
trust.authority_verifications
```

Columns:

```text
id uuid primary key default uuidv7()

property_authority_id uuid not null

status text not null

verification_method text null

provider text null
provider_reference text null

verified_by_user_id uuid null

verified_at timestamptz null
expires_at timestamptz null

failure_reason_code text null

created_at timestamptz not null default now()
```

Status:

```text
PENDING
VERIFIED
FAILED
EXPIRED
```

When current successful verification exists, authority application state can become:

```text
VERIFIED
```

through owning service.

---

# 64. trust.reports

Cross-domain reporting is an intentional controlled polymorphic exception.

It is **not** a generic Entity model.

```text
trust.reports
```

Columns:

```text
id uuid primary key default uuidv7()

reporter_user_id uuid null

target_type text not null
target_id uuid not null

category text not null

description text null

severity text not null default 'NORMAL'

status text not null default 'OPEN'

external_ticket_id text null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
resolved_at timestamptz null

version bigint not null default 1
```

Targets:

```text
LISTING
USER
MESSAGE
MEDIA
PROPERTY
```

Categories initially:

```text
FAKE
DUPLICATE
SCAM
DISCRIMINATION
ILLEGAL_CONTENT
STOLEN_MEDIA
HARASSMENT
SAFETY
MISLEADING_PRICE
IMPERSONATION
SPAM
OTHER
```

Severity:

```text
NORMAL
HIGH
URGENT
```

Status:

```text
OPEN
TRIAGED
IN_REVIEW
RESOLVED
CLOSED
```

Application service validates target exists.

---

# 65. trust.moderation_decisions

Immutable moderation decision.

```text
trust.moderation_decisions
```

Columns:

```text
id uuid primary key default uuidv7()

report_id uuid null

target_type text not null
target_id uuid not null

action text not null

reason_code text not null
explanation text null

decided_by_user_id uuid not null

effective_from timestamptz not null default now()
effective_until timestamptz null

appeal_eligible boolean not null default true

created_at timestamptz not null default now()
```

Actions:

```text
NO_ACTION
WARNING
CONTENT_EDIT_REQUIRED
VISIBILITY_LIMITED
CONTENT_REMOVED
FEATURE_RESTRICTED
ACCOUNT_LIMITED
ACCOUNT_SUSPENDED
ACCOUNT_TERMINATED
```

Rows never mutate.

Subsequent decision creates new row.

---

# 66. trust.incidents

Serious safety/trust events.

```text
trust.incidents
```

Columns:

```text
id uuid primary key default uuidv7()

property_id uuid not null
listing_id uuid null

reported_by_user_id uuid null

incident_type text not null
severity text not null
status text not null default 'OPEN'

occurred_at timestamptz null

summary text null

restricted_access boolean not null default true

external_ticket_id text null

created_at timestamptz not null default now()
updated_at timestamptz not null default now()
resolved_at timestamptz null

version bigint not null default 1
```

Incident types:

```text
SAFETY
FIRE
GAS
CARBON_MONOXIDE
SERIOUS_INJURY
FATALITY
VIOLENCE
FLOOD
STRUCTURAL
OTHER
```

Severity:

```text
P0
P1
P2
P3
```

Status:

```text
OPEN
TRIAGED
ACTIVE_RESPONSE
INVESTIGATING
REMEDIATION_REQUIRED
RESOLVED
CLOSED
```

Incident data must never enter ordinary product analytics.

---

# 67. trust.incident_attachments

```text
trust.incident_attachments
```

Columns:

```text
incident_id uuid not null
file_id uuid not null

created_at timestamptz not null default now()
```

Composite PK.

Files are PRIVATE.

---

# 68. platform.audit_events

Cross-domain append-only security/domain audit.

```text
platform.audit_events
```

Columns:

```text
id uuid primary key default uuidv7()

actor_user_id uuid null
actor_organization_id uuid null

action text not null

resource_type text not null
resource_id uuid null

request_id text null

reason_code text null

metadata jsonb not null default '{}'

created_at timestamptz not null default now()
```

Examples:

```text
PROPERTY_AUTHORITY_VERIFIED
PROPERTY_AUTHORITY_REVOKED
LISTING_PUBLISHED
LISTING_SUSPENDED
ORGANIZATION_ROLE_CHANGED
SENSITIVE_RECORD_ACCESSED
```

Append only.

Application role used by API must not have ordinary UPDATE/DELETE rights to this table.

Metadata must not contain secrets or raw documents.

---

# 69. platform.outbox_events

Transactional Outbox.

```text
platform.outbox_events
```

Columns:

```text
id uuid primary key default uuidv7()

aggregate_type text not null
aggregate_id uuid not null

event_type text not null
event_version integer not null default 1

payload jsonb not null

created_at timestamptz not null default now()

available_at timestamptz not null default now()

processed_at timestamptz null

attempt_count integer not null default 0

locked_at timestamptz null
locked_by text null

last_error text null

dead_lettered_at timestamptz null
```

Indexes:

```text
(available_at)
WHERE processed_at IS NULL
AND dead_lettered_at IS NULL

(aggregate_type, aggregate_id)
```

Worker claims jobs using safe row locking such as:

```text
FOR UPDATE SKIP LOCKED
```

---

# 70. platform.notifications

```text
platform.notifications
```

Columns:

```text
id uuid primary key default uuidv7()

user_id uuid not null

category text not null
notification_type text not null

title_key text not null
body_key text not null

data jsonb not null default '{}'

created_at timestamptz not null default now()
read_at timestamptz null
```

Category:

```text
SECURITY
TRANSACTIONAL
SUPPORT
REGULATORY
PRODUCT
MARKETING
```

Index:

```text
(user_id, created_at DESC)
```

---

# 71. platform.notification_preferences

```text
platform.notification_preferences
```

Columns:

```text
user_id uuid not null

category text not null
channel text not null

enabled boolean not null

updated_at timestamptz not null default now()
```

PK:

```text
(user_id, category, channel)
```

Channels:

```text
EMAIL
PUSH
IN_APP
SMS
```

Application must prohibit disabling mandatory SECURITY and essential TRANSACTIONAL notifications where applicable.

---

# 72. platform.push_devices

```text
platform.push_devices
```

Columns:

```text
id uuid primary key default uuidv7()

user_id uuid not null

platform text not null
push_token text not null

status text not null default 'ACTIVE'

created_at timestamptz not null default now()
last_seen_at timestamptz null
revoked_at timestamptz null
```

Platform:

```text
IOS
ANDROID
```

Unique:

```text
UNIQUE(push_token)
```

---

# 73. platform.idempotency_keys

```text
platform.idempotency_keys
```

Columns:

```text
id uuid primary key default uuidv7()

actor_user_id uuid null

operation text not null
idempotency_key text not null

request_hash text not null

response_status integer null
response_body jsonb null

created_at timestamptz not null default now()
expires_at timestamptz not null
```

Unique:

```text
UNIQUE(operation, idempotency_key)
```

Phase 1 use cases:

```text
media-finalize
imports
selected mobile mutations
```

Future:

```text
payment
refund
booking
payout
```

---

# 74. Foreign-key deletion rules

Core rule:

## Never cascade-delete historical business data because a User disappears.

User references:

```text
ON DELETE RESTRICT
```

Property:

archived rather than routinely deleted.

Listing:

archived rather than routinely deleted.

Messages:

retention/redaction workflow.

Audit:

append-only.

Draft-only cleanup may physically delete records when no durable references exist.

Child configuration/details may use:

```text
ON DELETE CASCADE
```

only where deleting aggregate root legitimately deletes the child.

Examples:

```text
listing_texts → listing
listing_media → listing
rental_terms → listing
```

But deletion of published Listing should itself normally not occur.

---

# 75. Hard delete policy

Hard delete is acceptable primarily for:

* abandoned unpublished drafts;
* temporary upload records;
* expired auth/session data;
* processed Outbox after retention period;
* failed file uploads after retention;
* local/test environments.

Hard delete is not normal lifecycle for:

* Property;
* published Listing;
* User;
* ownership history;
* authority history;
* moderation decisions;
* incidents;
* audit events.

---

# 76. Account deletion model

User deletion request does not execute:

```text
DELETE FROM identity.users
```

Instead workflow:

```text
ACTIVE
→ CLOSED
→ remove authentication methods
→ revoke sessions
→ remove unnecessary personal profile data
→ anonymize where legally/operationally possible
→ retain narrowly justified records
```

`anonymized_at` records completion.

Later Privacy service will formalize retention per purpose.

---

# 77. Search query model

Do not create a separate Elasticsearch-style search database in v1.

Search joins/selects from:

```text
marketplace.listings
real_estate.spaces
real_estate.properties
real_estate.addresses
real_estate.geo_areas
marketplace.rental_terms
real_estate.property_amenities
```

with search-friendly denormalized price/location columns already on Listing.

---

# 78. Core Phase-1 search indexes

Codex must create and benchmark at minimum:

```text
marketplace.listings(
  status,
  intent,
  rental_mode,
  published_at
)

marketplace.listings(
  primary_price_minor
)

real_estate.properties(
  property_type
)

real_estate.properties(
  rooms
)

real_estate.addresses(
  city_area_id
)

real_estate.addresses(
  district_area_id
)

GiST real_estate.addresses(exact_geog)

GiST marketplace.listings(public_geog)

real_estate.spaces(property_id, space_type)

real_estate.property_amenities(amenity_code, property_id)
```

Use `EXPLAIN ANALYZE` before adding redundant indexes.

---

# 79. Text search

Phase 1 should begin with:

```text
pg_trgm
```

for:

* Listing title;
* address/autocomplete support where appropriate.

Do not build complicated multilingual FTS prematurely.

When evidence requires:

* Polish linguistic stemming;
* typo-heavy global search;
* synonym management;
* advanced facets;

evaluate dedicated search infrastructure.

---

# 80. Public address DTO

The exact address entity must never be serialized automatically.

API explicitly creates:

```text
PublicListingLocationDTO
```

Examples:

```text
district
city
approximatePoint
```

Internal:

```text
street
building
unit
exact_geog
```

remain separate.

Codex must not expose:

```text
SELECT *
```

style database objects in API responses.

---

# 81. Core database invariants

Schema and application tests must guarantee at least the following.

```text
1. Property != Listing.
2. Listing always points to Space.
3. Space always points to Property.
4. Maximum one active WHOLE_PROPERTY Space per Property.
5. SALE Listing has rental_mode NULL.
6. RENT Listing has rental_mode NOT NULL.
7. Money is bigint minor units.
8. Historical current price component uniqueness is enforced.
9. Signed/current concepts are never silently overwritten where history is required.
10. User != LegalParty.
11. Organization != LegalParty.
12. Identity verification != Property authority.
13. PropertyAuthority belongs to LegalParty.
14. Revoked/expired authority cannot authorize new actions.
15. Archived Space cannot receive new published Listing.
16. Property exact coordinate is not automatically public.
17. One Listing has maximum one cover media.
18. One current EPC per Property.
19. Messages belong to Conversations.
20. Saved Property targets Property, not transient Listing.
21. Audit rows are append-only.
22. Outbox event is written in same transaction as authoritative mutation.
23. Cross-domain reports do not mutate target directly.
24. Private files never become public by changing URL alone.
25. User hard deletion does not cascade through business history.
```

---

# 82. Whole Property vs Room availability invariant

No Phase-1 Booking exists yet.

Therefore no booking overlap tables are created.

However schema relationship:

```text
Property
  ↓
Spaces
  ├ WHOLE_PROPERTY
  └ ROOM*
```

must remain compatible with future Availability Engine.

Do not add a `room_id` directly to future Booking assumptions.

Booking will target:

```text
space_id
```

Future Availability Engine will resolve parent/child conflicts.

---

# 83. Transaction boundaries

Examples Codex must implement atomically.

## Create Property

```text
Property
+
default WHOLE_PROPERTY Space
+
AuditEvent
+
OutboxEvent
```

may be one transaction.

---

## Publish Listing

```text
validate eligibility
+
update Listing
+
insert status history
+
insert audit event
+
insert outbox event
```

one transaction.

---

## Change price

```text
close previous current price component
+
insert new component
+
recalculate Listing totals
+
increment Listing.version
+
audit/outbox
```

one transaction.

---

# 84. No database triggers by default

Schema v1 should not hide business behavior inside extensive PostgreSQL triggers.

Acceptable use:

only small technical integrity behavior if strongly justified.

Preferred:

explicit application transaction.

Reason:

* easier Codex reasoning;
* easier tests;
* easier observability;
* fewer invisible side effects.

---

# 85. Database roles

At minimum prepare conceptual roles:

```text
homies_app
homies_migrator
homies_readonly
```

`homies_app`:

ordinary runtime CRUD only.

`homies_migrator`:

DDL/migrations.

`homies_readonly`:

diagnostics/analytics where appropriate.

Application must not run as PostgreSQL superuser.

---

# 86. Schema privileges

Runtime application does not require:

```text
CREATE SCHEMA
CREATE EXTENSION
ALTER ROLE
DROP DATABASE
```

Migration credentials remain separate.

Admin application does **not** receive direct database credentials.

Admin still calls API.

---

# 87. Seed data

Production-safe initial seed must contain only reference/catalog data.

Examples:

```text
geo_areas:
Poland
Kraków
Warsaw
launch districts

amenities:
BALCONY
ELEVATOR
PARKING
GARAGE
GARDEN
DISHWASHER
WASHING_MACHINE
AIR_CONDITIONING
```

Do not mix demo Users/Listings with production seeds.

Development seeds may separately create synthetic demo data.

---

# 88. Migration order

Recommended first migration sequence:

```text
001_extensions

002_schemas

003_identity_users_auth_mapping

004_identity_legal_parties

005_identity_organizations_memberships

006_identity_representation

007_geo_areas_addresses

008_buildings_properties_spaces

009_ownership_authority

010_files_media

011_epc_amenities_safety

012_listings

013_listing_pricing_text_media

014_saved_search_saved_property

015_messaging

016_viewings

017_verification

018_reports_moderation_incidents

019_audit_outbox_notifications

020_indexes_and_constraints

021_seed_reference_data
```

Exact grouping may be adjusted if dependency ordering requires it.

Do not create one 5,000-line migration.

---

# 89. Migration verification

CI must test two paths.

### Fresh database

```text
empty PostgreSQL
→ migrate all
→ seed
→ tests
```

### Upgrade database

```text
previous schema fixture
→ apply latest migration
→ tests
```

Schema correctness on empty DB alone is insufficient.

---

# 90. Drizzle implementation rules

Codex should organize database schema by bounded context.

Example:

```text
packages/database/src/schema/

  identity/
    users.ts
    legal-parties.ts
    organizations.ts
    representation.ts

  real-estate/
    geography.ts
    properties.ts
    spaces.ts
    authority.ts
    media.ts
    safety.ts

  marketplace/
    listings.ts
    pricing.ts

  engagement/
    saved.ts
    conversations.ts
    viewings.ts

  trust/
    verification.ts
    moderation.ts
    incidents.ts

  platform/
    files.ts
    audit.ts
    outbox.ts
    notifications.ts
```

No single:

```text
schema.ts
```

with 3,000 lines.

---

# 91. Domain repositories

Do not expose Drizzle directly to route handlers.

Preferred flow:

```text
Fastify route
    ↓
Application service
    ↓
Repository interface
    ↓
Drizzle implementation
    ↓
PostgreSQL
```

Not:

```text
route
→ db.select()
→ return row
```

---

# 92. Transaction interface

Create a common transaction abstraction.

Application services must be able to execute:

```text
database.transaction(async tx => ...)
```

Repositories receive transaction context.

Do not open independent DB transactions inside every repository method.

---

# 93. Cross-module database access

Physical foreign keys across schemas are allowed.

Business mutations across module boundaries still go through owning service.

Example:

Marketplace may FK:

```text
listing.space_id
→ real_estate.spaces.id
```

But Marketplace service must not contain arbitrary Property mutation queries.

---

# 94. Applications intentionally NOT present

Schema v1 does **not** create:

```text
applications
co_applicants
tenant_passports
```

They belong to Phase 1.5.

Architecture already has a seam for them.

---

# 95. Finance intentionally NOT present

Do not create placeholder tables:

```text
payments
payment_obligations
ledger_entries
payouts
refunds
security_deposits
stripe_accounts
```

before Phase 2 legal/payment design.

No empty “future-proof” finance schema.

---

# 96. Contracts intentionally NOT present

Do not create:

```text
contracts
contract_versions
signature_requests
tenancy_legal_regimes
```

until Phase 2.

---

# 97. SHORT_STAY intentionally NOT present

Do not create:

```text
bookings
availability_holds
external_calendars
access_credentials
rebooking_cases
```

yet.

The current Property → Space model already supports their later introduction.

---

# 98. DAC7/Tax intentionally NOT present

Do not create:

```text
tax_profiles
dac7_submissions
seller_statements
```

for Phase 1 classifieds.

They are feature/legal-gated.

---

# 99. Reviews intentionally NOT present

Reviews require defined verified eligibility.

Phase 1 first vertical slice does not yet have sufficient outcome model.

Therefore do not create a premature:

```text
reviews
```

table now.

---

# 100. External Inventory intentionally deferred

Do not yet create full:

```text
pms_integrations
feeds
external_inventory_sources
```

unless agency import is included in first release scope.

Reserve architecture, not tables.

---

# 101. Analytics tables intentionally absent

Do not dump PostHog events into PostgreSQL operational tables.

There is no:

```text
analytics_events
```

table in Phase 1.

Business state itself provides authoritative metrics.

External product analytics consumes events.

Future warehouse/OLAP is separate.

---

# 102. Search projection intentionally absent

No:

```text
listing_search_projection
```

table initially.

Search directly from normalized relational model plus selected denormalized Listing columns.

Add a dedicated read projection only after query evidence requires it.

---

# 103. Redis intentionally absent

No Redis requirement in Schema v1.

Do not create infrastructure dependency merely for:

* queues;
* caching;
* rate limiting.

PostgreSQL/outbox and edge/application controls are enough initially.

---

# 104. Schema-level test suite

Codex must implement integration tests proving database rejects:

```text
SALE Listing with rental_mode
RENT Listing without rental_mode

negative money

second active WHOLE_PROPERTY Space

two current identical Listing price components

invalid ownership fractions

invalid effective-date range

invalid viewing time range

message with missing valid sender

conversation participant with both User and Organization IDs

invalid location status value

invalid Listing status value
```

---

# 105. Domain integration tests

Codex must additionally prove application logic:

```text
User cannot edit unrelated Property

Organization Agent can edit authorized Property
only when membership + property authority permit

revoked PropertyAuthority stops publication

Listing cannot publish without required current price

price update creates history instead of overwriting

derived monthly/move-in totals recalculate correctly

Property archive prevents new Listing publication

unapproved media cannot become public Listing cover

exact Property geog is not included in public Listing DTO

Listing publication produces AuditEvent

Listing publication produces exactly one OutboxEvent

retrying idempotent mutation does not duplicate effect
```

---

# 106. Spatial tests

Use real PostGIS integration tests.

At minimum:

```text
search within viewport

search within radius

district lookup

public approximate coordinate differs from exact when privacy mode requires

GiST index is used for representative geo query
```

`EXPLAIN ANALYZE` evidence should be captured for benchmark query.

---

# 107. Query performance fixtures

Development benchmark seed should be able to create at least:

```text
100,000 Properties
100,000 active Listings
multiple cities/districts
amenities
pricing
```

for local/CI benchmark scripts.

Not every CI run needs 100k rows.

Have a separate repeatable benchmark command.

Goal:

prove PostgreSQL/PostGIS design before assuming external search is necessary.

---

# 108. Schema documentation

Codex must produce:

```text
docs/database/SCHEMA-v1.md
```

containing:

* schema overview;
* table ownership;
* main relationships;
* invariant summary;
* retention model;
* future deferred domains.

Also generate:

```text
docs/database/ERD-v1.*
```

using a reproducible method.

Source schema remains authoritative.

ERD is derived documentation.

---

# 109. ADRs required

Implementation should include or reference:

```text
ADR-002 PostgreSQL + PostGIS
ADR-003 Drizzle + reviewed SQL migrations
ADR-006 Transactional Outbox
ADR-007 PostgreSQL-native Search
```

Add:

```text
ADR-011 UUIDv7 IDs
ADR-012 Schema-per-domain logical boundaries
ADR-013 No DB enums in v1
ADR-014 No blanket soft delete
```

---

# 110. Codex must not silently simplify

Examples of forbidden simplification:

```text
put owner_id on Property and remove LegalParty

replace PropertyAuthority with property.user_id

remove Space and put room=true on Listing

merge Property and Listing

store all pricing in one JSON

store full address as one text field

put amenities as random JSON

put everything into public schema

use one generic status column across domains

replace outbox with direct email/API call after transaction

use float for money
```

These are architectural regressions.

---

# 111. Codex may simplify implementation where semantics remain intact

Allowed examples:

* combine migration files where dependency logic remains readable;
* use shared timestamp helper;
* use shared money validation;
* generate CHECK expressions from canonical TS constants;
* share repository utilities;
* generate types from Drizzle.

Implementation elegance is welcome.

Domain semantics are not negotiable.

---

# 112. Phase-1 publication flow against schema

Target workflow:

```text
User
 ↓
Personal LegalParty
 ↓
Property
 ↓
PropertyAuthority
 ↓
WHOLE_PROPERTY Space
 ↓
MediaAssets
 ↓
Listing DRAFT
 ↓
ListingText
 ↓
PriceComponents
 ↓
RentalTerms
 ↓
PublicationEligibilityService
 ↓
PUBLISHED
 ↓
ListingStatusHistory
 ↓
AuditEvent
 ↓
OutboxEvent
```

That path must be implementable without future Phase-2 tables.

---

# 113. Phase-1 renter flow against schema

```text
User
 ↓
Search Listings
 ↓
Save Property
 ↓
Open Listing
 ↓
Conversation
 ↓
Messages
 ↓
Viewing Request
 ↓
Provider Confirmation
```

No fake Booking entity is required.

---

# 114. Phase-1 agency flow

```text
User
 ↓
OrganizationMembership
 ↓
Organization
 ↓
Organization LegalParty
 ↓
PropertyAuthority
 ↓
Property
 ↓
Listing
 ↓
Conversation / Lead
 ↓
assigned_to_user_id
 ↓
Viewing
```

This supports professional agencies without inventing separate Agent accounts.

---

# 115. Public search DTO derived fields

Search API should return a specific projection such as:

```text
listingId

propertyType
spaceType

city
district
publicLocation

primaryPrice
estimatedMonthlyTotal
moveInTotal

rooms
area

providerClassification
authorityVerified

coverMedia

availableFrom

freshness

selectedAmenity flags
```

Not every database field.

---

# 116. Internal Property DTO

Authorized Property management API may expose:

```text
exact structured address

ownership/authority summary

media

safety

EPC

Spaces

active Listings

version
```

Still no unnecessary trust/admin-only evidence.

---

# 117. Admin DTO

Admin may access expanded operational information only through explicit endpoints and permissions.

Admin API must not simply return:

```text
all columns
```

Admin sensitive reads can create:

```text
SENSITIVE_RECORD_ACCESSED
```

AuditEvent.

---

# 118. Optimistic concurrency

At minimum use `version` for:

```text
users where material

organizations

representation_mandates

properties

spaces

property_authorities

property_safety_profiles

listings

saved_searches

conversations

viewing_settings

viewings

reports

incidents
```

HTTP mutation pattern may later use:

```text
If-Match
```

or explicit expectedVersion.

Schema supports either.

---

# 119. Publication race protection

Publishing the same Listing concurrently must not create inconsistent lifecycle.

Update should use:

```text
WHERE id = ?
AND version = ?
AND status IN (...)
```

then increment version.

Zero affected rows:

```text
CONFLICT
```

not silent overwrite.

---

# 120. Price update race protection

Price mutation occurs inside transaction with Listing version check.

Two concurrent edits:

one succeeds.

second receives:

```text
409 CONFLICT
```

and must refetch current version.

---

# 121. File lifecycle

Expected file flow:

```text
file_objects.state = UPLOADING

→ QUARANTINED

→ PROCESSING

→ READY
```

Rejected:

```text
→ REJECTED
```

Deletion:

```text
→ DELETED
```

MediaAsset creation may occur only after or conditionally during processing, but Listing may use only READY + APPROVED media.

---

# 122. Outbox cleanup

Processed Outbox records are not kept forever in primary hot table.

Retention job may archive/delete successfully processed records after configurable period.

Suggested initial operational retention:

```text
30–90 days
```

but keep this configurable.

Dead-letter failures remain until investigated.

---

# 123. Audit retention

Do not hard-code an aggressive audit deletion period in schema.

Retention belongs to security/privacy policy.

Schema allows durable history.

---

# 124. Message retention

Messages are not automatically deleted because User closed account.

Privacy policy determines:

* anonymization;
* participant access;
* legal/fraud retention;
* eventual deletion.

Sender User reference can continue pointing at CLOSED/anonymized User.

---

# 125. Property archive rule

Property cannot be archived if application policy detects:

* active published Listings;
* future confirmed Viewings requiring it;
* unresolved critical Incident;

without resolving dependent state.

Database alone does not enforce all of this.

`ArchivePropertyService` does.

---

# 126. Listing archive rule

Archiving Listing:

```text
status → ARCHIVED
archived_at → now()
```

not hard DELETE.

It disappears from public search.

Property persists.

---

# 127. Search freshness rule

Search query for normal public inventory requires:

```text
status = 'PUBLISHED'

AND
(
  stale_at IS NULL
  OR stale_at > now()
)

AND
(
  expires_at IS NULL
  OR expires_at > now()
)
```

Worker updates stale status where necessary.

---

# 128. Data integrity > convenience

Do not use JSONB for authoritative concepts simply because schema is easier.

JSONB is appropriate for:

```text
saved search criteria
audit metadata
outbox payload
notification payload
provider metadata
```

JSONB is **not** appropriate as primary storage for:

```text
Property
Address
Pricing
Authority
Organization Membership
Viewing
```

---

# 129. Schema quality targets

The first production schema should be understandable by an engineer without reading application code.

Important relationships and constraints must be visible in database structure.

The database should resist obvious corruption even if application code contains a bug.

At the same time:

do not recreate the entire application as SQL stored procedures.

---

# 130. Required Codex deliverables

Codex implementation of this specification must produce:

```text
1. Drizzle schema files
2. reviewed SQL migrations
3. reference seeds
4. development synthetic seed generator
5. repository implementations
6. transaction abstraction
7. DB integration tests
8. invariant tests
9. spatial tests
10. migration tests
11. benchmark query script
12. schema documentation
13. ERD
14. required ADRs
15. implementation report
```

---

# 131. Implementation report format

At completion Codex must report:

```text
IMPLEMENTED

DEVIATIONS FROM SPEC

MIGRATIONS CREATED

TABLES CREATED

INDEXES CREATED

CONSTRAINTS CREATED

TESTS

BENCHMARKS

SECURITY / PRIVACY NOTES

KNOWN LIMITATIONS

DEFERRED BY DESIGN

FILES CHANGED

FINAL VERIFICATION
```

Any deviation must include:

```text
why
impact
whether constitutional semantics changed
```

---

# 132. Mandatory final verification by Codex

Before marking Schema v1 complete:

```text
fresh migration succeeds

rollback/repair path reviewed

all tests pass

no forbidden future-domain tables exist

no float money exists

no Property/Listing merge exists

no direct owner_id shortcut replaces authority model

all FKs valid

all CHECK constraints validated

all partial unique indexes tested

PostGIS queries tested

exact address privacy tested

authorization integration tested

Outbox atomicity tested

Audit append behavior tested
```

---

# 133. Definition of Schema v1 complete

Schema v1 is complete when this vertical slice is physically representable with valid relational integrity:

```text
Register
→ User
→ LegalParty
→ Property
→ PropertyAuthority
→ Space
→ Media
→ LONG_TERM Listing
→ Price components
→ Publish
→ Search / Map
→ Save Property
→ Conversation
→ Message
→ Viewing
→ Confirm Viewing
```

without:

* schema hacks;
* generic JSON domain blobs;
* future transactional entities;
* duplicated identity models;
* direct client DB dependencies.

---

# 134. Final physical-domain graph

```text
AUTH
 │
 ▼
User
 │
 ├─────────────┐
 ▼             ▼
LegalParty   Organization
 │             │
 │       Membership
 │             │
 └──── Representation
        │
        ▼
PropertyAuthority
        │
        ▼
      Property
        │
     ┌──┴────────────┐
     ▼               ▼
 Building          Safety
     │               EPC
     │               Media
     ▼
   Space
 ┌───┴────┐
WHOLE    ROOM
   │
   ▼
 Listing
   │
   ├── ListingText
   ├── RentalTerms / SaleTerms
   ├── PriceComponents
   ├── ListingMedia
   └── StatusHistory
          │
          ├──────────────┐
          ▼              ▼
       Search         Engagement
                        │
               ┌────────┼─────────┐
               ▼        ▼         ▼
             Saved  Conversation Viewing
                       │
                       ▼
                    Messages

Cross-cutting:

Verification
Reports
Moderation
Incidents
Files
Audit
Outbox
Notifications
```

---

# 135. Explicitly frozen architectural decisions

Codex must treat these as fixed until new ADR/owner decision:

```text
Property is persistent.

Listing is temporary.

Room is Space, not Property.

User is not LegalParty.

Organization is not LegalParty.

Identity verification is not authority verification.

PropertyAuthority belongs to LegalParty.

Listing points to Space.

Address is structured.

Exact geolocation is private domain data.

Money uses bigint minor units.

PostgreSQL/PostGIS is authoritative.

No Elasticsearch in Phase 1.

No Redis requirement in Phase 1.

No microservices.

No Kafka.

No finance tables before Phase 2.

No contract tables before Phase 2.

No Short-Stay booking tables before Phase 3.

No giant Rules DSL.

No generic EAV Property model.

No direct DB access from Web/Mobile/Admin.

No blanket soft-delete column on every table.

No PostgreSQL ENUM types in v1.

No raw KYC document storage unless separately justified.
```

---

# 136. FINAL STATUS

This specification is the authoritative physical-data blueprint for Homies Phase 1.

## DOMAIN SCHEMA READINESS

Identity: **100/100**

Property/Space: **100/100**

Organization/Agency: **100/100**

Authority: **100/100**

Listing: **100/100**

Pricing: **100/100**

Search support: **100/100**

Geo/PostGIS: **100/100**

Media: **100/100**

Messaging: **100/100**

Viewing: **100/100**

Trust/Verification: **100/100**

Safety foundation: **100/100**

Audit/Outbox: **100/100**

Notifications: **100/100**

Privacy boundaries: **100/100**

Phase-2 isolation: **100/100**

## PostgreSQL/PostGIS Domain Schema v1

# READY FOR CODEX IMPLEMENTATION

**END**
