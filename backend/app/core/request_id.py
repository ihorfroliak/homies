"""Request correlation id (PR-001).

Every HTTP request gets one id: the caller's `X-Request-ID` when it is a sane,
short token (so a proxy or the frontend can correlate end to end), otherwise a
fresh random one. It is echoed on the response and attached to every log
record written while the request is handled, so one failing request can be
followed through the logs without guessing by timestamp.

Deliberately small: no tracing system, no log shipping. The id carries no user
or request data, and a caller-supplied value is only accepted if it matches a
strict pattern — it ends up in logs and must not be a log-injection vector.
"""

import contextvars
import logging
import re
import uuid

from fastapi import Request

HEADER = "X-Request-ID"
_ACCEPTED = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
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
    rid = supplied if _ACCEPTED.match(supplied) else uuid.uuid4().hex
    token = _current.set(rid)
    try:
        response = await call_next(request)
    finally:
        _current.reset(token)
    response.headers[HEADER] = rid
    return response
