# BP-10 — Idempotent conversation start and message append

| Field | Value |
|---|---|
| Purpose | FE-003 backend prerequisite BP-10 ([FE-003 §10.1](FE-003-save-conversation-viewing-DRAFT.md)); beta blocker BB-11 |
| Authority | **D-108** ([`docs/DECISIONS.md`](../DECISIONS.md)) — founder decision approving FD-1…FD-9 and this contract (2026-10-10); FE-003 §3.2, §10.1, AC-C7 (D-104, D-105); canon 04 §73 and 04a §6 (respected through FE-003's "equivalent unique key" clause); PR-003 (D-89, D-90); BP-1 code convention |
| Authorisation | founder: BP-10 Phase B implementation authorised; allowlist expanded twice (head-pinning tests, release-policy record). `MERGE AUTHORIZED: NO`; `FE-003 IMPLEMENTATION AUTHORIZED: NO`; `FE-VIS-001 IMPLEMENTATION AUTHORIZED: NO` |
| Risk | **R2** — concurrency, private engagement, privacy, authorization/replay, plus a migration: a 05 §9 high-risk change, so the mandatory Codex audit applies |
| Baseline | `main` = `be150da11b9838409fcf8ee2d8ca4bd8b0311307` (tree `7a21621725f6250fd0f84e67db09fbda0964be7b`), CI `37518003115` success 6/6; Alembic head `a3c5e7f9b1d4` |
| Branch | `claude/BP-10-idempotent-message-send` |
| Phase A | read-only audit + proposed contract, PASS (2026-10-07); transport report outside the repository (not authority) |
| Status | **BUILDER VERIFIED CANDIDATE — PHASE C REQUIRED** (the exact candidate SHA is in the builder handoff; a file cannot name the commit that contains it). `PHASE C C1: NOT YET ACCEPTED` · `PHASE C C2: NOT YET ACCEPTED` · `MANDATORY CODEX AUDIT: NOT YET ACCEPTED` · `MERGE AUTHORIZED: NO` |

## 1. Problem

A send whose response is lost (PR-003 U1/U2: committed, but the client sees a
transport error, 504 or 503 `commit_unknown`) was re-sent as a second
message. And a retry could be **refused** — `RECONTACT_BLOCKED`, quota, 404,
`CONVERSATION_CLOSED` — for a message that had in fact been delivered, when
its lookup ran before a lock wait that a moderation decision overtook (Phase A
M2 C1); the user then resends with a new id, and that duplicates too.

## 2. Founder decisions (D-108)

| ID | Decision |
|---|---|
| FD-1 | Mechanism A′: a message-local equivalent unique key. `platform.idempotency_keys` is **not** instantiated for BP-10 |
| FD-2 | Per-key serialisation with a transaction-scoped `pg_advisory_xact_lock`, domain-separated two-int key |
| FD-3 | First execution 201; successful replay **201** (never 200) |
| FD-4 | No independent BP-10 idempotency expiry: `client_message_id` is coextensive with the authoritative Message row and its permitted retention/anonymisation lifecycle. No expiry, no nulling job, no cleanup worker, no independent retention policy |
| FD-5 | Stable code `IDEMPOTENCY_KEY_REUSED`: same key + different body or target → 409 |
| FD-6 | Current access outranks replay: a provider without current access to the conversation gets 404; the key is never a capability token |
| FD-7 | `schema_transition = EXPAND`, `rollback_to_previous = BLOCKED`; BB-11 rollout gate — keyed frontend sends stay off until every serving backend instance runs BP-10. No deployment authorised |
| FD-8 | PostgreSQL engines: `hide_parameters=True` (SQLite unchanged) — every application engine, through `create_bounded_engine`; the migration job (`app/scripts/migrate.py`, outside this allowlist) opens its own engine and carries no message data (residual, recorded in the builder handoff) |
| FD-9 | `client_message_id` is required on both routes; no optional unkeyed write path |

## 3. Contract

**Guarantee.** For one sender user U and one `client_message_id` K: at most
one USER message ever exists (both routes, any timing, any crash, every
instance running BP-10). If an attempt committed, every later attempt with
the same request gets that message — 201, current projection — unless the
caller has lost access to the conversation (404). A new conversation, its
participants and its `conversation.started` audit row are created at most once
per K, atomically with the message. A replay writes nothing.
*Not guaranteed:* delivery of any response; deduplication across keys or when
the client lost K (reload); deduplication on an instance not running BP-10;
byte-identical bodies (current state; redacted → null). Terminology:
at-most-one authoritative message effect with idempotent retry semantics over
at-least-once HTTP — not "exactly-once delivery".

**API.** Both `POST /v1/classifieds/{offer_id}/conversations` and
`POST /v1/conversations/{conversation_id}/messages` take `MessageIn
{body (1–4000, stripped, not blank — unchanged), client_message_id (UUID v4,
required)}`; any UUID v4 spelling pydantic accepts is stored canonically
(`str(uuid)`: lowercase, hyphenated); missing / non-v4 → 422. Responses: 201
(first and replay, identical schema — start `ConversationDetail`, append
`MessageOut`); 404; 409 `OWN_LISTING` / `RECONTACT_BLOCKED` /
`CONVERSATION_CLOSED` / `IDEMPOTENCY_KEY_REUSED`; 422; 429 (start
`CONVERSATION_QUOTA`; both: the rate limit, no code); 503 + `Retry-After`
("retrying the same logical send with the same `client_message_id` is safe").
The key is never echoed — not in `MessageOut`, `ConversationDetail`, GET
conversation, moderation evidence or reports.

**Schema / migration.** `messages.client_message_id varchar(36) NULL` (no
default, no backfill) and `uq_messages_sender_client_message
(sender_user_id, client_message_id) WHERE client_message_id IS NOT NULL`
(`postgresql_where` + `sqlite_where`). Alembic `11d778ab87a3` (parent
`a3c5e7f9b1d4`): EXPAND, rollback BLOCKED; `release.json` head = minimum =
maximum = `11d778ab87a3` (migrate first). Port deviation #23. Nothing else:
no idempotency table, hash, response body, expiry, state, operation or target
column, no CHECK.

**Identity and matching.** (sender_user_id, client_message_id), one namespace
for both routes (route is never part of the identity, the lock key or the
match); `sender_organization_id` is not part of it. Same request = same
sender + same canonical key + same target (append: stored
`conversation_id`; start: the stored conversation's `listing_id` and
`requester_user_id` = caller) + the same stored stripped body (exact string,
`messages.body`, never the projection; no Unicode normalisation). A start
retried as an append, or an append retried as a start, with the same context
and body is a **replay**. Anything else with that key → 409
`IDEMPOTENCY_KEY_REUSED`, nothing written, the original binding intact.

**Send lock.** `SELECT pg_advisory_xact_lock(CAST(:cls AS integer),
CAST(:obj AS integer))` — `cls = SEND_LOCK_CLASS` (`0x42503130`, "BP10"),
`obj = int.from_bytes(sha256(b"bp10.message-send\0" + user_id + b"\0" +
str(uuid)).digest()[:4], "big", signed=True)`; never Python `hash()`, never
unsigned, never bigint, never route/target/body/organisation. PostgreSQL only
(SQLite: no-op, never evidence). Taken in the top-level transaction (refused
inside a savepoint), while holding no row lock, before any final refusal; the
lookup is a separate statement, READ COMMITTED, unlocked.

**Order.** Start: auth → validation → send lock → lookup → replay / 409 →
listing FOR SHARE → visibility → OWN_LISTING → users lock → thread → G-14 →
quota → create → message → commit. Append: auth → validation → `_load`
(current side, 404) → send lock → lookup → replay / 409 → conversation FOR
UPDATE → CLOSED → message → commit. Global order unchanged: send lock →
listing → users → conversation → message.

**Linearization / state.** The COMMIT of the send transaction; ABSENT →
COMPLETED is derived from the message row — no RESERVED / IN_PROGRESS /
COMPLETED record exists.

**Lost race.** An IntegrityError leaving the write path → full rollback (never
a savepoint) → fresh keyed lookup → replay or 409; no keyed row → log
SQLSTATE and constraint name only and raise `RuntimeError("integrity:
<constraint>")` without the original (its DETAIL carries the key and the
failing row). Unrelated constraint failures are never reported as
`IDEMPOTENCY_KEY_REUSED`.

**Rate / quota.** Rate limits unchanged; replays spend the ordinary IP budget;
a replay never counts toward the conversation quota.

**Observability.** `homies_message_idempotency_total{route=start|append,
outcome=replay|conflict|race_recovered}`; first sends are not counted (HTTP
metrics are); no key, message, user, conversation, listing, body or hash label;
no new alert.

## 4. Proof obligations

Tests: `U` = `backend/tests/test_bp10_message_idempotency.py` (SQLite:
behaviour only), `P` = `backend/tests/test_bp10_message_idempotency_pg.py`
(PostgreSQL, migrated schema), mutants `backend/scripts/mutation/bp10_mutants.py`.

| INV | Invariant | Control | Deterministic test | PostgreSQL test | Mutant |
|---|---|---|---|---|---|
| INV-1 | ≤1 USER message per (sender, key) | unique index + key on every `_post` + send lock | U T1 | P p1, p2b, t4, t5, t8 | B01, B01b, B02 |
| INV-2 | one namespace across start and append | lookup ignores the route | U start↔append replays | P t22[append/start] | — (route never in the code path) |
| INV-3 | no false final coded refusal for a committed send | send lock + lookup before every refusal | U t13, t16, t21 | **P t22** (three-party) | B04, B05, B06, B06b, B10, B21 |
| INV-4 | absence is stable under the send lock | lock, then a separate READ COMMITTED lookup | — | P t5, t4, inv4, t8, t27 | B04, B05 |
| INV-5 | a replay writes nothing | replay returns before any write, never commits | U t17/t18/t20, t19 | P t4 (one audit, two participants) | B15 |
| INV-6 | replay = current authorised projection | fresh SELECT + `MessageOut` / `_out` | U t13, t15, stored-body test | P t5 (same id, same instant) | — |
| INV-7 | actor isolation | sender in lookup and index | U other-account test | — | B03 |
| INV-8 | mismatch → 409, original intact | target + stored-body comparison | U t2 (body, conversation, listing, requester) | P t8 | B12, B12b, B13, B13b, B13c |
| INV-9 | start atomicity | full rollback on a lost race | U lost-race test | P t4 | B14 |
| INV-10 | bounded waits, no new deadlock cycle | lock_timeout; send lock first, holding no row lock | — | P inv10/p6a, p8, t22 (no deadlock), t6, t7 | B06, B06b |
| INV-11 | refusals write nothing, key unused | refusals raise before COMMIT | U t11 | P t11 | B17 |
| INV-12 | key/body never logged or exposed | route-wide handler, sanitized error, `hide_parameters`, no echo | U t24 (×3) | P fd8 | B18, B19, B20 |
| INV-13 | canonical UUID v4 | pydantic `UUID4` → `str()` | U t23 (×2) | — | B16 |
| INV-14 | release safety | EXPAND + BLOCKED + migrate-first + BB-11 gate | `test_release_manifest.py`, `test_schema_compat.py`, `test_moderation_core.py` | `test_release_pg.py` bootstrap | (PR-002 harness) |

T1–T28 mapping: T1 U t1×2 · T2 U t2×3 · T3 U t3 + other account · T4–T8 P ·
T9 U t9 (+ P t10 committed) · T10/T12 P t10_t12 [committed, rolled_back] ·
T11 U t11 + P t11 · T13 U t13 · T14 U t14 · T15 U t15 · T16 U t16 · T17/T18/T20
U t17_t18_t20 · T19 U t19 · T21 U t21 · **T22 P t22 [with/without × start/append]**
· T23 U t23×2 · T24 U t24×3 · T25 `test_tst01_openapi_contract.py` · T26
`test_dr_restore_phase1_pg.py` (keyed seed, index definition after restore),
`test_release_manifest.py`, `test_td01_migrations.py` · T27 P t27 · T28 U t28×2
+ P t28. Metric: `test_obs02_03_metrics.py`.

## 5. Phase C and merge gate

Two independent audits of the exact candidate SHA — **C1** PostgreSQL /
transactions / concurrency / crash windows / COMMIT unknown / send lock /
savepoints / migration locks, and **C2** security / privacy / API /
authorization / replay / log leakage / OpenAPI codes — plus the **mandatory
Codex audit** (05 §9), then founder/GPT adjudication of the exact SHA. No
builder self-merge. Only a later explicit founder instruction can say
`MERGE AUTHORIZED: YES`; keyed FE-003 sends wait for BP-10 on every serving
instance (BB-11).

## 6. Learning

* Head-pinning and chain-shape tests (`test_moderation_core`,
  `test_schema_compat`, `test_release_pg`) and the release-policy record must
  be in a schema-bearing task's allowlist; a grep for the literal head misses
  tests that derive the head from the graph but hard-code the chain shape.
* SQLite returns `DateTime(timezone=True)` values naive (UTC); response
  instants are compared as instants there, exactly on PostgreSQL.
* The advisory lock is load-bearing only in a three-party interleaving; a
  two-party race is held by the unique index alone, so only the T22 harness
  (PostgreSQL) can kill the "no lock" mutants.

## 7. Builder verification (before the candidate commit)

Disposable PostgreSQL 16 + PostGIS 3.4 (`postgis/postgis:16-3.4`), the pinned
test image (Python 3.12; SQLAlchemy 2.1.1, pydantic 2.13.5, psycopg 3.3.6).

| Gate | Result |
|---|---|
| full backend suite, SQLite + PostgreSQL (`TEST_DATABASE_URL`, `HOMIES_REQUIRE_RESTORE_DRILL=1`) | 1964 passed, 1 skipped (Stripe live suite, not requested), 0 failed; restore drills 10 passed |
| `ruff check app tests alembic scripts` · `mypy` · `alembic heads` · `export_openapi --check` · frontend `check:api` | all clean; one head `11d778ab87a3` |
| BP-10 mutation harness (`bp10_mutants.py`, 28 mutants) | 28 killed, 0 survived — the advisory-lock mutants by the PostgreSQL T22 harness |
| existing mutants M09, M10 (`task002_mutants.py`) | killed (anchor unchanged) |
| internal builder review B1 / B2 / B3 (not Phase C) | 1 MATERIAL (OpenAPI 422 body dropped) fixed in correction cycle 1; NONBLOCKING test-precision items fixed; 0 open BLOCKER / MATERIAL |

Branch CI and the exact candidate identity: builder handoff.
