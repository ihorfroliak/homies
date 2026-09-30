# TASK-013 — Search, map & marketplace discovery

| Field | Value |
|---|---|
| Status | IN_REVIEW — builder complete; ChatGPT/founder adjudication and independent audit requested |
| Owner (writer) | Claude Code |
| Accepted starting SHA | `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` (TASK-012 accepted by TASK-012RA) |
| Branch | `claude/TASK-013-search-map-discovery` |
| Decisions | D-68…D-74, D-75 (TASK-012 acceptance record); 04a §21 |

## Goal

"Show me current homes that fit where I want to live, what I can pay and
when I can move" — one coherent, trustworthy discovery model over the
accepted Property / Geography / Listing / Freshness foundation.

## AS-IS (at `879bf56`)

* One public search endpoint, `GET /v1/classifieds`, a 250-line handler
  building filters inline: legacy `city`/`district` (D-57 rules), single
  `country_code`/`admin_area_id`/`locality_id`/`geo_area_id`, `bbox` and
  radius on `public_geog` (already the public point), monthly-total range,
  rooms, listed area, furnished, parking, pets, elevator, `has[]`
  attributes, `available_by` (D-64), `max_term_months`, single
  `space_type`; sorts newest / price_asc / price_desc / size_desc with **no
  tie-breaker**; offset paging (limit ≤ 100, offset unbounded); exact count.
* No map endpoint; no category/subtype, base-rent or move-in filters; no
  query echo.
* Rendering: public `place` walked the admin hierarchy per row — 10 / 49 /
  105 SELECTs for 1 / 10 / 24 structured listings; the ORM's default joined
  eager loads joined `properties`/`spaces` a second time on top of the
  search's own joins.
* Pricing: components → stored summaries (`primary_price_minor` = base rent,
  `estimated_monthly_total_minor` = mandatory monthly incl. estimated
  utilities, `move_in_total_minor` = monthly + mandatory one-offs incl.
  deposit). `AGENCY_FEE` exists in the component enum but cannot be set via
  the API.
* Provider data: authorities (OWNER / PROPERTY_MANAGER / …), holders
  (PERSON / ORGANIZATION); no listing-level provider (04 §43
  `provider_legal_party_id` not built).
* Rental mode: classifieds are LONG_TERM only; dormant `/v1/listings` not
  mounted.

## Design (as built)

| Area | Decision |
|---|---|
| Query model | `properties/search.py`: `SearchQuery` (frozen), `search_query()` FastAPI dependency (parse + validate), `filters()`, `select_matching()`, `order_by()`, `count_matching()` — the only way list and map select rows (D-68) |
| Composition | dimensions AND; repeated values OR (`admin_area_id`, `locality_id`, `geo_area_id`, `category`, `subtype`, `space_type`); `has[]` = ALL |
| Validation | 422 for unknown values, subtype outside chosen categories, min > max, places outside `country_code`, bad bbox/radius, unknown sort, offset > 10 000; unlikely = empty |
| Eligibility | `freshness.public_clause` first (D-59) |
| Geography | country; admin areas with descendants (one recursive CTE for all seeds); localities; search areas; legacy city/district (D-57); viewport; radius |
| Spatial privacy | `public_geog` only (D-70); probed |
| Property / space | category, subtype, space type, rooms, listed area, furnished, parking, pets, elevator, catalogue attributes |
| Money | `min_rent`/`max_rent`, `min_monthly_total`/`max_monthly_total`, `max_move_in_total`; response `utilities_basis` (D-69) |
| Availability | `available_by` excludes UNKNOWN; `available_soonest` sorts UNKNOWN last |
| Sorting | newest (default) / price_asc / price_desc / size_desc / available_soonest, NULLs last, `id` tie-breaker (D-71) |
| Default sort | newest = publication time. Confirmation never changes it (no gaming by reconfirming); a republish after a pause does (the listing genuinely came back to market) — accepted trade-off |
| Paging | offset, limit 1–100, offset ≤ 10 000 |
| Map | `GET /v1/classifieds/map`: `MapPoint` projection, cap 500 (query order), `total` / `with_point` / `without_point` / `truncated`; clustering client-side (grid points) — server-side deferred |
| URL state | `query` = canonical URL parameters, `sort` echoed (D-72) |
| Metrics | `homies_search_requests_total{surface,results}`, `homies_search_filter_used_total{filter}` — names and buckets only (D-73) |
| Rendering | `contains_eager` for the search's own joins; selectin for address → locality / search area; one recursive query preloads every area path of the page |
| Indexes | `addresses(geo_area_id)`, `classified_offers(primary_price_minor)` — migration `d0f2b4c6e8a1` (D-74) |

## Deferred, with reasons

* Provider (private owner / agency) and "no agency fee" facets — no
  authoritative listing-level provider (04 §43 `provider_legal_party_id`)
  and no recordable agency fee; inferring them would be guessing.
* Server-side clustering — public points are ~550 m grid cells; a capped,
  ordered projection plus client clustering suffices for Phase 1A.
* Multi-area UI — the query already accepts repeated place ids (OR); a
  polished multi-area product is later.
* SEO pages — contract ready (D-72); pages, canonical/noindex routing later.

## Scale assumptions

Tested at ~5 000 synthetic listings (EXPLAIN ANALYZE, local, diagnostic
only). Phase-1A launch expectation: 10³–10⁴ active listings, where every
measured discovery query executes in ~1–35 ms locally. Dedicated search
infrastructure becomes a question only with measured p95 over budget at
10⁵–10⁶ active listings (D-74).

## Frontend / beauty readiness

The contract lets a UI do: desktop filters + list + map side by side; mobile
list ↔ map toggle; filter changes keyed by the canonical query; result cards
that show rent, monthly total with its utilities basis, move-in total, place
(country / region / locality / search area), move-in state and "confirmed
current" — without reimplementing any rule. Filter labels map one-to-one to
parameters with stated meaning.

## Out of scope

Saved properties/searches, alerts, recommendations, ML/semantic ranking,
tenant profile, applications, contracts, payments, SHORT_STAY search,
agency import, SEO page generator, frontend redesign, external search
infrastructure.

## Independent audit

**Required**: a change to what the public can find (every listing's
discoverability), a new public spatial surface where the privacy boundary
(D-58/D-70) is load-bearing, and a migration.

## Evidence (2026-09-28, local; Python 3.14.3 venv, PostgreSQL 16.4 / PostGIS 3.4.3)

| Check | Result |
|---|---|
| Full suite, SQLite | 802 passed, 301 skipped |
| Full suite, PostgreSQL/PostGIS | 1102 passed, 1 skipped (Stripe Test Mode suite) |
| New: `test_search.py` (SQLite) / `test_search_pg.py` (PG) | 22 / 10 cases (included above; `test_search.py` re-run after strengthening the list≡map test: 22 passed) |
| ruff · mypy · OpenAPI `--check` | clean · no issues (87 files) · regenerated, up to date |
| Query count, 24 structured listings, list limit 1 / 10 / 24 | `879bf56`: 10 / 49 / 105 → TASK-013: 8 / 9 / 9 SELECTs; map: ≤ 4 |
| EXPLAIN ANALYZE, ~5 000 synthetic listings (diagnostic) | default page 31.7 → 22.3 ms after removing duplicate eager joins; bbox uses `ix_classified_offers_public_geog`; locality uses `ix_addresses_locality`; search area and rent range used sequential scans → new indexes chosen by the planner (rent range 7.3 → 3.6 ms) |
| Migration | TASK-012 head `b8d0f2a4c6e8` → `d0f2b4c6e8a1` on data: rows unchanged, indexes present; down and up; single head (`test_td01`) |
| Mutation | S01–S12 12/12 (assertions); F 16/16, Z 6/6, R 12/12, G 10/10 regression ([report](../reviews/2026-09-28-task013-mutation.md)) |

Python 3.12 and CI not run.

## TASK-013A → TASK-013R (2026-09-28)

TASK-013A (Codex, [archived verbatim](../reviews/2026-09-28-task013a-codex-task013-audit.md)): **TASK_013_REQUIRES_TARGETED_FIXES** — F13A-01 (P2), F13A-02 (P3), F13A-03 (note). TASK-013R, from exactly `56567d24bd764563bc21707c0c027e637a206e16`, on `claude/TASK-013R-search-validation-map-count`:

* **Reproduced first** on the candidate (both surfaces): `10**100` and out-of-column-range integers for rent/monthly/move-in totals, rooms, area and term → PostgreSQL `NumericValueOutOfRange`; NUL in `city`, `district`, `locality_id`, `admin_area_id`, `geo_area_id` → `DataError` (both an HTTP 500 in a deployed process); `furnished=INVALID`, `parking=INVALID` → 200 with zero results.
* **Repair (D-76):** validation before SQL — bounds, NUL, lengths, catalogue values, repetition budgets, canonical-length backstop; normalization of the canonical query; the map partition from one aggregate (`search.count_map_partition`).
* **Not changed:** public eligibility, spatial model (public point only), price semantics, sorting/paging, the index migration `d0f2b4c6e8a1` (untouched), no new migration.
* Tests: `tests/test_search_validation.py` (SQLite) and `tests/test_search_validation_pg.py` (PostgreSQL: the 500-inputs, partition, deterministic publication-between-statements interleaving, cap 499/500/501, 21×24h cutoff on counts, public-point counts). Mutants V01–V06 and S01–S12 re-run: see the TASK-013R report.

Pending: narrow independent re-audit (TASK-013RA). TASK-013 is **not accepted**; TASK-014 Phase B stays blocked.

## Known debt

* Owner view (`/v1/me/classifieds`) still ~2 queries per listing (not the
  discovery path; unchanged).
* `total` is an exact count per request (5–17 ms at 5 000 listings) — revisit
  with an estimate or cap when volume demands.
* Provider / agency-fee facets, server-side clustering, SEO pages, multi-area
  UI: deferred (above).
* Due-reminder scan unbounded (TASK-012 note, unchanged).
