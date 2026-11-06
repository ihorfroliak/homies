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
| UX-R6 | No new defect. Recovery from 503, 429 and timeout passed before any change here, on the retry fixes already in the base | — | `e2e/recovery.spec.ts` now proves it through a fault proxy in front of the real API |

## Back/forward cache: not exercised

`e2e/bfcache.spec.ts` re-enables the cache and only counts `pageshow.persisted`. Result: never
restored. Chromium reports `MainResourceHasCacheControlNoStore`,
`JsNetworkRequestReceivedCacheControlNoStoreResource` and others. WebKit: not persisted, no reason
available. Firefox: not executed. So the restore handlers are proven only by synthetic events in
`pageshow.test.tsx`, labelled so. On Chromium here that path cannot currently run.

## Results on `b905d81` (later commits are documentation)

- Typecheck, lint, `check:api`, build: exit 0. Unit: 319/319.
- Bundled Chromium, desktop and mobile, whole suite on a fresh database: 203 passed, 7 skipped.
- WebKit, without engagement specs (their fixtures are per project): 62 passed, 4 failed, 8 skipped,
  11 not run because a serial spec stopped. `recovery` alone: 9/9; the failure was a timeout in the
  shared run. Skip-link and return-focus specs fail on WebKit focus behaviour (`Received: inactive`),
  not compared on the base. The saved-list spec gets no session, inferred to be the Secure cookie on
  `http://localhost`, not measured. Engagement on WebKit: not executed.
- Firefox: NOT_EXECUTED. `spawn UNKNOWN`; the unsigned binary is refused by the OS ("Permission
  denied"). Security settings were not changed.
- Focused mutation: 33 mutants, 30 caught by an assertion in the intended test file, 3 equivalent:
  the path regex and the length bound are second layers behind the codec fixed point, and the abort
  check before `setLoaded` has no observable effect. First pass found two real test gaps, now closed.

## Not verified

Independent review of this change: OPEN. Price changes on the real backend (BFF answers injected).
Screen readers, real users. An unchanged listing URL entered by hand in the same tab keeps its origin.
After the back link the list opens at the top; browser Back keeps position.
