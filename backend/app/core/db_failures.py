"""Database unavailability as an HTTP answer (PR-003).

A request that fails because the database could not serve it in time — no
pooled connection within the pool wait, no connection, a lock or statement
timeout, or the client deadline — is a temporary condition of this instance,
not a bug in the request: it is answered 503 with Retry-After instead of a
generic 500. Anything else (a constraint violation, a programming error, an
SQLite error in tests) is not touched and keeps its existing handling.

A COMMIT abandoned at the client deadline is different: the server may have
committed before it stopped answering. That response says the outcome is
unknown, so a client checks before it repeats a non-idempotent write.
"""

from __future__ import annotations

import logging

import psycopg
from fastapi import Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from sqlalchemy import exc as sa_exc

from app.core.db_deadline import DatabaseDeadlineExceeded

log = logging.getLogger("homies.db")

RETRY_AFTER_S = 5

# Bounded labels only: `reason` is one of REASONS.
REASONS = ("pool_timeout", "connection", "lock_timeout", "statement_timeout",
           "client_deadline", "commit_unknown")
UNAVAILABLE = Counter(
    "homies_db_unavailable_responses_total",
    "Requests answered 503 because the database could not serve them in time",
    ["reason"],
)
for _reason in REASONS:
    UNAVAILABLE.labels(reason=_reason)


def unavailability_reason(error: BaseException) -> str | None:
    """Why the database could not serve, or None if `error` is something else."""
    if isinstance(error, sa_exc.TimeoutError):  # QueuePool wait exceeded
        return "pool_timeout"
    if not isinstance(error, sa_exc.OperationalError):
        return None
    orig = error.orig
    if isinstance(orig, DatabaseDeadlineExceeded):
        return "commit_unknown" if orig.operation == "commit" else "client_deadline"
    if isinstance(orig, psycopg.errors.LockNotAvailable):
        return "lock_timeout"
    if isinstance(orig, psycopg.errors.QueryCanceled):
        return "statement_timeout"
    if isinstance(orig, psycopg.OperationalError):
        return "connection"
    return None


async def database_unavailable_handler(request: Request, error: Exception) -> JSONResponse:
    reason = unavailability_reason(error)
    if reason is None:
        raise error  # not an availability problem: the generic 500 path (request_id)
    UNAVAILABLE.labels(reason=reason).inc()
    # Path and class only: the message can carry the DSN or SQL (D-37).
    log.warning("database unavailable (%s): %s %s %s", reason, request.method,
                request.url.path, type(getattr(error, "orig", error)).__name__)
    detail = ("The database stopped answering while this request was being committed; "
              "its outcome is unknown. Check before repeating it."
              if reason == "commit_unknown" else "Service temporarily unavailable")
    return JSONResponse(status_code=503, content={"detail": detail},
                        headers={"Retry-After": str(RETRY_AFTER_S)})
