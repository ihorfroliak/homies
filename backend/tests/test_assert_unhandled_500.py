"""The shared unhandled-500 assertion checks the correlation id (CONV-001A CV-N3).

Before MICRO-001, `assert_unhandled_500` passed for a 500 without
X-Request-ID or with a log record under another id. These tests prove it now
refuses both, and accepts the real middleware behaviour end to end.
"""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.request_id import request_id_middleware
from tests.conftest import assert_unhandled_500


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(request_id_middleware)

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    return app


def test_the_real_middleware_passes_with_and_without_a_caller_id(caplog):
    client = TestClient(_app())
    with caplog.at_level(logging.ERROR, logger="homies.http"):
        assert_unhandled_500(client.get("/boom"), caplog, RuntimeError)
        rid = "caller-supplied-0001"
        assert_unhandled_500(client.get("/boom", headers={"X-Request-ID": rid}), caplog,
                             RuntimeError, request_id=rid)


class _Response:
    def __init__(self, headers):
        self.status_code, self.headers, self.text = 500, headers, "{}"

    def json(self):
        return {"detail": "Internal Server Error"}


class _Caplog:
    def __init__(self, request_id):
        record = logging.LogRecord("homies.http", logging.ERROR, __file__, 1, "unhandled", None,
                                   (RuntimeError, RuntimeError("x"), None))
        record.request_id = request_id
        self.records = [record]


@pytest.mark.parametrize("headers, logged_id, supplied", [
    ({}, "abc-00000001", None),                                   # no X-Request-ID
    ({"X-Request-ID": "abc-00000001"}, "other-0000001", None),    # log under another id
    ({"X-Request-ID": "abc-00000001"}, "abc-00000001", "caller-0001"),  # caller id ignored
])
def test_it_refuses_a_500_without_a_matching_correlation_id(headers, logged_id, supplied):
    with pytest.raises(AssertionError):
        assert_unhandled_500(_Response(headers), _Caplog(logged_id), RuntimeError,
                             request_id=supplied)
