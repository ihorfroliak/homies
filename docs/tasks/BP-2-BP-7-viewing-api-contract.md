# BP-2 + BP-7 — Viewing API contract

| Field | Value |
|---|---|
| Purpose | FE-003 backend prerequisites ([FE-003 contract §10.1](FE-003-save-conversation-viewing-DRAFT.md)): **BP-2** typed `viewing-slots` response with the authoritative `timezone`; **BP-7** the backend refuses a viewing cancellation at or after its start |
| Authorisation | founder/GPT bounded task, BP-2 + BP-7 only. `FE-003 IMPLEMENTATION AUTHORIZED: NO` |
| Risk | R1 (API contract; no migration) |
| Baseline | `main` = `6be148b6fefea22e42764e2f6178d1a03433043c` (BP-1 merge), CI `37258817313` success 6/6 |
| Branch | `claude/BP-2-BP-7-viewing-api-contract` |
| Candidate | see §7 |
| Disposition (TASK-016, 2026-10-06) | merged into `main` at `6adca78c9ae6342438f08b8b7c8cfd1b88be714a` (parents `6be148b6` + candidate `caf383833bf3eacc846a6345bc603db041d09bda`); founder/GPT reviewed; main CI `37370779484` (attempt 4) success. The status text below is kept as written at handoff |

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
4. `decision_now = freshness.db_now(db)`; `starts_at <= decision_now` →
   `VIEWING_STARTED`;
5. `_transition` (status + version compare-and-set, `VIEWING_CHANGED`) with
   `cancelled_at = decision_now`, audit `viewing.cancelled`, fact
   `ViewingCancelled` with `cancelled_at = canonical_instant(decision_now)`.

**Clock (04a §20, founder/GPT correction):** BP-7 decides on the **database
clock** — `freshness.db_now(db)`, the authoritative decision instant
(`statement_timestamp()` on PostgreSQL; the process clock in UTC on the
SQLite test engine), taken once under the row lock and used for the check,
the row's `cancelled_at` and the fact's `cancelled_at` (as close-engagement
already does in `trust/effects.py`). The pre-existing app-clock usages of the
viewing module — slot derivation, the default slot start date, confirm
`VIEWING_TIME_PASSED`, outcome `VIEWING_NOT_STARTED`, the request's
already-booked check — were **not** modified and remain separate
clock-convergence debt against 04a §20.

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
| `test_either_side_cancels_only_before_the_start` | 2 actors × 2 states × before/exactly/after (12 cases), the database clock controlled via `freshness.db_now`; refusal leaves state, audit and facts untouched; success writes one audit and one fact, with the row's and the fact's `cancelled_at` equal to the decision instant |
| `test_the_cancel_decision_is_the_database_clock` | a far-off app clock (`viewings._now`) neither blocks a timely cancel nor allows a late one |
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

* **Clock (04a §20):** raised as nonblocking by the hostile review; the
  founder/GPT review classified it **material for BP-7** (a new business
  decision must follow §20) → corrected, see the DB-clock correction below.
  The other viewing app-clock usages stay separate debt.

**DB-clock correction (after founder/GPT review of `5efc8fd`):** only the
BP-7 cancellation decision moved to `freshness.db_now(db)` (one decision
instant for check, `cancelled_at` and fact). Re-run on the correction:
ruff, mypy (126 files), OpenAPI regenerated (the cancel operation description
is its docstring) and `--check` up to date, frontend `check:api` OK, Spectral
0 errors / 49 warnings, focused SQLite (viewings, DST, facts, engagement
safety, listing freshness, OpenAPI contract) **149 passed**, PostgreSQL
(viewings PG, concurrency R4, engagement safety PG, freshness tz PG)
**76 passed**. The full local suite was **not** re-run after the correction
(last full run: `8efdd68`, 1895 passed); the branch CI backend job runs the
full suite on the corrected HEAD. BP-2 code is unchanged by the correction.
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
