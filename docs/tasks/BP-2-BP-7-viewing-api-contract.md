# BP-2 + BP-7 — Viewing API contract

| Field | Value |
|---|---|
| Purpose | FE-003 backend prerequisites ([FE-003 contract §10.1](FE-003-save-conversation-viewing-DRAFT.md)): **BP-2** typed `viewing-slots` response with the authoritative `timezone`; **BP-7** the backend refuses a viewing cancellation at or after its start |
| Authorisation | founder/GPT bounded task, BP-2 + BP-7 only. `FE-003 IMPLEMENTATION AUTHORIZED: NO` |
| Risk | R1 (API contract; no migration) |
| Baseline | `main` = `6be148b6fefea22e42764e2f6178d1a03433043c` (BP-1 merge), CI `37258817313` success 6/6 |
| Branch | `claude/BP-2-BP-7-viewing-api-contract` |
| Candidate | see §7 |

## 1. BP-2 — typed `viewing-slots`

`GET /v1/classifieds/{listing_id}/viewing-slots` (signed-in only, unchanged).

| | Before | After |
|---|---|---|
| OpenAPI 200 schema | `{}` (untyped); TS `unknown` | `$ref: ViewingSlotsOut` |
| Body | `{"slots": [...], "duration_minutes": …}` | `{"slots": [...], "duration_minutes": …, "timezone": …}` |

```text
ViewingSlotsOut
  slots:            list[datetime]   UTC instants (derived; a request names one exactly)
  duration_minutes: int | null       settings.duration_minutes; null without settings
  timezone:         str | null       settings.timezone (validated IANA); null without settings
```

| Case | Response |
|---|---|
| enabled settings | derived slots, configured duration, configured zone (e.g. `Europe/Lisbon`) |
| disabled settings | `slots: []`, configured duration, configured zone (settings exist → authoritative) |
| no settings | `slots: []`, `duration_minutes: null`, `timezone: null` |

**Timezone authority:** `engagement.viewing_settings.timezone` — the zone the
provider's windows are written in, validated by `SettingsIn.real_zone`
(`ZoneInfo`); canon 04 §57. Never hard-coded, inferred from the city or the
browser, or an offset. Without settings there is no authoritative zone, so the
honest value is `null` (no default invented).

**Unchanged:** visibility (404 not public), authentication, `days` (1–31,
default 14), `start`, slot derivation (DST, notice, windows, blackouts,
capacity, buffers, ordering, de-duplication), queries. **Privacy:** only
`slots`, `duration_minutes`, `timezone`; no windows, blackouts, capacity,
buffers, notice, booking mode or occupancy.

**Serialisation note:** the typed model encodes the same aware UTC instants as
`…Z` instead of `…+00:00`. The instant is identical; the request route parses
either (test `test_a_returned_slot_string_is_requestable_as_is`). No client
consumes the route yet (FE-003 not implemented).

## 2. BP-7 — no cancellation from the start on

`POST /v1/viewings/{viewing_id}/cancel`: allowed only while `now < starts_at`;
refused when `now >= starts_at` with **409 `VIEWING_STARTED: …`** (BP-1
convention), for the requester and the provider alike.

Guard order (unchanged lock and CAS):

1. `_viewing_for` — a legitimate side, otherwise 404 (privacy unchanged);
2. `_locked` — the row FOR UPDATE, re-read;
3. state ∉ {REQUESTED, CONFIRMED} → `VIEWING_STATE_CONFLICT` (terminal
   states keep their answer at any time);
4. `starts_at <= now` → `VIEWING_STARTED`;
5. `_transition` (status + version compare-and-set, `VIEWING_CHANGED`),
   audit `viewing.cancelled`, fact `ViewingCancelled` — unchanged.

**Clock:** the module's server clock `viewings._now()` (UTC), the same clock as
the sibling guards (`VIEWING_TIME_PASSED` on confirm, `VIEWING_NOT_STARTED` on
outcome) and the `cancelled_at` stamp. Canon 04a §20 names the database clock
as the authority; the viewing module has used the app clock since TASK-002
(pre-existing deviation, not introduced here) — recorded as nonblocking debt
(move all viewing time guards to the DB clock together), not changed in BP-7.

| Actor | State | before start | exactly at start | after start |
|---|---|---|---|---|
| requester | REQUESTED | 200 → CANCELLED | 409 `VIEWING_STARTED`, unchanged | 409 `VIEWING_STARTED`, unchanged |
| requester | CONFIRMED | 200 → CANCELLED | 409 `VIEWING_STARTED`, unchanged | 409 `VIEWING_STARTED`, unchanged |
| provider | REQUESTED | 200 → CANCELLED | 409 `VIEWING_STARTED`, unchanged | 409 `VIEWING_STARTED`, unchanged |
| provider | CONFIRMED | 200 → CANCELLED | 409 `VIEWING_STARTED`, unchanged | 409 `VIEWING_STARTED`, unchanged |

Refusal writes nothing (no row change, no audit, no fact). Not done here:
expiry of a passed REQUESTED (DEBT-1 — it stays REQUESTED), cancellation source
(BP-5), G-14 cleanup of existing viewings (BP-6). No new state, no migration.

## 3. Tests (`backend/tests/test_viewings.py`)

| Test | Proves |
|---|---|
| `test_the_slot_response_carries_the_settings_timezone` | `Europe/Lisbon` returned (a hard-coded Warsaw fails); duration 45; exact Lisbon-derived instants |
| `test_a_returned_slot_string_is_requestable_as_is` | round trip of the returned string; default zone `Europe/Warsaw` from settings |
| `test_disabled_settings_still_name_their_timezone` | `[]`, 30, `Europe/Lisbon` |
| `test_no_settings_means_no_authoritative_timezone` | `[]`, null, null |
| `test_the_slot_response_stays_signed_in_only` | 401 without a token |
| `test_the_slot_response_is_a_named_schema_in_openapi` | `$ref ViewingSlotsOut`; date-time items; nullable fields |
| `test_either_side_cancels_only_before_the_start` | 2 actors × 2 states × before/exactly/after (12 cases), clock controlled via `viewings._now`; refusal leaves state, audit and facts untouched; success writes one audit and one fact |
| `test_a_finished_viewing_stays_a_state_conflict_after_its_start` | DECLINED / CANCELLED after start → `VIEWING_STATE_CONFLICT`, not `VIEWING_STARTED` |
| `test_a_stranger_still_sees_nothing_after_the_start` | 404 for a non-side |
| `test_a_passed_request_is_left_as_it_is` | no expiry; stays REQUESTED |

Existing slot, DST, cancel, CAS (`VIEWING_CHANGED`), facts and engagement-safety
tests are unchanged and green.

## 4–6. Evidence

See §7 (commands and counts) and the final report. OpenAPI regenerated by
`python -m app.scripts.export_openapi`; frontend `schema.d.ts` regenerated by
`npm run gen:api` (parity only — no UI).

## 7. Verification and candidate

Reproducible runtime `homies-test-py312` (Python 3.12) and a disposable
`postgis/postgis:16-3.4` (`docs/production/CI-AND-RUNTIME.md`).

| Check | Result |
|---|---|
| focused SQLite on `8efdd68` (viewings, viewing DST, measurement facts, engagement safety, listing freshness) | 143 passed |
| focused PostgreSQL on `8efdd68` (viewings PG, concurrency R4, engagement safety PG, freshness tz PG) | 76 passed |
| **full suite SQLite + PostgreSQL** on `8efdd68` (`HOMIES_REQUIRE_RESTORE_DRILL=1`) | **1895 passed, 1 skipped** (Stripe live, not requested), 0 failed |
| after review follow-ups (`69a6878`): ruff · mypy (126 files) · OpenAPI `--check` · SQLite (viewings, DST, OpenAPI contract, facts, engagement safety) · PostgreSQL (viewings PG, concurrency R4, engagement safety PG) | clean · clean · up to date · 112 passed · 30 passed |
| frontend `check:api` | `schema.d.ts` matches `openapi.json` |
| Spectral (`lint:openapi`) | 0 errors, 49 warnings (baseline set) |
| `git diff --check` | clean |

**Hostile read-only review** of `8efdd68`: 0 BLOCKER. Code: no defects.
MATERIAL (governance): contract/evidence/DEVLOG not yet committed → this
commit. NONBLOCKING, adopted (`69a6878`): field descriptions in
`ViewingSlotsOut`; cancel description trimmed to the rule. NONBLOCKING,
recorded only:

* **Clock (04a §20):** viewing time guards use the app clock (pre-existing,
  followed not introduced); a later task should move all viewing guards to
  the database clock together.
* **BP-11 note:** `timezone` is a viewing-settings value; when BP-11 opens the
  derived-slot read to anonymous callers it must state that the zone (like
  `duration_minutes`) is part of the public derived contract, while windows,
  blackouts, capacity and booking mode stay private.
* Disabled vs absent settings are distinguishable by `duration_minutes` /
  `timezone` (already true for duration before BP-2).

Candidate: the branch HEAD reported with the branch CI run (final report).
Builder status: **BUILDER VERIFIED CANDIDATE** — not merged, not deployed.

## 8. Out of scope (untouched)

BP-3, BP-4, BP-5, BP-6, BP-8, BP-9, BP-10, BP-11 (anonymous slots), BP-12,
FE-003 frontend, FE-VIS-001, Admin, deployment; DEBT-1 (passed REQUESTED
expiry); decline after start (unchanged backend behaviour).
