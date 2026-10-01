"""Periodic freshness maintenance on the existing BackgroundWorker seam.

The same shape as the notification worker (app/composition.py registers
both); no second scheduler stack. Off by default
(`listing_freshness_worker_enabled`): the operation is also a CLI
(`python -m app.scripts.listing_freshness sweep`) for an external scheduler.
Visibility never waits for this — the public rule is evaluated on read — so
the interval only decides how soon owners see `stale` and events appear.
Running it in several processes at once is safe: every pass is a conditional,
row-locking, skip-locked update plus deduplicated events.
"""

import logging
import threading

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.worker_loop import run_loop
from app.modules.properties import freshness

log = logging.getLogger("homies.freshness")


def run_once() -> dict:
    """Sweep in batches until a pass transitions less than a full batch."""
    totals = {"staled": 0, "reminded": 0}
    while True:
        with SessionLocal() as db:
            result = freshness.sweep(db, limit=settings.listing_freshness_batch)
            db.commit()
        totals["staled"] += len(result.staled)
        totals["reminded"] += len(result.reminded)
        if len(result.staled) < settings.listing_freshness_batch:
            return totals


class FreshnessWorker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _pass(self) -> None:
        log.info("listing freshness sweep: %s", run_once())

    def _loop(self) -> None:
        # PR-003: the shared loop (failure backoff, worker metrics).
        run_loop("listing-freshness", self._stop, self._pass,
                 lambda: settings.listing_freshness_interval_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="freshness-worker",
                                        daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


worker = FreshnessWorker()
