# FE-UX-KRK-002 — Kraków search results, map and listing detail

Founder handoff 2026-11-06. Risk class R1: frontend presentation and client state
on existing public/BFF routes. Builder: Claude Code, branch
`claude/FE-UX-KRK-002-search-detail`, own worktree.

Base: candidate `6c6bb0237112653b37b71769d0a5fdc0d0f1fcba` (Draft PR25,
`codex/fe-vis-001b-home-map`, not integrated, final map review gate OPEN). This
work depends on PR25; the Draft PR targets that branch until PR25 is integrated.
The inherited diff is not this task's work. PR25's branch is not modified.

## Scope

A. Kraków results. B. Results map and marker cards. C. Listing detail and the
entries to existing protected actions. A small no-JS mobile navigation repair.

Out of scope: search inside an administrative district (neighbourhood routes are
not its equivalent); new cities; new API, migration, geography model or
authorization rule; inbox/provider redesign; production map provider, staging,
deployment; paid providers, real messages; merging PR25 or this PR.

## Findings on the real application

Observed 2026-11-06 at `http://localhost:3001` (PR25 preview, synthetic data), read
only, at 360/390/768/1440 px. "Probe" means a scripted Edge run on the real page.

| # | Screen | Problem | Evidence | Minimal fix | Test |
|---|---|---|---|---|---|
| 1 | Results | Back after changing sort: URL says newest, select still says cheapest | Probe: `select=najtansze` on `/wynajem/krakow` | Forms opt out of browser state restore; reset on bfcache restore | e2e back/forward |
| 2 | Results | Back after applying a filter: URL has no filter, input still holds 5000 | Probe: `koszt_do value: 5000` | Same as 1 | e2e back/forward |
| 3 | Results | Removing a chip leaves the filter button on the old count | Probe: button "Pokaż 7 ofert", heading "10 ofert" | Remount filter panel per URL state | e2e |
| 4 | Results | Opening filters pushes List/Map down and leaves half the row empty | Capture 1440 | Desktop panel anchored to toolbar, three-column form | Capture, e2e |
| 5 | Results | No way back to all of Kraków from a neighbourhood; the area is not an active-filter chip | Source: `activeFilters` excludes it, panel lists areas only | Area chip and "Cały Kraków" link | e2e |
| 6 | Results | Empty result in map mode on mobile shows a blank map, explanation hidden | Probe: heading not visible at 390 | No map when there are no results | e2e |
| 7 | Results | Client navigation gives no pending feedback | Source: no pending state, `loading.tsx` not usable (it would turn 404s into 200s) | Link-level pending mark | Unit |
| 8 | Results | Retry link points at the current URL, so it may not refetch | Source: `next/link` to same href | Plain anchor, full reload | Source + manual |
| 9 | Results mobile | Controls take five rows; List/Map scrolls away | Capture 390 | Compact toolbar; floating List/Map as in 001C | Capture |
| 10 | Cards | Save button adds a separate row; cards very long on mobile (6568 px for 10) | Capture 390 | Save in card header, shorter photo | Capture |
| 11 | Map split | Prices wrap inside narrow cards at 1440; map notes have large gaps | Capture 1440 | 001C proportions, wider container, tight notes | Capture |
| 12 | Map | Close price pills overlap at 360 | Probe: `2 950 zł~3 950 zł` | Screen-space grouping, see below | Unit + e2e geometry |
| 13 | Map | Same-cell stack above 10 cannot reach the rest | Source: `CARD_LIMIT` slice, no control | "Pokaż kolejne" pages through existing detail route | Unit |
| 14 | Map | Closing the card drops focus to `body` | Probe: `focus after esc: BODY` | Return focus to the opener | e2e |
| 15 | Map | Keyboard users tab through every card before reaching markers | Probe: tab order | Skip link to the map | e2e |
| 16 | Map | "Tylko dzielnica" note says use the list, but mobile map hides it with no link | Capture 390 | Link to list; same when the map fails | Capture |
| 17 | Detail | At 1440×1000 costs start at y=835 and the main action at y=1386 | Probe | Rail and costs in the first columns, 001C hero | Capture, e2e |
| 18 | Detail | "Wróć do wyników" loses filters and view | Probe: href `/wynajem/krakow` from a filtered map | Remember last results path per tab, validated | e2e, unit |
| 19 | Detail | A pending request is labelled "umówione oglądanie" | Source: `seeViewing` used for REQUESTED and CONFIRMED | Status from the server; neutral link wording | Unit |
| 20 | Detail | Costs rendered twice in the DOM, one hidden by width | Source: `mobileCosts` + aside | One cost section | e2e (one visible) |
| 21 | Header | Mobile menu is unavailable without JavaScript | Review note in PR25 | Noscript links; inert button hidden | e2e no-JS |

## Map decision

Near price pills are grouped in screen space when their rectangles intersect at
the current zoom. A group is drawn at one member's real public coordinate; nothing
is offset or spiderfied. It reads "N ofert", opens a card listing every member, and
offers zoom. Groups are recomputed after zoom and resize, so zooming in restores the
individual prices. Same-cell privacy stacks are never split and server point data
is unchanged. `MapPoint` has no utilities basis, so a pill cannot show "ok."/"od";
the card and detail keep the qualified amount. Adding it would need a new API
contract and is not done here.

## Design source

Visual decisions follow the preserved `Homies 001C Dzielnica Product Convergence`
export: toolbar with chips, floating List/Map below 1024 px, list 6:5 map from
1024 px and 7:5 with two-column list from 1440 px, card hierarchy, detail hero band
in the area colour, "Koszty" as sum then components then move-in, rail with actions.
Prototype slots, messages and statuses stay reference only.

Differences kept deliberately: the cost bar is drawn only from amounts the API
returned and is decorative; no "Pierwszy miesiąc" row, because the client does not
derive server totals; no blurred neighbourhood zone, because no geometry is
available and an invented shape would imply a location. Area colours identify a
place and are not a rating; unknown areas use the neutral band.

## Verification required

Lint, typecheck, unit, production build, targeted e2e with axe, real captures at
360/390/768/1440, real backend on a disposable database, CI on the final exact SHA.
Independent review of this change is a separate gate; a builder receipt is not
acceptance. No conversion or retention claim follows from this work.
