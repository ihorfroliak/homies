# BP-1 — Stable API refusal / conflict codes

| Field | Value |
|---|---|
| Purpose | FE-003 backend prerequisite BP-1 ([FE-003 contract §10.1](FE-003-save-conversation-viewing-DRAFT.md)): every FE-003 refusal carries a stable machine-readable code, so the client never parses English `detail` |
| Authorisation | founder/GPT bounded task, BP-1 only. `FE-003 IMPLEMENTATION AUTHORIZED: NO` |
| Risk | R1 (API contract stabilisation; no migration, no semantic change except the required `Retry-After`) |
| Baseline | `main` = `dc74da3fbc57eff89437dbe5d7a65d4a0a47ceb0` (HM-1 merge), CI `37242309945` success 6/6 |
| Branch | `claude/BP-1-stable-api-codes` |
| Candidate | see §7 |

## 1. Convention (unchanged)

The existing project convention, already used by `RECONTACT_BLOCKED`,
`CONVERSATION_CLOSED`, `LISTING_HELD`, `HELD_BY_MODERATION`,
`MEDIA_RESTRICTED`: the stable code is the prefix of the string `detail`,
`"CODE: human text"`, matched by the client's
`^([A-Z][A-Z0-9_]{2,63}):\s` (`frontend/web/src/api/errors.ts`). No new
error envelope, exception framework or migration. Codes are module constants
next to the existing ones. Human text after the prefix is diagnostics only.

## 2. Code matrix

| Code | Endpoint | HTTP (unchanged) | Before | Now | Test evidence |
|---|---|---|---|---|---|
| `OWN_LISTING` | `POST /v1/classifieds/{id}/conversations`; `POST /v1/classifieds/{id}/viewings` | 409 | "This is your own listing" | `OWN_LISTING: …` | `test_conversations.py::test_you_cannot_message_your_own_listing`; `test_viewings.py::test_you_cannot_book_a_viewing_of_your_own_flat` |
| `VIEWINGS_NOT_OFFERED` | `POST …/viewings` | 409 | no settings: "This listing takes no viewings yet"; **disabled settings: "That time is not an offered slot"** | `VIEWINGS_NOT_OFFERED: …` for no **or disabled** settings (§3) | `test_viewings.py::test_a_listing_without_viewings_says_so` (no row created) |
| `SLOT_NOT_OFFERED` | `POST …/viewings` | 409 | "That time is not an offered slot" | `SLOT_NOT_OFFERED: …` (taken, too soon, blacked out, DST gap, never offered) | `test_viewings.py::test_only_an_offered_slot_can_be_requested` |
| `SLOT_FULL` | `POST /v1/viewings/{id}/confirm` | 409 | "That slot is already full" | `SLOT_FULL: …` | `test_viewings.py::test_the_last_place_cannot_be_confirmed_twice` (second stays REQUESTED); PG `test_viewings_pg.py` race |
| `VIEWING_ALREADY_BOOKED` | `POST …/viewings` | 409 | "You already have a viewing of this flat booked" | `VIEWING_ALREADY_BOOKED: …` | `test_viewings.py::test_one_booked_viewing_per_tenant_per_flat` |
| `VIEWING_STATE_CONFLICT` | confirm, decline, cancel, outcome | 409 | "The viewing is {STATUS}" (3 sites) | `VIEWING_STATE_CONFLICT: the viewing is {STATUS}` | `test_viewings.py::test_an_action_on_a_finished_viewing_is_a_state_conflict` (state unchanged) |
| `VIEWING_CHANGED` | confirm, decline, cancel, outcome (`_transition` CAS) | 409 | "The viewing was changed meanwhile" | `VIEWING_CHANGED: …` | `test_viewings.py::test_a_transition_on_a_changed_viewing_is_viewing_changed` (§5) |
| `VIEWING_TIME_PASSED` | confirm | 409 | "That viewing time has passed" | `VIEWING_TIME_PASSED: …` | `test_viewings.py::test_a_request_whose_time_has_passed_cannot_be_confirmed` (stays REQUESTED) |
| `VIEWING_NOT_STARTED` | outcome | 409 | "The viewing has not happened yet" | `VIEWING_NOT_STARTED: …` | `test_viewings.py::test_an_outcome_waits_for_the_viewing_to_happen` |
| `MESSAGES_ONLY` | `POST /v1/classifieds/{id}/contact` | 409 | "This owner accepts messages only, not phone calls" | `MESSAGES_ONLY: …` | `test_classifieds_board.py::test_message_only_owners_never_disclose_a_number` |
| `PHONE_NOT_VERIFIED` | `POST …/contact` | 403 | "Verify your phone number before contacting owners" | `PHONE_NOT_VERIFIED: …` | `test_classifieds_board.py::test_a_user_without_a_verified_phone_is_refused` |
| `REVEAL_QUOTA` | `POST …/contact` | 429 + `Retry-After` | "Daily limit of owner contacts reached…" | `REVEAL_QUOTA: …`, `Retry-After` unchanged | `test_reveal_quota.py::test_the_next_one_is_refused`, `::test_the_refusal_says_when_to_come_back` |
| `CONVERSATION_QUOTA` | `POST …/conversations` | 429 | "Daily limit of new conversations reached…", **no `Retry-After`** | `CONVERSATION_QUOTA: …` + **`Retry-After`** (§4) | `test_conversations.py::test_new_conversations_are_capped_but_open_ones_continue`, `::test_the_conversation_quota_says_when_the_oldest_start_ages_out` |
| `SAVED_LIMIT` | `POST /v1/me/saved-listings/{id}` | 409 | "At most N listings can be saved" | `SAVED_LIMIT: …` (cap 500 unchanged; re-save still 200) | `test_saved_listings.py::test_the_per_user_cap_holds` |
| `SAVED_SEARCH_DUPLICATE` | `POST /v1/me/saved-searches` (pre-check + IntegrityError retry); `PATCH …/{id}` (pre-check + IntegrityError) | 409 | "This search is already saved" | `SAVED_SEARCH_DUPLICATE: …`; `Location` kept where it was sent (POST paths, PATCH pre-check); PATCH IntegrityError path still sends none | `test_saved_searches.py::test_parameter_order_does_not_change_the_fingerprint` (Location), `::test_a_new_query_gets_a_new_baseline` (PATCH, Location); PG `test_task014r_repairs_pg.py::test_a_patch_blocked_on_the_unique_fingerprint_answers_409` |
| `SAVED_SEARCH_LIMIT` | `POST /v1/me/saved-searches` | 409 | "At most N searches can be saved" | `SAVED_SEARCH_LIMIT: …` (cap 50 unchanged; checked before duplicate, as before) | `test_saved_searches.py::test_the_per_user_cap_holds` (no row added) |

**Preserved codes** (untouched text and semantics): `RECONTACT_BLOCKED`
(conversation start, viewing request), `CONVERSATION_CLOSED` (send),
`LISTING_HELD` (confirm) — asserted by the existing
`test_engagement_safety.py` / `test_engagement_safety_pg.py` suites, run
green on the candidate.

## 3. One code-mapping decision

A request against **disabled** viewing settings (`enabled=False`) was refused
by the slot check ("not an offered slot") because `slots()` offers nothing
for disabled settings. It now answers `VIEWINGS_NOT_OFFERED`, the same as no
settings: the listing takes no viewings at all (BP-1 §6.2 "settings/offer
capability absent"). Same status (409), same outcome (no viewing), no change to
slot derivation or availability. It is checked at the same point the
no-settings refusal already was (after the settings lock, before the slot
check).

## 4. `Retry-After`

* `CONVERSATION_QUOTA`: derived from the existing rolling 24 h window on the
  same app clock and rows as the count — the start that must age out is the
  (count − quota + 1)-th oldest in the window; `Retry-After = ceil(that +
  24 h − now)`, at least 1 s. Naive SQLite instants are read as UTC.
* `REVEAL_QUOTA`: unchanged (`_quota_used`, oldest reveal in the window).
* Both 24 h quotas can send up to 86 400 s; the frontend `retryAfter()` caps
  at 3 600 s (`frontend/web/src/api/errors.ts`) — nonblocking FE note for
  FE-003d/FE-003c (the client must not auto-retry a daily quota anyway).

## 5. Test notes

`VIEWING_CHANGED` is the defensive version compare-and-set of `_transition`.
Every caller locks the row first (`_locked`, FOR UPDATE + re-read), so on
PostgreSQL a concurrent change waits and is then seen as
`VIEWING_STATE_CONFLICT`; the CAS refusal is reachable only without that lock
(this was already so before BP-1, and OpenAPI calls the code defensive). The
test drives `_transition` with a stale row after a committed version bump —
the exact refusal path — and checks the row is unchanged.

`CONVERSATION_QUOTA` `Retry-After` is tested for the oldest start (index 0)
and for a quota lowered below the count (the second oldest must age out), so
a regression to "always the oldest" fails.

## 6. OpenAPI and contract

`responses=` on the touched routes document each stable code (conversation
start/send, viewing request/confirm/decline/cancel/outcome, contact reveal,
saved listing/search), regenerated with `python -m app.scripts.export_openapi`
(drift check passes); `frontend/web/src/api/schema.d.ts` regenerated by
`npm run gen:api` (`check:api` passes). Spectral: 0 errors, 49 warnings (the
same warning set as the baseline).

## 7. Verification and candidate

Local runs in the reproducible runtime (`homies-test-py312`, Python 3.12;
disposable `postgis/postgis:16-3.4`), see `docs/production/CI-AND-RUNTIME.md`:

| Check | Result |
|---|---|
| focused SQLite (viewings, conversations, reveal quota, classifieds board, saved listings/searches, engagement safety) on `144a013` | 184 passed |
| focused PostgreSQL (engagement safety, viewings, reveal quota, TASK-014R repairs, concurrency R4) on `144a013` | 37 passed |
| **full suite SQLite + PostgreSQL** (`HOMIES_REQUIRE_RESTORE_DRILL=1`) on `144a013` | **1874 passed, 1 skipped** (Stripe live, not requested), 0 failed |
| after review follow-ups (`bb6f325`): ruff · mypy (126 files) · OpenAPI `--check` · targeted SQLite (conversations, viewings, OpenAPI contract, classifieds board, reveal quota) | clean · clean · up to date · 119 passed |
| frontend `check:api` | `schema.d.ts` matches `openapi.json` |
| Spectral (`ops/contracts`, `lint:openapi`) | 0 errors, 49 warnings (baseline set) |
| `git diff --check` | clean |

Hostile read-only review of `144a013`: 0 BLOCKER, 0 MATERIAL; nonblocking
findings adopted where in scope (Retry-After index test, VIEWING_CHANGED
described as defensive, stale comment) — `bb6f325`; declined as scope
expansion: a `conversation_daily_quota ≥ 1` config validator (separate debt).

Candidate: the branch HEAD reported with the branch CI run (final report).
Builder status: **BUILDER VERIFIED CANDIDATE** — not merged, not deployed.

## 8. Out of scope (untouched)

BP-2…BP-12 (incl. BP-7 cancel-after-start `VIEWING_STARTED`, BP-8 reveal
G-14 block, BP-10 idempotency, BP-12 message-report verification), FE-003
frontend, FE-VIS-001, Admin, deployment. Nonblocking notes: refusals outside
BP-1 stay prose-only (saved-search PATCH version 409, `/matches` invalid-query
409, report `OwnListing`/`QuotaExceeded`, middleware 429, 503); the PATCH
IntegrityError duplicate path sends no `Location` (as before).
