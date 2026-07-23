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

**MC-01 — SEC-01 rate limiting + SEC-02 fail-fast secrets — complete.**
Design + implementation + 31 tests. Output:
[perimeter design](design/sec-01-02-perimeter.md).

**Next proposed cycle:** not started — awaiting approval. Recommendation in the
report below (`FIN-01` real Stripe sandbox run, or `BK-01` auto-void).

## Completed cycles

Phase 0 skeleton · D4 vertical slice · D5 hardening · D6 warfare · D7 readiness
board (NO-GO) · D8 release loop + Alembic + DB append-only · D9 disaster
recovery drill · B1 Stripe Connect adapter · OAT-01 business acceptance ·
OAT-02 notification layer · OAT-03 outbox + reliable delivery · CI packaging fix ·
AUDIT-01. Full detail in [BUILD_HISTORY.md](BUILD_HISTORY.md).

## Health

| Signal | Value |
|---|---|
| Tests | **84 passing** (unit, integration, business/OAT, security probes, rate limiting, secret config) |
| Lint | ruff clean (`app tests alembic scripts`) |
| CI | ✅ green on `main` (backend + contracts) |
| Warfare (manual) | all verdicts pass; 1 known gap (ghost booking) |
| DR drill (manual) | backup + restore + financial reconciliation verified |
| Deployment | **none** — nothing is deployed anywhere |
| Frontend | **none** — `apps/` is empty |

## Known issues (top, full list in the audit)

- ~~SEC-01 (P0) no rate limiting~~ — **closed** in MC-01.
- ~~SEC-02 (P0) dev-default secrets fail open~~ — **closed** in MC-01.
- **FIN-01 (P0)** Stripe path never run against a real sandbox — **only remaining P0**.
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
