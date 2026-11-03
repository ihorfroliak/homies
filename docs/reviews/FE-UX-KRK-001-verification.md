# FE-UX-KRK-001 — builder verification and open review gate

Base UX + route-correction code SHA: e6084756646b1c4854a5e5b53f749b35e6584ec8.
Attribution follow-up is recorded below; final candidate is the current PR25 SHA.
Base main: d103a4cf5c966320efe2b13a2fae9b73f601d276.
Date: 2026-11-03. Draft PR25. This is a builder receipt, not independent acceptance.

## Executed

- d73efef: lint, TypeScript, 225 unit tests in27 files, production build PASS.
- e608475: lint, TypeScript, three focused map unit tests, production build PASS.
- e608475: navigation E2E6/6 PASS, desktop/mobile, real synthetic alpha API:
  menu keyboard/Escape and auth cancellation/focus; overflow/axe; district
  details selection; on-demand map request; return preserves district/budget.
- Automated Chromium production-preview capture: desktop1440x1000 and
  mobile390x844; six public markers in each; opening a marker yielded real
  listing cards/links; no page errors or horizontal overflow. No API responses
  were mocked in this smoke. No authentication or data writes in capture.
- Source Home Mapa HTML rendered from preserved archive with its support assets;
  inspected alongside candidate captures. This is a partial composition review,
  not pixel parity: founder chose18 official boundaries over13 schematic shapes;
  warmer action colour and mobile disclosure are newer explicit direction.
- Earlier hydration correction at4b0: CI41613258968 SUCCESS6/6. Do not extend
  that result to later UX commits. CI41709963985 targets e608; the current PR
  head's CI remains the required integration evidence (including docs successors).

## Failures retained, not hidden

Initial local map smoke exposed404: browser used server-only by-slug route,
which is not BFF-allowlisted. e608 switches to existing public locality search,
then exact CITY/slug match; missing city fails closed, never nationwide. Unit
regression checks the actual BFF allowlist; no permission surface was widened.
Initial local auth smoke used an internal HTTP container hostname and lacked
secure-context crypto.randomUUID. Retest uses localhost inside the isolated test
container's shared preview network namespace; no application safeguard changed.
The browser-visible founder preview remains localhost:3001.

## Review / limitations

Separate read-only source review of f6e5b66 found no concrete P0–P3 findings;
[receipt](FE-UX-KRK-001-f6e5b66.md). The later map-switch exact-SHA review could
not complete: specialist runtime reported an account usage limit. **NOT VERIFIED;
review gate OPEN.** This is an environment limitation, not a model-safeguard
rejection and not evidence of a pass. Do not merge on this receipt alone.

No street basemap provider configured; UI says so. Public points remain the
existing privacy projection; same-cell listings remain stacks. Mobile captures
show nearby price pills may overlap before zooming: existing renderer limitation,
not evidence of address accuracy. Full district containment search is absent;
no fake mapping to similarly named neighbourhoods. No-JS mobile menu is still
unavailable. Human usability, screen-reader testing, conversion/retention uplift,
complete product-surface visual parity and external beta readiness NOT VERIFIED.

Screenshots and browser traces stay in the private local HOMIES-UX-KRK-001
artifact directory; personal browser chrome is excluded from repository evidence.
The reproducible synthetic functional tests live in frontend/web/e2e/navigation.spec.ts.
No main merge, deployment, provider activation, schema change or reseeding.

## Local development basemap follow-up

After the preceding blank-style smoke, the founder's requested street-map
experience was resolved within existing accepted G-11 (development-only source
permitted, beta/production selection deferred). The isolated preview compose
selects OpenFreeMap Positron; source code/default CI remain provider-agnostic
and do not enable any external tiles by default. Renderer corrections enable MapLibre's source attribution control (previously
disabled) and reserve space beneath the listing popup for the credits.
Local visual/network verification follows on the final candidate; do not infer
it from the earlier blank-style captures.

Primary sources inspected 2026-11-03:
[service](https://openfreemap.org/), [quick start](https://openfreemap.org/quick_start/),
[terms](https://openfreemap.org/tos/), [privacy](https://openfreemap.org/privacy/).
The public service requires no account/API key/payment. Attribution is required;
the TileJSON supplies OpenFreeMap / OpenMapTiles / OpenStreetMap credits.
Style, sprites, glyphs and tile endpoints were observed on the single origin
https://tiles.openfreemap.org, already supported by explicit configured-origin CSP.
No wildcard or script-origin relaxation. User account data/messages/private
addresses are never sent to it; normal browser network metadata and requested
map tiles are visible to the service/CDN. Privacy documentation describes error
and security-incident logging exceptions; this is not a zero-data or legal
certification claim. No bulk download, geolocation request or production choice.

Development basemap smoke: six markers per viewport;12 successful map resource
responses per viewport, zero failed resources/page errors/console errors or
horizontal overflow. Source credits resolved from TileJSON. Both desktop and
mobile screenshots were inspected, including an open listing card. No map
resource request occurred before the explicit homepage map selection.

Final attribution spacing check found a4px overlap on the390px mobile viewport
with expanded two-line credits; the popup now reserves64px below it. Rebuilt
successfully and repeated real street-map capture/geometry assertions on both
viewports. This small renderer follow-up is still within the open final review
gate; no broader map behaviour or public-coordinate semantics changed.
