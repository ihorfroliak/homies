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

## `events.asyncapi.yaml` — domain event catalog (design artifact)

The AsyncAPI catalog is a **design-time** description of domain events, not a
generated runtime contract (there is no external event bus yet — events are an
in-process outbox). It has also drifted from the events the code actually emits
(OAT-02/03 added several). Aligning it is tracked separately as a smaller
follow-up; it is not auto-generated because the events are internal.
