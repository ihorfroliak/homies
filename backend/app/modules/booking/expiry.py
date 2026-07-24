"""BK-01 — expire unpaid bookings that hold inventory past their deadline.

An abandoned checkout (browser closed, app killed, webhook lost) leaves a
booking `pending` forever, and `pending` blocks the calendar — a zero-cost
inventory DoS. This sweep frees such bookings.

Safety model (single authoritative row transition):

    UPDATE bookings SET status='expired'
    WHERE id = :id AND status = 'pending'

Only one worker's UPDATE can affect a given row, and the `status='pending'`
guard means a booking confirmed a microsecond earlier (status now 'confirmed')
is a no-op — there is no PAID+EXPIRED outcome and no double booking. A payment
that succeeds *after* expiry is handled by the late-success path in
payments.service (capture + auto-refund), exactly like a cancellation.

`expired` is not in BLOCKING_STATUSES, so the calendar is freed immediately.
The scheduler is safe for the current single-process deployment; the row-level
UPDATE guard also makes it safe if multiple workers are introduced later (see
docs/DECISIONS.md D-24).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.modules.booking.models import Booking

log = logging.getLogger("homies.booking.expiry")

EXPIRY_RUNS = Counter("homies_booking_expiry_runs_total", "Expiry sweeps executed")
EXPIRY_SCANNED = Counter("homies_booking_expiry_scanned_total", "Candidate bookings scanned")
EXPIRY_EXPIRED = Counter("homies_booking_expiry_expired_total", "Bookings expired")
EXPIRY_FAILURES = Counter("homies_booking_expiry_failures_total", "Per-booking expiry failures")
EXPIRY_DURATION = Histogram("homies_booking_expiry_duration_seconds", "Sweep duration")
EXPIRY_BACKLOG = Gauge("homies_booking_expiry_backlog", "Due-but-not-yet-expired bookings")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def expire_due_bookings(db: Session, now: datetime | None = None, batch: int | None = None) -> dict:
    """One sweep. Per-booking error isolation: one failure never aborts the
    batch. Idempotent: a second run finds nothing because the rows are no
    longer `pending`."""
    now = now or _now()
    batch = batch or settings.booking_expiry_batch
    EXPIRY_RUNS.inc()

    with EXPIRY_DURATION.time():
        candidates = db.scalars(
            select(Booking.id)
            .where(
                Booking.status == "pending",
                Booking.payment_expires_at.is_not(None),
                Booking.payment_expires_at <= now,
            )
            .limit(batch)
        ).all()
        EXPIRY_SCANNED.inc(len(candidates))

        expired = 0
        failed = 0
        for booking_id in candidates:
            try:
                # Authoritative, atomic transition. rowcount == 1 only if this
                # worker won and the booking was still pending.
                result = db.execute(
                    update(Booking)
                    .where(Booking.id == booking_id, Booking.status == "pending")
                    .values(status="expired", payment_expires_at=None)
                )
                if result.rowcount == 1:
                    db.commit()
                    expired += 1
                    EXPIRY_EXPIRED.inc()
                    log.info(
                        "booking expired id=%s prev=pending new=expired reason=payment_ttl",
                        booking_id,
                    )
                else:
                    db.rollback()  # someone else moved it (paid/cancelled/expired)
            except Exception:  # noqa: BLE001 — isolate; one bad row must not stop the sweep
                db.rollback()
                failed += 1
                EXPIRY_FAILURES.inc()
                log.exception("booking expiry failed id=%s", booking_id)

    backlog = db.scalar(
        select(Booking.id)
        .where(Booking.status == "pending", Booking.payment_expires_at <= now)
        .limit(1)
    )
    EXPIRY_BACKLOG.set(1 if backlog else 0)
    return {"scanned": len(candidates), "expired": expired, "failed": failed}


class BookingExpiryWorker:
    """Minimal periodic scheduler — deliberately not a generalized task system.
    Mirrors the notification worker: a daemon thread that calls one sweep per
    interval and never dies on a single failure. Disabled under ENV=test for
    deterministic drive."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                with SessionLocal() as db:
                    expire_due_bookings(db)
            except Exception:  # noqa: BLE001 — the scheduler must survive any iteration
                log.exception("booking expiry sweep failed")
            self._stop.wait(settings.booking_expiry_interval_seconds)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="booking-expiry", daemon=True)
        self._thread.start()
        log.info("booking expiry worker started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


worker = BookingExpiryWorker()
