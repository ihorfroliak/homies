# Code Quality & Logic Audit — Homies backend

**Date:** 2026-07-28 · **Auditor role:** Senior Software Engineer / Architect ·
**Scope:** whole repository (`C:\Users\ihorf\Projects\homies`), evidence-based.
**Method:** full source read of every backend module + infra/CI/docs, then real
checks executed locally.

**Executive verdict:** the *transactional money spine* is genuinely strong,
well-tested and hard to break; the *platform around it* (deploy, observability,
frontend, reproducibility) barely exists, and a handful of real logic defects sit
in the payment/currency path that will bite the moment real Stripe money flows.
Nothing is deployed, so none of this is causing harm today — but several findings
are latent production bugs, not style nits.

---

## Evidence — real checks executed (not static reading)

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check app tests alembic scripts` | **All checks passed** (ruff 0.15.20 in venv — note: pin says 0.15.22) |
| Unit + integration suite | `pytest -q` | **134 passed, 15 skipped** in 35s (skipped = Postgres-gated, no `TEST_DATABASE_URL` locally) |
| Test inventory | — | 147 test functions across 20 files + gated `stripe_live` |
| Typecheck | — | **not possible** — no mypy/pyright dep, no config (finding M9/CI) |
| Coverage | — | **not measured** — no pytest-cov (finding, Testing) |
| Build (Docker) | — | not run in CI; Dockerfile reviewed statically (finding M6) |
| Repo tree | `find infra data apps -type f` | **0 files** — all three are empty skeletons (finding M7) |

Runtime warnings observed during the suite (all reproducible):
`httpx`/starlette testclient deprecation; `HTTP_422_UNPROCESSABLE_ENTITY`
deprecation; one anyio path pointing at `Downloads\homies\...\.venv` (a **stale
duplicate repo copy** — workspace hygiene, verify).

---

## Executive Summary

- **Money correctness core:** double-entry ledger, balanced-and-no-zero-line
  enforcement, append-only at **two** layers (ORM event + DB trigger, owner-proof),
  Postgres exclusion constraint for no-double-booking, `FOR UPDATE` capture lock,
  post-payout escrow invariant. Validated by real multi-connection Postgres
  concurrency tests. This is the best part of the codebase and it is sound.
- **Real logic defects** cluster in the payment/currency edges: currency is never
  constrained yet the ledger sums balances currency-blind; the Stripe webhook
  discards the raw event on any handler exception; the Stripe intent idempotency
  key is random despite a comment claiming it is booking-derived; the external
  Stripe call runs inside a DB transaction holding a row lock.
- **Platform maturity is near zero:** never deployed, empty `infra/`, blind
  `/healthz`, no observability/tracing/structured logs, unpinned runtime deps, no
  typecheck/coverage/security-scan in CI, Docker runs as root, payments default to
  simulation with a live dev/test webhook endpoint always mounted.
- **Docs vs reality:** `README.md` describes PostGIS geo-search, Redis, Meilisearch,
  Kafka, k8s/Helm/Terraform/ArgoCD and a data platform — **none exist in code**. The
  internal `docs/` (PROJECT_STATE, DECISIONS, reviews) are, by contrast, accurate.

---

## Critical Issues

None *currently active* (nothing is deployed; payments run in simulation, so no real
money moves). The findings that would be Critical the day real Stripe is enabled are
promoted to the top of High below and marked ⚠️.

---

## High Priority Issues

### ⚠️ H1 — Currency is unconstrained but the ledger is currency-blind
- **Severity:** High (Critical once any non-PLN listing exists)
- **Files:** `app/modules/listings/schemas.py:12` (`currency` accepts any 3 chars),
  `app/modules/ledger/service.py:72-90` (`account_balance` / `all_balances`),
  `app/modules/payments/service.py:318` (I5 escrow invariant).
- **Problem:** `ListingCreate.currency` only validates `min_length=3, max_length=3`;
  `default_currency="PLN"` (config) is used **nowhere**. A booking carries the
  listing's currency into `Payment` and into every `JournalEntry`. But
  `account_balance(code)` sums `JournalLine.amount` for an account across **all
  currencies** — `JournalLine` has no currency column and the query has no currency
  filter.
- **Root cause:** single-currency was a *documented assumption* (DECISIONS "deferred:
  currency-scoped accounts") but was never *enforced in code*.
- **Conditions:** any host creates a listing with `currency != "PLN"` (e.g. `"USD"`),
  and a booking on it captures/refunds.
- **Production impact:** `booking_escrow` mixes USD minor units with PLN minor units
  in one integer sum. The I5 post-payout invariant (`account_balance(BOOKING_ESCROW)
  > 0 → abort`) becomes meaningless: it can falsely pass while real per-currency
  escrow is non-zero, or falsely abort a valid payout. Reconciliation and founder
  balances are silently wrong. This is *incorrect financial operations*.
- **Fix:** enforce `currency == settings.default_currency` at listing creation until
  multi-currency is really built; independently, add a `currency` column to
  `JournalLine` (or scope balances by the entry's currency) and make every balance /
  invariant query currency-scoped. Add a test that a non-PLN listing is rejected.
- **Confidence:** High (mechanism confirmed in code; not yet triggered by data).

### ⚠️ H2 — Stripe webhook discards the raw event on any processing exception
- **Severity:** High
- **File:** `app/modules/payments/router.py:56-104` (`stripe_webhook`).
- **Problem:** the handler does `db.add(WebhookEvent(...)); db.flush()` then dispatches
  to `service.process_intent_*`, and only `db.commit()`s at the very end (line 103).
  `flush` is not `commit`. If any handler raises (e.g. `process_charge_refunded`
  raises 409 "Refund after payout needs clawback flow", or `process_intent_succeeded`
  raises 409 for a payment not in `requires_payment`), the exception propagates, the
  `get_db` dependency closes the session **without committing**, and the whole
  transaction — **including the raw `WebhookEvent`** — is rolled back.
- **Root cause:** the "persist raw event for audit + idempotency" step shares one
  transaction with the ledger-affecting dispatch, so it is only durable on full
  success. The docstring's guarantee ("persists the raw event (audit)") is false for
  any failing event.
- **Conditions:** real Stripe mode; a `charge.refunded` after payout, or a late
  `payment_intent.succeeded` on an already-refunded/voided payment.
- **Production impact:** the event vanishes (no audit row), AND FastAPI returns the
  409 (a 4xx) to Stripe, which treats 4xx as "don't retry" and **drops the event
  permanently**. A post-payout Stripe refund thus leaves the ledger unreconciled with
  no record and no retry — the exact opposite of the intended trust/retry model
  (D-18).
- **Fix:** persist the raw `WebhookEvent` in its **own committed transaction** before
  dispatch (so audit is durable regardless of outcome); for trusted-but-unprocessable
  events return 5xx (retry) or 200-with-parked-status, never a silent 4xx drop; route
  "needs clawback" to a dead-letter/incident instead of raising 409.
- **Confidence:** High on mechanism; Medium on real-world frequency (stripe path not
  yet exercised — FIN-01 blocked on keys).

### ⚠️ H3 — Stripe PaymentIntent idempotency key is random, contradicting its own comment
- **Severity:** High
- **File:** `app/modules/payments/provider.py:90-98`.
- **Problem:** the comment says "the caller's booking id makes this safe to retry
  without duplicate charges", but the key is
  `f"pi_{host_account_id}_{amount}_{currency}_{uuid4().hex[:12]}"` — it embeds a
  **random UUID**, not the booking id. Two calls for the same booking produce
  different keys, so Stripe's idempotency provides no protection against
  application-level retries.
- **Root cause:** copy/comment drift; the intended key was never wired.
- **Conditions:** stripe mode; the booking transaction fails after
  `create_payment_intent` succeeds (network blip, DB commit failure), and the flow is
  retried.
- **Production impact:** orphaned PaymentIntents on rollback and, on retry, a second
  intent for the same booking → possible **double charge** / reconciliation drift.
  (SDK-internal network retries are still safe because they reuse the key within one
  call; the gap is app-level.)
- **Fix:** make the key deterministic and booking-scoped, e.g.
  `idempotency_key=f"pi_{booking.id}"` (pass `booking.id` into the provider). Add a
  gated stripe-live test asserting a repeat call returns the same intent.
- **Confidence:** High (code plainly contradicts the comment).

### H4 — External Stripe call executed inside the booking transaction while holding a row lock
- **Severity:** High (throughput) — latent until stripe mode + load
- **Files:** `app/modules/booking/router.py:54-103` (locks `Listing` `with_for_update`
  at line 55, commits at 102), `app/modules/payments/service.py:22-41`
  (`create_payment_for_booking` calls `provider.create_payment_intent`, a network
  call, at line 27).
- **Problem:** the network Stripe API call happens *between* acquiring the `FOR UPDATE`
  lock on the listing row and committing. The DB row lock + a pooled connection are
  held for the entire round-trip to Stripe.
- **Root cause:** side-effectful external I/O mixed into the DB transaction boundary.
- **Conditions:** stripe mode under concurrency; any Stripe latency spike.
- **Production impact:** all concurrent bookings of the same listing serialize behind
  one slow Stripe call (head-of-line blocking); connections are pinned during I/O,
  accelerating pool exhaustion (see M1). In simulation the call is instant, so this is
  invisible today.
- **Fix:** create the intent **outside** the row-locked section — either after commit
  (create booking `pending`, then create the intent and attach it in a short follow-up
  transaction), or move intent creation to a background step. Never hold a row lock
  across network I/O.
- **Confidence:** High on structure; impact reasoned (not load-tested).

---

## Medium Priority Issues

- **M1 — DB pool not sized against the threadpool.** `app/core/db.py:13` —
  `create_engine(..., pool_pre_ping=True)` with default pool (`size 5 + overflow 10 =
  15`). All endpoints are sync `def`, so Starlette runs them in a 40-token threadpool;
  two background workers also draw from the same pool. >15 concurrent DB requests
  block. *Fix:* set `pool_size`/`max_overflow`/`pool_recycle` explicitly and align with
  the threadpool + workers. Confidence: High.
- **M2 — Money stored as INT4, no DB CHECK constraints.** `total_amount`,
  `nightly_price_amount`, `amount` (bookings/listings/payments) and `journal_lines.amount`
  are `sa.Integer` (int4, ceiling ~2.147e9 minor units ≈ 21.4M PLN per value); no DB-level
  `CHECK (amount >= 0)` / `price > 0` (only Pydantic guards). *Fix:* migrate money columns
  to `BigInteger`; add CHECK constraints so a non-API writer can't post negatives. Confidence: High.
- **M3 — Public unauthenticated `/metrics`, `/docs`, `/openapi.json`, `/redoc`.**
  `app/main.py:103` + `app/core/ratelimit.py:77` (EXEMPT_PREFIXES). `/metrics` leaks
  business counters (bookings, payments, queue depth); interactive docs expose the full
  API surface in prod. *Fix:* gate docs off in prod, put `/metrics` behind network policy
  or auth. Confidence: High.
- **M4 — Runtime dependencies unpinned; builds non-reproducible.** `backend/pyproject.toml:10-22`
  uses `>=` lower bounds only, no lockfile, no hashes. The ruff-pin lesson (D-26) was not
  applied to runtime deps. Evidence: the local venv already floats (ruff 0.15.20 vs pinned
  0.15.22, pytest 9.x, httpx deprecation warning; `stripe>=9.0` while earlier work hit SDK
  15.x). *Fix:* add a lockfile (pip-tools/uv) with hashes; pin FastAPI/Pydantic/SQLAlchemy/Stripe
  to compatible ranges. Confidence: High.
- **M5 — Dev/test webhook endpoint always mounted in production.**
  `app/modules/payments/router.py:30-42` (`/v1/payments/webhook/simulated`). With the
  default `payment_provider="simulation"` (TD-03) a booking can be marked paid — moving the
  ledger — via this endpoint given the shared secret, with no real charge. SEC-02 forces a
  non-default secret in prod, but the endpoint still exists. *Fix:* register it only when
  `env in {local,test}` or `payment_provider=="simulation"` **and** never in production.
  Confidence: High.
- **M6 — Dockerfile: root user, app not actually installed, no healthcheck.**
  `backend/Dockerfile` — no `USER`; `RUN pip install .` runs before `COPY app` so setuptools
  finds no package (only dependencies are installed; the app runs via CWD import); no
  `HEALTHCHECK`. *Fix:* copy source before install (or install with `--no-deps` after copy),
  add a non-root `USER`, add a healthcheck. Confidence: High (structure); the container still
  runs, so impact is hardening + fragility, not an outage.
- **M7 — README + empty `infra/ data/ apps/` misrepresent the architecture.** `README.md`
  claims PostGIS geo-search, Redis cache/queues, Meilisearch, Kafka event bus, k8s/Helm/
  Terraform/ArgoCD, and an S3→DWH→dbt→BI data platform. `find infra data apps -type f` → **0
  files**; grep confirms Redis/Meili/NATS appear only as unused config URLs. *Fix:* rewrite the
  README to describe what exists; delete or clearly label empty skeletons. Confidence: High.
- **M8 — No real observability; blind health check.** `app/main.py:98` `/healthz` returns a
  static `{"status":"ok"}` and never touches the DB (its test, `tests/test_health.py`, only
  asserts "ok" → false confidence). No `/readyz`, no HTTP latency/status metrics middleware,
  no request/correlation id, no structured logging, no tracing/error-tracking. Only a few
  domain counters exist. *Fix:* the OBS-1 cycle already scoped in the project audit. Confidence: High.
- **M9 — CI gaps: no typecheck, coverage, dependency/secret/SAST scan, or image build.**
  `.github/workflows/ci.yml` runs lint + migrate + pytest (with real Postgres — good) but:
  no mypy, no coverage, no `pip-audit`/`gitleaks`/`bandit`/CodeQL, no Dependabot, and the
  Docker image is never built → a broken Dockerfile keeps CI green. *Fix:* add typecheck +
  coverage gate + dependency/secret scan + `docker build`. Confidence: High.

---

## Low Priority / Improvements

- **L1 — Dead infrastructure in compose.** `ops/docker-compose.yml` runs Redis, Meilisearch,
  NATS; none are imported anywhere (`grep` confirms). Resource + attack surface for nothing (TD-06).
- **L2 — `ensure_account` lazy-create race.** `ledger/service.py:30-37` — first-ever capture of a
  fresh account code can race two transactions → unique-violation 500 (self-heals afterwards).
  *Fix:* seed `provider_cash`/`booking_escrow`/`platform_revenue` in the migration.
- **L3 — Registration email TOCTOU.** `identity/router.py:55-64` — concurrent same-email registers
  both pass the existence check; one hits the unique constraint → 500 instead of 409. *Fix:* catch
  IntegrityError → 409.
- **L4 — `city.ilike(city)` passes raw wildcards.** `listings/router.py:80` — `%`/`_` in the query
  act as LIKE wildcards (parameterized, so not SQLi, just surprising results). *Fix:* escape
  wildcards or use equality/`=`.
- **L5 — No max stay length / far-future cap.** `booking/schemas.py` + `router.py:65` — `nights =
  (check_out - check_in).days` is unbounded → absurd totals and an int4 overflow path (see M2).
- **L6 — Reconciliation N+1 + unpaginated Stripe list.** `payments/reconciliation.py:20-68` runs 2
  count queries per payment; `stripe_ledger_reconciliation` uses `BalanceTransaction.list(limit=100)`
  with no pagination → only the last 100 compared but reported as match/mismatch. Also `orphan_payments`
  checks `booking_id is None`, impossible under the non-null FK (dead check).
- **L7 — Admin password passed as CLI arg.** `scripts/create_admin.py:19` — visible in `ps`/shell
  history. *Fix:* `getpass`/stdin/env.
- **L8 — Misc:** no access-token revocation or refresh-token reuse-detection or user-disable;
  version drift (`pyproject` 0.1.0 vs app 0.3.0); stale `alembic/env.py` docstring ("local dev uses
  create_all" — no longer true after TD-01); `make lint` lints `app tests` while CI lints
  `app tests alembic scripts` (scope mismatch can let migration/script lint errors reach CI).
- **L9 — SQLite tests use `create_all`, not migrations.** `conftest.py:33` — ORM/migration drift is
  only caught by the gated Postgres suite; that suite now runs in CI (CI-03), so it *is* covered, but
  a model change with a forgotten migration passes the whole fast suite.

---

## Architecture Review

- **Actual architecture:** FastAPI modular monolith. Composition only in `main.py`; one-way module
  deps (booking→listings/payments, payments→ledger/identity) as documented; cross-module integration
  via a DB-backed domain-event/outbox. Layering is clean: `router` (transport) → module `service`
  (application) → `ledger`/`provider` (domain/infra), with the ORM models as the persistence layer.
  No circular imports; the few in-function imports are deliberate (break import cycles / keep the
  simulation SDK-free).
- **Matches the claim?** The *internal* ADR/DECISIONS claims match the code. The *README* does not
  (M7). The "notifications is a separately deployed process" claim is aspirational — it's an in-process
  daemon thread today.
- **Scaling seams:** single-process assumptions are pervasive and *honestly documented* (D-14 in-process
  rate limiter, D-24 single-scheduler) — but there is no leader election, so running >1 instance
  multiplies rate limits and runs the expiry sweep N times (the row-guard keeps it *correct*, just
  wasteful). External I/O inside transactions (H4) is the main structural scaling defect.
- **Overengineering vs under:** appropriately minimal for a pilot (no MQ, no microservices). The only
  "extra shells" are the unused compose services (L1) and empty infra/data/apps trees (M7).

## Business Logic Review

- **Booking state machine:** `pending → confirmed → completed | cancelled | expired | payment_failed`.
  Transitions are guarded (cancel only from pending/confirmed, complete only from confirmed, check-in
  only from confirmed/checked_in). Idempotent creation via `(guest_id, idempotency_key)` unique +
  replay short-circuit. Date validation correct (`check_out > check_in`, no past check-in). Solid.
- **Payment/expiry race:** the late-success path (capture-then-auto-refund for cancelled/expired) plus
  the row-guarded atomic `UPDATE ... WHERE status='pending'` sweep make "payment commits just after
  expiry" safe (no PAID+EXPIRED, escrow nets to zero). This is the strongest logic in the repo and is
  covered by real Postgres concurrency tests.
- **Idempotency:** booking (unique key), domain events (`dedup_key` unique), webhook (`stripe_event_id`
  unique + `FOR UPDATE` on the payment row), notification delivery (stable idem key). Good — except the
  Stripe *intent* key (H3) and the webhook event-loss on exception (H2).
- **Timezones/dates:** consistently tz-aware (`datetime.now(timezone.utc)`), with explicit SQLite
  tz-normalization helpers (`_aware`, refresh-token tz fix). No naive/aware mixing found.
- **Financial math:** integer minor units throughout; fee = `amount * bps // 10_000` (floor — the
  platform never over-credits itself; host rounding favours the host, acceptable and consistent). The
  zero-line guard prevents a zero fee line. The one real math hazard is currency-blindness (H1).

## Backend & API Review

- Consistent `/v1` prefix, tag-per-module, generated + drift-guarded OpenAPI. Request/response validation
  via Pydantic v2 with sane bounds. Auth = HS256 JWT (access) + rotating hashed refresh tokens; RBAC via
  `require_role`. Object-level authz is enforced per-resource (booking parties/admin) and is IDOR-probe
  covered.
- Error handling is mostly correct HTTP semantics; the notable exception is the webhook 4xx-drop (H2)
  and the pattern of raising 409 from webhook handlers (Stripe won't retry).
- No SSE/WebSocket. Rate limiting is well-designed (see Security). Timeouts: **no outbound HTTP timeout**
  is set for the Stripe SDK calls (default SDK timeout applies) — combined with H4 this compounds the
  head-of-line risk. Resilience: workers isolate per-row failures and never die on one iteration (good).

## Frontend Review

- **No production frontend exists.** `apps/` is empty; `frontend/design-system/` is a framework-agnostic
  HTML/CSS/JS showcase (tokens + components), browser-verified, explicitly *not* a running app. Therefore
  state management, async flows, caching, optimistic updates, re-renders, offline behaviour, etc. are
  **N/A — nothing to review**. This is itself the finding: the client tier is unbuilt (consistent with
  PROJECT_STATE). No CORS is configured on the API, which is a safe default but must be added when a
  browser client appears.

## Database Review

- **Schema:** single Alembic migration, well-formed. FKs on all real relationships; unique constraints
  where needed (`users.email`, `payments.booking_id`, `payments.provider_intent_id`,
  `domain_events.dedup_key`, `webhook_events.stripe_event_id`, `bookings(guest_id,idempotency_key)`).
  Indexes on hot lookups + `payment_expires_at` for the sweep. Nullability is deliberate and correct.
- **Integrity guards:** btree_gist exclusion constraint `excl_booking_overlap` with predicate
  `status IN ('pending','confirmed')` — **matches** the app's `BLOCKING_STATUSES` (verified). DB triggers
  make `journal_entries/journal_lines/audit_log/domain_events` append-only for *every* role (owner-proof) —
  the standout DB-integrity feature.
- **Gaps:** money columns are int4 (M2); no CHECK constraints on amounts/dates; ledger accounts created
  lazily rather than seeded (L2); no partial index tuned for the expiry sweep predicate (minor). `all_balances`
  uses an outer join + group-by (fine); reconciliation is N+1 (L6). No N+1 in the request hot paths worth
  flagging beyond `my_bookings` doing one payment lookup per booking (bounded by a user's own bookings).

## Testing Review

- 147 test functions; genuinely green when run (134 passed / 15 skipped locally; the 15 are Postgres-gated
  and run in CI where a `postgres:16` service is provided). Real adversarial + concurrency coverage on a real
  engine (12-thread double-booking → 1, 10 webhook deliveries → 1 capture, concurrent expiry → 1). Security
  authz has 12 IDOR probes. Failure paths (late-success refund, retry/dead-letter, invalid signature) are
  tested. This is above-average for a pilot.
- **Gaps:** no coverage measurement (untested branches invisible); no typecheck; the real-Stripe path
  (`stripe_live`) is gated and unverified (FIN-01 blocked on keys), so H2/H3/H4 are reasoned from code, not
  proven by a run; `test_health.py` asserts a static "ok", giving false confidence in a health check that
  doesn't check anything (M8). CI does run the critical suites incl. Postgres — the quality gates it lacks are
  typecheck/coverage/security-scan/image-build (M9).

## Security Review

- **Strong:** scrypt password hashing with `hmac.compare_digest`; JWT type/exp checks; refresh-token rotation
  (hashed at rest, single-use); RBAC + per-object authz (IDOR-proof, probe-tested); token-bucket rate limiting
  with per-policy fail-open/closed and a failures-only account bucket (no lockout DoS); X-Forwarded-For only
  trusted per `TRUST_PROXY_HOPS`; fail-fast secret validation (SEC-02) that names fields never values;
  payment-environment agreement model; append-only audit at the DB level; webhook signature trust boundary
  with correct 400-vs-5xx split. SQL is fully parameterized (SQLAlchemy) — no injection found.
- **Weaknesses:** public `/metrics` + interactive docs in prod (M3); the always-mounted simulated webhook (M5);
  container runs as root (M6); no dependency/secret scanning (M9); no access-token revocation / refresh-reuse
  detection / user-disable (L8); admin-create leaks the password via argv (L7). No XSS/CSRF surface (JSON API,
  bearer tokens, no cookies, no server-rendered HTML). SSRF: the only outbound calls are to Stripe (fixed host).
  No CORS configured (safe default).

## DevOps / CI/CD Review

- **CI:** solid where it exists — real Postgres service, migration-first, health-checked, lint + full suite,
  plus a contracts job (Spectral + AsyncAPI). Missing: typecheck, coverage, dependency/secret/SAST scanning,
  Dependabot, and any `docker build` (M9).
- **Deploy:** **none.** `infra/{helm,k8s,terraform}` are empty; there is no prod compose, no deploy workflow,
  no rollback automation. `ensure_schema()` correctly *verifies* (not creates) schema outside local, which is a
  good migration-safety posture — but there's no pipeline that runs `alembic upgrade head` before boot in a real
  environment yet.
- **Config/secrets:** env-driven via pydantic-settings; SEC-02 refuses insecure prod secrets. No secrets manager
  integration (expected — nothing deployed).
- **Runtime ops:** graceful shutdown of workers via lifespan (`stop()` + `join(timeout=5)`) — good. No liveness/
  readiness distinction, no HEALTHCHECK in the image, no backup/restore automation (a manual DR drill is
  documented, not scheduled).

---

## Positive Findings (what is genuinely well done)

1. **Owner-proof append-only ledger** — enforced at both ORM and DB-trigger level; corrections are compensating
   entries. Rare to see done properly.
2. **No-double-booking is a DB invariant**, not application logic — TOCTOU-proof exclusion constraint whose
   predicate matches the app's blocking statuses.
3. **Payment concurrency is real** — `FOR UPDATE` capture lock + row-guarded expiry, proven by multi-connection
   Postgres tests, not SQLite theatre.
4. **Idempotency everywhere it matters** (booking, events, webhook, delivery) with honest at-least-once framing.
5. **Rate limiting is thoughtfully designed** — per-policy failure semantics, no account-lockout DoS, correct
   proxy-trust model.
6. **Secret fail-fast + payment-environment model** prevent the classic "prod on fake money / live keys on a
   laptop" mistakes.
7. **Alembic single source of truth**, migration-first CI on real Postgres; generated + drift-guarded OpenAPI.
8. **Clean, readable, consistently-styled code** with genuinely useful comments that explain *why*; disciplined
   timezone handling; lint clean; tests actually pass.
9. **Internal docs (PROJECT_STATE/DECISIONS/BUILD_HISTORY/reviews) are accurate and evidence-based** — a real
   asset (only the public README drifted).

---

## Recommended Action Plan

### 1. Immediate fixes (before any real Stripe money or deploy)
- **H1** enforce single currency (reject non-PLN listings) — one validator + one test. Blocks a financial-integrity
  bug at negligible cost.
- **H2** persist the raw webhook event in its own committed transaction before dispatch; stop returning silent 4xx
  for trusted-but-unprocessable events.
- **H3** make the Stripe intent idempotency key `pi_{booking.id}` (deterministic, booking-scoped).
- **M5** stop mounting `/payments/webhook/simulated` in production.
- **M3** disable interactive docs and protect `/metrics` in prod.

### 2. Short-term improvements
- **H4** move the Stripe intent creation out of the row-locked booking transaction.
- **M1** size the DB pool; **M2** migrate money columns to BigInteger + add CHECK constraints.
- **M4** add a dependency lockfile with hashes; pin runtime deps.
- **M9** add typecheck + coverage gate + `pip-audit`/`gitleaks` + `docker build` to CI; **M6** non-root container +
  healthcheck.
- **M8 / OBS-1** real `/healthz`+`/readyz` (DB check), HTTP metrics, structured logs with a request id.
- **M7** rewrite the README to match reality; remove/label empty skeletons; **L1** drop unused compose services.

### 3. Long-term improvements
- Multi-currency ledger (currency-scoped accounts/balances) if the business needs it.
- Chargeback/dispute + clawback flow (removes the H2 409 dead-end); external Stripe reconciliation with pagination (L6).
- Shared rate-limit store + scheduler leader election before running >1 instance (D-14/D-24).
- Deploy pipeline (migrate-then-boot), rollback strategy, scheduled backups; then build the Product A frontend from the
  design-system contract.
- Access-token revocation / refresh-reuse detection / user-disable; move off root-argv admin creation.

---

## Scores (justified, not fabricated)

| Dimension | Score | Basis |
|---|---|---|
| **Overall Code Quality** | **8/10** | Clean, readable, consistent, genuinely useful comments, lint-clean, tests pass. Minus: a few dead checks, no static typing, some doc/comment drift (H3, env.py). |
| **Architecture** | **7/10** | Excellent module/ledger/event design and honest scaling notes. Minus: README/infra fiction, external I/O inside transactions (H4), single-process assumptions, no client tier. |
| **Business Logic Correctness** | **7/10** | Money spine strong and concurrency-proven. Minus: currency-blind ledger (H1), webhook event-loss (H2), random intent key (H3). |
| **Test Coverage & Reliability** | **7/10** | Broad, adversarial, real-Postgres concurrency, actually green. Minus: no coverage metric, no typecheck, real-Stripe path unverified. |
| **Security** | **7/10** | Strong authn/authz/rate-limit/secret-fail-fast/append-only audit, IDOR-proven, no injection. Minus: public /metrics+/docs, root container, sim-webhook surface, no scanning. |
| **Production Readiness** | **4/10** | Never deployed; empty infra; blind health check; no observability/tracing/backups/rollback; unpinned deps; payments default to simulation. The core is ready; the platform is not. |

**Bottom line:** this is a well-engineered *transactional core* wrapped in an *unbuilt platform*. Fix H1–H3 and M5/M3
before anyone touches real money; the rest is a normal hardening runway. The internal engineering discipline
(evidence-based docs, adversarial tests, DB-level invariants) is well above typical solo-project standard — the gap is
breadth (deploy, observability, frontend, reproducibility), not depth of the money code.

_No code was modified during this audit. All findings are read-confirmed or check-confirmed; items reasoned from
un-exercised paths (stripe mode) are labelled as such._
