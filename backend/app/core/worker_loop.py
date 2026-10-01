"""The loop every background worker runs (PR-003).

One pass, then a wait, until stopped — with three properties the per-worker
loops did not all have:

* a failed pass never ends the loop and never makes it hotter: after
  consecutive failures the wait grows (doubling, capped) and never drops below
  the worker's own interval;
* a pass is bounded: it only waits on the database through the deadline-guarded
  engine (app/core/db_deadline.py), so a frozen database fails it instead of
  occupying the thread for ever;
* a database outage is one line per failed pass, not a traceback storm (Phase
  A S12: 126 log lines/s); any other failure keeps its full traceback;
* liveness is observable: `homies_worker_next_pass_due_timestamp_seconds` says
  when the next pass should start. A worker that is hung in a pass or whose
  thread died stops moving it, which an alert can see (WorkerOverdue) whatever
  the worker's interval is.

Labels are bounded: `worker` is a composition name (app/composition.py).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from prometheus_client import Counter, Gauge

from app.core.db_failures import unavailability_reason

log = logging.getLogger("homies.workers")

PASSES = Counter("homies_worker_passes_total", "Background worker passes by outcome",
                 ["worker", "outcome"])
CONSECUTIVE_FAILURES = Gauge("homies_worker_consecutive_failures",
                             "Failed passes in a row (0 after a successful pass)", ["worker"])
NEXT_PASS_DUE = Gauge("homies_worker_next_pass_due_timestamp_seconds",
                      "Unix time the worker's next pass is due to start", ["worker"])

FAILURE_BACKOFF_BASE_S = 1.0
FAILURE_BACKOFF_CAP_S = 60.0


def next_delay(interval_s: float, consecutive_failures: int) -> float:
    """The wait before the next pass: the interval, or longer after failures."""
    if consecutive_failures <= 0:
        return interval_s
    backoff = FAILURE_BACKOFF_BASE_S * 2 ** min(consecutive_failures - 1, 16)
    return max(interval_s, min(FAILURE_BACKOFF_CAP_S, backoff))


def run_loop(name: str, stop: threading.Event, run_pass: Callable[[], object],
             interval_s: Callable[[], float]) -> None:
    failures = 0
    NEXT_PASS_DUE.labels(worker=name).set(time.time())  # the first pass is due now
    while not stop.is_set():
        try:
            run_pass()
        except Exception as exc:  # noqa: BLE001 — one failed pass must never end the worker
            failures += 1
            PASSES.labels(worker=name, outcome="failed").inc()
            reason = unavailability_reason(exc)
            if reason is not None:
                # Reason only: the message can carry the DSN or SQL (D-37).
                log.warning("worker %s pass failed: database unavailable (%s), %d in a row",
                            name, reason, failures)
            else:
                log.exception("worker %s pass failed (%d in a row)", name, failures)
        else:
            failures = 0
            PASSES.labels(worker=name, outcome="ok").inc()
        CONSECUTIVE_FAILURES.labels(worker=name).set(failures)
        delay = next_delay(interval_s(), failures)
        NEXT_PASS_DUE.labels(worker=name).set(time.time() + delay)
        stop.wait(delay)
