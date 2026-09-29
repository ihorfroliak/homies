"""Process logging for the deployed entry point (PR-001).

Before this, nothing configured Python logging: uvicorn set up its own loggers
and every `homies.*` record below WARNING went nowhere — "schema verified at
head", worker progress, sweep results were silently dropped. This installs one
stdout handler on the root logger, once, in the deployed process only
(app/main.py); tests keep pytest's own capture.

LOG_FORMAT=text (default) or json — one JSON object per line for a log
shipper. LOG_LEVEL=INFO by default. Every record carries the request id
(app/core/request_id.py), "-" outside a request. Messages are logged as given:
code must not put secrets in them (config errors name fields, never values).
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_homies_configured", False):
        return
    from app.core.config import settings

    if settings.env == "test":
        return  # pytest owns log capture
    import app.core.request_id  # noqa: F401 — installs the request_id record attribute

    handler = logging.StreamHandler(sys.stdout)
    if os.environ.get("LOG_FORMAT", "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    root._homies_configured = True  # type: ignore[attr-defined]
