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

**TD-01 — Alembic single schema source of truth — complete.** `create_all`
removed from app startup and the ops script; `ensure_schema()` applies
migrations in local dev and verifies head elsewhere (fails loudly if not
migrated); the Docker image ships migrations; live app now boots via migrations.
A Postgres migration/integration test suite (gated by `TEST_DATABASE_URL`)
validates the real schema. [TD-01 design](design/td-01-schema-source-of-truth.md),
D-28/D-29. **Next: CI-03 — real Postgres service in CI** (phase 2 of this task).

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
| Tests | **134 passing** on SQLite / **142** with Postgres, 1 gated Stripe suite |
| Lint | ruff clean (`app tests alembic scripts`), ruff pinned 0.15.22 |
| CI | ✅ green on `main` (backend + contracts) — Postgres service pending CI-03 |
| Warfare (manual) | all verdicts pass |
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
- **OBS-01 (P1)** `/healthz` does not check the database.
- **CI-03 (P1)** CI has no Postgres service yet — Postgres migration/concurrency
  tests skip in CI (next phase of this task).
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

CI-03 — add a real Postgres service to CI (phase 2 of the current task) so the
migration/concurrency/DB-guard tests run against the real engine instead of
skipping.
