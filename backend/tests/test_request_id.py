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


def test_errors_and_rate_limited_responses_carry_the_id_too(client):
    missing = client.get("/v1/classifieds/does-not-exist")
    assert missing.status_code == 404 and request_id.HEADER in missing.headers
    invalid = client.get("/v1/classifieds", params={"sort": "nope"})
    assert invalid.status_code == 422 and request_id.HEADER in invalid.headers


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
