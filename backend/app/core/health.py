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

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import engine

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
        return CheckResult(
            ok=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            error=type(exc).__name__,
        )
    return CheckResult(ok=True, latency_ms=round((time.perf_counter() - started) * 1000, 2))
