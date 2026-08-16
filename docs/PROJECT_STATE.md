# PROJECT STATE

Single place to answer "where are we right now". Updated after every completed
micro-cycle. Companions: [BUILD_HISTORY.md](BUILD_HISTORY.md) (what happened),
[DECISIONS.md](DECISIONS.md) (why), [RELEASE.md](../RELEASE.md) (release gate).

**Last updated:** 2026-08-05 · **Branch:** `main` · CI green

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
- **M9b**: supply-chain and build gates. CI now audits declared dependencies,
  scans full history for secrets, **builds the image** (never built before,
  though TD-01 made its contents load-bearing) and enforces a coverage floor.
  The 5 CVEs found were all in `pip` itself and are deliberately outside the
  gate; runtime dependencies are clean. D-36.
- **OBS-01**: readiness/liveness split. `/readyz` checks the database and
  returns 503; `/healthz` deliberately does not, because a failing liveness
  probe restarts the container and would turn one database outage into a
  fleet-wide crash loop. Writing the test exposed that nothing bounded the
  TCP connect. D-37.
- **OBS-02/03**: HTTP metrics (latency, status class, throughput by route
  template) and business event counters on the money/booking funnel. Money is
  deliberately absent from Prometheus - it stays in the ledger (D-38).
- **OBS-07**: `GET /v1/admin/kpi` answers GMV, refunds, recognised commission,
  payouts, take/refund rate, nights and ADR from the ledger. Still unanswerable
  and declared as such in the payload: CM2 (no cost data), occupancy (no
  availability model), NPS/CSAT, CAC/runway/DSO, chargebacks (FIN-03). D-40.
- **OBS-06**: Prometheus and Alertmanager now run in the stack and 11 alert rules
  exist, every one unit-tested by promtool in CI. Nothing alerts at zero traffic
  by design. Alert *delivery* is still unconfigured - OBS-08. D-39.

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
| Tests | **192 passing** SQLite-only (Postgres suites add 18 in CI), 1 gated Stripe suite |
| Lint | ruff clean (`app tests alembic scripts`), ruff pinned 0.15.22 |
| Typecheck | **mypy clean** on `app/` - blocking CI gate, pinned 2.3.0 (D-35) |
| Coverage | **85.8% branch** on `app/`, gated at 80 (M9b) |
| Supply chain | pip-audit clean on declared deps · gitleaks on full history · image built in CI |
| CI | ✅ green on `main` — backend job runs a real postgres:16 service (migration-first) |
| Concurrency | validated on **real Postgres** in CI (double-book→1, webhook→1 capture, expiry→1) |
| Observability | HTTP + business metrics **scraped by Prometheus**; 11 alert rules, all promtool-tested in CI |
| Alert delivery | ⚠️ **nowhere** — Alertmanager routes to a local sink; the real destination is a founder decision |
| Adversarial harnesses | ✅ **re-verified on the live stack** — warfare 7/7, refund_warfare, live_smoke; recon ok=true, grand_total=0 |
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
- ~~M9b (Medium) no supply-chain or build gates~~ — **closed** (D-36).
- **M9c (Low, not started)** branch protection is still not configured: the
  gates are enforceable but nothing *requires* them to pass before a merge to
  `main`. This is a GitHub repo setting, not code — it needs the repo owner.
- ~~OBS-01 (P1) blind health check~~ - **closed**: `/readyz` checks the database,
  `/healthz` deliberately does not (D-37).
- ~~OBS-02 (P1) no HTTP metrics~~ - **closed** (latency, status class, throughput
  by route template).
- **OBS-03 (P1) closed together with OBS-07**: event counts (registrations, bookings by
  outcome, payments, payouts) now exist. **Monetary KPIs deliberately do not** -
  GMV/commission/net revenue must come from the ledger, not a resettable
  counter (D-38) - they are answered by the KPI endpoint instead (D-40).
- ~~OBS-07 (P1) no ledger-backed KPI queries~~ - **closed**: `GET /v1/admin/kpi`
  answers the monetary rows from the ledger (D-40). The endpoint also returns an
  `unavailable` list naming what it cannot compute and what would unblock it.
- ~~OBS-06 (P2) nothing scrapes `/metrics`~~ - **closed**: Prometheus + Alertmanager
  in compose, 11 tested alert rules, readiness exposed as `homies_database_up`.
- **OBS-08 (P1, new)** alerts are delivered **nowhere**. Alertmanager points at a
  local sink; picking the real channel (email/Telegram/PagerDuty) is a founder
  decision with account and cost implications. Until it is set, a `page` alert
  fires into a void.
- **WAR-01** (still true, now re-confirmed by running them) the warfare harnesses
  cannot run unmodified since MC-01: the
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

Awaiting approval. Ranked candidates: OBS-08 real alert destination (needs a
founder choice) · M9c branch protection (owner action) · real Product A frontend (React/Expo from
the design-system contract) · FIN-01 (needs Stripe test keys).
