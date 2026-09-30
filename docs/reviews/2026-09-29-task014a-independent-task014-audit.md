# TASK-014A — Independent Audit: Saved Listings, Saved Search & Alerts

| Field | Value |
|---|---|
| Audited SHA | `196c88796cf34a6b19860259cc6ff81c94dbe8d2` (branch `claude/TASK-014-saved-search-alerts`, also on `origin`) |
| Accepted parent | `3f324b6ddff6c7557894eb5f65736729d956f7eb` — `git merge-base --is-ancestor` exit 0 |
| Auditor | Claude, independent read-only session (not the TASK-014 builder); 2026-09-29 |
| Worktree | fresh detached `homies-audit-evidence/TASK-014A/wt`, `git status --short` empty, mounted **read-only** into every test container |
| Probes | auditor-owned, in a disposable `git archive` copy (`copy/backend/tests/test_t14a_*.py`); mutation on a second copy (`copy-mut/`), restored and diff-verified pristine |
| Candidate edits / commits / push / deploy | none |
| Production | **NOT READY** |
| Deployment | **NOT DEPLOYED** |

## 1. Evidence environment

| Item | Value |
|---|---|
| SOURCE_SHA | `196c88796cf34a6b19860259cc6ff81c94dbe8d2` |
| AUDIT_HARNESS_SHA | none (not committed); probes = files under `copy/backend/tests/test_t14a_*.py`, `probes/t14a_mutate.py` |
| OS | Linux containers on Docker Desktop 29.2.1 (WSL2 VM) on Windows 11 |
| Python | 3.12.14 (image `pr001a-test-py312`) |
| Dependencies | PR-001R pinned constraints set baked into the image; `pip check` clean; satisfies candidate `pyproject` (ruff 0.15.22, mypy 2.3.0, coverage 7.13.0, pip-audit 2.9.0 pinned identical); freeze in `logs/pip-freeze.txt` |
| PostgreSQL / PostGIS | 16.4 / 3.4.3, image `postgis/postgis:16-3.4@sha256:44126d87…` — the **same digest as CI** |
| DBs | three dedicated containers (full suite / probes / mutation), network `t14a-net`; nothing shared with other sessions' databases |
| CI | **NOT RUN** — GitHub API: 0 workflow runs for this SHA, no PR (CI triggers only on PR / push to main) |

**Clock observations.** A fresh Docker restart gave 0 backward steps in a 90 s probe. However, a 3 000 s watcher (0.1 s sampling) running **during the full PostgreSQL suite** recorded **7 backward wall-clock steps**: 0.023, 0.319, 0.478, 0.052, 0.644, 0.303, 0.056 s (at t = 199, 739, 1009, 1039, 1429, 2781, 2840 s). This is the F13RA-N02 condition, milder than the builder's report. The DB and host clocks agreed to the millisecond when spot-checked. No temporal assertion was weakened. The full suite still passed. Even so, **the stable-clock requirement was not met**.

→ **EVIDENCE = NOT_VERIFIED** (strict rule): all gates are green on Linux/Py3.12/PG16/PostGIS, but not on a proven-stable clock and not in CI.

## 2. Quality gates actually run (Python 3.12)

| Gate | Command | Result |
|---|---|---|
| ruff | `ruff check app tests alembic scripts` | All checks passed (exit 0) |
| mypy | `python -m mypy` | Success: no issues in 103 files (exit 0) |
| OpenAPI drift | `tests/test_tst01_openapi_contract.py` (inside both full suites) | passed |
| Full SQLite | `pytest -q -rfEs` | **986 passed, 360 skipped, 0 failed** (605 s) |
| Full PostgreSQL/PostGIS | `pytest -q -rfEs` with `TEST_DATABASE_URL` | **1345 passed, 1 skipped, 0 failed** (1784 s) |
| Targeted TASK-014 (candidate) | 5 files, mutation baseline | 99 passed |
| Auditor probes | `test_t14a_*.py` | 12 + 14 + 43 + 2 + 4 + 5 + 1 + 1 + 1 passed (after fixing probe bugs of my own) |
| Scale | `TASK014_SCALE=full tests/test_saved_search_scale_pg.py` | passed |

**Skips.**
- SQLite: 360 skips, all environment-gated:
  - `TEST_DATABASE_URL` not set: 109 PG, 73 PG-migration and 16 PG-privilege tests.
  - 9 pg_dump/pg_restore tests.
  - 2 "needs real Postgres" and 1 "needs PostgreSQL".
  - 1 Stripe Test Mode test (not requested).
  - The rest are the same classes across parametrizations.
- PostgreSQL: 1 skip — `tests/stripe_live/test_stripe_live.py:26`, the Stripe live suite, which was not requested.

## 3. Gate results

### PUBLIC_GENERATION — ACCEPTED

- **Only two write paths.** Every write of `status='active'` / `last_confirmed_available_at` in `app/` was enumerated. Only `publish_classified` (router.py:530) and `confirm_classified` (router.py:684) make a listing public, and both go through `publicity.make_public`.
- **Other writers only take listings down.** Revoke, space archive and sweep only pause or stale. Create is draft-only; the schema has no `status` field. `listings/router.py` is the legacy booking table.
- **The public rule is status + confirmation only** (`freshness.public_clause`). No other public path exists.

Probe `test_generation_paths` checked each transition through a fresh connection. The expected tuple is (status, gen, public_since, #events, #work items):

| Transition | Result |
|---|---|
| draft → publish | (active, 1, ✓, 1, 1) |
| confirm / republish while public | unchanged |
| RECONFIRM_DUE (15 d) confirm | unchanged |
| paused → publish | gen 2 |
| stale (real sweep) → confirm | gen 3 |
| stale → publish | gen 4 |
| silently expired while still `active` → confirm | gen 5 |
| exactly 21 d → publish | gen 6 |
| 21 d − 1 min → confirm | unchanged |

Dedup keys ran `…:1 … :6`, consecutive. Archived listings, archived spaces and revoked authority answer 409 or 404 and open nothing.

### ATOMICITY — ACCEPTED

Five injected faults were tried, each on both publish-from-draft and confirm-after-silent-expiry:
1. `_open_episode` raising after the generation/status/public_since UPDATE.
2. `events.emit` raising after the event flush.
3. A raise after the work-item flush (`location.refresh` / `freshness.emit`).
4. A raise at `audit` just before commit.
5. A PL/pgSQL trigger refusing the work-item INSERT.

In all 10 cases a fresh engine connection saw the prior state unchanged (status, generation, public_since, last_confirmed, events, work items). The retry opened exactly one episode, with its work item joined to the right event. There is no internal commit: builder mutant A07 (early commit) is killed.

### CONCURRENCY — ACCEPTED

Each case was checked with database lock evidence (`pg_blocking_pids`, `pg_locks` rows), not with sleeps.

| Race | Linearization / mechanism | Final state |
|---|---|---|
| publish vs publish (seam only) | offer row `FOR UPDATE`; B waits on A's `transactionid ShareLock` | gen 1, B `became_public=False` |
| confirm vs publish / confirm vs confirm after silent expiry | same row lock; B re-reads a fresh confirmation | exactly +1 |
| sweep (holding) vs confirm | confirm waits; sees `stale` → opens | +1 |
| confirm (holding) vs sweep | sweep `SKIP LOCKED` does not wait and does not stale | +1, active |
| revoke (holding property lock) vs publish | publish waits on property lock → 404 | paused, no new gen |
| publish (first) vs revoke | revoke waits → pauses after | paused, gen +1 (opened then closed) |
| space archive vs publish | property lock → 409 | no new gen |
| N in-flight vs N+1 created | N ack touches only N; N+1 pending; N deliveries `superseded` at send | 1 email |
| two claimers | `FOR UPDATE SKIP LOCKED` → disjoint | — |
| two senders, one delivery | delivery row lock; loser sees `delivered` | 1 email |
| reconcile vs live sender | reconcile UPDATE waits on row; re-evaluates, no reset | 1 email |
| two workers, two searches of one user | unique index wait; loser inserts 0, no error | 2 matches, 1 delivery/channel |

### SAVED_LISTING — ACCEPTED

- **Ownership (IDOR):**
  - User A's list shows only A's saves.
  - A deleting B's target returns 204, but B's save survives.
  - A calling GET, PATCH, DELETE or /matches on B's search gets 404.
  - A marking a foreign inbox item as read gets 404.
- **Tombstones.** Six states were tested: pause, silent expiry without a sweep, stale, archived, space archive and authority revoke. Each returns `{saved_id, listing_id, saved_at, availability_status: NO_LONGER_AVAILABLE, listing: null}`.
- **Sentinels.** No sentinel appeared in any tombstone: street, building, unit, postcode, exact coordinates, owner phone and e-mail, title and price.

### SAVED_SEARCH — ACCEPTED

- **One canonical form.** A stored query's canonical string equals the `query` echo of `GET /v1/classifieds` (and `/map`) for 8 shapes: geography, repeated values, bbox, radius, attributes, availability/term, and empty. Both go through the single `build_query` path.
- **Duplicates.** Parameter order, repeated values and page state (`limit`/`offset`) all produce the same fingerprint → 409.
- **Refusals.** Unknown parameters and repeated scalars get 422.
- **Other checks:** zero-result searches save with 201 and `match_count 0`, and two users may save the same query.
- **Races.** Eight parallel identical creates gave exactly one 201 and seven 409s. Concurrent PATCH has a defect: see F-4.

### QUERY_FIDELITY — NEEDS_FIX (P3, F-2)

These cases correctly become INVALID in the API. The worker makes no match and `/matches` returns 409:
- retired locality
- deleted geo area
- catalogue attribute made non-filterable
- schema version 2
- unparseable canonical query
- unknown criterion

At send time the same cases give `query_invalid`. None of them broadened the search.

**Not met:**
- A mismatched fingerprint stays **VALID**.
- A stored canonical query corrupted into a *valid subset* (a filter dropped, fingerprint left unchanged) stays VALID. It then **matched and would alert** a listing the original query excludes.
- A valid but non-canonical spelling is accepted.

### ANCHOR_COMPLETENESS — ACCEPTED

The analysis showed the filter and key rules are symmetric:
- The filter uses `Address.locality_id`, `geo_area_id`, `country_code` and the admin-area descendants of both the address and its locality's area.
- The keys use the same columns plus the full `area_path` ancestors.
- The recursive CTE and the parent walk both use `parent_id` with no status filter.

**Randomized oracle test** (seed 20260929):
- 35 listings: locality, locality + search area, admin area only at every level, unstructured city, with and without coordinates. Five further shapes were refused by the API (locality + admin area together).
- 495 random valid searches, anchors `* 145 / L 188 / A 245 / G 35 / C 43`. They cover no geography, country only, locality with OR, admin areas at every level, search areas, city, bbox and radius, AND with a second geo dimension, and non-geo filters.

**Results:**
- The oracle is `evaluate_for_listing` over every search. It found 2 601 true pairs.
- The candidates covered 10 565 pairs. **False negatives: 0.** False positives: 7 964, which is acceptable.
- Production matches equal the oracle set exactly.
- A search on a retired area matched nothing.
- `evaluate_for_listing` equals the live list endpoint for 60 sampled searches.
- My mutants X01/X02 (ancestors dropped, locality's area dropped) are killed by the candidate's tests.

### BASELINE_NO_FLOOD — ACCEPTED

- **No flood.** Three already-public matches are visible (`match_count 3`) but produce 0 deliveries.
- **No re-alert.** Re-confirming or re-publishing them produces no work.
- **New listings alert.** A new listing produces 1 match and 1 e-mail.
- **Query change.** A PATCH to the query moves the baseline, so nothing already matching alerts.
- **In-flight race.** The publication transaction starts (DB instant T1), the search is saved (baseline T2 > T1), then the publication commits. Result: no alert, but the listing is visible in `/matches`. This is the documented DB-instant rule: a false negative, never a flood (NOTE N-6).

### MATCH_DEDUP — ACCEPTED

The primary key `(saved_search_id, listing_id, public_generation)` decides. The loser waits on the unique index, inserts 0 rows with `ON CONFLICT DO NOTHING`, and gets no deadlock and no 500. The key is load-bearing: builder test B shows a raw duplicate INSERT raises `saved_search_matches_pkey`.

### USER_DELIVERY_DEDUP — ACCEPTED

`uq_alert_deliveries_user_episode_channel` gives two matches but one delivery per channel. The constraint is load-bearing: the removal mutant B-A09 is killed.

### GENERATION_ISOLATION — ACCEPTED

`acknowledge` filters on the exact generation, and the removal mutant is killed. In the N/N+1 probe the result was N `done` and N+1 `pending`. The N+1 work was then processed, N's deliveries were `superseded`, and N+1 delivered.

### SEND_TIME_REVALIDATION — ACCEPTED

Fifteen changes were each applied after the delivery was queued *and claimed*. The outcomes:

| Change | Outcome |
|---|---|
| search paused | `search_inactive` |
| search deleted | `search_deleted` |
| notifications off | `search_inactive` |
| PRODUCT EMAIL off | EMAIL `preference_disabled`; IN_APP still delivered |
| e-mail unverified | EMAIL `email_not_verified`; IN_APP delivered |
| listing paused | `listing_not_public` |
| silent expiry | `listing_not_public` |
| stale | `listing_not_public` |
| space archived | `listing_not_public` |
| authority revoked | `listing_not_public` |
| new generation | `superseded` |
| price | `no_longer_matches` |
| attributes (rooms) | `no_longer_matches` |
| availability date | `no_longer_matches` |
| query INVALID | `query_invalid` |

Not supported: "user unavailable" beyond a user missing entirely (there is no account-status model; documented in 04a §22). A changed or removed address is re-resolved at send time.

### UNSUBSCRIBE — ACCEPTED (see F-1 for the crash-window defect filed under transport)

**Token properties:**
- 32 random bytes (43-character urlsafe string).
- Only `sha256(token)` is stored, in one row. The raw token appears in no row of any table (`row::text` scan) and in no API response or log.
- The token encodes no identifier.

**Behaviour:**
- Invalid, expired and replayed tokens all get the same generic `{"status":"ok"}` with no effect (expired: none; replay: idempotent).
- A malformed token gets 422, which echoes only the caller's own input.
- Per-search scope turns off only that search. Global scope turns off PRODUCT EMAIL only; IN_APP continues.
- A transactional (`events`) e-mail to the same user is still sent.
- Rate limit: 10 then 429.
- The race "queued → unsubscribe commits → send decision" suppresses the send.

NOTE N-3: a token stays replayable for 180 days — after the user re-enables alerts, replaying an old link disables them again.

### DELIVERY_TRANSPORT — ACCEPTED_WITH_DEBT (F-1, F-5)

DB exactly-once logical delivery holds: a UNIQUE key plus a row claim. **External SMTP is at-least-once**, which D-09 already sets as the canon. The crash probe ran this sequence:
1. The mailbox accepts the message.
2. The worker dies before commit.
3. The delivery stays `processing`.
4. After STALE_CLAIM, reconcile moves it back to `pending`.
5. The worker resends: a second e-mail with the same `X-Idempotency-Key`. No MTA dedupes on that header.

Beyond D-09, see **F-1**: the first e-mail's unsubscribe links are dead. The alert path stores no provider text; `outcome` is a fixed machine string. The legacy `events` path stores `str(exc)` in `notifications.last_error`. For `SMTPRecipientsRefused` that string contains the recipient address and any provider text (F-5).

### PRIVACY — ACCEPTED

Sentinels were planted for:
- street, building, unit and postcode
- exact coordinates
- owner phone and owner e-mail
- renter e-mail
- title and price, where the context forbids them
- raw token

**Surfaces checked (no leaks):**
- e-mail subject and body
- the Saved Search endpoints (single and list)
- `/matches` (public shape; title and price allowed there)
- inbox, saved listings and the unsubscribe response
- `/metrics`
- the TASK-014 tables, `domain_events` and `notifications` (full `row::text`)
- all log records

**Log evidence was not vacuous.** Every logger was re-enabled and the real `StubEmailChannel` was used. The flow emitted `homies.alerts` and `homies.notifications` records, including `email[stub] recipient=present …` and an `alert work item failed` traceback from a forced error, and none contained a sentinel.

**Spatial matching uses the public point only.** A bbox around the exact point matched 0; a 5 m radius around the exact point matched 0; a bbox around the public grid point matched 1.

### MIGRATION — NEEDS_FIX (P3, F-3)

**Passes:**
- There is one head, `f3b5d7e9a1c2` ← `d0f2b4c6e8a1`.
- Empty → head works (every PG session did this).
- **Failed upgrade.** I pre-created a colliding `unsubscribe_tokens`. The whole run rolled back in its single transaction: version stayed `d0f2…`, no `public_generation` column, no `saved_searches`. After cleanup, upgrade / downgrade / upgrade succeeded.
- **Downgrade fidelity.** The downgrade restores the TASK-013 schema exactly: columns, constraints, indexes and triggers equal a clean `d0f2` scratch database.
- **Model/migration drift.** `compare_metadata` found no TASK-014 differences; the only diffs are the pre-existing computed `public_geog`.
- **Constraints and FKs** were checked.

**Backfill on populated data:**
- A never-published listing gets generation 0.
- A published listing gets 1, with `public_since = published_at` — an approximation, since earlier episodes are unknowable.
- No events and no work items are written.
- A new search plus the worker produce 0 deliveries.

**Fails:**
- A populated downgrade followed by re-upgrade leaves the old `ListingBecamePublic:<id>:<g>` events in place.
- A listing that had **≥ 2 episodes** comes back with generation 1. Its next publish computes generation 2, collides with the surviving `:2` dedup key, and `make_public` raises `RuntimeError("public generation opened twice")`. The result is HTTP 500 on **every** later publish. Confirmed twice.
- Reconcile also resurrects one work item from the surviving events. No flood followed, because the downgrade dropped all searches.

Downgrade is not a production rollback guarantee. `MIGRATION-ROLLOUT.md` §5 says downgrades are dev-only, and it has no row for this migration.

### WORKER_RECOVERY — ACCEPTED

- **Crash after claim.** The item stays `processing`. Reconcile before STALE_CLAIM does not touch it; after STALE_CLAIM it is reclaimed and processed. Result: 1 match, 1 e-mail, attempts = 2.
- **Idempotent reconcile.** Three reconciles in parallel reclaimed it exactly once.
- **Lost work items.** A lost work item is restored only when `public_since` falls within 7 days (an 8-day-old one is not). A second reconcile restores 0.
- **Bounded delivery retries.** Transient failures back off and go `dead` at `notification_max_attempts = 5`.
- **Bounded recovery.** Reconcile is bounded: limit 200, a 7-day window, and it never crosses searches × listings.
- **Poison work items.** One is retried forever: `attempts` has no cap and `last_error` is never written (NOTE N-2).
- **Lock holding.** Long matching holds no work-row lock and so does not serialise workers. It does hold FK KEY SHARE locks (NOTE N-1).

### PERFORMANCE — ACCEPTED_WITH_DEBT

The builder's scale harness was reproduced on my database with 10 000 searches × 1 000 listings. Candidate and match counts were identical, and runtimes were local only:

| New listing in | Candidates | Matches | SQL statements | Evaluation statements | Local runtime |
|---|---|---|---|---|---|
| Kraków | 7 096 | 4 304 | 49 | 15 | 16.3 s |
| Warszawa | 4 903 | 2 906 | 40 | 12 | 8.3 s |
| Balice | 3 016 | 1 832 | 35 | 10 | 9.9 s |

- **Candidate query:** bitmap heap scan on `ix_saved_search_anchors_key`, about 15 ms. Row estimates are stale (1 vs 1 999) but the plan is sound.
- **Own worst case:** 10 000 distinct non-geographic searches (all `*`) → 10 000 candidates, 83 statements, 9.6 s. Cost scales with candidates; there is no cartesian scan.
- **Debt:**
  - Per-query SQL construction cost.
  - A `*`-anchored search is a candidate for every listing.
  - A 20-item batch is processed sequentially, so later items in a batch may pass STALE_CLAIM (5 min) at heavy scale. With multiple replicas that means duplicate but idempotent processing.
  - Lock coupling, see NOTE N-1.
  - The list endpoint's per-search `query_state` is an N+1, bounded at 50 per user.

### PRODUCT_REGRESSION — ACCEPTED

The full SQLite and PostgreSQL/PostGIS suites (TASK-012/013 included) pass on Python 3.12. The TASK-012/013 test files are unchanged except for two small, compatible edits (`test_listing_freshness_pg.py`, `test_phase1_runtime.py`, for the inbox route and the `public_generation` column). No accepted behaviour was weakened.

## 4. Findings

### F-1 — P3 — The SMTP crash window leaves dead unsubscribe links, and the endpoint still answers "ok"

- **Location:** `backend/app/modules/alerts/delivery.py` `_send_email` (tokens issued at ~L158–159, send at ~L167); `worker.process_deliveries`.
- **Rule involved:** 04a §22 / D-81 — one-click unsubscribe must work, and the response is generic by design.
- **Evidence (`test_smtp_accept_then_crash_before_commit`):**
  - Both unsubscribe tokens are INSERTed in the same transaction that sends. The mailbox accepted the message, then the transaction died before commit.
  - The token rows for the delivered e-mail: `[0, 0]`.
  - Clicking "stop alerts for this search" returned `{"status":"ok"}`, but `notifications_enabled` stayed **true**.
  - Reconcile then resent: 2 e-mails with the same idempotency key.
- **Expected:** every link in a sent e-mail is valid.
- **Suggested repair:** issue and commit the tokens (or derive them deterministically per delivery) *before* the SMTP call. Document the duplicate-send window under D-09.
- **CANONICAL DECISION REQUIRED:** no.

### F-2 — P3 — The stored-query integrity is never verified; corruption into a valid subset silently broadens

- **Location:** `backend/app/modules/saved/service.py` `load_query` (L~58–64).
- **Rule involved:** TASK-014A §7 — never broaden; mismatched fingerprint or corrupt query → INVALID.
- **Evidence:**
  - `query_fingerprint = '0'*64` → VALID.
  - `canonical_query` rewritten to `locality_id=<Balice>` (the `max_rent` filter removed) → VALID. It matched a 250 000 listing that the original `max_rent=100000` excludes.
  - A non-canonical spelling → VALID.
- **Trigger:** only an out-of-band write, such as manual SQL or a future migration bug. No application path writes an inconsistent pair.
- **Suggested repair:** in `load_query`, require `fingerprint(version, canonical) == stored` and `q.canonical() == stored canonical`; otherwise INVALID.
- **CANONICAL DECISION REQUIRED:** no.

### F-3 — P3 — Downgrade followed by re-upgrade makes affected listings permanently unpublishable (500)

- **Location:** migration `f3b5d7e9a1c2` `downgrade()` / backfill; `publicity._open_episode` (a raise on dedup collision).
- **Evidence:**
  - `test_populated_downgrade_upgrade_backfill_no_flood`.
  - Leftover events: `ListingBecamePublic:<id>:1`, `…:2`.
  - Two publishes after the round trip both raised `RuntimeError: public generation opened twice`; the state stayed `paused`, generation 1.
  - Reconcile restored 1 work item from the leftover events.
- **Expected:** downgrade is the inverse of upgrade on disposable data.
- **Suggested repair:** downgrade deletes `ListingBecamePublic` events, or the upgrade backfill sets generation to the maximum surviving event generation. Add the migration to `MIGRATION-ROLLOUT.md`.
- **Severity:** P3 because downgrades are dev-only by policy.
- **CANONICAL DECISION REQUIRED:** no.

### F-4 — P3 — A concurrent PATCH of two searches to the same query returns 500

- **Location:** `backend/app/modules/saved/router.py` `update_saved_search`: `_duplicate` is a check-then-act with no `IntegrityError` handling.
- **Evidence:** in 4 of 5 barrier-synchronised trials the result was `['200', 'EXC IntegrityError']`. Uniqueness held, so no duplicate row exists.
- **Suggested repair:** catch `IntegrityError` → 409, as `create_saved_search` already does.
- **CANONICAL DECISION REQUIRED:** no.

### F-5 — P3 — Every SMTP error is classified transient; provider text containing the recipient reaches `notifications.last_error`

- **Location:** `backend/app/modules/events/providers.py` `SmtpEmailChannel.send`.
- **Cause:** `smtplib.SMTPException` subclasses `OSError`, so the first `except` catches everything and the permanent branch is dead code. This predates TASK-014, but TASK-014 now routes alert e-mail through it.
- **Evidence:**
  - `SMTPRecipientsRefused` → `transient=True`.
  - Its `error` field held `"{'victim-t14a@example.com': (550, b'5.1.1 <victim…> user unknown; pw=hunter2')}"`.
- **Effect on alerts:** a permanent refusal is retried 5 times; `outcome` stays a fixed string.
- **Effect on the events worker:** after D-81, `to` is the real address, so `last_error` can hold it plus arbitrary provider text. DB only, not logs. The builder documented this.
- **Suggested repair:** order the `except` clauses correctly, and store a class name or code rather than `str(exc)`.
- **CANONICAL DECISION REQUIRED:** no.

### F-6 — P3 — Test gaps: mutants that survive the candidate's TASK-014 suite

The killer suite was the whole TASK-014 test set: 5 files, 99 tests, green baseline. The production code is correct in every case below:

| Mutant | Effect of the mutation | Covered by my probes? |
|---|---|---|
| **X13** | revalidation ignores `user_id`, so another user's matching search keeps a deleted search's delivery alive | no |
| **X18** | paused searches become candidates | no (still suppressed at send, but matches are recorded) |
| X04 | `FOR UPDATE` removed in `make_public` | the CAS UPDATE fails closed |
| X06 | send-time verified-e-mail check removed | yes; an `assert` fails closed |
| X07 | superseded check removed | yes |
| X08 | expired token accepted | yes |
| X10 | reconcile window unbounded | yes |

**Suggested repair:** add tests for X13 and X18, and port my probes for X06/X07/X08/X10. **CANONICAL DECISION REQUIRED:** no.

### NOTES

- **N-1** — Lock coupling. An open matching transaction holds FK `KEY SHARE` locks on `classified_offers` and `users` rows, so the owner's publish/confirm (`FOR UPDATE`) and `_lock_account` wait for it. `pg_locks` evidence shows up to ~16 s at scale. Consider `FOR NO KEY UPDATE` in `make_public` and short matching transactions.
- **N-2** — A poison work item is retried without a cap, and `listing_public_generations.last_error` is never written.
- **N-3** — Unsubscribe tokens are replayable for 180 days. `used_at` is recorded but not enforced, so replaying after a re-enable disables alerts again.
- **N-4** — Exhausted transient retries end up labelled `permanent_failure`.
- **N-5** — `MIGRATION-ROLLOUT.md` has no row for `f3b5d7e9a1c2`.
- **N-6** — Baseline in-flight race: a publication committed after a search's baseline, with an earlier DB instant, is never alerted. This is documented debt, a false negative, never a flood.
- **N-7** — **F13RA-N01** is inherited and unchanged. The production backstop was verified: the live search returns 422 "longer than 16384" for 3 × 25 four-byte-Unicode IDs, and the saved search is refused. Only the test/comment wording (`tests/test_search_validation.py:74–87`) overstates the guarantee. NOTE only; not repaired.
- **N-8** — The Docker VM clock is unstable (see §1); CI was not run.

## 5. Mutation quality

My own runner is `probes/t14a_mutate.py`, run on a separate copy:
- A green baseline (99 passed) came first.
- A mutant counts as killed only on a FAILED behavioural test with no ERROR.
- Original bytes were restored after each mutant and SHA-verified.
- The whole copy was diff-checked pristine afterwards.

A first attempt left every mutant NOT_APPLIED because of CRLF, and one un-restored file was repaired from the pristine worktree before the rerun.

**Results:**
- **Builder high-value mutants, re-run independently (12/12 killed):** A01 IDOR, A02 tombstone, A05/A06 generation, A07 atomicity, A09 delivery uniqueness, A10/A11 send-time, A12 unsubscribe, A14 INVALID broadening, A15 N/N+1, A16 exact point.
- **Auditor mutants (11/18 killed):** X01, X02, X03 (reconfirm-due counted as not public, which would flood at every 14–21-day confirmation), X05, X09, X11, X12, X14, X15 (inbox privacy), X16, X17 (log privacy).
- **Survivors:** X04, X06, X07, X08, X10, X13, X18 (see F-6).

## 6. Final verdicts

```text
SAVED_LISTING = ACCEPTED
SAVED_SEARCH = ACCEPTED
QUERY_FIDELITY = NEEDS_FIX
PUBLIC_GENERATION = ACCEPTED
ATOMICITY = ACCEPTED
CONCURRENCY = ACCEPTED
ANCHOR_COMPLETENESS = ACCEPTED
BASELINE_NO_FLOOD = ACCEPTED
MATCH_DEDUP = ACCEPTED
USER_DELIVERY_DEDUP = ACCEPTED
GENERATION_ISOLATION = ACCEPTED
SEND_TIME_REVALIDATION = ACCEPTED
UNSUBSCRIBE = ACCEPTED
DELIVERY_TRANSPORT = ACCEPTED_WITH_DEBT
PRIVACY = ACCEPTED
MIGRATION = NEEDS_FIX
WORKER_RECOVERY = ACCEPTED
PERFORMANCE = ACCEPTED_WITH_DEBT
PRODUCT_REGRESSION = ACCEPTED
EVIDENCE = NOT_VERIFIED
```

```text
P0: 0
P1: 0
P2: 0
P3: 6
NOTE: 8
```

```text
TASK_014_REQUIRES_TARGETED_FIXES
```

**Reasoning.** Every critical correctness and privacy gate passed: public generation, atomicity, anchor completeness, send-time revalidation and privacy. Two explicitly required behaviours fail: stored-query integrity (INVALID on a fingerprint mismatch) and the downgrade/re-upgrade round trip. The unsubscribe crash window (F-1) produces a silent false "ok". Stable-clock Python 3.12 certification was not obtained. All fixes are small and local. After repair, a CI or stable-clock Linux Python 3.12 run on the new SHA is needed. **No acceptance marker is emitted.**

```text
PRODUCTION READINESS:
NOT READY

DEPLOYMENT:
NOT DEPLOYED
```

## 7. Evidence index (`homies-audit-evidence/TASK-014A/`)

| Path | Contents |
|---|---|
| `CHECKPOINT.md` | stage-by-stage record, resume commands |
| `logs/ruff-mypy.log` | lint and type-check runs |
| `logs/sqlite-full.log`, `logs/pg-full.log` | full-suite runs |
| `logs/probe-*.log` | generation, concurrency, product, anchor, migration, recovery |
| `logs/scale-full.log` | scale reproduction |
| `logs/mutation.log` | mutation run |
| `logs/clock-*.log`, `probes/clockwatch-pgsuite.json` | clock evidence |
| `copy/backend/tests/test_t14a_*.py` | auditor probes |
| `probes/t14a_mutate.py`, `probes/t14a-mutation-results.json` | mutation runner and results |
| `t.sh`, `tc.sh` | runners |

---

```text
CHATGPT HANDOFF

Project:
Homies

Task:
TASK-014A — Independent Audit

Audited SHA:
196c88796cf34a6b19860259cc6ff81c94dbe8d2

Accepted parent:
3f324b6ddff6c7557894eb5f65736729d956f7eb

Independent auditor session:
YES

SAVED_LISTING = ACCEPTED
SAVED_SEARCH = ACCEPTED
QUERY_FIDELITY = NEEDS_FIX
PUBLIC_GENERATION = ACCEPTED
ATOMICITY = ACCEPTED
CONCURRENCY = ACCEPTED
ANCHOR_COMPLETENESS = ACCEPTED
BASELINE_NO_FLOOD = ACCEPTED
MATCH_DEDUP = ACCEPTED
USER_DELIVERY_DEDUP = ACCEPTED
GENERATION_ISOLATION = ACCEPTED
SEND_TIME_REVALIDATION = ACCEPTED
UNSUBSCRIBE = ACCEPTED
DELIVERY_TRANSPORT = ACCEPTED_WITH_DEBT
PRIVACY = ACCEPTED
MIGRATION = NEEDS_FIX
WORKER_RECOVERY = ACCEPTED
PERFORMANCE = ACCEPTED_WITH_DEBT
PRODUCT_REGRESSION = ACCEPTED
EVIDENCE = NOT_VERIFIED

P0: 0
P1: 0
P2: 0
P3: 6  (F-1 SMTP crash → dead unsubscribe links + false "ok"; F-2 fingerprint/canonical not verified → valid-subset corruption broadens;
        F-3 downgrade→re-upgrade → publish 500 for listings with ≥2 episodes; F-4 concurrent PATCH duplicate → 500;
        F-5 all SMTP errors transient + recipient/provider text in notifications.last_error; F-6 surviving mutants X13, X18 (+X04/X06/X07/X08/X10))
NOTE: 8

Python:
3.12.14 (Linux container, Docker Desktop VM); pinned PR-001R constraints set, pip check clean

PostgreSQL/PostGIS:
16.4 / 3.4.3 — postgis/postgis:16-3.4@sha256:44126d87… (same digest as CI)

Clock evidence:
DB and host clocks agree; 90 s pre-check 0 steps; BUT during the full PG suite, 7 backward wall-clock steps (0.02–0.64 s) in 3 000 s → not stable (F13RA-N02 condition persists, milder). CI NOT RUN (0 workflow runs for SHA).

Tests actually run:
ruff PASS; mypy PASS (103 files); SQLite full 986 passed / 360 skipped (env-gated) / 0 failed; PG full 1345 passed / 1 skipped (Stripe live) / 0 failed; OpenAPI drift PASS (in both);
auditor probes 83 PG + 1 SQLite passed (generation/atomicity 12, concurrency 14, product 43, anchor oracle 2, migration 4, recovery/scale 5, F13RA-N01 1, PATCH race 1);
scale repro 10k×1k passed; mutation 30 mutants: 23 killed, 7 survived (production correct).

Overall verdict:
TASK_014_REQUIRES_TARGETED_FIXES

Repair required:
YES (F-1…F-6 targeted; then CI or stable-clock Linux Py3.12 rerun on the new SHA)

Production:
NOT READY

Deployment:
NOT DEPLOYED

REQUEST TO CHATGPT:
Adjudicate TASK-014A and decide whether TASK-014 becomes the accepted Phase-1A product baseline.
```
