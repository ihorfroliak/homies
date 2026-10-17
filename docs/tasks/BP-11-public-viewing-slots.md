# BP-11 — Public derived viewing slots

Status: BUILDER_VERIFIED / REVIEW_REQUIRED (CI and independent acceptance pending).
Founder HOMIES-DELIVERY-002 directive,
2026-10-16, sections 5–6. Risk R2 with mandatory independent exact-SHA
security/availability review under 05 §9. Sole writer: Codex BP-11 worktree.
Base: `4ed8fe8ab334a8d8e344b80e266da2be3b661aee` (BP-8 integrated).
Branch: `codex/BP-11-public-viewing-slots`. No merge/deployment authorization.

## Contract

Implement D-104 OD-6 / 04a §24 and FE-003 BP-11: guests and authenticated
callers see only derived UTC starts, duration and IANA timezone for PUBLIC
listings. Preserve freshness/hold/privacy refusal and every authenticated
viewing write. Reads are advisory, never reservations. Preserve capacity,
both buffers, notice, blackout and unique-instant DST semantics.

Measure original code FIRST using synthetic disposable PostgreSQL, then
compare identical fixtures: small/many weekly/one-off, dense/full bookings,
blackouts, maximum days, no settings, spring/autumn DST. Record candidates,
returned slots, SQL calls/time, endpoint wall time and concurrent work, with
EXPLAIN ANALYZE BUFFERS evidence. Remove candidate-dependent SQL round trips.
No speculative index, cache, migration, new entity, provider, or service.

Bound requests to 1–31 days; public start dates from today through one year
ahead (inclusive), relative to the schedule's timezone. This transport abuse
bound does not rewrite stored schedules or constrain authenticated booking
writes. Apply a dedicated per-IP bucket before DB work. Explicitly trusted
proxy addresses and hop count are necessary before honoring forwarding
headers; Uvicorn must leave peer attribution to that policy.

Range-filter stored windows, blackouts and confirmed occupancy. Operational
row/work ceilings must fail closed with a neutral retryable 503 rather than
truncate or return false availability. Document ceilings and measurements.
No cache unless measurements justify it and privacy invalidation is safe.

## Acceptance / verification

Anonymous/authenticated PUBLIC; private/paused/held/missing; no/disabled
settings; confirmed/requested bookings; capacity; buffers; notice; blackout;
DST spring/autumn; date boundaries; dedicated limiter/429/Retry-After;
forged forwarding headers; response privacy; authenticated booking writes;
public read versus real PostgreSQL booking-write race. Tests must assert
bounded SQL independently of candidate count and equivalence of outputs.
Ruff, Mypy, OpenAPI drift, generated web API/type checks and required CI.
Separate exact-SHA reviewer after frozen candidate; Draft PR only.

Relevant doctrine: A1 guest inspection before sign-in; A2 derived-only privacy;
A4/A9 bounded DB work; A5 less friction to a legitimate viewing.

Out of scope: BP-9 private provider authority, BP-3/BP-4, FE-003 UI, AGENT-002,
production infrastructure, paid providers, baseline re-audit. IBB-001 remains
last formal backend baseline; BP-5 BARRIER/rollback BLOCKED and all debt stay.
Parent alone owns PROJECT-STATUS.md. This record and evidence own BP-11 facts.

## Builder delivery — 2026-10-17

Implemented derived-only anonymous reads, bounded window/blackout/confirmed
booking projections and strict-overlap counting using sorted starts/ends.
Each core computation issues at most three SQL statements; no candidate-loop
SQL remains. Booking writes still take their original capacity locks and
independently revalidate current availability. No migration/index/cache added.

New operational browsing horizon (directive §6.4): today through +366 days,
with a 1–31 day page, using the schedule timezone (UTC if no settings).
This is a bounded request policy, not a previously approved one-year picker
or a rewrite of stored schedules. A dedicated test confirms authenticated
booking requests outside the read horizon still follow existing domain rules.

Limits, proxy rollout requirements, actual before/after metrics and test
results are in [BP-11-performance.md](BP-11-performance.md). No local full
suite or mutation certification claimed. Required CI and a genuinely separate
exact-SHA security/availability review remain acceptance gates. Draft only;
no automatic merge, production readiness, deployment or provider activation.
