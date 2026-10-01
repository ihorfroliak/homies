"""Liveness and readiness probes (OBS-01).

The split between the two is deliberate and load-bearing:

* **Liveness** (`/healthz`) answers *"is this process still working?"*. A failing
  liveness probe makes an orchestrator **restart the container**. It must
  therefore not depend on anything external: if it checked the database, a
  database outage would fail every replica at once, restart all of them, and
  turn a recoverable dependency outage into a self-inflicted crash loop — which
  then stampedes the database with cold starts the moment it comes back.

* **Readiness** (`/readyz`) answers *"should this instance receive traffic?"*. A
  failing readiness probe **removes the instance from the load balancer and
  leaves the process running**, so it rejoins by itself once the dependency
  returns. This is where a database check belongs.

The audit records OBS-01 as "`/healthz` does not check the database", but
implementing that literally builds the outage amplifier described above. The
same finding goes on to name the actual gap — "no readiness/liveness split" —
and that is what this module closes.

Scope is deliberately the database only. A stopped notification worker does not
make the instance unfit to serve HTTP, so it is an alerting concern (OBS-02/03),
not a readiness one. Schema drift is not re-checked here either: startup already
refuses to boot unless migrations are at head (D-35).
"""

import asyncio
import sys
import time
from dataclasses import dataclass

import anyio
import psycopg
from prometheus_client import Gauge
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.db import engine

# OBS-06: /readyz answers an orchestrator, but Prometheus cannot read an HTTP
# probe — without these the most important dependency in the system had no
# alertable signal at all. The gauge is refreshed by every readiness probe
# rather than at scrape time, so a hung database slows the probe (finite, see
# below) instead of the scrape. The timestamp exists because a stale `1`
# reads as healthy: alerts must require freshness, not just the value.
DATABASE_UP = Gauge("homies_database_up", "1 if the last readiness probe reached the database")
DATABASE_CHECKED_AT = Gauge(
    "homies_database_last_check_timestamp_seconds", "Unix time of the last readiness probe"
)

# The probe must fail fast. An orchestrator re-probes every few seconds; a probe
# that blocks on a *hung* (rather than refused) database stacks up behind itself
# and, on the application pool, would exhaust it — at which point the probe has
# caused the outage it was meant to report.
#
# PR-001R F11: server-side `statement_timeout` and `connect_timeout` were not
# enough. A *frozen* server (paused VM/container, stalled process) still has a
# kernel that completes TCP handshakes and acknowledges data, so no TCP timeout
# fires, and a warm pooled connection's `pool_pre_ping` then waits for a reply
# for ever. Readiness therefore does not use the application pool at all on
# PostgreSQL: each probe opens one fresh connection under a client-side
# wall-clock deadline and closes it. A stuck probe cannot hold an application
# connection.
#
# PR-001R2 (PR-001RA RA-1) — what is and is not bounded, stated exactly:
#
# * PROBE_DEADLINE_S is the DEPENDENCY DECISION BUDGET: after it, the probe has
#   decided "not ready" (asyncio.wait_for fires). It is not the time the HTTP
#   response takes.
# * Completion after the decision includes clean-up that this code does not
#   control, and it is finite but longer in the measured fault cases:
#     - server frozen before the handshake (cold or with a warm app pool):
#       ~2.0–2.5 s — connect_timeout decides first;
#     - server frozen after the connection is established, query in flight:
#       ~7–13 s — on cancellation psycopg 3.3 sends a cancel request
#       (≤ ~5 s) and drains the connection (≤ ~5 s) before the task ends;
#       measured 7.25–7.28 s on a real `docker pause`, 8.0 s with a
#       cooperative cancel, 13.05 s when the cancel request is frozen too;
#     - host name that cannot be resolved: the resolver runs in a thread that
#       asyncio.run joins before returning — 3.8–4.0 s for a stopped Docker
#       container, ~10 s for an unreachable resolver (glibc retries); the OS
#       resolver's own timeouts, not this budget, decide that case.
#   Every case fails closed (503, exception class name only). There is no
#   universal end-to-end wall-clock guarantee, and none is claimed.
# * PR-003 (RA-3 closed): the endpoints no longer share the application thread
#   pool. /readyz awaits `check_database_async` on the event loop: one shared
#   in-flight probe per database (single flight — a probe storm opens one
#   connection, not one per caller), a response at the decision budget, and the
#   driver's clean-up left to finish in the background instead of in the
#   response. Business requests stuck on the database hold pool threads, not
#   the event loop, so they cannot delay /healthz, /readyz or /metrics.
PROBE_STATEMENT_TIMEOUT_MS = 2000
PROBE_CONNECT_TIMEOUT_S = 2  # libpq minimum is 2
PROBE_DEADLINE_S = 3.0  # dependency decision budget (see above), not end-to-end
# Clean-up after a decision the driver owns: psycopg's cancel attempt (≤ 5 s)
# plus its drain (≤ 5 s). Tests use it to bound the measured worst case.
PROBE_DRIVER_CLEANUP_S = 10.0


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    latency_ms: float
    # Exception *class name* only, never the message: a SQLAlchemy connection
    # error stringifies the DSN, and /readyz is unauthenticated. See D-37.
    error: str | None = None


def check_database(database_url: str | None = None) -> CheckResult:
    """A bounded `SELECT 1` against the application's database.

    PostgreSQL: a fresh, dedicated connection under a wall-clock deadline
    (never the application pool). Anything else (SQLite in tests): the
    application engine, which cannot hang on a network.
    """
    url = database_url or settings.database_url
    started = time.perf_counter()
    try:
        if url.startswith("postgresql"):
            _probe_postgres(url)
        else:
            _probe_engine()
    except _PROBE_ERRORS as exc:
        return _failed(started, exc)
    return _succeeded(started)


async def check_database_async(database_url: str | None = None) -> CheckResult:
    """`check_database` for the event loop (PR-003): what /readyz awaits.

    PostgreSQL: joins the in-flight probe of this database or starts one, and
    decides at PROBE_DEADLINE_S whatever the probe is still doing; no thread
    pool is involved. SQLite (tests) runs in a worker thread — it cannot hang
    on a network.
    """
    url = database_url or settings.database_url
    started = time.perf_counter()
    try:
        if url.startswith("postgresql"):
            if _is_proactor(asyncio.get_running_loop()):
                # psycopg's async connection cannot run on Windows' proactor
                # loop (a developer's machine): the threaded probe instead.
                return await anyio.to_thread.run_sync(check_database, url)
            probe = _shared_probe(_libpq_url(url))
            done, _ = await asyncio.wait({probe}, timeout=PROBE_DEADLINE_S)
            if not done:
                raise TimeoutError
            probe.result()
        else:
            await anyio.to_thread.run_sync(_probe_engine)
    except _PROBE_ERRORS as exc:
        return _failed(started, exc)
    return _succeeded(started)


_PROBE_ERRORS = (SQLAlchemyError, psycopg.Error, OSError, TimeoutError)

# One in-flight probe per database. Keyed by the libpq URI; a task belongs to
# the loop that made it, so another loop never joins it.
_inflight: dict[str, asyncio.Task[None]] = {}


def _shared_probe(conninfo: str) -> asyncio.Task[None]:
    loop = asyncio.get_running_loop()
    task = _inflight.get(conninfo)
    if task is None or task.done() or task.get_loop() is not loop:
        task = loop.create_task(_probe_postgres_async(conninfo), name="homies-readiness-probe")
        _inflight[conninfo] = task

        def _settled(t: asyncio.Task[None], key: str = conninfo) -> None:
            if _inflight.get(key) is t:
                del _inflight[key]
            if not t.cancelled():
                t.exception()  # retrieved: a failed probe is an answer, not a loop warning

        task.add_done_callback(_settled)
    return task


def _is_proactor(loop: asyncio.AbstractEventLoop) -> bool:
    proactor = getattr(asyncio, "ProactorEventLoop", None) if sys.platform == "win32" else None
    return proactor is not None and isinstance(loop, proactor)


def _probe_engine() -> None:
    with engine.connect() as conn, conn.begin():
        conn.execute(text("SELECT 1"))


def _failed(started: float, exc: BaseException) -> CheckResult:
    _publish(up=False)
    return CheckResult(
        ok=False,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        error=type(exc).__name__,
    )


def _succeeded(started: float) -> CheckResult:
    _publish(up=True)
    return CheckResult(ok=True, latency_ms=round((time.perf_counter() - started) * 1000, 2))


def _libpq_url(url: str) -> str:
    """The SQLAlchemy URL as a libpq URI (driver suffix dropped, query kept)."""
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def _probe_postgres(url: str) -> None:
    """Run the async probe on a private event loop in the calling thread.

    /readyz is a sync endpoint, so this runs on a threadpool worker. The
    decision budget and the driver's finite clean-up (module comment) bound how
    long that worker is held; name resolution is bounded by the OS resolver. A selector loop is asked for
    explicitly because psycopg's async connection cannot run on Windows'
    default proactor loop — the probe then behaves the same on a developer
    machine as in the Linux image.
    """
    asyncio.run(_probe_postgres_async(_libpq_url(url)), loop_factory=asyncio.SelectorEventLoop)


async def _probe_postgres_async(conninfo: str) -> None:
    conn: psycopg.AsyncConnection | None = None

    async def probe() -> None:
        nonlocal conn
        conn = await psycopg.AsyncConnection.connect(
            conninfo,
            autocommit=True,
            connect_timeout=PROBE_CONNECT_TIMEOUT_S,
            options=f"-c statement_timeout={PROBE_STATEMENT_TIMEOUT_MS}",
            application_name="homies-readiness",
        )
        await conn.execute("SELECT 1")

    try:
        # The decision: past the budget the probe is "not ready". Cancelling a
        # query in flight lets psycopg try a server-side cancel and drain the
        # connection first — finite (PROBE_DRIVER_CLEANUP_S), not instant.
        await asyncio.wait_for(probe(), PROBE_DEADLINE_S)
    finally:
        if conn is not None:
            await conn.close()


def _publish(*, up: bool) -> None:
    DATABASE_UP.set(1 if up else 0)
    DATABASE_CHECKED_AT.set(time.time())
