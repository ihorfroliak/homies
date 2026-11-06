# FE-UX-KRK-002 — builder verification and open gates

Base: PR25 candidate `6c6bb0237112653b37b71769d0a5fdc0d0f1fcba`. Builder receipt,
not independent acceptance. Final exact SHA and its CI run are recorded on the
Draft PR; results below do not extend to later commits.

## Foundation test failure

Test: `e2e/foundation.spec.ts` › `no CSP violation and no console error on load`.
Request, read through CDP: `GET http://localhost:<port>/favicon.ico`, CDP type
`Other`, initiator `other`, status 404. The console line is the browser's own
"Failed to load resource". Playwright page events do not show this request.

Reproduced unchanged on the base SHA in its own worktree and production build, with
the same spec and the same installed Edge: failed on desktop and mobile. Therefore
not introduced by this task. Cause: the application declares no icon, so the browser
falls back to `/favicon.ico`, which does not exist. Base CI run 41712573028 was green
on the bundled Chromium; that it requests no favicon is an inference, not measured.

Fix: `src/app/icon.svg` from the existing brand mark, which makes Next declare it.
After the fix the same CDP probe shows no 4xx, no console error and one icon link, and
`foundation` passes 20/20 locally on Edge. The assertion is unchanged. A new test
requires the declared icon to answer 200 with an SVG type, because CI's browser
cannot catch this class of defect through the console.

## Local run (real API, PostGIS, disposable database, Edge, production build)

Whole suite at `f98229a`: non-engagement specs 96 passed, 6 skipped; engagement specs
54 passed on a freshly recreated database and manifest. The six skips are per-width or
per-project cases covered by the other project. An earlier run failed
`engagement-boundaries` on mobile because of this task: the test helper read the menu
button before hydration. The helper now waits for hydration and the spec passes. A run
with a stale manifest failed 54 engagement tests; that was the environment, and the seed
said so. The workstation restarted at 2026-11-06 04:05; the founder then authorized
starting Docker Desktop. Only this task's `krk002-*` containers were recreated.

The large-stack test was added after that run and passed on both projects; CI runs the
whole suite on the final SHA. Captures at 360/390/768/1440 px from the final code against
a fresh database: no horizontal overflow, no console or page errors, no overlapping pills
(one pair at 360 px before). Base SHA comparison: 1 console 404 at first load, 0 now.

## What the tests claim

| Requirement | Evidence | Level |
|---|---|---|
| Every listing reachable; stacks whole; no point moved | Each public cell has one marker on its own coordinates; opening all visible pills reaches all API points exactly once; a stack card equals its cell | e2e, CI |
| No overlap at 360/390 px | Rectangle geometry on real markers | e2e |
| Above 10 in one stack | Real Lublin fixture stack pages to more than 10 distinct listings with focus on the first new one; exact totals and failure notice in unit tests | e2e, unit |
| Zoom, resize, focus return | Group zooms apart; resize regroups with the same total; focus back on opener | e2e |
| Filters, sort, view through Back/Forward and back link | Sequence through a listing on both projects | e2e, CI |
| Only internal results paths used | Unit refusals; tampered session storage in the browser | Unit, e2e |
| Direct open without a search | New tab with no stored results gets the city link | e2e |

## Not verified

Independent review of this change: OPEN. PR25's own final review gate stays OPEN.
Screen-reader use, human usability, field performance, Safari and Firefox. `MapPoint`
has no utilities basis, so pills cannot show "ok."/"od". After a back link the list
returns to the top; browser Back restores position. No conversion or retention claim.

`src/growth.test.ts` (file unchanged by this task) timed out at 5000 ms in full local
unit runs while the workstation CPU was at 100 % after the restart. It passed 6/6 alone
and 239/239 in the full suite at 15 % CPU, so the cause is load on a 2000-iteration test.
The test was not changed.
