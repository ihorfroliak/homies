# FE-002 — Seeker slice: Search → Results → Map/List → Listing detail

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED** on its branch — part of the PROGRAM-001 candidate, **not merged to `main`**; **NOT DEPLOYED** |
| Disposition (TASK-016, 2026-10-06) | on `main` via the PROGRAM-001 merge `c32ac63f9a4c08366369a2088709b658754373e6` (merge of `779b30fe2ecc5d4542a50efc8494eb6220409327`, externally reviewed, founder-approved); BUILDER VERIFIED; NOT DEPLOYED. The status text is kept as written |
| Risk class | **R2** (public data projection change, new public endpoint, search correctness, privacy of location) |
| Branch | `claude/FE-002-seeker-search-detail` (from FE-001) |
| Canon / design | DESIGN-001 §2–§9, UI-STATE-MAP, DESIGN-SYSTEM-v1; GROWTH-001 EVENTS-v1; founder G-11, G-12, G-13 |
| Not in scope | FE-003 (save, conversation, viewing — **not authorised**); owner panel; moderator app |

The founder's rule stands: this is **developer-built UI on Design System v1
tokens**, not completed high-fidelity design. The Figma desktop frames are a
non-binding visual reference (D-106: design-tool state is not authority); mobile frames are not drawn yet (Starter-plan limit).

## 1. Routes

| Route | What | Status codes |
|---|---|---|
| `/` | hero, search box (city + max monthly cost → `/szukaj`), three factual pillars, "Najnowsze w Krakowie" (6 real listings, streamed; hidden on error), owner note (no dead link) | 200 |
| `/szukaj` | GET handler: city name → `/wynajem/{slug}`, cost carried; unknown name → national results | 303 |
| `/wynajem[/{miasto}[/{obszar}]]` | results list; `?widok=mapa` map mode (split list/map ≥ 1024 px, one mode below) | 200; 404 for unknown city/area or deeper paths |
| `/oferta/{id}` | listing detail | 200; 404 for anything not public (never 410); inline retry state on 429/503/timeout |

## 2. Search URL codec (`src/search/codec.ts`)

One codec, Polish parameters, canonical serialisation (fixed order, defaults
omitted) — DESIGN-001 §8: `koszt_od/do`, `najem_od/do`, `na_start_do` (whole
złoty → ×100 minor units), `pokoje_od`, `metraz_od`, `umeblowanie`
(pelne/czesciowe/brak), `parking` (ulica/miejsce/garaz), `zwierzeta=tak`,
`winda=tak`, `dostepne_do`, `okres_do`, `mapa` (bbox), `sort`
(najnowsze/najtansze/najdrozsze/najwieksze/najwczesniej), `strona`, `widok`.
Parsing never throws: invalid, unknown, repeated or inverted-range parameters
are dropped and the page says *"Pominęliśmy nieprawidłowy filtr w adresie."*
`strona` is capped at the backend's 10 000 offset. `utm_*` is ignored (it is
attribution, not a filter).

A backend 422 naming a parameter the codec let through gets **one retry
without it** — never a redirect, so it cannot loop.

## 3. States (DESIGN-001 §5)

| State | Implementation |
|---|---|
| pre-search | `/wynajem` shows honest national results + "Wybierz miasto, aby zawęzić" |
| results | count in a polite live region with Polish plurals; cards; sort (GET form, auto-submit with JS); filters (native `<details>` + GET form; live count "Pokaż N ofert" via `/bff/v1/classifieds?…&limit=1`, debounced 300 ms, aborted on change); removable chips; "Pokaż więcej" + page links |
| zero results | empty state + up to 3 **real** relaxations (one parallel `limit=1` re-count per removed filter, decision-weight order) |
| API error | inline alert with retry; filters intact |
| 429 / 503 | Polish message from the shared error model; detail page shows an inline retry state |
| map | price pills (monthly total), **stacks** for points in one public cell (never spiderfied), MapCard reads public details through the BFF (MapPoint has no title/cover, gap G5), "Szukaj w tym obszarze" only after a user pan/zoom (never a silent re-query), bbox becomes a removable "Obszar mapy" chip with the district-only note; truncated and district-only counts said in words; no WebGL → message + link to the list |

**Loading:** there is deliberately no route-level `loading.tsx` on the results
route — it makes Next.js stream a 200 before `notFound()` runs, turning unknown
places into soft 404s (found by E2E). The home rail streams with a skeleton.

## 4. Map provider (G-11)

`maplibre-gl` 6.11.2 is loaded **only in map mode** (dynamic import; E2E
asserts it is absent from list mode and the home page). With no
`NEXT_PUBLIC_MAP_STYLE_URL` the map draws a plain background — no tile server
is contacted (E2E asserts no tile requests). OSM's public tile servers are
never used. A production provider is a founder decision.

## 5. Backend changes in this slice (additive, no schema change)

| Change | Why | Proof |
|---|---|---|
| `ClassifiedOut.facts` (`PublicFacts`: category, subtype, rooms, area_m2, space_area_m2, floor, floors_total, has_elevator, furnished, parking, pets_allowed) built field by field | gap **G1**: search already filters/sorts on these, the listing could not show them | SQLite full 1352 passed; targeted PG 230 passed; E2E detail facts |
| `GET /v1/geo/localities/by-slug?country=&slug=` (exact slug, ACTIVE, cities first, ≤ 20) | gap **G7**/BG-2: name search is prefix-on-name, so `krakow` never finds "Kraków" and `lodz` never finds "Łódź" | 3 new tests in `test_geography.py` |
| `app/scripts/seed_e2e.py` | E2E needs real data: 12 **fictional** listings (10 Kraków, 2 Warszawa) created through the real API in-process; refuses unless `HOMIES_ALLOW_E2E_SEED=1` and `ENV ∈ {local,test,ci}`; idempotent; refuses a partial seed | local runs + CI job `web` |

Locality slug has no index; the web server caches slug resolution for 10
minutes per process. An index is a later EXPAND migration (**PERF-G7**), not
taken here to keep `NO_SCHEMA_CHANGE`.

`release.json` is unchanged in this slice: no migration, so no barrier.

## 6. Measurement (EVENTS-v1; G-12)

`search_performed` (search_id, filter-dimension set, locality/area ids, sort,
result_count, 500-PLN price band, surface), `search_results_viewed`,
`map_mode_entered`, `listing_viewed` (with the search_id and absolute
position of the card that was opened — kept **in memory**, never in the URL or
storage). All go through the consent gate: by default nothing is emitted. E2E
proves both the silence without consent and the payload with consent, and that
no event carries `user_id`, an e-mail or a raw URL.

## 7. Privacy

The public page shows city, district and the APPROXIMATE public point only;
E2E asserts no seeded street name reaches a listing page. Listing detail
copy: *"Lokalizacja przybliżona — dokładny adres zna tylko właściciel."*
Detail and results are `noindex` while the kill switch is off.

## 8. Known gaps and deviations

| # | Item | Effect |
|---|---|---|
| FE2-1 | No contact/save/viewing CTA (FE-003 not authorised) | detail shows a neutral "kolejny etap" note in the contact box |
| FE2-2 | `published_at` not public (G2) | "Najnowsze" relies on the backend `newest` sort; no "dodano X dni temu" |
| FE2-3 | No photo alt/caption or variants (G5) | photos use positional alt ("Zdjęcie 1 z 3"); full-size images on cards |
| FE2-4 | Attributes/amenities not shown or filterable in the UI | `has=` exists in the API; UI later |
| FE2-5 | Parking cost semantics — **decided (D-102, 04a §24 G4)**: only mandatory, non-separable parking belongs in the total; the owner input cannot yet say optional vs mandatory (modelling gap), so a stated parking fee stays a mandatory component — no heuristic change | parking fee shown as a separate line in the breakdown |
| FE2-6 | Mobile high-fidelity frames missing (Figma Starter limit) | mobile layout follows DESIGN-001 §4 rules, not drawn frames |
| FE2-7 | Next.js logs "The destination stream closed early" when a test closes a page mid-stream | benign client-abort log; tests unaffected |
| FE2-8 | E2E backend runs with rate limiting off (all Playwright workers share one IP) | 429 UI is covered by unit tests of the error model, not by E2E |

## 9. Verification

Local (Docker, node 24 / Playwright 1.63 image, API on PostGIS with the seed):
`check:api` · `typecheck` · `lint` · Vitest **78/78** · `next build` ·
Playwright **40/40 twice** (desktop + mobile; foundation, seeker, axe on
results/detail, budget, map, analytics). Backend: ruff, mypy (126 files),
OpenAPI drift check, SQLite full **1352 passed / 508 skipped / 0 failed**,
targeted PG **230 passed**. CI job `web` runs the same chain on a PostGIS
service with the seed.

## 10. Security review repairs (PROGRAM-001)

**SEC-002** slug resolution uses a bounded LRU (2 000 cities × 10 min) that
caches each city with its areas, so random slugs neither grow memory nor
multiply backend calls. **SEC-004** the E2E seed needs the opt-in, an
explicitly set development `ENV` and a database named `*_e2e|*_test|*_ci`
(7 tests). Public facts no longer carry `floors_total` (building height + the
~550 m cell + subtype can single out a building); `floor` stays — both are
**CANONICAL DECISION REQUIRED (D-101)**. Over-long or malformed place slugs are
404. The map card says "Pokazujemy 10 z N" and reuses fetched details. Found
while adding the CSP check: the maplibre module worker had never loaded (the
bundler does not emit it); it is now served same-origin from
`public/vendor/maplibre-gl-<version>/` and the map sets the URL explicitly.
