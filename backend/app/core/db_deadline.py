"""Client-side database deadlines (PR-003).

Why the driver needs its own deadline
-------------------------------------
Server-side limits (`statement_timeout`, `lock_timeout`) are enforced by the
server. A server that is *frozen* (paused VM or container, stalled process) or
*gone* behind a partition never enforces them and never answers — and a frozen
host's kernel still acknowledges TCP, so neither TCP retransmission nor
keepalives notice. A synchronous psycopg call then waits on the socket for
ever: the request thread, its pooled connection and, with enough of them, the
whole AnyIO thread pool are lost (PR-001RA RA-3, measured in PR-003 Phase A).

The control
-----------
Every blocking call the application makes through a pooled connection —
`execute`/`executemany` (results are received inside them), `commit`,
`rollback` (pool reset included) and the pre-ping — is armed with a client
deadline of `statement_timeout + grace` on one watchdog thread. A live server
answers within `statement_timeout` (with the result or with its own 57014), so
the deadline only expires when the server cannot answer. Then the watchdog
shuts the socket down: the waiting call wakes at once with an error, the
connection is broken (psycopg marks it so) and SQLAlchemy invalidates it
instead of returning it to the pool. No cancel request is sent — that would be
another network wait on the same unresponsive server.

What it means for a transaction
-------------------------------
* expired during a statement: the transaction never committed (the server
  rolls it back when it notices the session is gone, or
  `idle_in_transaction_session_timeout` ends it) — safe to retry;
* expired during COMMIT: the outcome is UNKNOWN — the server may have
  committed before it stopped answering. `DatabaseDeadlineExceeded.operation`
  says so ("commit"); callers must not report success, and a retry is safe
  only for idempotent writes (see docs/tasks/PR-003).

Only the application's pooled engines are guarded. The readiness probe has its
own async deadline (app/core/health.py) and the migration job its own engine
and lock budget (PR-002).
"""

from __future__ import annotations

import heapq
import itertools
import logging
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import psycopg
from prometheus_client import Counter

log = logging.getLogger("homies.db")

# Bounded labels only: `operation` is one of OPERATIONS.
OPERATIONS = ("statement", "commit", "rollback")
DEADLINE_EXCEEDED = Counter(
    "homies_db_client_deadline_exceeded_total",
    "Database calls abandoned at the client deadline (server did not answer); "
    "the connection was shut down and discarded",
    ["operation"],
)
for _op in OPERATIONS:
    DEADLINE_EXCEEDED.labels(operation=_op)


class DatabaseDeadlineExceeded(psycopg.OperationalError):
    """The server did not answer within the client deadline.

    A psycopg OperationalError on purpose: SQLAlchemy wraps it as
    `sqlalchemy.exc.OperationalError`, and the connection it came from is broken
    (its socket was shut down), so the pool invalidates it. `operation` ==
    "commit" means the outcome of the transaction is unknown.
    """

    def __init__(self, operation: str, budget_s: float):
        super().__init__(
            f"database did not answer within the client deadline ({budget_s:g}s, {operation})"
        )
        self.operation = operation
        self.budget_s = budget_s


@dataclass(eq=False)
class _Arm:
    id: int
    deadline: float
    fd: int
    fired: bool = field(default=False)


def _shutdown_socket(fd: int) -> None:
    """Shut the socket down without closing the descriptor (libpq owns it).

    shutdown(2) acts on the socket, so the thread blocked on it wakes with EOF;
    the descriptor stays valid until psycopg/SQLAlchemy close the connection.
    """
    sock = socket.socket(fileno=fd)
    try:
        sock.shutdown(socket.SHUT_RDWR)
    finally:
        sock.detach()


class Watchdog:
    """One daemon thread that interrupts calls past their deadline.

    `arm` and `disarm` take a lock, never the network. Firing happens under the
    same lock, so once `disarm` returns the call can no longer be interrupted:
    a call that completed in time is never cut afterwards.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._heap: list[tuple[float, int]] = []
        self._armed: dict[int, _Arm] = {}
        self._ids = itertools.count()
        self._thread: threading.Thread | None = None

    def arm(self, fd: int, budget_s: float) -> _Arm:
        arm = _Arm(next(self._ids), time.monotonic() + budget_s, fd)
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="db-deadline-watchdog",
                                                daemon=True)
                self._thread.start()
            earliest = self._heap[0][0] if self._heap else None
            self._armed[arm.id] = arm
            heapq.heappush(self._heap, (arm.deadline, arm.id))
            if earliest is None or arm.deadline < earliest:
                self._wake.notify()
        return arm

    def disarm(self, arm: _Arm) -> bool:
        """Stop watching; True if the deadline already fired."""
        with self._lock:
            self._armed.pop(arm.id, None)
            return arm.fired

    def armed(self) -> int:
        with self._lock:
            return len(self._armed)

    def _run(self) -> None:
        with self._lock:
            while True:
                # Disarmed entries are dropped lazily when they reach the top.
                while self._heap and self._heap[0][1] not in self._armed:
                    heapq.heappop(self._heap)
                if not self._heap:
                    self._wake.wait()
                    continue
                deadline, arm_id = self._heap[0]
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    self._wake.wait(remaining)
                    continue
                heapq.heappop(self._heap)
                arm = self._armed.pop(arm_id)
                arm.fired = True
                try:
                    _shutdown_socket(arm.fd)
                except OSError as exc:  # already closed by its owner: nothing waits on it
                    log.warning("db deadline: socket shutdown failed: %s", type(exc).__name__)


WATCHDOG = Watchdog()

# Only for a guarded connection made outside create_bounded_engine (which sets
# the policy's own value on every connection it opens).
DEFAULT_CLIENT_DEADLINE_S = 7.0


@contextmanager
def client_deadline(conn: psycopg.Connection[Any], operation: str) -> Iterator[None]:
    """Run one blocking driver call under the connection's client deadline."""
    try:
        fd = conn.pgconn.socket
    except psycopg.OperationalError:
        # Already closed or broken: the call fails on its own, without waiting.
        yield
        return
    budget = getattr(conn, "client_deadline_s", DEFAULT_CLIENT_DEADLINE_S)
    arm = WATCHDOG.arm(fd, budget)
    try:
        yield
    except psycopg.Error as exc:
        if WATCHDOG.disarm(arm):
            DEADLINE_EXCEEDED.labels(operation=operation).inc()
            log.warning("db deadline exceeded: operation=%s budget_s=%g", operation, budget)
            raise DatabaseDeadlineExceeded(operation, budget) from exc
        raise
    finally:
        # Idempotent; on success a fire that raced the reply leaves the
        # connection shut and broken — its next use fails and it is discarded.
        WATCHDOG.disarm(arm)


class DeadlineCursor(psycopg.Cursor[Any]):
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        with client_deadline(self.connection, "statement"):
            return super().execute(*args, **kwargs)

    def executemany(self, *args: Any, **kwargs: Any) -> None:
        with client_deadline(self.connection, "statement"):
            super().executemany(*args, **kwargs)


class DeadlineConnection(psycopg.Connection[Any]):
    client_deadline_s: float = DEFAULT_CLIENT_DEADLINE_S

    def commit(self) -> None:
        with client_deadline(self, "commit"):
            super().commit()

    def rollback(self) -> None:
        with client_deadline(self, "rollback"):
            super().rollback()
