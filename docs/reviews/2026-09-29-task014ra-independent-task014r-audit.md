# TASK-014RA — Narrow Independent Re-audit of TASK-014R

Auditor: Claude, in an independent read-only session on 2026-09-29. This session did not build TASK-014 or TASK-014R. It made no fixes, no commits, no pushes, no merges and no deployments.

| | |
|---|---|
| Audited SHA | `7ffb4f51dd315363362df1a5f8fc5c19a57767dc` (`origin/claude/TASK-014R-alert-integrity-repair`) |
| Original TASK-014 candidate | `196c88796cf34a6b19860259cc6ff81c94dbe8d2` |
| Accepted parent | `3f324b6ddff6c7557894eb5f65736729d956f7eb` |
| Evidence harness | `3d37a7e8e29b71a6c57b7b3884d9632eef6c8fc9` (branch `evidence/TASK-014R-stable`) |
| Evidence run / job | `36595074447` / `109497758765` |
| Evidence folder | `C:\Users\ihorf\Projects\homies-audit-evidence\TASK-014RA\` (`CHECKPOINT.md`, `logs/`, `probes/`, `copy/backend/tests/test_t14ra_*`) |

## 0. Exact SHA and independence

Checks run in a fresh detached worktree `wt/`:

- `git rev-parse HEAD` returned `7ffb4f51dd315363362df1a5f8fc5c19a57767dc`.
- `git status --short` was empty.
- `merge-base --is-ancestor 196c887 HEAD` exited 0.
- `merge-base --is-ancestor 3f324b6 HEAD` exited 0.
- `rev-list --count 196c887..HEAD` returned 2:
  - `39f158e` — fix(alerts) TASK-014R
  - `7ffb4f5` — test(alerts): the scale fixture writes genuine fingerprints

The diff from `196c887` to HEAD touches 19 files, all inside the expected repair surface:

- **Migration:** `f3b5d7e9a1c2`.
- **Production code:**
  - `alerts/delivery.py`
  - `events/providers.py`
  - `saved/router.py`
  - `saved/service.py`
- **Mutation harness:** `scripts/mutation/task014r_mutants.py`.
- **Tests:**
  - `test_task014r_repairs{,_pg}.py`
  - 2 existing test files, adjusted
- **Documentation and audit records:**
  - `DECISIONS`
  - `DEVLOG`
  - `PROJECT-STATUS`
  - `04a`
  - `IMPLEMENTATION-CONVERGENCE`
  - `MIGRATION-ROLLOUT`
  - the TASK-014 contract
  - the reviews

No unrelated feature work is present. `39f158e..7ffb4f5` changes only `tests/test_saved_search_scale_pg.py` and `DEVLOG.md`.

## 1. Audit chain

- **Archived TASK-014A report:** `docs/reviews/2026-09-29-task014a-independent-task014-audit.md` is **byte-exact** with the auditor's original `TASK-014A/TASK-014A-FINAL-REPORT.md` (SHA-256 `b9db00f7…a891a`, 552 lines).
- **Documents read:**
  - the TASK-014 contract
  - D-81 and D-82
  - `04a` §22
  - `IMPLEMENTATION-CONVERGENCE`
  - `MIGRATION-ROLLOUT`
  - the TASK-014R mutation review
- **D-81** now carries an inline TASK-014R amendment.
- **Rollout doc:** it now has a row for `f3b5d7e9a1c2`, which closes N-5.
- **Wording nits:** listed under RA-N2.

## 2. Environment

**Local runs (supporting evidence only).** The local Docker VM clock is known to be unstable, so these runs are not the evidence of record.

- Image `pr001a-test-py312`: Python 3.12.14, pip check OK, 70 packages. CI has 71 because it also installs the project itself.
- `postgis/postgis:16-3.4@sha256:44126d87…` — the same digest as the harness. That is PostgreSQL 16.4 with PostGIS 3.4.3.

**Evidence of record:** the stable GitHub run described in §14.

## 3. Results by item

### F-1 → **F1_DURABLE_UNSUBSCRIBE = CLOSED**

**Code path** (`alerts/delivery.py:163-200`), in order:

1. `ensure_unsubscribe_capabilities` does an idempotent `insert_ignore` keyed on the `token_hash` primary key.
2. `db.commit()` makes the capability rows durable.
3. The delivery row is re-locked `FOR UPDATE`.
4. The code checks the delivery is still `processing` and runs `revalidate` again.
5. Only then is SMTP called.

If the linked search changes in the meantime, the links are re-provisioned, with at most 2 loops. After that the outcome is a transient `search_changed`.

**Probe: accept, then crash.** I simulated "SMTP accepts the message, then the process dies before the outcome commit", three times over:

- At each SMTP call, a **brand-new DB connection** already saw both capability rows: `[[1,1]]×3`.
- The delivery stayed `processing`; reconcile then re-sent it.
- The run produced 4 emails in total, all with the same idempotency key.
- **All 4 carried identical links.**
- The token table held **2 rows** throughout.
- The first email's per-search link worked, and so did its global link.

**Probe: search deleted mid-flight.** I deleted the linked search after the commit. The email then carried working links for the surviving search.

**Old probe re-run.** The old TASK-014A crash probe now reports token rows `[1,1]` and a working click.

**Delivery semantics:** one logical delivery (unique `(user, listing, generation, channel)`) is not the same as exactly-once SMTP. SMTP is **at-least-once** (D-09), which is accepted.

### N-3 → **N3_TOKEN_REPLAY = CLOSED**

The unsubscribe endpoint handles tokens as follows:

- An unknown token has no effect.
- An expired token has no effect.
- A token whose `used_at` is set counts as a replay and changes nothing.
- The first valid use applies the unsubscribe and records `used_at`.

**What was probed:**

- an unknown token;
- an expired token;
- a valid per-search token, used, then replayed after re-enabling alerts;
- a valid global token, used, then replayed after re-enabling alerts.

**Results:**

- All 7 answers were identical: `200 {"status":"ok"}`.
- After re-enabling, both scopes stayed **enabled** despite the replay.
- `used_at` was not refreshed.
- A token shorter than 16 characters gets a schema 422. That is unchanged and does not enumerate anything.

### Capability security → **CAPABILITY_SECURITY = ACCEPTED**

**Construction:**

```
key   = HMAC-SHA256(JWT_SECRET, "homies/unsubscribe-capability/v1")
token = b64url(HMAC-SHA256(key, delivery_id \n scope \n search_id))
```

**What was checked:**

- **Size:** 43 characters, 32 bytes — 256 bits.
- **At rest:** the raw token is found in no table. Only its SHA-256 is stored, as the primary key, and it cannot be reversed.
- **Independent re-implementation:** it matches the production token exactly.
- **Guessing without the key:** every guess built from `(delivery_id, scope, search_id)` alone failed. Knowing those ids without the server secret is not enough.
- **Domain separation:** it is explicit through the purpose label. The label contains no `.`, while JWT signing input always does, so JWT signing cannot act as an oracle for this key.
- **Every input matters:** changing the delivery, scope, search or null-search gives a distinct token (5/5).
- **Rows are bound:** each row binds user, scope and search. Transplanting a token to another search has no effect.
- **Unambiguous separators:** the ids are UUIDs, so they contain no newline.
- **Determinism stays per delivery:** retries of one delivery reuse its token, and deliveries remain isolated from each other.
- **Production secret:** insecure or short secrets are refused at startup (`config.py:232`).
- **Secret rotation:** links already sent keep working, because the stored hash does not depend on the key. A retry after rotation adds at most 2 rows.

### F-2 → **F2_QUERY_INTEGRITY = CLOSED**

**The check** (`saved/service.py:57-74`): a stored query is VALID only if **both** hold:

- the parsed query's canonical form equals the stored string;
- the recomputed fingerprint equals the stored fingerprint.

Otherwise it is INVALID.

**Every consumer goes through it:**

- API `query_state`
- `/matches`
- `matching.py:124`
- `delivery.py:123` (send-time revalidation)

**Probe with 9 kinds of stored row:**

- **Unchanged:** VALID, `/matches` 200, 1 match.
- **8 corrupted kinds:**
  - fingerprint set to all zeroes;
  - a different but valid fingerprint;
  - a valid subset with a dropped filter;
  - a non-canonical string;
  - schema v2;
  - a retired locality;
  - a missing geo area;
  - a non-filterable attribute.

For each of the 8 corrupted kinds:

- the query is INVALID in GET and in the list;
- `/matches` returns 409;
- the worker produced **0** match rows, even for a listing that only a broadened query would match.

**Send time:** when the row was corrupted after queueing (zeroed fingerprint, dropped filter, non-canonical string), both channels were `suppressed query_invalid` and no email went out. A corruption never broadens.

### Scale fixture → **SCALE_FIXTURE = ACCEPTED**

**Fixture:** stores the real `fingerprint(1, canonical)`. A duplicate `(user, canonical)` pair is moved to the next free user rather than given a forged fingerprint.

**Full scale:** 10 000 searches and 1 000 listings.

- **Validity:** all 10 000 were VALID through the production `load_query` (500 users, 10 000 unique user–fingerprint pairs).

| City | Candidates | Matches | Deliveries | SQL statements |
|---|---|---|---|---|
| Kraków | 7 096 | 4 304 | 500 | 49 |
| Warszawa | 4 903 | 2 906 | 500 | 40 |
| Balice | 3 016 | 1 832 | 489 | 35 |

These counts are identical to the TASK-014A run.

**Why the test cannot go vacuously green:** it asserts `1 <= evaluations`, and a board of all-INVALID queries produces 0 evaluations. §15 shows exactly that failure on `39f158e`.

### F-3 → **F3_MIGRATION_ROUNDTRIP = CLOSED**

**How `_reconcile_surviving_generations` works:**

- It reads the structured payload with the regex `^[1-9][0-9]{0,17}$`. It never parses the dedup key.
- It joins only listings that exist.
- It only ever raises a generation, never lowers it.
- It inserts historical work items as `done`, with `ON CONFLICT DO NOTHING`.

**Probe setup:**

- Listings with public generations 0 (never public), 1 public, 1 paused, 2 public, 4 public and 4 paused.
- Downgrade to TASK-013.
- 7 malformed or unrelated events, all ignored:
  - generation `abc`, `-3`, `0` and a 19-digit value;
  - an unknown listing;
  - a missing generation;
  - another event type.
- 1 well-formed forged event: accepted, with its bad instant replaced by `now()`.
- Re-upgrade to head.

**Results:**

- **Generations** are identical to before the downgrade; none regressed.
- **Work rows:** 14, all `done`.
- **Reconcile** restored 0 rows. `run_once` did no work and made no deliveries, so there is **no alert flood**.
- **Republishing** every listing returned 200, and the generation became the previous maximum + 1 (for example 4 → 5).
- **No duplicate dedup keys**, and **no HTTP 500**.
- **Only new generations alert.**

### MIGRATION_REGRESSION = ACCEPTED

- **Alembic heads:** exactly one, `f3b5d7e9a1c2`, whose parent is `d0f2b4c6e8a1`.
- **Empty DB → head:** passes, with 0 work rows and 0 events.
- **Populated TASK-013-shaped DB → head:** passes. `git grep` confirms that TASK-013 never emits `ListingBecamePublic`.
  - draft 0 / published 1 / multi-episode 1;
  - 0 work rows;
  - no fabricated events and 0 deliveries.
- **Builder's round-trip test:** passes in the full PG suite.

### F-4 → **F4_PATCH_CONCURRENCY = CLOSED**

**The fix** (`saved/router.py:321-343`) turns an integrity error into 409 only when it is the unique constraint `uq_saved_searches_user_fingerprint`. On SQLite, which does not report constraint names, it checks whether another search of the same user already holds the fingerprint. Any other integrity error is re-raised.

**Probes on real PostgreSQL:**

- **Racing PATCHes:** 8 of 8 races returned `[200, 409]`, with no 500. Exactly one row remains per query.
- **Forced lock wait:** I held a competing uncommitted change so the PATCH had to wait on the unique index, then committed the competitor. The PATCH answered **409**.
- **Unrelated integrity error:** an injected unrelated `IntegrityError` still **propagates**, and the row is left unchanged.
- **Clean session:** a later PATCH through the same client returns 200.

### F-5 → **F5_SMTP_CLASSIFICATION = CLOSED**

**Ordering:** `SMTPException` is a subclass of `OSError`, so SMTP-specific handling now runs before the generic `OSError` branch. `SMTPRecipientsRefused` is not a subclass of `SMTPResponseException`, and it has its own branch.

**Results for 20 cases:**

| Error | Classification |
|---|---|
| Recipient 450 | transient |
| Recipient 550 | permanent |
| Recipients mixed 450/550 | permanent |
| Authentication 535 / 454 | permanent |
| Command not supported | permanent |
| DATA 451 | transient |
| DATA 554 | permanent |
| Sender 553 | permanent |
| HELO 501 | permanent |
| Connect 421 | transient |
| Connect 554 | permanent |
| Server disconnected | transient |
| `TimeoutError` / socket timeout | transient |
| Connection refused / `gaierror` / `OSError` / `SSLError` | transient |
| Bare `SMTPException` | transient |

**Stored reasons:** every stored reason has the form `Class` or `Class:code`.

**Bounded retries:** a transient failure is retried at most 5 times and then ends as `retries_exhausted`. Authentication and configuration failures are permanent and are never retried indefinitely.

### SMTP error privacy → **SMTP_ERROR_PRIVACY = ACCEPTED**

**What was injected:** error text from a fake `smtplib.SMTP`, sent through the real `SmtpEmailChannel`, containing these sentinels:

- the recipient address;
- a password-like token;
- provider free text;
- an internal hostname.

**Paths exercised:**

- the alert path, with 5 exception types, run through to the terminal state;
- the events path (`notifications.last_error`).

**Where I searched:**

- every table, as `row::text`;
- DEBUG logs;
- the Prometheus registry;
- `/v1/me/inbox`.

**Result: 0 leaks.** The only exclusions were `users.email` and `verification_codes`, which hold the address legitimately. Stored errors are machine strings only, such as `SMTPRecipientsRefused:550` and `OSError`.

### N-4 → **N4_RETRY_SEMANTICS = CLOSED**

Terminal outcomes seen by the probe:

| Cause | Status / outcome | Attempts |
|---|---|---|
| Recipient 550 | `dead` / `provider_rejected:SMTPRecipientsRefused:550` | 1 |
| Authentication 535 | `dead` / `provider_rejected:SMTPAuthenticationError:535` | 1 |
| DATA 451, `OSError`, timeout | `dead` / `retries_exhausted` | 5 |

Values fit the 48-character column and carry no provider text.

### F-6 → **F6_MUTATION_CLOSURE = CLOSED**

**How mutants were run:** my wrapper `probes/t14ra_mutate.py` takes the builder's 16 mutants. For each one it:

1. confirms a green baseline;
2. applies the mutant;
3. runs the tests with `-rfE`;
4. restores the original file and verifies its SHA.

The SHA-256 manifest of `app/` and `alembic/` is identical before and after the whole run (`SOURCES-RESTORED`).

**Builder tests: 16 of 16 killed.** Every one had a green baseline, and each kill was reported as `N failed` with no error. The mutants were X13, X18, X06, X07, X08, X10, F1-a, F1-b, N3, F2-a, F2-b, F3, F4, F5-a, F5-b and N4.

**What the kills assert:** behaviour — `(status, outcome)` sets, empty match rows and recipient lists. None was a collection or setup error.

**My own tests: 11 of 12 mutants killed.** F2-a survived only because the fingerprint check already catches any text-only corruption (see RA-N3). The builder's test kills F2-a with a consistent rewrite of both text and fingerprint.

**X13, verified independently.** User A deletes their search while user B's search matches the same listing. A's delivery is `suppressed search_deleted`, and only B is emailed. A variant where A's search is INVALID gives `query_invalid`.

**X18, verified independently.** A paused search, or one with notifications off, creates 0 match rows and 0 deliveries. Both the builder's tests and mine kill this mutant.

## 14. Stable evidence → **STABLE_EVIDENCE = ACCEPTED**

**Run metadata** (public API):

- Run 36595074447, attempt 1, event **push** on `evidence/TASK-014R-stable` (not a PR merge ref), head `3d37a7e`.
- Job 109497758765 ran on `ubuntu-24.04`, runner image `ubuntu24/20260920.314.1`, and every step succeeded.

**Harness source** (read directly at `3d37a7e`):

- It checks out `SOURCE_SHA` explicitly and fails unless HEAD equals it.
- It pins the same PostGIS digest and uses Python 3.12.
- It records `pip freeze`.
- Every gate step fails the run on error.
- The mutation step requires a clean tree and 16 of 16 kills.

**Annotations:**

- **Provenance:** `SOURCE_SHA=7ffb4f5… checked_out=7ffb4f5… HARNESS_SHA=3d37a7e… run=36595074447 attempt=1`.
- **Environment:** Python 3.12.14, PostgreSQL 16.4, PostGIS 3.4.3, `ntp=yes`.
- **Dependencies:** SHA-256 `2a0e43b8…`, 71 packages.
- **Gates:**
  - Lint, typecheck and migration all pass.
  - Targeted tests: **126 passed**.
  - Full SQLite: **1018 passed / 364 skipped / 0 failed**.
  - Full PG/PostGIS: **1381 passed / 1 skipped (Stripe live) / 0 failed**.
  - Mutation: **16 of 16 killed**.

**Not reviewed:** the raw job log and the artifact (`task014r-evidence`, id 11046152799). Both need admin authentication (HTTP 403; see RA-N4).

**Local reproduction at the exact SHA:** SQLite **1018 / 364 / 0** and PG **1381 / 1 / 0** (exit 0), plus ruff and mypy passing on 103 files. The counts are identical to CI.

## 15. Earlier failed evidence runs → **EVIDENCE_HISTORY = ACCEPTED**

Two earlier runs are relevant:

- **Run 36591263102** (harness `54fa35c`)
- **Run 36593065935** (harness `5ed3c2e`)

Both proved `checked_out=39f158ed…`. Each failed exactly one test, in both the targeted and the full PG step:

```
test_saved_search_scale_pg.py::test_matching_scales_with_candidates_not_with_the_board
assert 1 <= 0
```

**Cause:** the forged fingerprint `fingerprint(1, canonical+"#i")` made every seeded search INVALID under the new F-2 check, so there were 0 evaluation statements. The run genuinely detected the bad fixture, which counts as positive evidence.

**Correction:** `7ffb4f5` is a bounded test-and-docs change on top of `39f158e`, and the final SOURCE_SHA includes it.

## 16. Regression boundary → **PRODUCT_REGRESSION = ACCEPTED**

**What the repair diff changes:**

- the send path;
- unsubscribe;
- the SMTP adapter, which is shared with transactional email. The change is classification only and stays bounded by the attempt limit;
- the mapping of PATCH errors;
- `load_query`;
- a reconcile step that runs only on upgrade.

**What it does not touch:**

- `make_public` and public generation;
- candidates and anchors;
- the baseline;
- dedup;
- the TASK-012 public rule;
- the TASK-013 SearchQuery and geography.

**Re-run of my TASK-014A probes at the new SHA:** 77 passed. They cover:

- **Unchanged:** public generation, atomicity, concurrency.
- **Anchors:** 0 false negatives out of 2 601 oracle positives.
- **Baseline and no-flood:** hold.
- **N/N+1 isolation:** holds.
- **Send-time revalidation:** all 15 changes suppressed.
- **Privacy:** clean.
- **Worker recovery:** retries are bounded.

The full local and CI suites are both green.

## 17. Known debt — preserved, not reopened

- N-1: lock coupling.
- N-2: a poison work item is retried without a cap.
- N-6: the baseline in-flight race.
- N-7 / F13RA-N01: wording only (MICRO-001).
- X04: the CAS fails closed.
- The local Docker VM clock.
- Node 20 Actions deprecation.

TASK-014R introduced none of these.

## New findings (all NOTE — none blocking)

### RA-N1 — NOTE (pre-existing debt)

- **Where:** `alerts/worker.py:69-77` and `delivery.claim_deliveries`.
- **What happens:** a channel can raise an exception that is neither `SMTPException` nor `OSError` (for example a `ValueError`). The delivery then stays `processing`, reconcile returns it to `pending`, and it is claimed again with no attempts cap. The probe observed 8 attempts against a limit of 5, and the delivery never reached a terminal state.
- **Scope:** token rows stayed at 2, so there is no accumulation. The same behaviour exists at `196c887`; it is the delivery-side analogue of N-2.
- **Repair:** fold into the N-2 retry-policy follow-up. Either cap attempts in `claim_deliveries`, or finish the delivery in the worker's `except`. No canonical decision is needed.

### RA-N2 — NOTE (docs)

- **Where:** `docs/tasks/TASK-014-…md:67` and `docs/DECISIONS.md:16`.
- **What:** the contract still says "two fresh unsubscribe tokens" at line 67. D-81 still carries the old `secrets.token_urlsafe(32)` sentence before the TASK-014R amendment, and its status column still reads "Builder, pending TASK-014A".
- **Repair:** a wording pass, which is a MICRO-001 candidate.

### RA-N3 — NOTE (test design)

- **Where:** `saved/service.py:70-73`.
- **What:** the canonical-form check is defence in depth. The fingerprint check already catches any text-only corruption; the canonical-form check is needed only when both text and fingerprint are rewritten consistently, which the builder's test covers.
- **Effect:** this is why F2-a survives my tests.
- **Repair:** none needed.

### RA-N4 — NOTE (evidence access)

- **What:** the raw CI log and the artifact need admin authentication (HTTP 403).
- **What acceptance rests on instead:**
  - the run and job metadata;
  - the harness source;
  - the machine-emitted annotations;
  - my local exact-SHA reproduction, whose counts are identical.
- **Action:** the owner may want to download and archive `task014r-evidence`.

### RA-N5 — NOTE (hypothetical input)

- **Where:** `_SURVIVING_EPISODES` in the migration.
- **What:** the backfill trusts well-formed `ListingBecamePublic` payloads, and a forged well-formed payload raises the counter. Malformed payloads are rejected; the probe confirmed this.
- **Edge case:** a timestamp that matches `^\d{4}-\d{2}-\d{2}T` but is invalid would abort the upgrade. That fails closed, because the upgrade runs as one transaction. This is INFERRED from the SQL and was not executed.
- **Why it does not matter:** only `_open_episode` writes these events, and it always writes a consistent payload.
- **Repair:** none needed.

**Counts:** P0 0 · P1 0 · P2 0 · P3 0 · NOTE 5

## 18. Required results

```text
F1_DURABLE_UNSUBSCRIBE = CLOSED
N3_TOKEN_REPLAY = CLOSED
CAPABILITY_SECURITY = ACCEPTED
F2_QUERY_INTEGRITY = CLOSED
SCALE_FIXTURE = ACCEPTED
F3_MIGRATION_ROUNDTRIP = CLOSED
MIGRATION_REGRESSION = ACCEPTED
F4_PATCH_CONCURRENCY = CLOSED
F5_SMTP_CLASSIFICATION = CLOSED
SMTP_ERROR_PRIVACY = ACCEPTED
N4_RETRY_SEMANTICS = CLOSED
F6_MUTATION_CLOSURE = CLOSED
STABLE_EVIDENCE = ACCEPTED
EVIDENCE_HISTORY = ACCEPTED
PRODUCT_REGRESSION = ACCEPTED
```

## 19. Final verdict

```text
P0: 0
P1: 0
P2: 0
P3: 0
NOTE: 5

TASK_014_ACCEPTED_WITH_NONBLOCKING_NOTES

TASK_014_PHASE_1A_SLICE_ACCEPTED

SHA:
7ffb4f51dd315363362df1a5f8fc5c19a57767dc
```

This SHA becomes the new accepted PRODUCT baseline. The audit did **not** merge it into main.

## 20. Status

```text
PRODUCTION READINESS:
NOT READY

DEPLOYMENT:
NOT DEPLOYED
```

Accepting TASK-014 does not mean Homies is ready for production.

---

```text
CHATGPT HANDOFF

Project:
Homies

Task:
TASK-014RA — Narrow Independent Re-audit of TASK-014R

Audited SHA:
7ffb4f51dd315363362df1a5f8fc5c19a57767dc

Original TASK-014 candidate:
196c88796cf34a6b19860259cc6ff81c94dbe8d2

Accepted parent:
3f324b6ddff6c7557894eb5f65736729d956f7eb

Independent auditor session:
YES

F-1:
CLOSED

N-3:
CLOSED

F-2:
CLOSED

F-3:
CLOSED

F-4:
CLOSED

F-5:
CLOSED

N-4:
CLOSED

F-6:
CLOSED

Stable evidence:
ACCEPTED (run/job metadata, harness source and annotations reviewed; raw log/artifact 403 admin-only; local exact-SHA reproduction identical: SQLite 1018/364/0, PG 1381/1/0)

SOURCE_SHA:
7ffb4f51dd315363362df1a5f8fc5c19a57767dc

HARNESS_SHA:
3d37a7e8e29b71a6c57b7b3884d9632eef6c8fc9

Evidence run:
36595074447 / job 109497758765

Tests independently run:
SQLite full 1018p/364s/0f; PG full 1381p/1s/0f; ruff+mypy pass; single Alembic head, empty->head and populated TASK-013->head OK; auditor probes: t14ra_repairs 53p, t14ra_migration 4p, t14ra_mig013 1p, scale validity + full scale 2p (10000/10000 VALID; 7096/4304, 4903/2906, 3016/1832); TASK-014A regression probes 77p; mutations 16/16 killed (builder tests), 11/12 killed (auditor tests), sources sha-restored

P0:
0

P1:
0

P2:
0

P3:
0

NOTE:
5

Overall verdict:
TASK_014_ACCEPTED_WITH_NONBLOCKING_NOTES

TASK-014 accepted:
YES

Accepted product SHA:
7ffb4f51dd315363362df1a5f8fc5c19a57767dc

Remaining debt:
N-1 lock coupling; N-2 poison work item uncapped (+RA-N1 delivery-side analogue); N-6 baseline in-flight race; N-7/F13RA-N01 wording (MICRO-001, +RA-N2 doc wording); X04 CAS fail-closed; local Docker VM clock; Node 20 Actions deprecation; RA-N4 raw CI log/artifact not archived by auditor

Production:
NOT READY

Deployment:
NOT DEPLOYED

May participate in CONV-001:
YES — as the accepted TASK-014 product baseline, subject to ChatGPT adjudication and synchronisation with PR-001RA2

REQUEST TO CHATGPT:
Adjudicate TASK-014RA and synchronize it with PR-001RA2 before authorizing CONV-001 or any further mutation-bearing task.
```
