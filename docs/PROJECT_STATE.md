# PROJECT STATE

Single place to answer "where are we right now". Updated after every completed
micro-cycle. Companions: [BUILD_HISTORY.md](BUILD_HISTORY.md) (what happened),
[DECISIONS.md](DECISIONS.md) (why), [RELEASE.md](../RELEASE.md) (release gate).

**Last updated:** 2026-07-23 · **Commit:** `ea35259`+ · **Branch:** `main`

## Current phase

**Pilot hardening.** Transactional core is built and adversarially tested; the
perimeter (rate limiting, secrets, real payments) is not. Gate target:
Gate 1 — first safe production booking.

## Current cycle

**TST-01 — OpenAPI contract alignment — complete.** The HTTP contract is now
code-generated (`docs/api/openapi.json`, 35 paths) with a pytest drift-guard;
the three drifted hand-written specs are retired. Contract can no longer rot.
[api/README](api/README.md), D-27.

**Previous: MC-03 (BK-01) + UI-01.**
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
| Tests | **132 passing**, 1 skipped (gated Stripe Test Mode suite) |
| Frontend | design-system showcase in `frontend/design-system/` (runnable, no framework yet); `apps/` still empty |
| Lint | ruff clean (`app tests alembic scripts`) |
| CI | ✅ green on `main` (backend + contracts) |
| Warfare (manual) | all verdicts pass; 1 known gap (ghost booking) |
| DR drill (manual) | backup + restore + financial reconciliation verified |
| Deployment | **none** — nothing is deployed anywhere |
| Frontend | **none** — `apps/` is empty |

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
- **NEW (from MC-01):** rate-limit counters are per-process; deploying >1 instance
  weakens every limit (D-14). Warfare harnesses must run with `RATE_LIMIT_ENABLED=false`.
- **BK-01 (P1)** unpaid bookings block inventory forever (no auto-void).
- **TD-01 (P1)** dual schema path (create_all locally, Alembic in prod).
- **TST-01 (P1)** OpenAPI contracts drifted from implementation.
- **OBS-01 (P1)** `/healthz` does not check the database.

## Security risks

Perimeter partially closed: **rate limiting and secret fail-fast now exist**
(MC-01). Still open: no MFA (SEC-05), no email verification (SEC-03), no account
lockout policy beyond throttling (SEC-04). Object-level authorization is
**verified sound** (12/12 IDOR probes). Product B (free listings) will multiply the attack surface and must not
launch before rate limiting + moderation exist.

## Technical debt

TD-01 dual schema path · TD-02 contract drift · TD-03 simulation default ·
TD-06 dead infrastructure (Redis/Meilisearch/NATS running, unused) ·
TD-08 documentation-to-code ratio inverted.

## Next action

Founder decision on two items, then implement:

1. Approve micro-cycle `SEC-01`+`SEC-02` (rate limiting + secret fail-fast).
2. Resolve the **sequencing conflict** between operator-first (locked strategy)
   and free-marketplace-first (new master prompt) — see audit §17.
