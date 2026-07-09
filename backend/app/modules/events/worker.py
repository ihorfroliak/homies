"""Notification delivery worker (OAT-03). Polls the outbox (notifications
table), delivers via the channel abstraction, and drives the delivery state
machine. Single process, single DB — no MQ.

State machine:
    pending -> processing -> delivered
                          -> failed (transient, will retry) -> ... -> dead
                          -> dead (permanent failure or attempts exhausted)

Safety:
- claim uses FOR UPDATE SKIP LOCKED (Postgres) so two workers never grab the
  same row -> no duplicate delivery from duplicate workers;
- stale PROCESSING rows (a crashed worker) are reclaimed after a timeout ->
  restart-safe, at-least-once delivery;
- business events stay exactly-once (domain_events.dedup_key); delivery is
  at-least-once with an idempotency key so an idempotent provider dedupes.
"""

import logging
import random
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.modules.events import metrics
from app.modules.events.models import Notification
from app.modules.events.providers import channel_for
from app.modules.events.templates import render

log = logging.getLogger("homies.notifications")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _backoff(attempts: int) -> timedelta:
    base = settings.notification_backoff_base_seconds
    delay = base * (2 ** attempts)
    jitter = random.uniform(0, base)
    return timedelta(seconds=delay + jitter)


def reclaim_stale(db: Session) -> int:
    cutoff = _now() - timedelta(seconds=settings.notification_stale_processing_seconds)
    stale = db.scalars(
        select(Notification).where(Notification.status == "processing")
    ).all()
    n = 0
    for notif in stale:
        if (_aware(notif.claimed_at) or _now()) < cutoff:
            notif.status = "pending"
            notif.claimed_at = None
            n += 1
    if n:
        db.commit()
    return n


def claim_batch(db: Session, limit: int) -> list[Notification]:
    rows = db.scalars(
        select(Notification)
        .where(
            Notification.status.in_(("pending", "failed")),
            Notification.next_attempt_at <= _now(),
        )
        .order_by(Notification.next_attempt_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    for notif in rows:
        notif.status = "processing"
        notif.claimed_at = _now()
    db.commit()  # release the lock; rows are now marked processing (owned by us)
    return rows


def deliver_one(db: Session, notif: Notification) -> str:
    channel = channel_for(notif.channel)
    msg = render(notif.template_id or notif.event_type, notif.locale,
                 {"correlation_id": notif.correlation_id, **(notif.payload or {})})
    notif.attempts += 1
    result = channel.send(
        to=notif.recipient_user_id, subject=msg["subject"], body=msg["body"],
        idem_key=notif.id,  # stable per notification -> idempotent redelivery
    )
    if result.ok:
        notif.status = "delivered"
        notif.delivered_at = _now()
        notif.last_error = ""
        metrics.DELIVERED.labels(channel=notif.channel).inc()
        latency = (notif.delivered_at - _aware(notif.created_at)).total_seconds()
        metrics.LATENCY.observe(max(latency, 0))
    else:
        notif.last_error = result.error
        metrics.FAILED.labels(channel=notif.channel).inc()
        permanent = not result.transient
        if permanent or notif.attempts >= settings.notification_max_attempts:
            notif.status = "dead"
            metrics.DEAD.labels(channel=notif.channel).inc()
        else:
            notif.status = "failed"
            notif.next_attempt_at = _now() + _backoff(notif.attempts)
            metrics.RETRIES.labels(channel=notif.channel).inc()
            log.warning("notify retry id=%s attempt=%s err=%s",
                        notif.id, notif.attempts, result.error)
    notif.claimed_at = None
    db.commit()
    return notif.status


def run_once(db: Session, batch: int | None = None) -> dict:
    reclaimed = reclaim_stale(db)
    claimed = claim_batch(db, batch or settings.notification_worker_batch)
    results = {"delivered": 0, "failed": 0, "dead": 0, "reclaimed": reclaimed}
    for notif in claimed:
        outcome = deliver_one(db, notif)
        results[outcome] = results.get(outcome, 0) + 1
    metrics.refresh_queue_depth(db)
    return results


class NotificationWorker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                with SessionLocal() as db:
                    run_once(db)
            except Exception:  # noqa: BLE001 — worker must never die on one bad row
                log.exception("notification worker iteration failed")
            self._stop.wait(settings.notification_worker_interval_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="notif-worker", daemon=True)
        self._thread.start()
        log.info("notification worker started")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


worker = NotificationWorker()
