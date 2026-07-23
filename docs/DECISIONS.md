# DECISION LOG

Lightweight record of decisions that shape the system but are not full ADRs.
Formal architecture decisions live in [docs/adr/](adr/); strategic/business
decisions live in [docs/strategy/00-DECISIONS.md](strategy/00-DECISIONS.md).
Settled decisions are not revisited without new evidence.

| # | Date | Decision | Why | Status |
|---|---|---|---|---|
| D-01 | 2026-07-05 | Modular monolith, not microservices | Solo/small team, single DB, pilot scale; bounded contexts ≠ deployment units | Settled (ADR-0001) |
| D-02 | 2026-07-05 | Money as integer minor units | Floats cannot represent currency; matches Stripe | Settled (ADR-0002) |
| D-03 | 2026-07-05 | Ledger is the accounting truth; the payment provider is external | Money state must be reconstructable and reconcilable independently of Stripe | Settled |
| D-04 | 2026-07-05 | Ledger, audit and domain events are **append-only enforced by DB triggers**, not ORM guards | An admin with direct SQL must not be able to silently rewrite financial history | Settled |
| D-05 | 2026-07-05 | Booking overlap prevented by a Postgres **exclusion constraint**, not application logic alone | Application checks are TOCTOU-prone; the DB is the last line of defence | Settled |
| D-06 | 2026-07-05 | Payments via **Stripe Connect destination charges** | No payment licence needed; one atomic object per booking; fee split maps 1:1 onto the ledger | Settled (ADR-0007) |
| D-07 | 2026-07-05 | Operator-first business sequencing (managed hosting before self-service marketplace) | Revenue sooner, small surface, HeyHomie operations moat | ⚠️ **Challenged** by the 2026-07-23 master prompt (Product B up front) — founder decision pending, see audit §17 |
| D-08 | 2026-07-09 | Notification delivery: **transactional outbox + polling worker**, no message broker | Pilot scale does not justify Kafka/RabbitMQ; one process, one DB, correctness first | Settled |
| D-09 | 2026-07-09 | Delivery guarantee is **at-least-once + idempotency key**, not exactly-once | Exactly-once across an arbitrary external provider is not achievable; honesty over marketing | Settled |
| D-10 | 2026-07-23 | Keep `main` as the only long-lived branch; the abandoned early-draft history is preserved as tag `archive/early-draft` and its branch deleted | Two unrelated histories in one repo is a footgun; the tag keeps it recoverable forever | Settled |
| D-11 | 2026-07-23 | Distributable package is restricted to `app*`; `alembic/`, `scripts/`, `tests/` are repo tooling | setuptools flat-layout auto-discovery aborted the build once a second top-level dir appeared | Settled |
| D-12 | 2026-07-23 | Security assertions must be **executable probes**, not code review | "Can user A touch user B's data" is answered by a failing/passing test, not by reading a router | Settled |
| D-14 | 2026-07-23 | Rate limiting stores counters **in-process** (token buckets behind a `RateLimitStore` protocol), not in Redis or PostgreSQL | Redis is deployed nowhere and used by no code; a DB write per request is unacceptable; the app is a single uvicorn process. The protocol keeps a shared backend a drop-in change | Settled — **revisit before running >1 instance** |
| D-15 | 2026-07-23 | Login is limited **per IP and per account, with the account bucket spent only by failed attempts** | A pure account limit is an account-lockout DoS. Continuous refill + failures-only means an attacker adds friction but can never permanently lock a user out | Settled |
| D-16 | 2026-07-23 | Payment webhooks are **exempt** from rate limiting | Providers retry aggressively; throttling would create inconsistent financial state. The handler is signature-verified and idempotent, so exemption is free | Settled |
| D-17 | 2026-07-23 | Failure semantics are **per policy**: fail-closed for authentication, fail-open for reads and booking mutations | Mechanically failing open everywhere would let a limiter outage enable credential stuffing; failing closed everywhere would turn a perimeter control into an availability risk. The DB remains authoritative for booking correctness | Settled |
| D-13 | 2026-07-23 | **Deliberately not created**: 12 skill files + 10 specialist role definitions as requested | The same prompt forbids overengineering (§24). 22 scaffolding files that nothing invokes are documentation debt (see TD-08 — docs already outweigh code). Three high-leverage skills were created instead; more will be added when a real cycle needs one | Open — revisit if a cycle proves the need |

## Deferred (recorded so they are not silently forgotten)

| Item | Why deferred | Revisit when |
|---|---|---|
| Redis / Meilisearch / NATS usage | Running in compose but unused; Postgres covers current needs | Search quality or cache pressure demands it |
| Currency-scoped ledger accounts | Single currency (PLN) today | Before any second currency |
| Message broker | Outbox + worker is sufficient | Far beyond pilot volume |
| Microservice extraction | Modules have clean seams; extraction is cheap later | Team or scale actually requires it |
| Full disputes engine | `Incident` stub covers founder visibility | When dispute volume is non-zero |
