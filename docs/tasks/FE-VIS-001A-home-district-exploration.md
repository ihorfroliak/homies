# FE-VIS-001A — Visual foundation, Home, search entry and Kraków area exploration

Status: **CANDIDATE on a Draft PR — not merged, not deployed.** Founder direction
HOMIES-DESIGN-GROWTH-001 (2026-10-30) authorises preparing the FE-VIS-001
contract and building the first bounded visual slice on its own branch; the
founder's message of the same day directs that the DESIGN-001C Claude Design
work be applied. Base `main` `4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4`.
Writer: Claude Code. Risk R1 (frontend presentation; no API, schema, auth or
engagement-semantics change). FE-VIS-001B–D remain unauthorised until their
own contracts.

## 1. Sources

* Canon and accepted design: [DESIGN-001C-HANDOFF](../design/DESIGN-001C-HANDOFF.md)
  §3 invariants, §17 D-103, §25–§28 (U-1), **§31 HM-1**; DESIGN-001 §5.1;
  D-98 (Kraków first, LONG_TERM first), D-103.
* Claude Design exports supplied by the founder on 2026-10-30 (read as data,
  not committed). They match the files the handoff recorded as unrecoverable:
  * `Homies 001C MASTER.dc.html` — "Launch Core", the current-section index and the open decisions;
  * `Homies 001C Home Mapa.dc.html` — the current Home (section 02);
  * `Homies 001C Dzielnica Product Convergence.dc.html` — Foundations 1C: typography tokens and the area colour model;
  * the project archive `Homies.zip`.

## 2. What the slice applies from 001C

| 001C element | Applied | Notes |
|---|---|---|
| Typography: Bricolage Grotesque (display) + Public Sans (text) | yes, globally (`--font-display`, `--font-sans`) | via `next/font`: files are bundled at build and served from this origin; no request from the visitor to Google; CSP unchanged (`font-src 'self'`); `latin-ext` for Polish |
| Warm neutrals: ink #121212, secondary #4D4D4D, paper #F6F4EF | yes (`--c-ink-*`, `--c-surface-2`, new `--c-paper*`, `--c-rule`) | semantic status colours and the brand button colour outside Home are unchanged (FE-VIS-001B–D) |
| Area colour model `oklch(L C h)`: tint 0.935/0.032, hover 0.84/0.065, solid 0.46/0.085; hue per district | yes (`--area-*` tokens, `area-colour.ts`) | the 13 district hues of Home Mapa; Zabłocie from Convergence; Kazimierz 330 — Convergence put it beside Stare Miasto (60) and the two would read as the same place |
| Home composition: 5/7 grid from 1024 px; mobile: areas as a full-width section below the search (HM-1.2/1.3) | yes | |
| Copy: eyebrow "Kraków · wynajem długoterminowy"; H1 "Wybierz okolicę. Albo cały Kraków."; lead about total cost, start amount and confirmation date | yes | "· całe mieszkania" from the design is **not** used: the seed and the API contain rooms too |
| Search: Gdzie / Łącznie miesięcznie do / Pokoje, black pill submit | yes, as a no-JS GET form | the design's − / + budget stepper is a number input (no client JS) |
| "Kraków po okolicach" + "Kolor oznacza obszar, nie ocenę." + "Cały Kraków" | yes | real areas from the geo API; links to `/wynajem/krakow/{slug}` (HM-1.5) |
| **Drawn district map** | **no** | 001C MASTER open decisions 1–2: the home geography model and an approved boundary source and licence are pending. The prototype's polygons are hand-drawn, not geography. The geo API exposes no area geometry (G7). The accessible list is the HM-1.9 way in; the map adds to it later |
| Per-area counts | **no** | MASTER: names without numbers today; counts are a FUTURE DATA-BOUND STATE (HM-1.7) |
| Listing cards, filters dialog, header navigation ("Jak liczymy koszty", "Dla wynajmujących") | **no** | FE-VIS-001B/D. No link to pages that do not exist (I-14) |

## 3. Changes

* `frontend/design-system/tokens.css`: the 1C tokens above.
* `frontend/web/src/app/layout.tsx`: fonts and theme colour.
* `frontend/web/src/app/page.tsx` and its `.module.css`:
  * the Home composition;
  * the horizontally scrolling newest rail below 768 px;
  * the owner note restyled with truthful copy (no CTA — the owner flow does not exist).
* `frontend/web/src/components/home-search/*`: the new form, replacing the removed `components/search-box/*`.
* `frontend/web/src/components/area-explorer/*`: the area list and hues.
* `frontend/web/src/app/szukaj/route.ts`: also accepts `obszar` (kept only when it is one of the resolved city's areas in the geo API) and `pokoje_od` (1–100); the output is the canonical `/wynajem/{city}[/{area}]?koszt_do=&pokoje_od=`.
* `frontend/web/src/i18n/pl.ts`: the Home copy.

No backend, API, schema, auth, analytics or engagement change.

## 4. Invariants kept

D-103 / I-1: the area colour is place identity only, stated in words, and
never alone (the name is always shown). I-9: no counts, no ranking, no
urgency. I-14: no dead links. G9: no location beyond area names. HM-1.9:
areas reachable by keyboard and screen reader. The Home loads no map library
(the budget e2e test is kept).

## 5. Verification

* Unit: area hues, a hue↔CSS rule parity test, the area list, the search form.
* e2e (CI `web` job):
  * the home form carries area and rooms into the canonical URL;
  * the area list opens Kazimierz results, with an axe check;
  * the existing home test is adapted to the new form labels.
* Local evidence: see the PR.

## 6. Conversion hypothesis (to measure later, not claimed)

Choosing an area in one step (form or list) instead of typing a city raises
the share of Home visits that reach a results page with an area filter.
Measured server-side once MEASURE-001 exists:

* Home → results visits;
* results → listing views per session;
* and further down the funnel, persisted conversations or viewing requests.

Synthetic alpha traffic is not evidence.

## 7. Open decisions (founder)

* Home geography model and boundary source/licence (map).
* Final approval of the applied 1C values (typography, neutrals, area hues) at this review.
* The order of FE-VIS-001B (results and cards) and 001D (header and navigation).
