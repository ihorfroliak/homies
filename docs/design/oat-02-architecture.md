# OAT-02 — Operational Notification Layer (architecture)

Pilot-grade, brutally minimal. No event bus, no external MQ. Optimized for
correctness, observability, failure visibility. Modules:
`backend/app/modules/events/`.

## 1. Event model

Immutable, append-only `domain_events` (DB trigger `domain_events_append_only`
blocks UPDATE/DELETE even via direct SQL). Idempotent by unique `dedup_key`.
`correlation_id = booking_id` ties every event to its booking → full timeline
reconstructable from events alone.

Stable event set (7):
`BookingCreated, BookingConfirmed, CheckInAvailable, CheckInCompleted,
CancellationProcessed, PayoutExecuted, IncidentOpened`.

Emission points (in the same DB transaction as the state change, so
event+state are atomic):
- BookingCreated — `POST /bookings`
- BookingConfirmed + CheckInAvailable — payment success (webhook)
- CheckInCompleted — `POST /bookings/{id}/checkin`
- CancellationProcessed — `POST /bookings/{id}/cancel`
- PayoutExecuted — payout run (per booking)
- IncidentOpened — `POST /admin/incidents`

## 2. Notification routing

Static `ROUTING: event_type -> [(recipient_role, channel)]`. Roles:
guest / host / founder. Channels: `email | sms | in_app` (abstraction).
Recipient resolution: guest = booking.guest_id, host = listing.host_id,
founder = role-level feed (no user id). Payload is **structured** (dict:
amounts, dates, ids), not free text.

Delivery: pilot channels are **log-based** (`homies.notifications` logger);
in-app notifications are the stored `notifications` rows a user reads via
`GET /me/notifications`. Real email/SMS providers slot behind the channel
later without touching callers.

## 3. State visibility contract

`GET /bookings/{id}/state` — single source of truth:
```
{ booking_id, lifecycle_state, operational_state,
  financial: { total_amount, currency, payment_status, payout_status },
  timeline: [ {type, at, payload} ... ]  # from domain_events
}
```
`operational_state`: `none → checkin_available → checked_in → checked_out`.

Visibility surfaces: guest/host `GET /me/notifications`; founder
`GET /admin/founder-feed` (in-app founder notifications) + `GET /admin/incidents`;
dead-letter `GET /admin/notifications?status=failed`.

## 4. Failure handling

- **No-retry MVP policy.** Log channel cannot fail; a channel exception is
  caught, the notification is marked `failed` with the error, and it never
  propagates. Real channels get retry later.
- **Dead-letter = data, not a queue:** `notifications` rows with
  `status=failed` (`/admin/notifications?status=failed`).
- **STOP vs degraded:** notifications are **best-effort and decoupled** from
  money. A notification failure is **degraded mode** (booking + ledger
  already committed; delivery retried/inspected later). There is **no STOP**
  path where notifications block a booking or a ledger write — proven by
  wrapping delivery in try/except and by the money invariants staying green.

## 5. What this is NOT (anti-overbuild)

No Kafka/NATS wiring, no outbox worker, no template engine, no delivery SLA.
Events are written in-process in the same transaction; notifications are
rows + logs. This is the smallest thing that gives guest/host/founder
operational visibility and a reconstructable timeline for a 10-apartment
pilot. The AsyncAPI catalog (docs/api/events.asyncapi.yaml) remains the
target for a real bus if/when scale demands it.
