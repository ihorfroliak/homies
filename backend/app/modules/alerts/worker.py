"""Saved-search alert worker (TASK-014) — the existing PostgreSQL +
BackgroundWorker architecture, no queue infrastructure.

One pass (`run_once`):
1. claim up to `saved_search_work_batch` public-generation work items
   (FOR UPDATE SKIP LOCKED) and evaluate each in its own transaction;
2. claim up to `saved_search_delivery_batch` due deliveries and send each, in
   its own transaction, after send-time revalidation;
3. every `saved_search_reconcile_every` passes, reconcile (bounded).

Crash safety: claims are committed before work starts; a worker that dies
leaves `processing` rows that `reconcile` returns to `pending` after
STALE_CLAIM. Reprocessing is idempotent (database uniqueness), so a retry can
only ever produce the same matches and deliveries.
"""

import logging
import threading
from datetime import timedelta

from typing import cast as typing_cast

from sqlalchemy import String, and_, cast, func, literal, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.worker_loop import run_loop
from app.modules.alerts import delivery, matching, metrics
from app.modules.alerts.models import AlertDelivery
from app.modules.alerts.sql import insert_ignore
from app.modules.events.models import DomainEvent
from app.modules.properties import freshness
from app.modules.properties.models import ClassifiedOffer, ListingPublicGeneration
from app.modules.properties.publicity import LISTING_BECAME_PUBLIC
from app.modules.saved.models import SavedSearch

log = logging.getLogger("homies.alerts")

RECONCILE_WINDOW = timedelta(days=7)


def process_work(session_factory=SessionLocal, limit: int | None = None) -> dict[str, int]:
    limit = limit or settings.saved_search_work_batch
    with session_factory() as db:
        claimed = matching.claim_work(db, limit)
        db.commit()
    out: dict[str, int] = {}
    for listing_id, generation in claimed:
        with session_factory() as db:
            try:
                result = matching.process_generation(db, listing_id, generation)
                db.commit()
            except Exception:  # noqa: BLE001 — one bad item never stops the batch
                db.rollback()
                log.exception("alert work item failed")
                result = matching.Outcome("error")
        metrics.WORK_ITEMS.labels(outcome=result.outcome).inc()
        out[result.outcome] = out.get(result.outcome, 0) + 1
    metrics.WORKER_BATCHES.labels(stage="work").inc()
    return out


def process_deliveries(session_factory=SessionLocal, limit: int | None = None) -> dict[str, int]:
    limit = limit or settings.saved_search_delivery_batch
    with session_factory() as db:
        claimed = delivery.claim_deliveries(db, limit)
        db.commit()
    out: dict[str, int] = {}
    for delivery_id in claimed:
        with session_factory() as db:
            try:
                status = delivery.deliver(db, delivery_id)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                log.exception("alert delivery failed")
                status = "error"
        out[status] = out.get(status, 0) + 1
    metrics.WORKER_BATCHES.labels(stage="delivery").inc()
    return out


def reconcile(db: Session, limit: int = 200) -> dict[str, int]:
    """Bounded recovery; the caller commits. Never crosses searches with
    listings:
    * work items and deliveries stuck in `processing` past STALE_CLAIM go
      back to `pending` (a crashed worker);
    * a listing that is public now, whose current episode began within
      RECONCILE_WINDOW and has an event but no work item, gets its work item
      back (index on public_since; at most `limit` rows)."""
    now = freshness.db_now(db)
    cutoff = now - matching.STALE_CLAIM
    reclaimed_work = typing_cast(CursorResult, db.execute(
        update(ListingPublicGeneration)
        .where(ListingPublicGeneration.alert_status == "processing",
               ListingPublicGeneration.claimed_at < cutoff)
        .values(alert_status="pending", claimed_at=None)
    )).rowcount
    reclaimed_deliveries = typing_cast(CursorResult, db.execute(
        update(AlertDelivery)
        .where(AlertDelivery.status == "processing", AlertDelivery.claimed_at < cutoff)
        .values(status="pending", claimed_at=None)
    )).rowcount
    missing = db.execute(
        select(ClassifiedOffer.id, ClassifiedOffer.public_generation,
               ClassifiedOffer.public_since, DomainEvent.id)
        .join(DomainEvent, DomainEvent.dedup_key == (
            literal(LISTING_BECAME_PUBLIC + ":") + ClassifiedOffer.id + literal(":")
            + cast(ClassifiedOffer.public_generation, String)))
        .outerjoin(ListingPublicGeneration, and_(
            ListingPublicGeneration.listing_id == ClassifiedOffer.id,
            ListingPublicGeneration.public_generation == ClassifiedOffer.public_generation))
        .where(ClassifiedOffer.public_since >= now - RECONCILE_WINDOW,
               ClassifiedOffer.public_generation > 0,
               freshness.public_clause(db),
               ListingPublicGeneration.listing_id.is_(None))
        .order_by(ClassifiedOffer.public_since)
        .limit(limit)
    ).all()
    restored = insert_ignore(db, ListingPublicGeneration, [
        {"listing_id": r[0], "public_generation": r[1], "became_public_at": r[2],
         "event_id": r[3], "alert_status": "pending", "attempts": 0, "last_error": ""}
        for r in missing
    ], ["listing_id", "public_generation"])
    metrics.SAVED_SEARCHES_ACTIVE.set(db.scalar(
        select(func.count()).select_from(SavedSearch)
        .where(SavedSearch.status == "active", SavedSearch.notifications_enabled.is_(True))) or 0)
    return {"reclaimed_work": int(reclaimed_work or 0),
            "reclaimed_deliveries": int(reclaimed_deliveries or 0),
            "restored_work": restored}


def run_once(session_factory=SessionLocal, *, reconcile_now: bool = False) -> dict:
    result: dict = {"work": process_work(session_factory),
                    "deliveries": process_deliveries(session_factory)}
    if reconcile_now:
        with session_factory() as db:
            result["reconcile"] = reconcile(db)
            db.commit()
    return result


class AlertWorker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _loop(self) -> None:
        passes = 0

        def one_pass() -> None:
            nonlocal passes
            passes += 1
            run_once(reconcile_now=passes % settings.saved_search_reconcile_every == 1)

        # PR-003: the shared loop (failure backoff, worker metrics).
        run_loop("saved-search-alerts", self._stop, one_pass,
                 lambda: settings.saved_search_worker_interval_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="saved-search-alerts",
                                         daemon=True)
        self._thread.start()
        log.info("saved-search alert worker started")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


worker = AlertWorker()
