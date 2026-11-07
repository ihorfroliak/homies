# FE-UX-KRK-002R — builder receipt

Base `353324acb3d7784a4f798f5eaa400dbef30ea136`. Builder evidence, not independent acceptance.
The exact candidate SHA and CI run are in the founder report; results here do not extend to
later commits. Environment: Windows, real API on PostGIS, disposable database, synthetic seed,
production build. Failures injected at the BFF or by a fault proxy are named as such.

## Dispositions

| Issue | Reproduced | Root cause | Fix |
|---|---|---|---|
| UX-R1 | Yes. Real page showed `6 listopada 2026 11:00 (UTC)` for a Warsaw viewing while the zone loaded or its read failed | Unknown zone was treated as no schedule, so FE-003's UTC fallback applied | `ViewingWhen`: no hour until the schedule arrives; retry on failure. Fallback stays for no schedule (`timezone: null` or 404). `viewing-model.ts` unchanged |
| UX-R2 | Yes. Warsaw results, then a Kraków listing opened directly, offered the Warsaw search as "Wróć do wyników". `/wynajem/../oferta/1` navigated to `/oferta/1`, `/wynajem/.%2e/.%2e/wiadomosci` to `/wiadomosci` | Tab-wide "last results", and a prefix check on stored paths | Origin recorded per listing when its link is followed; stored path counts only if the codec produces exactly it. Saved list named as such; otherwise the city under a label claiming no search |
| UX-R3 | Yes. Card named a group that zooming had dissolved | Selection held in React state, not reconciled | `selectionStillValid` on regroup; focus inside moves to the pill holding the first listing |
| UX-R3 resize | Rejected as stated. Same zoom keeps pixel distances, so the group exists and the card rightly stays | — | Test pins this |
| UX-R4 | Yes. Reopened card made no request and showed the old price | Module cache with no expiry | Cache removed: no freshness rule exists to bound one, so no duration was invented. Reads live with the card; 404 says no longer available; failed read offers retry and shows no old price |
| UX-R5 | Restore not exercised, see below. Two neighbouring defects found: a restore would reset a never-submitted draft; a sort chosen before hydration was silently lost (Chromium 3/5 tries, WebKit 1/5) | Unconditional reset; listener attached after the choice | Reset only a submitted form; on mount submit a value that differs from the rendered default. After the fix 5/5 on both |
| F-01, review | Yes, 6 unit tests failed on `77f07ec`; reviewer reproduced it in Chromium and WebKit. Paging into a last page of 404 or 503 left focus on the body. Wider than reported: the pressed control also disappeared during every read, and after a successful retry | Focus went to a link by index, with no other target, and controls rendered only for the current read | Controls and notes stay until the read ends. Focus then goes to the first added listing, else Retry, else the next page, else Close. Retry follows the same rule. New browser test not run on the pre-fix build |
| F-02, review | Yes, 4 unit tests failed on `77f07ec`. While the schedule loaded or failed, `Potwierdź: 1 grudnia 2099 12:00 (UTC)` | UX-R1 fixed the visible time only; the `aria-label` formatted directly | One rule for both. FE-003's UTC fallback for a truly missing schedule stays. DOM accessible names, not a physical screen reader |
| F-03, review | Yes, see correction below | Test covered unmount, not a superseded read in a mounted card | Test added, guard kept, receipt corrected |
| UX-R6 | No new defect. Recovery from 503, 429 and timeout passed before any change here, on the retry fixes already in the base | — | `e2e/recovery.spec.ts` now proves it through a fault proxy in front of the real API |

## Back/forward cache: not exercised

`e2e/bfcache.spec.ts` re-enables the cache and only counts `pageshow.persisted`. Result: never
restored. Chromium reports `MainResourceHasCacheControlNoStore`,
`JsNetworkRequestReceivedCacheControlNoStoreResource` and others. WebKit: not persisted, no reason
available. Firefox: not executed. Same result on `25fc884`. So the restore handlers are proven only by synthetic events in
`pageshow.test.tsx`, labelled so. On Chromium here that path cannot currently run.

## Results on `25fc884` (later commits are documentation)

- Typecheck, lint, `check:api`, build: exit 0.
- Unit: 335/335. The first whole run had one failure: `growth.test.ts` "spreads buckets roughly
  evenly", `Test timed out in 5000ms` (2000 hashes in a loop, default timeout, under load). Alone it
  passed 5/5 and the second whole run passed. Not changed here; its timeout was not raised.
- Bundled Chromium, desktop and mobile, whole suite on a fresh database: 207 passed, 7 skipped.
- WebKit, without engagement specs (their fixtures are per project): 66 passed, 3 failed, 9 skipped.
  The F-01 browser test and the stack paging test need the stack fixture, so they ran separately
  on WebKit with it: 2 passed.
- The three WebKit failures, classified by the independent review of `77f07ec`, which measured
  them; this run did not repeat those measurements. Skip link and return focus after a pointer open
  (`Received: inactive`): identical on base `353324a`, inherited. Saved list: WebKit keeps the Secure
  cookie and does not send it over HTTP, and passes on local HTTPS, so an environment limit.
- `recovery` on WebKit passed in this shared run. The earlier timeout there did not recur; its cause
  remains not established, not fixed.
- Firefox: NOT_EXECUTED. All 64 attempts: `browserType.launch: spawn UNKNOWN`; 8 more not run behind
  them in a serial spec. Security settings were not changed. The review ran 7 passed, 1 not verified
  on Linux with no WebGL, so the Firefox map stays NOT VERIFIED.
- Focused mutation: 40 mutants, 38 caught, 2 survived. Caught means a named test in the intended file
  failed with an assertion; the runner no longer counts a TypeError or a timeout, as the review
  pointed out it did. No caught mutant had any other kind of failure. Survivors: the path regex and
  the length bound, second layers behind the codec fixed point for accepted return paths (confirmed
  by the review; the length bound also limits work on long input).

## Correction: mutant C6 was not equivalent

The receipt for `77f07ec` said the abort check before `setLoaded` "has no observable effect". That was
wrong. Page on before the first read finished; the new page loads, then the old read ends, and without
the check it overwrites the card and removes the new listing. Reviewer's F-03. The check stays, a
controlled test now pins it, and C6 is caught by that test. That schedule is synthetic: this race was
not observed on a real network.

## Not verified

Independent review of the F-01..F-03 repair: OPEN. Review of `77f07ec`: [REQUEST_CHANGES](2026-11-07-fe-ux-krk-002r-codex-review.md). Price changes on the real backend (BFF answers injected).
Screen readers, real users. An unchanged listing URL entered by hand in the same tab keeps its origin.
After the back link the list opens at the top; browser Back keeps position.
