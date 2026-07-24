# BK-01 — Unpaid booking expiry + first scheduler

Micro-cycle 03. Closes the ghost-booking inventory-DoS confirmed in
[FIN-01](fin-01-stripe-validation.md): an abandoned checkout left a booking
`pending` forever, and `pending` blocks the calendar.

## Booking state machine (extended, not replaced)

```
pending --(payment succeeded)------> confirmed --> completed
        --(payment failed event)---> payment_failed        [dates freed]
        --(user/admin cancel)------> cancelled             [dates freed]
        --(deadline passes, sweep)-> expired   ← NEW (BK-01) [dates freed]
```

`BLOCKING_STATUSES = (pending, confirmed)` — `expired`, like `cancelled` and
`payment_failed`, is not in it, so expiring a booking frees the dates instantly.

## Expiration semantics

- **Durable deadline**: a new `bookings.payment_expires_at` column, set at
  creation to `now + BOOKING_PAYMENT_TTL_SECONDS`. Persisted (not
  `created_at + N` arithmetic) so it survives a TTL config change, and nulled
  once the booking leaves `pending`.
- **Explicit `expired` state** (D-22): expiry is materially different from a
  user cancellation — no one chose it, and it carries a different
  business/analytics meaning — so it gets its own terminal state rather than
  overloading `cancelled`.

## Configuration

`BOOKING_PAYMENT_TTL_SECONDS`, default **1800** (30 min ≈ a checkout session).
Validated at settings load: must be within **[60, 86400]** — a zero or tiny
value that would expire live customers mid-checkout is impossible by
construction (`ValueError` on startup).

## Concurrency & the payment-vs-expiry race

The transition is a single authoritative, atomic row update:

```sql
UPDATE bookings SET status='expired', payment_expires_at=NULL
WHERE id = :id AND status = 'pending'
```

- **Two workers** cannot both expire one booking — only one UPDATE gets
  `rowcount == 1` (row lock); the other sees 0 and rolls back. Proven with two
  concurrent sweeps → exactly one expiry.
- **A paid booking is never expired** — the `status='pending'` guard makes the
  UPDATE a no-op the instant payment set it to `confirmed`. Proven.
- **Payment commits a moment after expiry** — the late webhook finds the
  booking `expired` and takes the existing late-success path
  (`payments.service.process_intent_succeeded`): capture **and immediate
  auto-refund**, so money is never held and the outcome is never
  PAID+EXPIRED-blocking. Proven: ledger nets to zero, escrow 0.

No PAID+EXPIRED, no double booking, under any interleaving.

## Scheduler

`BookingExpiryWorker` — a daemon thread that runs one `expire_due_bookings`
sweep every `BOOKING_EXPIRY_INTERVAL_SECONDS` (default 30s). Deliberately the
**smallest safe scheduler**, mirroring the notification worker — not a
generalized task system. Per-booking error isolation: one failing row
increments a failure counter and is skipped; the batch and the scheduler
continue. Disabled under `ENV=test` so tests drive sweeps deterministically.

## Observability

Prometheus: `homies_booking_expiry_runs_total`, `_scanned_total`,
`_expired_total`, `_failures_total`, `_duration_seconds` (histogram),
`homies_booking_expiry_backlog` (gauge — due-but-not-yet-swept). No
high-cardinality labels; booking ids appear only in structured logs
(`id`, `prev`, `new`, `reason`), never as metric labels. No payment credentials
are ever logged.

## Independence from webhook delivery

The sweep is the safety net for exactly the cases Stripe cannot be relied on
for: PaymentIntent left incomplete, browser closed, mobile app killed, webhook
delayed or lost. The booking lifecycle is now correct **regardless of whether
any webhook ever arrives**.

## Tests (14, deterministic)

`tests/test_bk01_booking_expiry.py` — no sleeps; time is controlled by setting
`payment_expires_at` or passing an explicit `now`. Deadline assigned on
creation; future deadline not expired; due booking expired; paid booking never
expired; idempotent (second sweep is a no-op); two concurrent sweeps expire
once; late payment after expiry auto-refunded (no PAID+EXPIRED); payment before
expiry keeps `confirmed`; batch of 5 expired together; one failing row does not
stop the batch; TTL config bounds enforced; metrics emitted; calendar freed and
re-bookable after expiry. Financial invariants and 12/12 authorization probes
remain green.

## Known limitation & future work

The scheduler is safe for the **current single-process deployment**. The
row-level UPDATE guard also keeps it correct if multiple workers/instances are
introduced — but before running multiple instances, the *scheduling* side
(every instance sweeping) should be reviewed to avoid redundant scans (leader
election or a shared schedule). Recorded as **D-24**. This same scheduler is the
natural home for the next automation jobs (daily reconciliation AUT-02,
auto-complete after checkout BK-02).
