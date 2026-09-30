"""Request correlation id (PR-001)."""

import logging

from app.core import request_id


def test_every_response_carries_a_generated_id(client):
    first = client.get("/healthz").headers[request_id.HEADER]
    second = client.get("/healthz").headers[request_id.HEADER]
    assert len(first) == 32 and first != second


def test_a_sane_caller_id_is_kept_for_end_to_end_correlation(client):
    rid = "frontend-7f3a9c10"
    assert client.get("/healthz", headers={request_id.HEADER: rid}).headers[
        request_id.HEADER] == rid


def test_a_hostile_caller_id_is_replaced_not_logged(client):
    for bad in ("short", "x" * 65, "evil\r\ninjected: yes", "id with spaces 123",
                "<script>alert(1)</script>"):
        got = client.get("/healthz", headers={request_id.HEADER: bad}).headers[
            request_id.HEADER]
        assert got != bad and len(got) == 32


def test_a_trailing_newline_does_not_pass_validation():
    """PR-001R N1: `^…$` with match() accepted "valid-id\\n" — `$` matches
    before a final newline. The header parser would normally refuse it first;
    the pattern must not rely on that."""
    assert request_id._ACCEPTED.fullmatch("frontend-7f3a9c10")
    assert not request_id._ACCEPTED.fullmatch("frontend-7f3a9c10\n")
    assert not request_id._ACCEPTED.fullmatch("frontend-7f3a9c10\r\n")


def test_the_middleware_replaces_an_id_with_a_trailing_newline():
    """At the middleware, with raw ASGI header bytes (HTTP clients refuse to
    send such a header, a hostile proxy or raw socket need not)."""
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"",
             "headers": [(b"x-request-id", b"frontend-7f3a9c10\n")]}

    async def call_next(_request):
        return Response("ok")

    response = asyncio.run(request_id.request_id_middleware(Request(scope), call_next))
    assert response.headers[request_id.HEADER] != "frontend-7f3a9c10\n"
    assert len(response.headers[request_id.HEADER]) == 32


def test_handled_errors_carry_the_id_too(client):
    missing = client.get("/v1/classifieds/does-not-exist")
    assert missing.status_code == 404 and request_id.HEADER in missing.headers
    invalid = client.get("/v1/classifieds", params={"sort": "nope"})
    assert invalid.status_code == 422 and request_id.HEADER in invalid.headers


def test_a_rate_limited_response_carries_the_callers_id(client):
    """PR-001R N7: the 429 is written by the rate limiter, inside this
    middleware; it must keep the id like any other response."""
    from app.core import ratelimit as rl
    from app.core.config import settings

    original = settings.rate_limit_enabled
    settings.rate_limit_enabled = True
    rl.limiter.reset()
    try:
        responses = [
            client.post("/v1/auth/login", headers={request_id.HEADER: f"probe-429-{i:04d}"},
                        json={"email": "nobody@example.com", "password": "wrong-password"})
            for i in range(rl.AUTH_LOGIN_IP.capacity + 2)
        ]
    finally:
        settings.rate_limit_enabled = original
        rl.limiter.reset()
    throttled = [(i, r) for i, r in enumerate(responses) if r.status_code == 429]
    assert throttled, [r.status_code for r in responses]
    for i, r in throttled:
        assert r.headers[request_id.HEADER] == f"probe-429-{i:04d}"
        assert "retry-after" in {k.lower() for k in r.headers}


# --- unhandled exceptions (PR-001R F1) ---------------------------------------


def _failing_app():
    """A real composition (every production middleware) with one route that
    raises after logging, and one that succeeds after logging."""
    import asyncio

    from fastapi import APIRouter

    from app.composition import build_app

    router = APIRouter(tags=["ops"])
    work_log = logging.getLogger("homies.test.work")

    @router.get("/boom/{n}")
    async def boom(n: int):
        work_log.warning("working on %s", n)
        await asyncio.sleep(0.001 * (n % 5))  # interleave concurrent requests
        raise RuntimeError(f"internal detail {n}: postgresql://u:s3cret@db/x")

    @router.get("/fine/{n}")
    async def fine(n: int):
        work_log.warning("working on %s", n)
        await asyncio.sleep(0.001 * (n % 3))
        return {"n": n}

    return build_app([router], [])


class _Grab(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


def _grab(*names):
    handler = _Grab()
    loggers = [logging.getLogger(n) for n in names]
    for lg in loggers:
        lg.addHandler(handler)
    return handler, loggers


def test_an_unhandled_exception_is_a_generic_500_with_the_request_id():
    from fastapi.testclient import TestClient

    handler, loggers = _grab("homies.http")
    try:
        # raise_server_exceptions stays at its default (True): if the exception
        # escaped the middleware, the test client would re-raise it here.
        resp = TestClient(_failing_app()).get(
            "/v1/boom/7", headers={request_id.HEADER: "caller-5e1f00d7"})
    finally:
        for lg in loggers:
            lg.removeHandler(handler)

    assert resp.status_code == 500
    assert resp.headers[request_id.HEADER] == "caller-5e1f00d7"
    assert resp.json() == {"detail": "Internal Server Error"}
    for leak in ("RuntimeError", "internal detail", "s3cret", "Traceback", "postgresql://"):
        assert leak not in resp.text

    errors = [r for r in handler.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1, "logged exactly once, by the middleware"
    assert errors[0].request_id == "caller-5e1f00d7"
    assert errors[0].exc_info and errors[0].exc_info[0] is RuntimeError
    assert "/v1/boom/7" in errors[0].getMessage()


def test_a_generated_id_is_the_same_on_the_500_and_in_its_log():
    from fastapi.testclient import TestClient

    handler, loggers = _grab("homies.http")
    try:
        resp = TestClient(_failing_app()).get("/v1/boom/3")
    finally:
        for lg in loggers:
            lg.removeHandler(handler)
    rid = resp.headers[request_id.HEADER]
    assert resp.status_code == 500 and len(rid) == 32
    assert [r.request_id for r in handler.records if r.levelno >= logging.ERROR] == [rid]


def test_the_500_is_counted_as_a_server_error():
    """Metrics sit inside this middleware and must still see the 5xx."""
    from fastapi.testclient import TestClient
    from prometheus_client import REGISTRY

    labels = {"method": "GET", "route": "/v1/boom/{n}", "status": "5xx"}
    before = REGISTRY.get_sample_value("homies_http_requests_total", labels) or 0
    TestClient(_failing_app()).get("/v1/boom/1")
    assert REGISTRY.get_sample_value("homies_http_requests_total", labels) == before + 1


def test_concurrent_failing_requests_do_not_mix_ids():
    import asyncio

    import httpx

    app = _failing_app()
    handler, loggers = _grab("homies.http", "homies.test.work")

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
            calls = []
            for n in range(40):
                path = f"/v1/boom/{n}" if n % 2 else f"/v1/fine/{n}"
                calls.append(ac.get(path, headers={request_id.HEADER: f"concurrent-{n:04d}"}))
            return await asyncio.gather(*calls)

    try:
        responses = asyncio.run(run())
    finally:
        for lg in loggers:
            lg.removeHandler(handler)

    for n, resp in enumerate(responses):
        assert resp.status_code == (500 if n % 2 else 200)
        assert resp.headers[request_id.HEADER] == f"concurrent-{n:04d}"
    work = [r for r in handler.records if r.name == "homies.test.work"]
    errors = [r for r in handler.records if r.name == "homies.http"]
    assert len(work) == 40 and len(errors) == 20
    # Every record was written under the id of the request that produced it.
    for record in work:
        assert record.request_id == f"concurrent-{int(record.args[0]):04d}"
    for record in errors:
        n = int(record.args[1].rsplit("/", 1)[1])
        assert n % 2 and record.request_id == f"concurrent-{n:04d}"
    assert request_id.current() is None


def test_log_records_carry_the_request_id(client, caplog):
    seen = []

    class Grab(logging.Handler):
        def emit(self, record):
            seen.append(getattr(record, "request_id", None))

    handler = Grab()
    logger = logging.getLogger("homies.test.request_id")
    logger.addHandler(handler)
    try:
        logger.warning("outside any request")
        assert seen[-1] == "-"
        token = request_id._current.set("abcdef0123456789")
        try:
            logger.warning("inside a request")
        finally:
            request_id._current.reset(token)
        assert seen[-1] == "abcdef0123456789"
    finally:
        logger.removeHandler(handler)


def test_process_logging_is_text_or_json_with_the_request_id(monkeypatch):
    import json

    from app.core import logging_config

    record = logging.LogRecord("homies.x", logging.INFO, __file__, 1, "hello %s", ("world",),
                               None)
    record.request_id = "abcdef0123456789"
    line = json.loads(logging_config.JsonFormatter().format(record))
    assert line["message"] == "hello world" and line["request_id"] == "abcdef0123456789"
    assert logging.Formatter(logging_config.TEXT_FORMAT).format(record).endswith(
        "homies.x [abcdef0123456789] hello world")
    # Under test the process logging is left to pytest.
    root = logging.getLogger()
    handlers = list(root.handlers)
    logging_config.configure_logging()
    assert root.handlers == handlers
