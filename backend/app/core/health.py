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

import time
from dataclasses import dataclass

from prometheus_client import Gauge
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import engine

# OBS-06: /readyz answers an orchestrator, but Prometheus cannot read an HTTP
# probe — without these the most important dependency in the system had no
# alertable signal at all. The gauge is refreshed by every readiness probe
# rather than at scrape time, so a hung database slows the probe (already
# bounded) instead of the scrape. The timestamp exists because a stale `1`
# reads as healthy: alerts must require freshness, not just the value.
DATABASE_UP = Gauge("homies_database_up", "1 if the last readiness probe reached the database")
DATABASE_CHECKED_AT = Gauge(
    "homies_database_last_check_timestamp_seconds", "Unix time of the last readiness probe"
)

# The probe must fail fast. An orchestrator re-probes every few seconds; a probe
# that blocks on a *hung* (rather than refused) database holds a pool connection
# and stacks up behind itself until the pool is exhausted — at which point the
# probe has caused the outage it was meant to report. Enforced server-side via
# SET LOCAL, so it reverts with the transaction and never leaks onto the pooled
# connection. SQLite (tests) has no equivalent and needs none.
PROBE_STATEMENT_TIMEOUT_MS = 2000


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    latency_ms: float
    # Exception *class name* only, never the message: a SQLAlchemy connection
    # error stringifies the DSN, and /readyz is unauthenticated. See D-37.
    error: str | None = None


def check_database() -> CheckResult:
    """Round-trip the real connection pool with a bounded `SELECT 1`."""
    started = time.perf_counter()
    try:
        with engine.connect() as conn, conn.begin():
            if conn.dialect.name == "postgresql":
                conn.execute(text(f"SET LOCAL statement_timeout = {PROBE_STATEMENT_TIMEOUT_MS}"))
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        _publish(up=False)
        return CheckResult(
            ok=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            error=type(exc).__name__,
        )
    _publish(up=True)
    return CheckResult(ok=True, latency_ms=round((time.perf_counter() - started) * 1000, 2))


def _publish(*, up: bool) -> None:
    DATABASE_UP.set(1 if up else 0)
    DATABASE_CHECKED_AT.set(time.time())
