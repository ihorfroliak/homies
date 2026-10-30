# DESIGN-001C verification — 2026-10-30

Scope: R1 presentation candidate on baseline `4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4`; not a general audit, production rollout or new formal baseline. Exact candidate is the commit containing this report; resolve with Git rather than a self-referential SHA.

## Source preservation
All seven original attachment SHA-256 values match the manifest. ZIP contains 38 entries, all extracted in the private local reference archive. The six separately attached HTML exports exactly match their ZIP counterparts. Empty Dzielnica is preserved, not fabricated. Git attributes disable text normalization for originals.
Archive content and scripts are reference material only. The app does not import or execute them.

## Automated evidence
- Node 24.21.0; existing lockfile; isolated Docker dependency/build volumes.
- ESLint: PASS, zero warnings.
- TypeScript: PASS (explicit typecheck and final Next build).
- Vitest: 204 tests passed across 21 suites on the first run. One further suite initially could not load ../../docs/api/openapi.json because the local test container lacked its read-only mount. After correcting only the local environment, its 2 tests passed. Aggregate: all 206 tests passed; not represented as one all-green invocation.
- Final Next.js build: PASS after the browser-discovered CSS repairs.
- Git diff whitespace check: PASS with repository line-ending settings.
- No backend tests, destructive DB tests, migrations or new security audit were needed or run for this presentation-only diff.
- GitHub CI: NOT RUN. Required before integration. No merge or deployment.

## Actual browser checks (real alpha backend, synthetic data)
Desktop 1440 × 1000 and mobile 390 × 844:
- Home renders, real newest listings display. Preview /healthz, original alpha /healthz and backend /readyz each return 200; preview response carries X-Robots-Tag: noindex, nofollow.
- Entered Kraków + 5000 zł and submitted real search: 7 results, URL /wynajem/krakow?koszt_do=5000.
- Card Save invokes the real guest login interruption; no fake saved state.
- Real detail page shows server monthly/start amounts, approximate area only and current FE-003 actions.
- No-schedule listing displays the real unavailable schedule message and disabled Continue.
- Kazimierz demo listing returns real BP-11 slots; switched to 31 October and selected 10:00–10:30. Continue requires login. No reservation was submitted.
- Mobile form overflow discovered and repaired: measured dialog scrollWidth equals clientWidth (358 px); the date strip scrolls inside its own container.
- Selected day and slot visibly distinguished. Full-width mobile dialog; action semantics unchanged.
- Home document width equals viewport content width (375 px); no page-wide horizontal overflow.
- Broad link recolor initially hid selected list/map text. Removed that override; final desktop screenshot confirms white Lista text on the active dark tab. The Mapa action changes the view and retains the search filter; no licensed basemap is configured.
- Existing login cancellation returns to slot selection; the active day can reset while a previously selected instant remains. No interaction logic was changed; retain as a follow-up UX note.
- Intermittent browser-control deadlines occurred; observations were refreshed before retries. These are not counted as app failures or passed checks.

No new authenticated save/message/viewing/provider transaction was executed in this design pass. Existing regression suites passed, but this is not a new full alpha certification. Dark theme was not visually certified.

## Limitations and next gate
Real fixture photos are synthetic color blocks; no market photos were substituted. No licensed basemap is configured in the local alpha. Home Mapa geography/boundaries, district palette rollout and proposed fonts remain separately unresolved/deferred, as recorded in README. The current request authorizes this bounded presentation candidate, not automatic acceptance of every export proposal.
Local preview is http://localhost:3001; accepted alpha remains http://localhost:3000. Founder visual review and exact-candidate CI remain before integration. IBB-001, all existing debt and production NOT READY / NOT DEPLOYED remain unchanged.
