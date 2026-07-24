# PROJECT STATE

Single place to answer "where are we right now". Updated after every completed
micro-cycle. Companions: [BUILD_HISTORY.md](BUILD_HISTORY.md) (what happened),
[DECISIONS.md](DECISIONS.md) (why), [RELEASE.md](../RELEASE.md) (release gate).

**Last updated:** 2026-07-24 · **Branch:** `main` · CI green

## Current phase

**Pilot hardening.** Transactional core is built and adversarially tested; the
perimeter (rate limiting, secrets, real payments) is not. Gate target:
Gate 1 — first safe production booking.

## Current cycle

**TD-01 + CI-03 — complete.**
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
| Tests | **148 passing** (SQLite unit + real-Postgres migration/concurrency), 1 gated Stripe suite |
| Lint | ruff clean (`app tests alembic scripts`), ruff pinned 0.15.22 |
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
- **OBS-01 (P1)** `/healthz` does not check the database.
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
