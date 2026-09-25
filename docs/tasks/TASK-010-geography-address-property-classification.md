# TASK-010 — Poland-wide geography, address & property classification

| Field | Value |
|---|---|
| Status | IN_REVIEW — builder complete; ChatGPT/founder adjudication pending; independent audit recommended (below) |
| Owner (writer) | Claude Code |
| Baseline | **Foundation Baseline 002** `36231840ee52d6185e73fda07e54eab33ffe41f3` (accepted) |
| Branch | `claude/TASK-010-geography-address-property-classification` |
| Also in scope | Canonical Product & Growth Doctrine (07); permanent archive of both TASK-009 audits; Baseline 002 record |

## Goal

The first Phase-1A product vertical slice after the accepted foundation:
Homies can represent a residential property **anywhere in Poland** with a
structured, source-aware address and a coherent classification, on a model
that takes another European country as data rather than a redesign — while
private location stays private.

## Product & Growth Doctrine dimensions (07 §2)

| Dim. | Effect |
|---|---|
| A1 UX | Backend for address autocomplete (`/v1/geo/localities`), region/area browsing, clear place names with their region; ordinary users never have to type "województwo" |
| A2 Trust | Addresses record resolution, source and verification; public shows place, never building/unit |
| A3 Automation | Reference-data import seam (idempotent, id-matched, rename/re-parent in place); future geocoding/normalisation/dedup hooks |
| A5 Liquidity | Structured place filters (country, any region, locality, neighbourhood) — the base of regional liquidity measurement |
| A8 Growth | Stable area/locality ids + slugs for future SEO landing pages and regional campaigns |
| A9 Scalability | Country → areas of any depth → locality; country-specific tiers are `kind_code` data |
| A10 Necessity | Free-text `city` could not support Poland-wide search, SEO or trust; this is foundational for every listing |

## AS-IS (reconstructed from code at the baseline)

* `properties`: free-text `city`, `district`, `postcode`, `municipality`
  (required by the API; only consumer the dormant short-stay tourist tax),
  `address` (street, number and often the unit in one string); exact
  `latitude`/`longitude` numeric(9,6) with finite/range/pair CHECKs (F-07);
  PostGIS `exact_geog` generated from them, GiST-indexed, created only by
  migration.
* `classified_offers`: public point (`public_latitude/longitude`,
  `public_geog`) from the exact point by precision EXACT / APPROXIMATE (grid)
  / DISTRICT; public DTO shows `city`, `district`, `public_location`.
* No country anywhere; Poland implicit. Search filters `city`/`district` by
  string equality, plus PostGIS bbox/radius on the public point.
* Classification: `property_type` lower-case legacy vocabulary (apartment,
  studio, room [readable, not creatable], house, townhouse, loft,
  aparthotel_unit); `aparthotel_unit` publication fails closed; Space types
  WHOLE_PROPERTY / ROOM.
* Legacy (dormant) short-stay listing creation derives a Property from text.

## Decisions (builder decisions within the contract; recorded as DECISIONS D-51…D-55, pending founder/ChatGPT adjudication — not yet canon in 04a)

| Decision | Outcome |
|---|---|
| Country identity | ISO 3166-1 alpha-2 code (`countries.code`). A standard, not any country's register; CHECK `^[A-Z]{2}$`. Default currency is informational |
| Geographic hierarchy | One generic `admin_areas` table, any depth, `level` 1..n, parent in the same country (composite FK), no self-parent, levels strictly increase (trigger, parent read FOR SHARE) → no cycles even under concurrent writes |
| AdministrativeArea vs Locality | Official units vs settlements. A locality belongs to its most specific unit; a village is not a municipality, a city is not assumed to be one |
| Neighbourhood / SearchArea seam | `geo_areas` (DISTRICT / NEIGHBOURHOOD / SEARCH_AREA), optional locality, PostGIS boundary; not forced into the official tree |
| Official source ids | `geo_sources` (namespaces: PL_TERYT_TERC, PL_TERYT_SIMC, PL_TERYT_ULIC, PL_PRG, PL_PRG_ADDRESS) + `geo_external_refs` (unique per source; ≤1 per entity per source; exactly one target). Never a primary key |
| Address structure | `addresses`: country, locality **or** admin area, optional search area, postal code, thoroughfare (nullable — village numbering), building number, typed text, resolution (STRUCTURED/UNSTRUCTURED), source, verification |
| Address ↔ Property | Building-level Address, owned by exactly one Property today (`properties.address_id` UNIQUE, NOT NULL). Unit number lives on Property. Exact point stays on Property (one exact-location system). Sharing across Properties waits for Building + dedup |
| Private vs public | Private: street, building, unit, postal code, typed text, exact point, address-point ids. Public: country, official areas, locality, search area (reference entities only) + the existing privacy-reduced point |
| Property classification | `category` APARTMENT \| HOUSE (canonical PropertyType), `subtype` under its category (CHECKed); legacy `property_type` kept and mapped both ways; ROOM refused as type, category or subtype |
| Subtype strategy | Only values with product/policy value: STUDIO, LOFT, APARTHOTEL_UNIT; DETACHED_HOUSE, SEMI_DETACHED_HOUSE, TERRACED_HOUSE. APARTHOTEL_UNIT publication stays fail-closed (either column) |
| Building | **Not built.** Not needed for one-owner listings; the building-level Address + separate unit number leave room for `Building → many apartment Properties` |
| Reference-data seam | `import_areas` / `import_localities`: idempotent upsert by the source's id, parents first, rename/re-parent in place, never delete (retire is a separate step). Download/version/activate/rollback of releases is future work; runtime never calls a government API |
| `municipality` | Optional (was required only for the dormant tourist tax); derivable from the hierarchy |

## In scope / out of scope

In: the above; `/v1/geo` read API; structured property create; public
`place`; search filters `country_code`, `admin_area_id` (descendants),
`locality_id`, `geo_area_id`; migration + backfill; doctrine; audit archive.

Out (per contract): search engine/ranking, map frontend, saved search/
property, alerts, referral, tenant profile, applications, landlord OS,
agency import, contracts, payments, ledger, MONTHLY, SHORT_STAY, foreign
tenancy law, national data ingestion, paid geocoder, Building entity,
address update endpoint.

## Acceptance tests

`tests/test_geography.py` (API/service), `tests/test_geography_pg.py`
(database, PostGIS, concurrency, migration), plus the full suites and OpenAPI
drift. Mutation: `scripts/mutation/task010_mutants.py`.

## Evidence (2026-09-25, local; Python 3.14.3 venv, PostgreSQL 16.4 / PostGIS 3.4.3 container)

| Check | Result |
|---|---|
| Full suite, SQLite | 740 passed, 207 skipped (PostgreSQL-only tests) |
| Full suite, PostgreSQL/PostGIS | 946 passed, 1 skipped (Stripe Test Mode suite, not requested) |
| `tests/test_geography.py` / `tests/test_geography_pg.py` | 35 / 19 passed (included above) |
| ruff (`app tests alembic scripts`) · mypy | clean · no issues (82 files) |
| OpenAPI export `--check` | up to date (regenerated) |
| Migration | upgrade from Baseline 002 head `d3f5b7a9c1e4` with data → backfill verified → downgrade → upgrade (`test_geography_pg`); fresh schema via migrations in every PG session |
| Mutation — TASK-010 | 10 / 10 killed ([report](../reviews/2026-09-25-task010-mutation.md)) |
| Mutation — regression | TASK-004 9/9, TASK-006 7/7, TASK-008 17/17 killed; E01–E04 survived as before (kept) |

## Builder notes

* **Eager load removed.** A first cut loaded `Property.address_record` with
  `lazy="joined"`; on PostgreSQL that turned the Property coordination lock
  (`SELECT … FOR UPDATE`) into an outer join and failed ("FOR UPDATE cannot be
  applied to the nullable side of an outer join"). All TASK-010 relationships
  are `lazy="select"`; the lock path is unchanged. Cost: the public list
  resolves `place` per row (N+1) — see known debt.
* **Foundation test evidence (TASK-009 P3) replaced where touched.** Three
  race tests (`test_publication_authority_race_pg.py` ×2 parametrised,
  `test_publication_proof_replacement_pg.py` ×1) asserted serial order through
  HTTP/thread completion order, which TASK-009 recorded as non-evidence; the
  extra post-commit reads of TASK-010 made them flip. They now assert on
  database state: the paused publication's transaction id (`backend_xid`) is
  captured at the protected gate, and when the competing loss/delete commits
  that transaction id is no longer running (`pg_stat_activity`). The existing
  blocker-PID evidence (`pg_blocking_pids`) and committed-state checks are
  unchanged. No production code of the foundation changed; no protected-proof
  restriction was removed. Still carrying the debt (not touched, green):
  `test_membership_accept_race_pg.py`, `test_publication_chain_gain_race_pg.py`.
* **`municipality` optional** (D-53): `test_municipality_is_required` became
  `test_municipality_is_optional_since_task_010`.

## Known debt (new)

* Public list N+1 on `place` (lazy loads per row); fine at Phase-1A volumes,
  batch-load before search at scale.
* Backfilled addresses are `UNSTRUCTURED` / `LEGACY_BACKFILL`; resolving them
  against reference data needs an ingested dataset (not in scope).
* No reference data ingested; release versioning/activation/rollback of
  imports is future work. PostGIS boundary/centroid columns exist but are empty.
* No Building; no address update endpoint; no address dedup.
* Legacy `property_type`, `city`, `district`, `postcode`, `municipality`,
  `address` still written as mirrors — retire in a later brownfield step.

## Independent audit

Recommended, not foundation-mandatory: the change is additive and touches a
05 §9 item (exact address / private data) and a data-transforming migration.
A targeted audit of the public-leakage boundary and the migration is
proportionate.
