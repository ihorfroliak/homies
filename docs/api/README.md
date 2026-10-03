# API contracts

## `openapi.json` — the HTTP contract (source of truth)

**Code-first, generated from the implementation.** FastAPI + pydantic produce
an accurate OpenAPI 3.1 spec from the real routes and models; this file is a
committed snapshot of it. Do not hand-edit it.

Regenerate after any route/model change:

```
cd backend && python -m app.scripts.export_openapi
```

A CI drift-guard (`backend/tests/test_tst01_openapi_contract.py`) fails the
build if the committed spec is out of date or if any served endpoint is missing
from it — so the contract can never silently rot.

### Why generated, not hand-written (TST-01)

The project's original hand-authored per-domain specs (`auth/listings/booking
.openapi.yaml`) drifted badly: they described **11 of 35** real paths, used
`{listingId}` where the app serves `{listing_id}`, and referenced concepts the
code never implemented (Request-to-Book, cancellation-policy enums, `Money`
objects). Contract-first (ADR-0005) was aspirational; in practice code led.
Rather than hand-maintain a spec that will drift again, the contract is now
generated and guarded. Decision recorded in `docs/DECISIONS.md` (D-27); the
retired specs remain in git history.

## `events.asyncapi.yaml` — Phase-1 domain event catalog

The events the Phase-1 application writes to its transactional outbox
(`domain_events`) — listings, moderation, engagement — reconciled with the code
in GROWTH-001 ([EVENTS-v1](../growth/EVENTS-v1.md)). There is no external bus.
`backend/tests/test_measurement_facts.py` pins the catalogue's payload keys to
the ones the code writes; CI validates it (`ops/contracts`).

`events.legacy-booking.asyncapi.yaml` is the booking-era catalogue
(UserRegistered, Booking*, Payment*, PayoutSent, Task*, ReviewSubmitted) —
**LEGACY_DORMANT**, kept for history and still validated.
