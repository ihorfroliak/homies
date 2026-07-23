# Full System Audit — Homies Rental Marketplace Platform

**Date:** 2026-07-23 · **Commit audited:** `ea35259` (main) · **Mode:** AUDIT ONLY,
no production implementation performed.

Prior audits reused rather than repeated (still valid, verified against current
code): [D7 Production Readiness Board](2026-07-05-d7-production-readiness-board.md),
[D6 Warfare](../design/d6-warfare-report.md), [OAT-01](2026-07-06-oat-01-report.md),
[OAT-02](2026-07-06-oat-02-report.md), [OAT-03](2026-07-09-oat-03-report.md),
[EA Review](2026-07-05-ea-review-part1-perspectives.md).
New evidence gathered this cycle: endpoint inventory, debt-marker scan,
**12 executable IDOR/authz probes** (`backend/tests/test_security_authz.py`),
clean-venv CI reproduction.

---

## 1. Executive Summary

Homies is a **modular-monolith backend** (FastAPI + PostgreSQL) with a
production-shaped **transactional core**: bookings, payments, double-entry
ledger, outbox-backed notifications. The money and concurrency core is the
strongest part of the system and is backed by executable evidence — double
booking is physically impossible at the DB level, webhooks are idempotent under
200× concurrency, the ledger balances to zero after adversarial runs and after a
restore drill.

The weakest parts are **product breadth and operations**: a rental marketplace
today has no photos, no geo-search, no reviews, no messaging, no disputes, and
no frontend of any kind. **Product B (free listings marketplace) does not exist
at all — 0% implemented.**

Security posture is better than expected at the object level (12/12 authz probes
pass, no IDOR found) but has a **hard perimeter gap: no rate limiting anywhere**
and **dev-default secrets that fail open**.

**Headline verdict:** the transactional spine is trustworthy; the product around
it is an early skeleton. Nothing is blocked by architecture — the modular
monolith has clean seams for everything missing.

### Scorecard (evidence-based)

| Dimension | Score | Basis |
|---|---:|---|
| Financial integrity | 78 | double-entry + invariants + warfare + restore drill |
| Concurrency safety | 82 | DB exclusion constraint, FOR UPDATE, 200× webhook proof |
| Object-level security (authz) | 85 | 12/12 probes pass, no IDOR |
| Perimeter security | 30 | no rate limiting, dev-default secrets, no MFA, no email verification |
| Product completeness (Product A) | 35 | core booking works; photos/search/reviews/messaging absent |
| Product completeness (Product B) | 0 | not started |
| Testing | 62 | 53 tests, strong unit/integration/business; no contract/load/E2E |
| CI/CD | 55 | green build+lint+test+contract-lint; no scanning, no branch protection |
| Observability | 25 | notification metrics only; healthz doesn't check DB |
| **Overall production readiness** | **~50** | up from 22 (D7) |

---

## 2. Current Architecture

```
homies/ (monorepo, trunk-based, main only)
├─ backend/                  FastAPI modular monolith (2 746 LOC app, 1 500+ LOC tests)
│  ├─ app/core/              config, db, security (JWT/scrypt/RBAC), audit
│  ├─ app/modules/
│  │   ├─ identity/          users, host profiles, refresh tokens
│  │   ├─ listings/          listings + host date blocks
│  │   ├─ booking/           availability (interval model), booking lifecycle
│  │   ├─ payments/          provider seam (Stripe Connect | simulation), webhooks, payouts
│  │   ├─ ledger/            double-entry accounts, journal, reconciliation
│  │   ├─ events/            domain events, outbox, worker, templates, providers, metrics
│  │   └─ admin/             read-only ops surface + incidents
│  ├─ alembic/               single initial migration (schema source of truth)
│  ├─ scripts/warfare/       adversarial harnesses (manual)
│  └─ scripts/backup/        DR backup/restore/drill (manual)
├─ docs/                     charter, strategy, business arch, ADRs, design, reviews, runbooks
├─ ops/                      docker-compose (api, PostGIS, Redis, Meilisearch, NATS)
├─ .github/workflows/ci.yml  backend + contracts jobs
├─ apps/ infra/ data/        EMPTY scaffolding from Phase 0
```

**Architectural principles in force (ADR-backed):** modular monolith (ADR-0001),
money as integer minor units (ADR-0002), PostgreSQL+PostGIS (ADR-0003),
event-driven integration (ADR-0004), contract-first APIs (ADR-0005), monorepo
trunk-based (ADR-0006), Stripe Connect destination charges (ADR-0007).

**Deployed services vs used services:** compose starts Redis, Meilisearch and
NATS — **none of them are used by the code**. Dead infrastructure (see TD-06).

---

## 3. Current Product Capabilities (verified working)

| Capability | State |
|---|---|
| Register / login / token refresh (rotating, single-use) | ✅ |
| RBAC: guest / host / admin | ✅ |
| Host onboarding (Stripe Connect **simulated**) | ✅ |
| Create / update / publish listing | ✅ |
| Host calendar blocks | ✅ |
| Search listings by city (exact-ish match, paged by limit/offset) | ⚠️ minimal |
| Availability calendar (interval model, exclusive check-out) | ✅ |
| Booking with mandatory Idempotency-Key | ✅ |
| Payment intent → webhook → confirm | ✅ (simulation; Stripe adapter untested vs sandbox) |
| Double-entry ledger, escrow, commission split, payout | ✅ |
| Cancellation + full refund + availability recovery | ✅ |
| Check-in state + booking state endpoint + event timeline | ✅ |
| Notifications: outbox, worker, retry, DEAD, metrics, founder audit | ✅ |
| Admin: users/bookings/payments/ledger/audit/incidents/queue | ✅ |
| Disaster recovery: encrypted backup + verified restore | ✅ (manual) |

**37 endpoints total.** No `TODO`/`FIXME`/`HACK` markers, no skipped tests.

---

## 4. Completed Work

Phase 0 skeleton → D4 vertical slice → D5 hardening → D6 warfare → D7 readiness
board → D8 release loop + Alembic + DB append-only triggers → D9 DR drill →
B1 Stripe Connect adapter → OAT-01 business acceptance → OAT-02 notification
layer → OAT-03 outbox + reliable delivery → CI fix. 20 commits, CI green.

## 5. Partially Completed Work

| Area | Done | Missing |
|---|---|---|
| Payments | adapter, webhooks, refunds, payouts, reconciliation | **real Stripe sandbox never exercised**; partial refunds; chargebacks/clawback; payout scheduling |
| Search | city filter + limit/offset | geo (no lat/lon on Listing at all despite PostGIS ADR), price/type/amenity filters, ranking, total count |
| Listings | title, city, address, capacity, flat nightly price | **photos**, property type, rooms/beds, amenities, house rules, min/max nights, seasonal pricing |
| Operations | incident stub, check-in flag | cleaning/turnover tasks, inspections, damage |
| Disputes | `Incident` entity only | evidence, decision, resolution, refund linkage |
| Observability | notification metrics | HTTP/business metrics, tracing, error tracking, DB health check |
| DR | backup+restore proven | automation/schedule, offsite, PITR |

---

## 6. Missing Capabilities

**Product A (commercial marketplace):** listing photos & media pipeline; geo
search; reviews (guest↔host, moderation); guest↔host messaging; disputes;
cancellation-policy engine (Flexible/Moderate/Strict); partial refunds; wishlist;
multi-listing/bulk host tools; co-hosts; email verification; **any frontend
(web or mobile) — `apps/` is empty**.

**Product B (free listings marketplace): entirely absent.** Requires a new
bounded context: `FreeListing` (owner, contact, status, expiry, moderation
state), publication without payment, contact/lead flow, moderation queue,
report-listing, trust score, SEO landing pages, sitemap, structured data.

---

## 7. Critical Security Findings

Object-level authorization was **probed, not assumed** — all 12 probes pass:
guest↔guest booking isolation, host↔host listing isolation, payout role
restriction, notification privacy, admin-surface denial, role-escalation via
registration blocked, missing/forged/wrong-secret tokens rejected, refresh
token unusable as access token, webhook without secret cannot confirm a booking.

| ID | Sev | Component | Finding | Evidence | Risk |
|---|---|---|---|---|---|
| SEC-01 | **P0** | whole API | **No rate limiting / brute-force protection anywhere** | grep: 0 matches for rate-limit in `app/` | credential stuffing on `/auth/login`, booking spam, inventory DoS, future free-listing spam |
| SEC-02 | **P0** | config | Dev-default secrets **fail open**: `jwt_secret`, `webhook_secret` have working defaults; app starts fine without env override | `app/core/config.py` | a deploy that forgets env vars is silently forgeable-token territory |
| SEC-03 | **P1** | identity | **No email verification**; any address can be registered and used | `auth/register` | fake accounts, spam, unusable notification channel |
| SEC-04 | **P1** | identity | No account lockout, no password breach/complexity check (min 10 chars only) | `schemas.py` | online guessing (compounded by SEC-01) |
| SEC-05 | **P1** | admin | **No MFA** for admin/founder; single shared admin account model | `security.py` | admin takeover = full financial visibility + payout triggering |
| SEC-06 | **P2** | identity | Email enumeration: register returns 409 for existing address | `register()` | account discovery |
| SEC-07 | **P2** | identity | No session/device list, no "revoke all sessions" | `RefreshToken` | stolen refresh token survives password change |
| SEC-08 | **P2** | API | No CORS policy defined (harmless today, wrong-by-default once a browser client exists) | `main.py` | future XSS/credential leakage surface |
| SEC-09 | **P3** | API | No security headers / request-size limits | `main.py` | DoS via large bodies |

**Not found (checked):** SQL injection (ORM-parameterised; the only raw SQL is
DDL guards with no user input), IDOR (12 probes), privilege escalation via
registration, webhook spoofing, refresh-token replay (single-use rotation
enforced).

---

## 8. Financial Integrity Findings

**Invariants currently enforced in code/DB:** I1 no overlapping active bookings
(Postgres exclusion constraint) · I2 every journal entry sums to zero
(`post_entry` + reconciliation) · I3 whole system sums to zero · I4 ledger,
audit and domain events are append-only (**DB triggers — owner-proof**) ·
I5 escrow never negative (post-payout check) · I6 cancelled booking holds no
escrow (late-success auto-refund) · I7 payout only for completed + succeeded
bookings · I8 confirmed ⇒ payment succeeded.

| ID | Sev | Finding | Risk |
|---|---|---|---|
| FIN-01 | **P0** | **Stripe path never exercised against a real sandbox** — provider defaults to simulation; no live 3DS/SCA, transfer, partial-capture or dispute observation | the entire money path is unproven against the real processor |
| FIN-02 | **P1** | **Refund after payout returns 409 — no clawback flow** | guest wins a dispute after host was paid ⇒ manual, unmodelled loss |
| FIN-03 | **P1** | **No chargeback / `charge.dispute.*` handling** | forced refunds arrive with no ledger representation |
| FIN-04 | **P1** | Only full refunds; no partial refund or cancellation-policy engine | every cancellation is 100% refund — commercially wrong and unmodelled |
| FIN-05 | **P2** | **Ledger accounts are not currency-scoped**; balances aggregate across currencies | multi-currency (a stated goal) would silently corrupt balances |
| FIN-06 | **P2** | Commission = single global `platform_fee_bps`; integer floor rounding, undocumented | no per-market/per-listing rate; rounding policy not a recorded decision |
| FIN-07 | **P2** | No VAT / invoicing / DAC7 data model | EU legal requirement for a commission marketplace |
| FIN-08 | **P2** | Payout is a **manual admin trigger**; no schedule, no payout statement entity | not operable at volume; host cannot see a payout document |
| FIN-09 | **P3** | Reconciliation endpoint exists but runs **on demand only** | divergence detected only when someone looks |

---

## 9. Booking / Concurrency Findings

Proven safe (D6 + re-run this cycle): 60 concurrent bookings on identical dates
→ exactly 1 succeeds (59× 409, DB exclusion constraint); 200 concurrent webhook
deliveries → exactly 1 capture; 10 concurrent payout runs → paid once; ledger
reconciles to zero after the full adversarial run; Postgres killed mid-load →
ACID recovery with reconciliation intact.

| ID | Sev | Finding | Risk |
|---|---|---|---|
| BK-01 | **P1** | **Ghost booking**: an unpaid `pending` booking blocks the calendar indefinitely — no TTL / auto-void | free inventory DoS; a competitor or bot can freeze a host's calendar at zero cost |
| BK-02 | **P2** | Booking completion is a **manual admin action**, not a post-checkout timer | operationally impossible at volume |
| BK-03 | **P2** | Idempotency-Key handling is not fully atomic (TOCTOU between existence check and insert) — money-safe, but a concurrent retry can receive 409 instead of the original booking | client-visible inconsistency under exact-race |
| BK-04 | **P2** | No min/max nights, no lead time, no turnover gap enforcement | operationally required for managed hosting |
| BK-05 | **P3** | Availability window capped at 366 days; no pagination metadata on search | minor |

---

## 10. Free Marketplace Risks (Product B — not yet built)

Nothing exists, so this is a **forward threat model** to design against, not a
finding against current code. Highest-risk vectors for a free-posting surface:
bulk automated posting; scam/phishing listings harvesting deposits; duplicate
and scraped listings; fake contact details; SEO spam poisoning the domain's
reputation; malicious URLs; image-based malware.

**Minimum viable defence set (recommended, risk-ordered):** email + phone
verification before publish · per-account and per-IP posting limits · Turnstile/
CAPTCHA on publish · moderation queue with auto-screening (text + image) ·
report-listing + block-user · listing expiry with re-confirmation · trust score ·
`rel="nofollow"` + `noindex` until moderated (protects SEO reputation — the
entire point of Product B) · duplicate detection by address/phone/image hash.

**Strategic note:** Product B doubles the attack surface and is the primary
brand-reputation risk. It must not be launched without moderation and rate
limiting (which SEC-01 says do not exist yet at all).

---

## 11. Testing Gaps

**Present (53 tests, all green):** unit + integration for auth/RBAC, booking
rules, e2e money flow, D5 hardening, B1 Stripe adapter (mocked), OAT-01 business
scenarios, OAT-02 notifications, OAT-03 delivery, **security/authz probes (new
this cycle)**.

| ID | Sev | Gap |
|---|---|---|
| TST-01 | **P1** | **Contract tests absent** — `docs/api/*.openapi.yaml` are linted for style but never verified against the implementation; they have drifted (they still describe Request-to-Book, cancellation policies, `Money` objects and fields the code does not have). Contract-first (ADR-0005) is currently decorative |
| TST-02 | **P1** | Concurrency (warfare) and DR drills are **manual**, not in CI — the double-capture race was found by chance re-running them |
| TST-03 | **P2** | No coverage measurement or threshold |
| TST-04 | **P2** | Migration tests not in CI (upgrade/downgrade verified by hand) |
| TST-05 | **P2** | Tests run on **SQLite**, production is **PostgreSQL** — DB-level guards (exclusion constraint, append-only triggers) are silently skipped in the suite |
| TST-06 | **P3** | No load/performance tests, no E2E (no frontend exists) |

---

## 12. CI/CD Gaps

Current: two jobs (`backend`: install→ruff→pytest; `contracts`: Spectral +
AsyncAPI), green on `main` after this cycle's packaging fix.

| ID | Sev | Gap |
|---|---|---|
| CI-01 | **P1** | **No branch protection / required checks** — `main` accepts direct pushes; broken code *can* reach main |
| CI-02 | **P1** | No dependency scanning (`pip-audit`), no secret scanning (gitleaks), no SAST |
| CI-03 | **P2** | No Postgres service container ⇒ CI never exercises the real DB guards (pairs with TST-05) |
| CI-04 | **P2** | No typecheck (mypy/pyright) |
| CI-05 | **P2** | No coverage gate, no migration check job |
| CI-06 | **P3** | No container build/scan, no deploy pipeline (nothing is deployed anywhere) |

---

## 13. Automation Gaps

| ID | Sev | Gap |
|---|---|---|
| AUT-01 | **P1** | Unpaid-booking auto-void (BK-01) — needs the first scheduled job |
| AUT-02 | **P1** | Daily reconciliation job + alert (endpoint exists, nothing runs it) |
| AUT-03 | **P1** | Automated, scheduled, offsite backups (drill proven, schedule absent) |
| AUT-04 | **P2** | Auto-complete bookings after checkout (BK-02) |
| AUT-05 | **P2** | No pre-commit hooks; no dependency update bot |
| AUT-06 | **P3** | Warfare/DR drills not scheduled |

**Note:** the notification worker is the only background process in the system.
A single, shared scheduler abstraction should serve AUT-01/02/04 rather than
three ad-hoc threads.

---

## 14. Observability Gaps

| ID | Sev | Gap |
|---|---|---|
| OBS-01 | **P1** | **`/healthz` does not check the database** — it returns healthy while the DB is down; no readiness/liveness split |
| OBS-02 | **P1** | No HTTP metrics (latency, status codes, throughput); Prometheus covers notifications only |
| OBS-03 | **P1** | **No business metrics** (registrations, bookings, conversion, GMV, payment success/failure, refunds, commission, payouts) — the founder KPI framework in `docs/strategy/06` has no data source |
| OBS-04 | **P2** | No error tracking (Sentry), no structured/JSON logging, no request/correlation id |
| OBS-05 | **P2** | No tracing |
| OBS-06 | **P2** | `ops/monitoring/` is empty — no Prometheus/Grafana actually deployed to scrape `/metrics` |

---

## 15. Technical Debt

| ID | Sev | Debt |
|---|---|---|
| TD-01 | **P1** | **Dual schema path**: dev/local uses `create_all` + startup guards, production uses Alembic. Already caused a live failure (`operational_state` missing after a model change) |
| TD-02 | **P1** | OpenAPI contracts drifted from implementation (see TST-01) |
| TD-03 | **P1** | Payment provider defaults to **simulation** — production correctness unproven (FIN-01) |
| TD-04 | **P2** | `docs/adr/_from-early-draft/` holds unpromoted salvaged ADRs pending a decision |
| TD-05 | **P2** | Ledger accounts not currency-scoped (FIN-05) |
| TD-06 | **P2** | **Dead infrastructure**: compose runs Redis, Meilisearch and NATS; no code uses any of them. `infra/`, `data/`, `apps/`, `ops/monitoring/` are empty Phase-0 scaffolding |
| TD-07 | **P3** | Simulated webhook endpoint ships in the same app as the real one (guarded by a secret and a provider check, but it is a production-visible test surface) |
| TD-08 | **P3** | `docs/` now holds 30+ strategy/review documents vs 2 700 LOC of app code — documentation-to-code ratio is inverted |

---

## 16. Priorities

### P0 — Critical (security / financial integrity / data)
| ID | Item | Complexity | Depends on | Test requirement |
|---|---|---|---|---|
| SEC-01 | Rate limiting + brute-force protection | M | — | abuse tests per endpoint class |
| SEC-02 | Fail-fast on default secrets outside local env | S | — | startup test: non-local + default secret ⇒ refuse to boot |
| FIN-01 | Exercise real Stripe **test** keys end-to-end | M | Stripe test creds (founder) | sandbox checklist in `docs/design/b1-stripe.md` §5 |

### P1 — High (production readiness)
BK-01 auto-void ghost bookings · AUT-02 daily reconciliation + alert ·
AUT-03 scheduled offsite backups · OBS-01 real health/readiness ·
OBS-02/03 HTTP + business metrics · TST-01 contract tests (or delete the stale
specs) · TST-02 warfare/DR in CI · CI-01 branch protection · CI-02 dependency +
secret scanning · SEC-03 email verification · SEC-05 admin MFA ·
FIN-02/03 clawback + chargeback · FIN-04 cancellation policies + partial refunds ·
TD-01 single schema path.

### P2 — Important
Listing richness (photos, geo, amenities, property type) · reviews · messaging ·
disputes beyond the incident stub · FIN-05 currency-scoped ledger ·
FIN-06/07/08 commission config, VAT/invoices, payout statements ·
BK-02/03/04 · TST-03/04/05 · CI-03/04/05 · OBS-04/05/06 · SEC-04/06/07/08 ·
TD-04/05/06.

### P3 — Optimization
Load tests · tracing · container pipeline · TD-07/08 · BK-05 · SEC-09.

---

## 17. Recommended Development Roadmap

**Sequencing principle:** close the perimeter before widening the surface. Every
new product surface (especially Product B) multiplies the cost of missing rate
limiting and moderation.

1. **Harden the perimeter** (P0): rate limiting, secret fail-fast, real Stripe test run.
2. **Make operations autonomous** (P1): scheduler → auto-void, daily reconciliation, scheduled backups; health/readiness; HTTP + business metrics; branch protection + scanning in CI.
3. **Make the marketplace real** (P2, Product A): listing photos + geo + amenities, search that deserves the name, reviews, messaging.
4. **Then Product B** (free listings) — only on top of rate limiting, moderation queue and trust signals.
5. **Frontend** — nothing is consumable by a human today; `apps/` is empty.

### ⚠️ Strategic conflict to resolve before step 4 (founder decision required)

The locked strategy (`docs/strategy/00-DECISIONS.md`, `01`, `07`) sequences the
company as **operator-first**: managed hosting on ~10 apartments until CM2 > 0,
with the self-service listings layer ("Homies Listed") deliberately in **Phase 2
/ V1–V2, after** the operator loop earns money. This master prompt places
**Product B up front as a growth engine**.

These are the same product, different sequencing. The conflict is real and is
the founder's call, not mine:

- **Operator-first (current locked plan):** revenue sooner, tiny surface, defensible via the HeyHomie operations moat; slower organic growth.
- **Free-marketplace-first (this prompt):** compounding SEO/inventory, network effects, but zero revenue, doubled attack surface, and moderation cost before any money exists — while rate limiting does not yet exist at all.

**Recommendation:** keep operator-first, and build Product B **after** P0+P1 —
its SEO value compounds over years and is not lost by starting one quarter
later, whereas launching an unmoderated free-posting surface on a brand-new
domain can permanently damage the domain's search reputation. Confirm or
override.

---

## 18. First Recommended Micro-Cycle

**Cycle `SEC-01`: request rate limiting + brute-force protection.**

- **Objective:** no endpoint can be hammered; login attempts are throttled per account and per IP.
- **Scope:** one small middleware + a per-route policy table; storage in Postgres or the already-running (currently unused) Redis — decision recorded in `docs/DECISIONS.md`.
- **Files:** `app/core/ratelimit.py` (new), `app/main.py` (wire), `app/modules/identity/router.py` (login policy), tests.
- **Risks:** false positives locking out legitimate users; must not add latency to the money path.
- **Tests:** burst on `/auth/login` ⇒ 429 after N attempts; burst on `/bookings` ⇒ 429; legitimate traffic unaffected; limiter failure must **fail open for reads, closed for auth**.
- **Why first:** it is the single P0 that unblocks every later surface (free listings, public search, messaging) and it is cheap. SEC-02 (secret fail-fast, S) can ship in the same cycle.

**Awaiting approval before implementation.**
