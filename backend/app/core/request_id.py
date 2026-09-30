"""Request correlation id (PR-001).

Every HTTP request gets one id: the caller's `X-Request-ID` when it is a sane,
short token (so a proxy or the frontend can correlate end to end), otherwise a
fresh random one. It is echoed on the response and attached to every log
record written while the request is handled, so one failing request can be
followed through the logs without guessing by timestamp.

Deliberately small: no tracing system, no log shipping. The id carries no user
or request data, and a caller-supplied value is only accepted if it matches a
strict pattern — it ends up in logs and must not be a log-injection vector.

This middleware is the outermost one, so it is also where an unhandled
exception ends (PR-001R, F1). Left to propagate, it reached Starlette's
ServerErrorMiddleware and uvicorn *after* the id had been reset: the client got
a 500 without `X-Request-ID` and the only traceback was logged with
request_id "-". It is caught here instead, logged once while the id is still
current, and answered with a generic 500 carrying the id.
"""

import contextvars
import logging
import re
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

HEADER = "X-Request-ID"
# fullmatch, not `^...$` + match: `$` also matches before a trailing newline
# (PR-001R N1).
_ACCEPTED = re.compile(r"[A-Za-z0-9._-]{8,64}")
log = logging.getLogger("homies.http")
_current: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def current() -> str | None:
    return _current.get()


def _install_log_record_factory() -> None:
    """Give every LogRecord a `request_id` attribute ("-" outside a request),
    so any formatter may include %(request_id)s without KeyErrors."""
    previous = logging.getLogRecordFactory()
    if getattr(previous, "_homies_request_id", False):
        return

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.request_id = _current.get() or "-"
        return record

    factory._homies_request_id = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)


_install_log_record_factory()


async def request_id_middleware(request: Request, call_next):
    supplied = request.headers.get(HEADER, "")
    rid = supplied if _ACCEPTED.fullmatch(supplied) else uuid.uuid4().hex
    token = _current.set(rid)
    try:
        response = await call_next(request)
    except Exception:
        # Path only: the query string may carry personal data. The client gets
        # nothing of the exception — class, message and trace stay in the log.
        log.exception("unhandled error: %s %s", request.method, request.url.path)
        response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    finally:
        _current.reset(token)
    response.headers[HEADER] = rid
    return response
