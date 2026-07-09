# OAT-03 — Transactional Outbox + Reliable Delivery

Single process, single DB, pilot scale. No Kafka/RabbitMQ/microservices.
Modules: `backend/app/modules/events/{service,worker,providers,templates,metrics}.py`.

## 1. Outbox design

The `notifications` table **is** the outbox. `emit()` writes the
`domain_events` row + one `notifications` row per routed recipient, all
`status=pending`, **inside the same DB transaction as the booking/payment
mutation**. Business logic never calls a provider. Guarantee:

> Booking committed → Event committed → Outbox committed — atomically.
> Roll back the business txn ⇒ no orphan event or notification (proven:
> `test_no_notification_without_committed_booking`).

## 2. Delivery state machine

```
pending ──claim──> processing ──ok──────────> delivered   (terminal)
                        │ transient fail & attempts<max ─> failed ──due──> processing ...
                        │ permanent fail OR attempts>=max ─> dead        (terminal, observable)
   (stale processing, crashed worker) ──reclaim──> pending
```
Transitions are deterministic; no hidden states. `attempts`, `next_attempt_at`,
`claimed_at`, `last_error`, `delivered_at` are explicit columns.

## 3. Worker

Single background thread (started in FastAPI lifespan; disabled under
`ENV=test` for deterministic drive). Each cycle:
1. `reclaim_stale` — `processing` older than `stale_processing_seconds` → `pending`.
2. `claim_batch` — `SELECT ... WHERE status IN (pending,failed) AND
   next_attempt_at<=now ORDER BY next_attempt_at LIMIT n FOR UPDATE SKIP LOCKED`
   → mark `processing`. **SKIP LOCKED ⇒ two workers never claim the same row**
   (proven live: A=40, B=0, overlap=0).
3. `deliver_one` — render template, call channel, drive the state machine.

Restart-safe: a crash leaves rows `processing`; the next run reclaims and
redelivers. The whole loop is wrapped so one bad row never kills the worker.

## 4. Retry policy

Exponential backoff with jitter: `delay = base*2^attempts + U(0,base)`;
`next_attempt_at = now + delay`. `max_attempts` configurable
(`NOTIFICATION_MAX_ATTEMPTS`, default 5). Transient failures retry; permanent
failures (`transient=False`) go straight to `dead`. Every retry increments
`attempts`, records `last_error`, and is logged + counted (metric).

## 5. Delivery semantics (honest)

- **Business events: exactly-once** — `domain_events.dedup_key` unique;
  duplicate emit is a no-op (proven: dup webhook → one BookingConfirmed set).
- **Notification delivery: at-least-once** — a crash after the provider
  succeeds but before marking `delivered` causes redelivery. Each send carries
  a stable idempotency key (`notification.id`) so an idempotent provider (or
  in-app, which is idempotent by construction) dedupes. True exactly-once
  across an arbitrary external provider is not claimed — it is at-least-once +
  idempotency key, which is the correct pilot guarantee.

## 6. Channel abstraction

`Channel.send(to, subject, body, idem_key) -> DeliveryResult(ok, transient,
error)`. Implementations: `InAppChannel` (the row is the delivery, always ok),
`StubEmailChannel` (pilot default, logs), `SmtpEmailChannel` (real SMTP;
network errors transient, bad recipient permanent), `StubSmsChannel`.
Swap via `EMAIL_PROVIDER=stub|smtp` — no caller changes.

## 7. Templates

`template_id + locale + variables` (structured payload). `render()` never
raises (missing variables → `-`, missing template → generic) so a template
bug cannot break delivery. en/uk seeded; 1 template per event.

## 8. Observability (Prometheus, `/metrics`)

`homies_notifications_delivered_total{channel}`, `_failed_total`, `_dead_total`,
`_retries_total`, `homies_notification_delivery_latency_seconds` (histogram),
`homies_notification_queue_depth{status}` (gauge). Founder audit without SQL:
`/admin/notifications` (status, attempts, last_error, timestamps),
`/admin/notifications?status=dead` (dead-letter), `/admin/notifications/queue`.

## 9. Failure recovery matrix

| Failure | Behaviour | Evidence |
|---|---|---|
| Provider timeout (transient) | retry with backoff, eventually delivered | `test_provider_timeout_then_recovers` |
| Permanent provider failure | → dead, observable in dead-letter | `test_permanent_failure_goes_dead` |
| Worker crash mid-flight | stale `processing` reclaimed → delivered | `test_worker_restart_reclaims_stale` |
| Duplicate workers | SKIP LOCKED → disjoint claims | live: overlap=0 |
| Crash after provider success | redeliver (at-least-once + idem key) | design; in-app idempotent |
| Business txn rollback | no event/notification created | `test_no_notification_without_committed_booking` |
| Delivery failure | booking/payment/ledger unchanged | `test_delivery_failure_does_not_touch_money` |

## 10. Performance notes (pilot scale)

Poll-based worker, `interval=1s`, `batch=20`. At 10 apartments (~tens of
bookings/day, a few events each) the outbox is near-empty; delivery latency is
worker-interval-bounded (≤1–2s, observed live). `next_attempt_at` + `status`
are indexed so `claim_batch` is an index range scan. This scales to thousands
of events/day on one process; a real bus is only needed far beyond pilot
(AsyncAPI catalog already documents that target).
