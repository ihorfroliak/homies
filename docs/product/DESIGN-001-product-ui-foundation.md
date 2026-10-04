# DESIGN-001 — Product / UX / UI Foundation

| Field | Value |
|---|---|
| Status | **FOUNDATION — on `main`** (PROGRAM-001, `c32ac63`). Visual direction: **1C Dzielnica** selected (D-103); **DESIGN-001C Product Convergence founder/GPT APPROVED at design-contract level**; FE-003 implementation NOT authorised; 1C production rollout = separate FE-VIS-001 — see §0 |
| Authority | subordinate to the canon ([07](../canonical/07-PRODUCT-GROWTH-DOCTRINE.md), [02](../canonical/02-BUSINESS-LOGIC.md), [03 §3](../canonical/03-SYSTEM-ARCHITECTURE-v1.1.md)); founder decisions D-98 (G-1, G-3, G-5, G-11, G-13) |
| Family | this document · [DESIGN-SYSTEM-v1](DESIGN-SYSTEM-v1.md) · [UI-STATE-MAP](UI-STATE-MAP.md) |
| Supersedes | `docs/design/PRODUCT_UX.md` (booking-era journeys) and the booking-specific parts of `docs/design/DESIGN_SYSTEM.md` |
| High-fidelity design | **PARTIAL.** Figma file *Homies — DESIGN-001 Seeker v1* (private; founder's workspace): Design System v1 variables (Light), 12 text styles, 9 components; desktop **Home**, **Results (list + map)**, **Unavailable (404)**. The desktop **Detail** frame has a known clipping defect; **mobile frames were not created** — the Figma Starter plan's MCP tool-call limit was reached. Mobile is specified here (READY FOR FIGMA) and rendered for real by FE-002 |

Grounded in the real API (`docs/api/openapi.json`). Where the UI needs
something the API lacks, it is listed under **API gaps** — never invented in
the client.

## 0. Design sync (2026-10-04, D-103)

| | |
|---|---|
| Selected direction | DESIGN-001B → **1C Dzielnica** (founder) |
| Design task | **DESIGN-001C — Product Convergence: founder/GPT APPROVED at design-contract level** (2026-10-04; produced in Claude Design) |
| Implementation | FE-003 contract approved, **implementation NOT authorised** (D-104/D-105); 1C production visual/token rollout = separate **FE-VIS-001** |
| Authoritative next input | **P-0**: the repository-readable approved handoff `docs/design/DESIGN-001C-HANDOFF.md` (the raw `.dc.html` stays the source visual artifact) |

Known invariants: expressive district/area colour is the selected identity,
and **area colour never means quality, trust or status**; Seeker v1
validated behaviour is preserved; the FE-002 architecture is the
implementation foundation; mobile web exists now; native is one
Expo/React Native app for renter, owner and agent capabilities and Admin
stays a separate secure web app (03 §2). Design System v1 below is what
production uses today. **No 1C token, layout or prototype value enters
production code before the approved DESIGN-001C handoff** — this document is
not a completed high-fidelity design.

## 1. Brief and principles (acceptance criteria)

Phase 1A: LONG_TERM, whole apartments first, Kraków first, seekers free, no
money handled. Promise (07, directional): *Najprzejrzystszy sposób na wynajem
mieszkania w Polsce.* First slice: the anonymous seeker path Home → Search →
Results (list/map) → Listing detail.

| # | Principle | Verifiable criterion |
|---|---|---|
| P1 | browse before registration | home, search, map and detail render fully for anonymous users; nothing blocks reading |
| P2 | no unnecessary auth wall | auth only at an action that needs it (save, saved search, message, viewing, phone); afterwards the user returns to that action (*return-to-intent*) |
| P3 | transparent pricing | every price surface shows the **monthly total** first, base rent second; "czynsz" is never used alone |
| P4 | totals always visible | `monthly_total_estimate` on card, marker and detail; `move_in_total` on card (second line) and detail |
| P5 | no hidden fees | every cost field in `ClassifiedOut` is shown; free-text `other_costs` verbatim and labelled *not included in totals* |
| P6 | freshness visible | `confirmed_on` as relative + absolute date on card and detail |
| P7 | verification ≠ freshness | freshness never says "zweryfikowana"; different component, icon and token |
| P8 | factual trust only | no scores, no "popular", no counts we cannot source |
| P9 | no fake urgency, no dark patterns | no "3 people are viewing", no countdowns, no pre-checked opt-ins, no confirmshaming |
| P10 | mobile-first | specs start at 360 px; one-handed flows; sticky bars respect safe areas |
| P11 | clear error recovery | every error says what happened, what still works and one next action; filters are never lost |
| P12 | truthful unavailable states | a listing 404 never implies the listing existed (D-59) |
| P13 | moderation reasons never public | public routes show no hold, report or decision state |
| P14 | privacy-safe location | no pin; APPROXIMATE drawn as an area (~550 m cell); DISTRICT shows no map; "exact address is not published" is stated |
| P15 | accessible | WCAG 2.2 AA (§8); axe in CI plus a manual keyboard and screen-reader pass |
| P16 | country-neutral core | currency from `currency`; copy in locale files; place types from the geo API |

## 2. Information architecture

**Seeker / public (Next.js public web):** `/` home · `/wynajem[/{miasto}[/{obszar}]]` results (list; `?widok=mapa` map mode) · `/oferta/{id}` detail · `/zapisane` (+ `/zapisane/wyszukiwania`) · `/wiadomosci[/{id}]` · `/ogladania` · `/konto` · `/logowanie`, `/rejestracja` (also as a sheet) · `/pomoc`.

**Supply ("Panel" mode in the same app):** `/panel` dashboard (listings needing action, new leads, upcoming viewings) · `/panel/nieruchomosci` properties → spaces · `/panel/oferty` (any status) · `/panel/oferty/nowa` wizard Property → Space → Details → Pricing → Recurring costs → Availability → Media → Preview → Publish · edit (price with `expected_version`, 409 → reload diff) · `/panel/leady` (provider stage) · `/panel/ogladania` · `/panel/oferty/{id}/moderacja` (hold + review request).

**Moderator (separate Next.js admin app, own origin, canon 03):** queue · target detail (LISTING, MESSAGE, MEDIA) + evidence + decision · media approvals · authority verify/revoke · audit. Desktop only (≥ 1024 px). Opening a target moves its reports to IN_REVIEW and is audited, so it is an explicit "Rozpocznij przegląd" action, not a hover. A 409 keeps the draft and shows the new head; never auto-retried. `close_engagement` is enabled only for VISIBILITY_LIMITED with SCAM/FAKE/SAFETY, and the form says what it does.

**Navigation:** seeker mobile bottom nav (5): Szukaj · Zapisane · Wiadomości · Oglądania · Konto (badges = real unread counts only); desktop top bar: logo · compact search · Zapisane · Wiadomości · "Dodaj ofertę" (ghost) · account. Supply: "Przełącz na panel" → Pulpit · Oferty · Leady · Oglądania · Konto.

Dormant legacy flows (booking, payments, payouts, short stay) are never exposed.

## 3. Journeys

**J1 Seeker** (high fidelity first): Home (city ComboBox over `/v1/geo/localities`, optional max monthly cost) → Results (scan, sort) → Filters (live count) → List/Map ("Szukaj w tym obszarze" after a pan — never a silent re-query) → Detail (costs, freshness, area, photos) → *later:* Save → Conversation → Viewing. Phone reveal (`contact_mode=phone`) needs a verified phone; show the remaining daily quota.

**J2 Supply:** register → verify phone → property (exact address private; APPROXIMATE vs DISTRICT explained) → space → details → pricing with a **live CostBreakdown preview exactly as seekers see it** → availability (`available_from` or none; `min_term_months` or `open_ended`) → media (rights declared; per-photo PENDING / APPROVED / REJECTED / RESTRICTED) → preview → publish (refusals list `quality.missing_required` and authority state, each with a fix link) → reconfirm ("Potwierdź aktualność", shows `reconfirm_at`) → leads → viewings → hold → one review request.

**J3 Moderator:** queue (severity, live and phone-verified reporters, open review request, held) → review → decide (action, reason, optional reclassification, explanation; `expected_head_decision_id`).

## 4. Responsive strategy

| Breakpoint | Width | Layout |
|---|---|---|
| sm | 0–479 | 4-col grid, 16 px margins; list-first, one card per row |
| md | 480–767 | two-up cards allowed |
| lg (tablet) | 768–1023 | list two-up; map is a full-screen mode as on mobile with a top segmented control; filters in a right drawer (480 px) |
| xl | 1024–1439 | **split view**: list 45 % / map 55 %, map sticky under the header; filters as a left side panel |
| 2xl | ≥ 1440 | split with the list capped at 760 px, two-up cards in the list |

Mobile list ↔ map: a persistent floating **Lista / Mapa** segmented switch
(bottom centre, above the bottom nav) toggles a deliberate full-screen map,
keeping filters and scroll position. One mode at a time (sane focus order
and screen-reader output) — never a desktop split shrunk.

Filters: desktop side panel; mobile full-screen sheet with a sticky footer
"Wyczyść" / **"Pokaż 124 oferty"**. The count comes from `GET
/v1/classifieds?…&limit=1` → `total`, debounced 300 ms, in-flight request
aborted on change; a zero count shows a warning instead of disabling the
button. `bbox` from the map is a removable chip ("Obszar mapy") that notes
district-only listings are excluded (bbox matches only the public point).

## 5. Screen specs — first seeker slice (desktop in Figma; mobile READY FOR FIGMA)

### 5.1 Home
Mobile: brand bar · H1 (positioning) · SearchBox (city + "Maks. koszt
miesięczny" + "Szukaj") · three factual pillars (*Pełny koszt miesięczny i na
start* · *Oferty potwierdzane jako aktualne* · *Bez opłat dla szukających*) ·
"Najnowsze w Krakowie" rail (real API results, up to 6) · owner CTA "Dodaj
ofertę bezpłatnie" · footer with Pomoc. Desktop: search inline in the hero,
3-up rail. No invented market statistics. Rail loading → skeleton; rail error
→ the section is hidden (never a broken rail).

### 5.2 Results (list)
Header: place H1 ("Mieszkania na wynajem — Kraków"), result count (polite live
region, Polish plurals), sort (Najnowsze / Najniższy koszt miesięczny /
Najwyższy koszt miesięczny / Największa powierzchnia / Najszybciej dostępne →
`newest, price_asc, price_desc, size_desc, available_soonest`; price sorts use
the monthly total), "Filtry (3)", removable chip row.

ListingCard: cover (4:3, `is_cover`, else the first approved photo) · SaveButton
· **monthly total** large ("3 450 zł / mies."; prefix "od" when utilities are
NOT_STATED, "ok." when ESTIMATED) · "Najem 2 900 zł · Na start 6 900 zł" ·
title (2 lines max) · district, city · move-in ("Od zaraz" / "Od 1 lis 2026" /
"Termin nie podany") · FreshnessBadge · rooms and area once API gap G1 lands.

Pagination: "Pokaż więcej" (URL `strona` kept in sync) plus page links for
crawlers; 24 per page; `offset` is capped at 10 000 → past that "Zawęź
wyszukiwanie".

| State | Trigger | UI |
|---|---|---|
| loading | first load / filter change | 6 card skeletons (static under reduced motion); count "Szukamy…" |
| pre-search | `/wynajem` without a place | honest national results + "Wybierz miasto, aby zawęzić" |
| zero results | `total = 0` | EmptyState "Brak ofert dla tych filtrów" + up to 3 **relax suggestions** (re-count with one filter removed, max 3 parallel `limit=1` requests, only in this state: "Usuń »Winda« → 12 ofert") + "Zapisz wyszukiwanie" (later slice) |
| API error | 5xx / network / 503 | inline Alert above the list, filters intact, "Spróbuj ponownie"; previous results stay visible, marked stale |
| 429 | rate limited | "Za dużo zapytań w krótkim czasie. Spróbujemy ponownie za chwilę." — auto-retry after `Retry-After` |
| 422 | tampered or old URL | invalid params dropped, search runs, toast "Pominęliśmy nieprawidłowy filtr" |

### 5.3 Map mode
`GET /v1/classifieds/map` with the same query. Markers are price pills
(monthly total). Points in one grid cell are a **stack** ("4 oferty" pill that
opens a list) — never spiderfied into fake positions. Selecting a marker opens
a MapCard (fetches the detail: MapPoint has no title or cover — gap G5).
Partial: `truncated` → "Na mapie widać 500 z 1 240 ofert. Przybliż mapę lub
zawęź filtry."; `without_point > 0` → "18 ofert ma podaną tylko dzielnicę —
znajdziesz je na liście." Tiles failing → "Mapa jest chwilowo niedostępna" +
switch to list. The map provider is development-only (G-11); with no style
configured the map renders a no-tile background with the cells and pills.

### 5.4 Filters
Order by decision weight: location (city ComboBox + areas from
`/v1/geo/localities/{id}/areas`) · **monthly cost** from/to · rent from/to (under
"Więcej") · **max move-in total** · type/subtype · rooms from · area from ·
available by (helper: listings without a date are not included) · max minimum
term · furnished · parking · pets · elevator · amenities (only `/v1/attributes`
where filterable, labels `label_pl`). `space_type` hidden in 1A (G-3), but the
URL supports it. PriceInput takes whole złoty (×100 to minor units).

### 5.5 Listing detail
Mobile, top to bottom: full-bleed swipe gallery ("1/12", tap → fullscreen) ·
title · district, city · **CostBreakdown summary** (monthly total + move-in
total, expandable) · FreshnessBadge (definition tooltip) · move-in and term ·
description · location · platform notes · "Zgłoś ofertę" (link, bottom).
Desktop: two columns — gallery grid (1 large + 4) and content left; sticky
360 px price card right.

CostBreakdown (server values only — the client never computes a total):

| Row | Field | Rule |
|---|---|---|
| Najem | `rent_amount` | always |
| Czynsz administracyjny | `admin_fee` | when > 0 |
| Media | `utilities_amount`, `utilities_basis`, `utilities_included` | INCLUDED → "w cenie najmu"; ESTIMATED → "ok. X zł (szacunkowo)"; NOT_STATED → "nie podano" |
| Parking | `parking_fee` | when > 0 (counted in the total today — gap G4) |
| **Razem miesięcznie** | `monthly_total_estimate` | "szacunkowo" when estimated; "od … + media" when utilities not stated |
| Kaucja (zwrotna) | `deposit_amount` | when > 0 |
| **Na start** | `move_in_total` (`move_in` breakdown) | caption "pierwszy miesiąc + kaucja" |
| Inne koszty | `other_costs` | verbatim, "Opis właściciela — nie wliczone w sumy" |

Amounts: tabular numerals, right-aligned, `Intl.NumberFormat('pl-PL', {style:
'currency', currency, useGrouping: 'always', minimumFractionDigits: 0})` from
minor units (pl-PL does not group four-digit numbers by default). Grosze only
when non-zero.

Freshness: "Potwierdzona jako aktualna 3 dni temu" + `<time>` with the absolute
date. Tooltip: "Właściciel lub agent potwierdził, że oferta jest nadal aktualna.
To nie jest weryfikacja nieruchomości." Null `confirmed_on` → hidden.

Location: APPROXIMATE → map with a translucent ~550 m cell, no pin, caption
"Przybliżona okolica (ok. 500 m). Dokładny adres nie jest publikowany.";
DISTRICT → no map, "Właściciel podał tylko dzielnicę: {district}."

Contact, save and viewing CTAs belong to FE-003 (not authorized in
PROGRAM-001): the first slice ships **no dead buttons** — the price card shows
the costs and freshness only.

**Unavailable (404):** "Nie znaleźliśmy tej oferty" / "Oferta może być
niedostępna albo link jest nieprawidłowy." Actions: "Szukaj mieszkań w
Krakowie", "Wróć do wyników" (when there is search context). HTTP 404, never
410; `noindex`.

## 6. Accessibility (WCAG 2.2 AA)

2.4.7 / 2.4.11 focus visible and not obscured (two-tone ring; scroll padding
for sticky chrome) · 2.5.8 target size ≥ 24 px, 44 px for primary/touch ·
2.5.7 dragging alternatives (map +/−, keyboard pan when focused, "Szukaj w tym
obszarze" button, the list as a full equivalent; gallery prev/next) · map
`role="region"` "Mapa ofert" with a skip link · 3.2.6 consistent help (Pomoc
in the same place) · 3.3.7 redundant entry (filters in the URL; wizard keeps
data) · 3.3.8 accessible authentication (paste allowed, autocomplete, no
puzzles) · 4.1.3 status messages (one polite live region for the count,
debounced, Polish plurals via `Intl.PluralRules('pl')`) · dialogs trap focus,
Esc closes, focus returns, background `inert` · 1.4.1 never colour alone ·
contrast ≥ 4.5:1 text, ≥ 3:1 UI (`--c-ink-300` never for meaningful text) ·
`lang="pl"`; codes never reach the screen unmapped.

## 7. Copy (Polish launch, G-13)

Calm, concrete, second person singular, no exclamation marks in errors, no
blame, no legalese. Errors say what happened and what to do; empty states
offer a next step; trust copy states facts and their source; freshness never
says "zweryfikowana"; unavailable copy never says "usunięta" or "wygasła" on
public routes; moderation copy is neutral with no allegation; viewing copy
always shows date + time (Europe/Warsaw). Terminology: **Najem** = base rent;
**Czynsz administracyjny** = admin fee ("czynsz" never alone); **Koszt
miesięczny** = total; **Na start** = move-in total; **Kaucja (zwrotna)**.

Key strings live in `frontend/web/src/i18n/pl.ts` (catalogue, not scattered
literals). Legal-wording items, not claims: **LD-1** "open_ended" label
("Bez minimalnego okresu najmu" pending review — "na czas nieokreślony" is a
legal contract type) · **LD-2** owner hold notice · **LD-3** "Bez opłat dla
szukających" · **LD-4** authority verification statement · **LD-5** closed
conversation / removed message notices (= TASK-015 L11) · **LD-6** "zwrotna"
for deposits.

## 8. URL design and indexing

Paths: `/wynajem`, `/wynajem/{locality-slug}`, `/wynajem/{locality-slug}/{area-slug}`, `/oferta/{id}`. Query (one codec, `frontend/web/src/search/codec.ts`):
`koszt_od`, `koszt_do` → `min/max_monthly_total` (whole zł ×100) · `najem_od`,
`najem_do` → `min/max_rent` · `na_start_do` → `max_move_in_total` · `pokoje_od`
→ `min_rooms` · `metraz_od` → `min_area_m2` · `umeblowanie` → `furnished` ·
`zwierzeta=tak` → `pets_allowed` · `winda=tak` → `has_elevator` · `dostepne_do`
→ `available_by` · `okres_do` → `max_term_months` · `sort` (najnowsze,
najtansze, najdrozsze, najwieksze, najwczesniej) · `strona` → offset ·
`widok=mapa` (UI only). Canonical order; defaults omitted; unknown or invalid
parameters dropped.

Indexing (only when the founder enables it — the default everywhere is
`noindex`): bare city/area paths with results, self-canonical; any filter,
sort, `widok`, `strona > 1` or zero-result page → `noindex, follow` with the
canonical on the bare path; `/oferta/{id}` while public; unavailable → 404 +
noindex; account, panel, admin → noindex. Landing families such as
`/wynajem/krakow/2-pokoje` are a later growth task (EXPERIMENTS-v1 #7).

## 9. API gaps (needed by this UI; never invented in the client)

| # | Gap | Need |
|---|---|---|
| G1 | card/detail facts not in `ClassifiedOut` (they exist on `PropertyOut`; search filters and `size_desc` already use them) | rooms, area_m2, floor, floors_total, furnished, parking, pets_allowed, has_elevator, category, subtype, attributes |
| G2 | recency | public `published_at` |
| G3 | structured price | public `price_components[]`; structured one-off fees (e.g. agency fee) so `move_in_total` covers them; admin fee "stated as 0" vs "not stated" |
| G4 | parking semantics | `parking_fee` is counted as a mandatory monthly cost in `pricing.summarize`; an optional spot inflates totals — **CANONICAL DECISION REQUIRED** |
| G5 | media | alt/caption, image variants (thumb/srcset), dominant colour; `cover_url` + `media_count` on list/map; `MapPoint` title and cover |
| G6 | trust facts | public authority-verified fact (without owner ids); public freshness policy days |
| G7 | geo for URLs and map | resolve by slug; centroid + bounds for the initial viewport |
| G8 | saved state on cards | saved ids for the signed-in user |
| G9 | engagement affordances | `ConversationOut.can_send`, `closed_by`; `ViewingOut.cancelled_by` (now `cancelled_by_homies`); typed viewing-slots schema; meeting point/address disclosure at CONFIRMED (**CANONICAL DECISION REQUIRED**, privacy) |
| G10 | error contract | documented 429/503 with `Retry-After`; a stable `COMMIT_UNKNOWN` code; machine-readable 422 `{param, code}` |
| G11 | district-only partition | filter for listings without a public point |
| G12 | sort enum | `sort` is a plain string in OpenAPI; publish its enum |

## 10. Proposed design decisions

D1-1 token convergence (DESIGN-SYSTEM-v1; primary button contrast fix — done) ·
D1-2 product font: keep the system-ui stack at launch (zero download, Polish
diacritics covered by every platform font); Inter in Figma is a stand-in ·
D1-3 explicit "Szukaj w tym obszarze" instead of auto re-query on pan · D1-4
grid-cell stacks, never spiderfied · D1-5 Polish URL codec, saved searches
store the API-canonical query (D-72) · D1-6 404, never 410, for unavailable
listings · D1-7 light theme at launch; dark stays defined, not shipped.
