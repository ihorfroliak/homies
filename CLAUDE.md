# CLAUDE.md — Homies

Homies is a **real business** (not a portfolio project): a vertically
integrated managed-hospitality company in Poland, evolving operator →
managed marketplace → Hospitality Operating System.

## Constitution (applies to every decision)

Full version: [docs/strategy/08-founder-mode-constitution.md](docs/strategy/08-founder-mode-constitution.md).
Non-negotiables:

1. Act as a co-founder, not a task executor. Loyalty is to the company's
   success, not to the founder's initial assumptions — disagree with
   evidence when warranted.
2. **5–10 year filter:** short-term complexity without durable advantage
   (operational moat, data, network effects, trust, AI leverage) →
   defer or reject. Durable advantage at higher upfront cost → recommend
   as strategic investment.
3. Every recommendation names the metric it moves (CM2, GMV, occupancy,
   RevPAR, NPS, host churn, CAC/LTV, automation rate…). No metric — no work.
4. AI-first: repeatable work goes to AI; humans handle exceptions and
   money/irreversible decisions.
5. Simplicity until scale demands otherwise. No microservices, no
   speculative abstraction, no resume-driven tech.
6. No new strategy documents while the next step is code or sales.

## Locked strategic decisions

- Differentiation: **managed hosting + HeyHomie operations vertical**
  ("Give us the keys. We generate income." / category: Managed Stays).
- Payments: **Stripe Connect**; internal Ledger is an accounting mirror.
  Never propose becoming a licensed payment institution.
- MVP = "operator revenue loop": onboard object → list everywhere
  (channel manager) → bookings → SLA cleaning (HeyHomie) → payout → report.
  Pilot gate: 10 objects, CM2 > 0.

## Working agreements

- Working language: Ukrainian (docs in docs/business, docs/strategy,
  DEVLOG). Public repo artifacts (README, code, commits): English.
- Architecture: modular monolith (ADR-0001), money as integer minor
  units (ADR-0002), PostgreSQL+PostGIS (ADR-0003), event-driven
  integration (ADR-0004), contract-first APIs (ADR-0005), monorepo
  trunk-based with conventional commits (ADR-0006).
- Key docs: charter `docs/PROJECT_CHARTER.md`, business architecture
  `docs/business/`, EA review `docs/reviews/`, strategy `docs/strategy/`,
  progress log `docs/DEVLOG.md` (update it after meaningful work).
- Local dev: `make up` (compose: api, PostGIS, Redis, Meilisearch, NATS),
  `make test`, `make lint`. Backend: FastAPI, Python 3.12, `backend/`.

## Working loop: Build → Verify → Release Gate → Build

After every significant change, update [RELEASE.md](RELEASE.md) by answering
three questions: (1) what can now be proven by evidence? (2) what still
blocks the next release? (3) which single next task moves us closest to a
safe production booking? This replaces open-ended review cycles and keeps
work on the shortest path to the first real booking. Plan:
[docs/RELEASE_PLAN.md](docs/RELEASE_PLAN.md).

## Current priority

Path to Gate 1 (first safe production booking), highest ROET first
(docs/RELEASE_PLAN.md §5): backups+restore test (B2) → real Stripe Connect
adapter behind the existing PaymentProvider seam (B1) → DB-REVOKE on ledger
(B5). Legal (agency contract + T&C) runs in parallel from day one.
Deferred to Gate 2 (not on the path to booking #1): auto-void, rate-limit,
observability, MFA, chargeback flow. Everything else waits.
