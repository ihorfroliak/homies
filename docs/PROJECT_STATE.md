# PROJECT STATE

Single place to answer "where are we right now". Updated after every completed
micro-cycle. Companions: [BUILD_HISTORY.md](BUILD_HISTORY.md) (what happened),
[DECISIONS.md](DECISIONS.md) (why), [RELEASE.md](../RELEASE.md) (release gate).

**Last updated:** 2026-08-04 · **Branch:** `main` · CI green

## Current phase

**Pilot hardening.** Transactional core is built and adversarially tested; the
perimeter (rate limiting, secrets, real payments) is not. Gate target:
Gate 1 — first safe production booking.

## Current cycle

**Audit remediation — all 4 High findings complete.** A read-only technical code audit
([2026-07-28](reviews/2026-07-28-technical-code-audit.md)) found 4 High / 9
Medium / 9 Low. Fixing them in priority order, one cycle each.
- **H1**: listing creation now rejects any currency but `settings.default_currency`.
  The ledger sums balances across currencies with no scoping, so a non-PLN
  listing silently corrupted escrow math and made invariant I5 meaningless.
- **H2**: the raw Stripe webhook event is committed in its own transaction
  **before** dispatch. It previously shared the handlers' transaction, so a
  handler failure erased the audit record — reproduced (unknown intent → 404,
  zero rows), then proven closed with the same script. `processed_at IS NULL`
  is now the dead-letter marker. D-31/D-32.
- **H3**: the Stripe intent idempotency key is derived from the booking id. It
  embedded a `uuid4()` despite a comment claiming otherwise, so Stripe's
  idempotency protected nothing and a retry could charge a guest twice. D-33.
- **H4**: the provider call now runs after the booking commits, so a slow
  Stripe no longer blocks every other booking of that listing. A booking whose
  provider call failed is healed by a replay; otherwise its TTL frees the dates.
  D-34.
- **All 4 High findings closed.**
- **M9a (CI-04)**: mypy is now a **blocking** CI gate. It paid for itself
  immediately — a missing migration directory used to be reported as a verified
  schema, so an app with no tables at all would start serving. Three latent
  None-handling gaps fixed alongside it. D-35.
- Next: **M9b** — supply-chain and build gates (pip-audit, gitleaks,
  `docker build`, Dependabot, coverage threshold). Already measured: 5 CVEs, all
  in `pip` itself with runtime dependencies clean; coverage 88%.

**Previous: TD-01 + CI-03.**
- TD-01: Alembic is the single schema source of truth; `create_all` removed;
  `ensure_schema()` (apply in local, verify elsewhere); image ships migrations.
- CI-03: CI now runs a real **postgres:16** service (health-checked,
  migration-first). 4 real concurrency tests validate double-booking,
  webhook idempotency, expiry and payment-vs-expiry with true row locks —
  the authoritative concurrency evidence (SQLite could not model it).
  [TD-01 design](design/td-01-schema-source-of-truth.md), D-28/29/30.

**Previous: TST-01, MC-03 (BK-01), UI-01.**
- BK-01: unpaid-booking TTL + first scheduler; ghost-booking DoS closed.
  [design](design/bk-01-booking-expiry.md).
- UI-01: framework-agnostic design system + runnable web/mobile showcase in
  `frontend/design-system/` (no frontend framework existed; this is the token +
  component contract a future React/Expo app consumes). Browser-verified.
  [DESIGN_SYSTEM](design/DESIGN_SYSTEM.md), [PRODUCT_UX](design/PRODUCT_UX.md),
  [ANALYTICS_EVENTS](design/ANALYTICS_EVENTS.md).

**Next:** awaiting approval — no cycle started (see remaining priorities in the
final report / audit).

## Completed cycles

Phase 0 skeleton · D4 vertical slice · D5 hardening · D6 warfare · D7 readiness
board (NO-GO) · D8 release loop + Alembic + DB append-only · D9 disaster
recovery drill · B1 Stripe Connect adapter · OAT-01 business acceptance ·
OAT-02 notification layer · OAT-03 outbox + reliable delivery · CI packaging fix ·
AUDIT-01. Full detail in [BUILD_HISTORY.md](BUILD_HISTORY.md).

## Health

| Signal | Value |
|---|---|
| Tests | **172 passing** on real Postgres (156 SQLite-only), 1 gated Stripe suite |
| Lint | ruff clean (`app tests alembic scripts`), ruff pinned 0.15.22 |
| Typecheck | **mypy clean** on `app/` - blocking CI gate, pinned 2.3.0 (D-35) |
| Coverage | 88% measured, not yet gated (M9b) |
| CI | ✅ green on `main` — backend job runs a real postgres:16 service (migration-first) |
| Concurrency | validated on **real Postgres** in CI (double-book→1, webhook→1 capture, expiry→1) |
| DR drill (manual) | backup + restore + financial reconciliation verified |
| Deployment | **none** — nothing deployed |
| Frontend | design-system showcase only (`frontend/design-system/`); `apps/` empty, no React/Expo app |

## Known issues (top, full list in the audit)

- ~~SEC-01 (P0) no rate limiting~~ — **closed** in MC-01.
- ~~SEC-02 (P0) dev-default secrets fail open~~ — **closed** in MC-01.
- **FIN-01 (P0)** Stripe Test Mode still not exercised — **blocked on credentials, not on code**.
  Webhook/signature path is now validated against the real SDK; API-calling
  scenarios are written and gated (`make test-stripe`).
- ~~BK-01 (P1) ghost booking~~ — **closed** in MC-03 (TTL + expiry scheduler).
- **FIN-03 (P1)** no chargeback/dispute representation in the ledger.
- **REC-01 (P1)** no Stripe-side reconciliation (orphaned payments, missing
  webhooks, payout mismatch are undetectable).
- ~~TST-01 (P1) OpenAPI drift~~ — **closed** (generated spec + drift guard).
- ~~TD-01 (P1) dual schema path~~ — **closed** (Alembic single source).
- ~~CI-03 (P1) no Postgres in CI~~ — **closed** (postgres:16 service, concurrency validated).
- ~~H1 (High) currency-blind ledger~~ — **closed** (single supported currency).
- ~~H2 (High) webhook event lost on dispatch failure~~ — **closed** (persist before dispatch).
- ~~H3 (High) random Stripe idempotency key~~ — **closed** (booking-scoped key).
- ~~H4 (High) Stripe call inside the row-locked transaction~~ — **closed**
  (provider call moved after commit; proven with a falsifiable Postgres test).
  **All four High findings from the 2026-07-28 audit are now closed.**
- ~~M9a (Medium) no typecheck in CI~~ — **closed** (blocking mypy gate, D-35).
- **M9b (Medium)** CI still has no dependency/secret scanning, no `docker build`
  and no coverage threshold: a broken Dockerfile or a vulnerable dependency
  still passes a green build.
- **OBS-01 (P1)** `/healthz` does not check the database.
- **WAR-01** the warfare harnesses cannot run unmodified since MC-01: the
  register/login rate limit rejects their bulk user creation
  (`RATE_LIMIT_ENABLED=false` is required). The harness bootstrap also assumes
  a `homies-api-1` container.
- rate-limit counters are per-process; >1 instance weakens limits (D-14).

## Security risks

Perimeter partially closed: **rate limiting and secret fail-fast now exist**
(MC-01). Still open: no MFA (SEC-05), no email verification (SEC-03), no account
lockout policy beyond throttling (SEC-04). Object-level authorization is
**verified sound** (12/12 IDOR probes). Product B (free listings) will multiply the attack surface and must not
launch before rate limiting + moderation exist.

## Technical debt

TD-03 simulation default (real Stripe pending keys) · TD-06 dead infrastructure
(Redis/Meilisearch/NATS in compose, unused) · TD-08 docs-to-code ratio inverted ·
AsyncAPI catalog drifted from emitted events (separate follow-up).

## Next action

Awaiting approval. Ranked candidates: CI-04 static typecheck · branch protection
+ dependency/secret scanning · OBS-01 real health/DB check · real Product A
frontend (React/Expo from the design-system contract) · FIN-01 (needs Stripe
test keys).
