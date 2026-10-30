# SEC-SESSION-001 — Backend session security and refresh-token lifecycle

Status: **PROPOSED TASK CONTRACT — implementation NOT authorized.** Prepared
2026-10-30 at the founder's request (documentation only). Base: `main`
`4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4`. Priority P0: closes BG-1 and BG-5, the FE-003
beta blockers BB-1/BB-2 ([FE-003 contract §10](FE-003-save-conversation-viewing-DRAFT.md)). Proposed sole writer: Claude Code (identity
and BFF session form one bounded context). Risk class R3 — authentication
and concurrency: the **independent exact-SHA Codex audit is mandatory** (05
§9); builder self-review and same-model specialists do not replace it.

Canon: [00-AUTHORITY](../canonical/00-AUTHORITY.md),
[05 §9](../canonical/05-DEVELOPMENT-GOVERNANCE-v1.md),
[IMPLEMENTATION-CONVERGENCE](../canonical/IMPLEMENTATION-CONVERGENCE.md) (BG-1, BG-5 open),
[FE-001 §3, §9, §11](../frontend/FE-001-foundation.md) (BFF session, backend gaps BG-1/BG-5, SEC-001),
[RELEASE-AND-MIGRATION](../production/RELEASE-AND-MIGRATION.md). External
principles: OWASP Session Management Cheat Sheet (server-side invalidation),
RFC 9700 §4.14 (refresh-token rotation and replay detection).

## 1. Verified current state (at `4f2fc434`)

| Fact | Source |
|---|---|
| `POST /v1/auth/login`, `POST /v1/auth/refresh`; **no logout or revocation endpoint** | `backend/app/modules/identity/router.py:79-120` |
| Refresh token: `secrets.token_urlsafe(48)`, only its SHA-256 stored in `refresh_tokens(id, user_id, token_hash UNIQUE, expires_at, revoked_at, created_at)` | `core/security.py`, `identity/models.py:63-71` |
| Refresh: SELECT by hash → check `revoked_at IS NULL` and expiry → set `revoked_at` → issue a new pair. **No row lock, no conditional update**: two concurrent transactions can both pass the check and both issue a valid successor (INFERRED from the code; to be proven by a red PostgreSQL test first) | `router.py:105-120` |
| Every refresh issues a new token valid `REFRESH_TOKEN_TTL_DAYS` (30) **from now** → the session slides forever; no idle or absolute limit; no link between generations; no reuse detection | `router.py:42-50` |
| Access token: HS256 JWT `{sub, role, type, iat, exp}`, 30 min; `get_current_user` decodes it **and already loads the user row per request** | `core/security.py` |
| BFF: tokens only in `__Host-hm_at` / `__Host-hm_rt` (httpOnly, Secure, SameSite=Lax); refresh cookie Max-Age hard-coded 30 days; CSRF on mutating routes | `frontend/web/src/server/session.ts` |
| BFF single-flight per process + **rotation memory 120 s keyed by the old token**: whoever presents the old token within the window receives the new pair (accepted trade-off FE-001 §11 SEC-001) | `session.ts` `refreshOnce` |
| BFF logout clears this device's cookies only; the refresh token stays valid server-side (BG-1) | `app/bff/auth/logout/route.ts` |
| A backend timeout after a rotation loses the pair (BG-5); BFF backend timeout `API_TIMEOUT_MS` default 8 s | FE-001 §11, `server/env.ts` |
| Rate limits: `auth_refresh` 30 burst / 0.5 s⁻¹, fail-closed | `core/ratelimit.py:64` |
| Existing test: rotated token reuse → 401 (SQLite) | `tests/test_auth_and_rbac.py:6` |

## 2. Goal

One coherent server-side session lifecycle:

* logout revokes on the server;
* a refresh generation yields at most one live successor, even under concurrency;
* replay of a superseded token is detected and contained;
* access tokens stop working when their session is revoked;
* sessions have server-enforced idle and absolute limits;
* a lost refresh response no longer logs the user out, without an unauthenticated grace.

## 3. Design

### 3.1 Session identity (new table `auth_sessions`)

| Column | Meaning |
|---|---|
| `id` (uuid, PK) | session id `sid` — the token family |
| `user_id` (FK users, indexed) | owner |
| `policy` | `USER` or `ADMIN` — chosen from the user's role at creation and re-evaluated on refresh |
| `created_at`, `absolute_expires_at` | absolute limit fixed at login; **never moved** by refresh |
| `last_refreshed_at` | idle clock: time of the last successful rotation (login counts as the first) |
| `revoked_at`, `revoked_reason` | `LOGOUT`, `LOGOUT_ALL`, `REUSE_DETECTED`, `IDLE_EXPIRED`, `ABSOLUTE_EXPIRED`, `ADMINISTRATIVE` |

`refresh_tokens` gains: `session_id` (FK, nullable for legacy rows),
`generation` (int), `rotated_at`, `successor_id` (self-FK), and
`rotation_key_hash` (§3.4). There is a **partial unique index on `session_id`
where `rotated_at IS NULL AND revoked_at IS NULL`**, so the database itself
refuses two live tokens in one session. Raw tokens and raw rotation keys are
never stored: SHA-256 only, as today.

All times come from the database clock (`now()` within the transaction).

### 3.2 Refresh (rotation)

One transaction, in this order:

1. Find the token by hash; take a row lock on its session (`SELECT … FOR UPDATE`
   on `auth_sessions`). This serialises refresh, logout and reuse revocation
   for that session. The lock order is session, then token.
2. Refuse with the generic 401 if any of these holds:
   * the token is unknown or expired;
   * the session is revoked;
   * `now() ≥ absolute_expires_at` — revoke the session with `ABSOLUTE_EXPIRED`;
   * `now() > last_refreshed_at + idle` — revoke the session with `IDLE_EXPIRED`.
3. Token **live** (not rotated, not revoked) → mark it rotated (`rotated_at`,
   `revoked_at`, `successor_id`, `rotation_key_hash`). Insert the successor
   with `generation + 1` and `expires_at = min(now + refresh TTL, absolute_expires_at)`.
   Set `last_refreshed_at = now()`. Issue an access token carrying `sid`.
4. Token **rotated** → §3.4 (retry or reuse).
5. Any exception rolls the whole transaction back: nothing rotated, the
   presented token stays live, and a retry is an ordinary refresh.

Legacy token (`session_id IS NULL`, issued before this release): lock the
token row, create a session with `absolute_expires_at = token.expires_at` (no
lifetime gained), then continue at step 3. No user is logged out by the
deploy.

### 3.3 Access-token invalidation — recommended Option B

| Option | Guarantee | Cost | Verdict |
|---|---|---|---|
| A. Accept a residual access-token lifetime | after logout or reuse, an issued access token works ≤ 30 min | none | rejected: a detected replay would leave the attacker 30 minutes |
| **B. Server-side session check** | access JWT carries `sid`. `get_current_user` loads the session together with the user it already loads (one query, primary-key lookups) and refuses a revoked or absolutely expired session. **Logout and reuse revocation take effect on the next request after commit** | one PK lookup per authenticated request, on the connection the request already uses; no network dependency | **recommended** |
| C. Short access TTL / deny-list | weaker or more state | — | not needed with B |

Access tokens without `sid` (issued before the release) are refused. The BFF
already refreshes once on 401 and repeats, so the transition is silent; the
legacy refresh path above supplies a `sid`. Performance guard: a test
asserts the authenticated request path issues no more statements than today
plus at most one.

### 3.4 Replay detection, lost responses and the BFF binding (BG-5)

* **Rotation key.** For every refresh attempt the BFF generates a random
  128-bit key and sends it as `Idempotency-Key`. The key lives only in that
  BFF process's memory for the attempt — never in a cookie, the browser or a
  log. The backend stores only its hash on the rotated token.
* **Retry path.** The same token arrives with the same key, within
  `REFRESH_RETRY_WINDOW` (proposed 30 s, ≥ 2 × `API_TIMEOUT_MS`), while the
  successor has never been used. This is a lost response: revoke the unused
  successor (`SUPERSEDED_BY_RETRY`), issue a fresh one, and return it. A thief
  holding only the old token does not know the key, so this is not an
  unauthenticated grace. The BFF retries a timed-out or network-failed
  refresh **once, with the same key**.
* **Reuse path.** Anything else on a rotated token: no key, a different key,
  an expired window, or a successor already used. Revoke the whole session
  (`REUSE_DETECTED`), emit the audit event and the metric, answer the generic
  401. Other sessions of the user are untouched.
* **Benign concurrency, analysed:**
  * same-process duplicates share one backend call (BFF single-flight);
  * a response the browser aborted is answered by the BFF rotation memory;
  * a backend timeout is answered by the retry path;
  * two **different** web replicas racing on one token: one wins, and the
    other presents a rotated token with a different key, so the reuse path
    logs the user out. This is a safe failure. Multi-replica web therefore
    still requires sticky sessions (already recorded as a scaling item), and
    alpha/staging run one web replica.
* **BFF rotation memory (FD-3).** It already lets the holder of the old token
  obtain the new pair for 120 s within one process. That is an accepted
  FE-001 trade-off, but it is in tension with the rule "no unauthenticated
  grace". Recommended: keep it, shorten it to 15 s, and purge it on logout
  and on any rejection. Changing an accepted FE-001 decision is a founder
  decision.

### 3.5 Logout semantics

| Operation | Contract |
|---|---|
| `POST /v1/auth/logout` (current session) | Body `{refresh_token}`; no bearer needed (the access token may have expired). Revokes **the session the token belongs to**: every generation, plus its access tokens via §3.3. Other devices are untouched. Answers `204` also for an unknown, expired or already-revoked token (idempotent; no validity oracle). Rate-limited under the auth policy |
| `POST /v1/auth/logout-all` | Bearer of a live session required. Revokes every session of **that user** (`LOGOUT_ALL`); `204`. Justified: self-service response to a lost device or suspected compromise; the UI entry point may follow later (FD-5) |
| Compromise / administrative | Internal service function `revoke_sessions(user_id, reason)`, used by reuse detection and by the incident runbook. **No public admin endpoint** in this task |
| Cross-user | A session can only be revoked by presenting its token, or as its own user via logout-all. There is no id-based revocation API |

BFF `POST /bff/auth/logout`:

1. CSRF check.
2. Call `/v1/auth/logout` with the refresh cookie, bounded by the BFF timeout, retrying once.
3. **Always** clear both cookies and purge the rotation memory for that token.
4. Answer `{authenticated: false, serverRevocation: "confirmed" | "unconfirmed"}`.

The UI must not claim server-side sign-out when it is `unconfirmed`; it says
the session ended on this device, and the server will end it at its idle limit.
Never report success that was not confirmed.

### 3.6 Expiry policy (values need founder approval — FD-1, FD-2)

| Policy | Access | Idle (since last successful refresh) | Absolute (from login, never extended) |
|---|---|---|---|
| USER (proposed) | 30 min (unchanged) | 7 days | 30 days |
| ADMIN | 30 min or shorter | stricter — values required (e.g. 8 h) | stricter — values required (e.g. 24 h) |

Consequences:

* An active user refreshes at least once per access lifetime of use, so the
  idle clock follows real activity at 30-min granularity.
* Users are signed out 30 days after login even if active.
* `TokenPair` gains the additive field `refresh_expires_in`; the BFF sets the
  refresh cookie's Max-Age from it instead of a hard-coded 30 days.
* The config fields are new and named in the ENVIRONMENT-MATRIX. MFA is out of scope.

### 3.7 Browser consistency (FE-003 behaviour preserved)

* Cookie attributes, CSRF and the `/bff/v1/*` allowlist stay unchanged.
* Account A logs out while A's refresh is in flight: A's session is revoked,
  so a late successor or cookie write is dead on its next use and cannot
  revive A. A login as B then shows only B's data (existing FE-003 isolation
  tests stay green).
* Simultaneous tabs share one BFF process path; a revoked session ends all tabs on their next call.

## 4. Database and migration

* One Alembic revision, `down_revision = 23e89acb98b4`, single head.
* Changes: new table `auth_sessions`; nullable columns, the self-FK and the
  partial unique index on `refresh_tokens`.
* Declaration: `schema_transition = EXPAND`. The BP-5 writer inserts tokens
  with `session_id NULL`, which the index ignores; old code ignores the new
  columns.
* `rollback_to_previous`: technically SAFE — rotation also sets `revoked_at`,
  so the old code still refuses rotated or revoked tokens. But a rollback
  re-opens BG-1 and BG-5 while it lasts. Declare SAFE with that rollback note,
  or BLOCKED, by founder decision (FD-4).
* Release manifest updated per RELEASE-AND-MIGRATION; the app and migrator
  roles stay unchanged; `app_grants.sql` gives `homies_app` DML on the new
  table. No BARRIER and no data backfill (legacy rows convert lazily, §3.2).
* Rollout: run the migration first; then roll the application; the BFF ships
  in the same release. The BFF must tolerate the old backend: an absent
  `refresh_expires_in` falls back to 30 days, and a 404 from `/v1/auth/logout`
  means `unconfirmed`.
* No migration is executed by this contract.

## 5. Scope

In:

* `identity` router, models and service for sessions, refresh, logout and logout-all;
* `core/security.py` (`sid` claim and session check);
* config fields;
* audit events and bounded metrics (`homies_auth_refresh_total{outcome}`, `homies_auth_sessions_revoked_total{reason}`);
* the migration and the release manifest;
* OpenAPI and the generated web types;
* the BFF (logout call, `Idempotency-Key` and one retry, rotation-memory purge/TTL, cookie Max-Age);
* the minimal logout copy for the `unconfirmed` case;
* the INCIDENT-RUNBOOK session-compromise playbook updated to use `revoke_sessions`;
* tests, the DEVLOG, and this contract's evidence section.

Out:

* OAuth or social login, a new identity service, MFA;
* SSE or WebSockets;
* notifications, profile or payments;
* an admin session-management UI;
* any infrastructure.

Existing tests are never weakened.

## 6. Acceptance test matrix

**PG** = must run on PostgreSQL 16 + PostGIS (`pg_client` / disposable
database; SQLite evidence is insufficient). **Red first** = written and
failing on `4f2fc434` before the fix.

| # | Test | Level |
|---|---|---|
| T1 | Login creates a session; the access JWT carries `sid`; `/v1/me` 200 | API |
| T2 | Refresh rotates: new pair works, `generation` +1, `last_refreshed_at` moves, `absolute_expires_at` does not | PG |
| T3 | The prior generation is refused after rotation | API |
| T4 | **Red first:** N concurrent refreshes of one token (threads on separate connections, barrier start) → exactly one 200 and exactly one live token in the session; the partial unique index holds | PG |
| T5 | Logout revokes the presented token's session: refresh 401, and **the existing access token 401 on the next request** | PG |
| T6 | Single-device logout leaves the user's other session fully working | API |
| T7 | Logout-all revokes every session of the user, and nobody else's | API |
| T8 | Reuse: a rotated token presented without/with a wrong key, or after its successor was used → session revoked (`REUSE_DETECTED`), the successor and its access token refused, other sessions intact | PG |
| T9 | Lost response: the same token and key within the window with an unused successor → new successor, the first one refused; outside the window, or with the successor used → reuse path | PG |
| T10 | Logout racing a refresh of the same session (both orders, barrier) → final state: session revoked, no live token | PG |
| T11 | The absolute limit cannot be extended: refresh near the end caps the successor's `expires_at`; after it → 401 and `ABSOLUTE_EXPIRED` | PG, controlled DB time |
| T12 | Idle: `last_refreshed_at` set 8 days back → refresh 401 and `IDLE_EXPIRED`; 6 days → 200 | PG, controlled DB time |
| T13 | ADMIN policy applies to an admin user's session (once FD-2 values exist) | API |
| T14 | `/v1/auth/logout` with another user's token revokes only that token's session; there is no id-based revocation route | API |
| T15 | Unknown, expired and revoked tokens get the same 401 or 204 body (no oracle) | API |
| T16 | Legacy refresh token (`session_id NULL`) converts to a session without gaining lifetime; a legacy `sid`-less access token → 401, then the BFF transparently refreshes | PG + Vitest |
| T17 | Audit events, logs and metrics contain no raw token, token hash, rotation key or unnecessary PII; labels bounded | API + log capture |
| T18 | Authenticated request path: at most one extra SQL statement | PG statement counter |
| T19 | Old-release compatibility: the BP-5 code path against the migrated schema (release check allowed; tokens with `session_id NULL` insert) | PG release test |
| W1 | BFF logout: backend 204 → cookies cleared, `confirmed`; backend down or timeout → cookies cleared, `unconfirmed`, never `confirmed`; rotation memory purged | Vitest |
| W2 | BFF refresh sends `Idempotency-Key`; a timeout → one retry with the same key; a different attempt → a new key | Vitest |
| W3 | Account A → logout during an in-flight A refresh → B login: only B's data, A not revived | Playwright (existing FE-003 isolation pattern) |
| W4 | Two simulated BFF processes racing one token → user logged out, no second live successor (documents the safe failure) | Vitest + PG |
| W5 | Refresh cookie Max-Age follows `refresh_expires_in` | Vitest |

Plus: OpenAPI drift test, full backend suite on SQLite and PostgreSQL, web
typecheck, lint, unit and e2e tests, and mutation of the rotation guard,
the session check and the reuse branch (mutants must be killed by T4, T5, T8).

## 7. Security and privacy risks

* **Lock contention:** per-session only; refresh volume is tiny.
* **A missed `get_current_user` path:** every authenticated dependency goes through it; a test enumerates protected routes with a revoked session.
* **Token hashes in logs:** forbidden (T17).
* **Clock skew:** DB clock only.
* **Rotation memory:** see FD-3.
* **Rollback window:** re-opens BG-1 (FD-4).
* **Multi-replica web without sticky sessions:** forced logouts (safe, documented).

## 8. Founder decisions required

| # | Decision | Recommendation |
|---|---|---|
| FD-1 | USER idle / absolute limits | 7 days / 30 days; access 30 min unchanged |
| FD-2 | ADMIN limits | values to choose (example 8 h idle / 24 h absolute); MFA separately later |
| FD-3 | BFF rotation memory (accepted FE-001 SEC-001 trade-off) | keep it, shorten 120 s → 15 s, purge on logout and rejection |
| FD-4 | Migration `rollback_to_previous` | SAFE, with a rollback note that BG-1/BG-5 re-open |
| FD-5 | Expose `logout-all` now | yes for the backend endpoint; the UI entry can follow |
| FD-6 | Retry window | 30 s |

These become a D-entry only when the founder decides them. This contract
changes no canonical decision.

## 9. Delivery and evidence (for the implementation, once authorized)

Branch `claude/SEC-SESSION-001-session-lifecycle`; red tests first (T4 at
minimum), then the fix; CI 6/6 on the exact candidate SHA; the report gives:

* base, candidate and tree SHAs;
* changed files;
* migration id and declarations;
* the test matrix with real results (PG runs named);
* mutation results;
* residual risks;
* `DEPLOYMENT STATUS`.

Then the independent Codex audit on that exact SHA; the founder merges. No
deployment.
