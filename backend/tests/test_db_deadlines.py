"""PR-003 database deadline policy — the parts that need no PostgreSQL.

The behaviour against a real (stopped, frozen, locked) PostgreSQL is in
test_db_deadlines_pg.py; this file pins the policy, the watchdog mechanism,
the 503 mapping, the worker loop and the health endpoints' isolation.
"""

import asyncio
import inspect
import socket
import threading
import time

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import exc as sa_exc

from app.composition import create_phase1_app
from app.core import db as core_db
from app.core import worker_loop
from app.core.config import Settings
from app.core.db_deadline import DatabaseDeadlineExceeded, Watchdog
from app.core.db_failures import database_unavailable_handler, unavailability_reason
from tests.conftest import assert_unhandled_500

# --- the policy ----------------------------------------------------------------


def test_the_policy_is_read_from_settings_in_one_place():
    d = core_db.DatabaseDeadlines.from_settings(Settings())
    assert d == core_db.DatabaseDeadlines(
        connect_timeout_s=3, pool_timeout_s=5.0, lock_timeout_ms=2000,
        statement_timeout_ms=5000, idle_in_transaction_timeout_ms=60000,
        client_connection_check_interval_ms=2000, client_grace_s=2.0)
    # The client deadline is derived: a live server always answers first.
    assert d.client_deadline_s == 7.0 > d.statement_timeout_ms / 1000


def test_the_application_engine_carries_every_server_limit():
    args = core_db._connect_args("postgresql+psycopg://u:p@h:5432/d")
    assert args["connect_timeout"] == 3
    options = args["options"]
    for setting in ("timezone=UTC", "statement_timeout=5000", "lock_timeout=2000",
                    "idle_in_transaction_session_timeout=60000",
                    "client_connection_check_interval=2000"):
        assert f"-c {setting}" in options


def test_the_application_pool_wait_is_bounded():
    engine = core_db.create_bounded_engine("postgresql+psycopg://u:p@127.0.0.1:1/d")
    try:
        assert engine.pool.timeout() == 5.0  # SQLAlchemy's default is 30 s
    finally:
        engine.dispose()


@pytest.mark.parametrize("overrides", [
    {"db_connect_timeout_seconds": 1},
    {"db_lock_timeout_ms": 5000, "db_statement_timeout_ms": 5000},
    {"db_lock_timeout_ms": 0},
    {"db_idle_in_transaction_timeout_ms": 5000, "db_statement_timeout_ms": 5000},
    {"db_pool_timeout_seconds": 0},
    {"db_client_grace_seconds": 0},
    {"db_client_connection_check_interval_ms": -1},
])
def test_an_unworkable_policy_is_refused_at_startup(overrides):
    with pytest.raises(ValidationError):
        Settings(**overrides)


# --- the watchdog ----------------------------------------------------------------


def _blocked_reader(sock: socket.socket, outcome: dict) -> threading.Thread:
    def read():
        started = time.monotonic()
        outcome["data"] = sock.recv(16)  # blocks: the peer never writes
        outcome["took"] = time.monotonic() - started

    t = threading.Thread(target=read, daemon=True)
    t.start()
    return t


def test_the_watchdog_wakes_a_blocked_reader_at_the_deadline():
    a, b = socket.socketpair()
    try:
        outcome: dict = {}
        reader = _blocked_reader(a, outcome)
        dog = Watchdog()
        arm = dog.arm(a.fileno(), 0.3)
        reader.join(5)
        assert not reader.is_alive(), "the blocked call was not interrupted"
        assert outcome["data"] == b""  # EOF: the socket was shut down, not closed
        assert 0.25 <= outcome["took"] < 2.0
        assert dog.disarm(arm) is True
        assert a.fileno() != -1  # the descriptor still belongs to its owner
    finally:
        a.close()
        b.close()


def test_a_call_that_finished_in_time_is_never_cut_afterwards():
    a, b = socket.socketpair()
    try:
        dog = Watchdog()
        arm = dog.arm(a.fileno(), 0.2)
        assert dog.disarm(arm) is False
        time.sleep(0.4)
        b.sendall(b"x")
        assert a.recv(1) == b"x"  # still open for reading
        assert dog.armed() == 0
    finally:
        a.close()
        b.close()


def test_the_earliest_deadline_fires_first_whatever_the_arming_order():
    pairs = [socket.socketpair() for _ in range(2)]
    try:
        dog = Watchdog()
        late = dog.arm(pairs[0][0].fileno(), 5.0)
        early = dog.arm(pairs[1][0].fileno(), 0.2)
        time.sleep(0.6)
        assert early.fired is True and late.fired is False
        assert dog.disarm(late) is False
    finally:
        for x, y in pairs:
            x.close()
            y.close()


# --- 503 mapping -----------------------------------------------------------------


def _operational(orig: Exception) -> sa_exc.OperationalError:
    return sa_exc.OperationalError("SELECT 1", {}, orig)


@pytest.mark.parametrize("error, reason", [
    (sa_exc.TimeoutError("QueuePool limit"), "pool_timeout"),
    (_operational(psycopg.OperationalError("connection refused")), "connection"),
    (_operational(psycopg.errors.LockNotAvailable("lock")), "lock_timeout"),
    (_operational(psycopg.errors.QueryCanceled("statement timeout")), "statement_timeout"),
    (_operational(DatabaseDeadlineExceeded("statement", 7.0)), "client_deadline"),
    (_operational(DatabaseDeadlineExceeded("rollback", 7.0)), "client_deadline"),
    (_operational(DatabaseDeadlineExceeded("commit", 7.0)), "commit_unknown"),
])
def test_availability_failures_are_classified(error, reason):
    assert unavailability_reason(error) == reason


def test_other_database_errors_are_not_availability_failures():
    assert unavailability_reason(_operational(Exception("sqlite: no such table"))) is None
    assert unavailability_reason(sa_exc.IntegrityError("INSERT", {}, Exception())) is None


def _app_raising(error: Exception) -> FastAPI:
    app = create_phase1_app()

    @app.get("/x/boom")
    def boom():
        raise error

    return app


def test_a_database_that_cannot_serve_is_a_503_with_retry_after():
    client = TestClient(_app_raising(_operational(DatabaseDeadlineExceeded("statement", 7.0))))
    r = client.get("/x/boom")
    assert r.status_code == 503
    assert r.headers["Retry-After"] == "5"
    assert r.json() == {"detail": "Service temporarily unavailable"}
    assert "X-Request-ID" in r.headers


def test_an_abandoned_commit_says_the_outcome_is_unknown():
    client = TestClient(_app_raising(_operational(DatabaseDeadlineExceeded("commit", 7.0))))
    r = client.get("/x/boom")
    assert r.status_code == 503
    assert "outcome is unknown" in r.json()["detail"]


def test_a_pool_wait_timeout_is_a_503():
    r = TestClient(_app_raising(sa_exc.TimeoutError("QueuePool limit"))).get("/x/boom")
    assert r.status_code == 503


def test_an_operational_error_that_is_not_availability_stays_a_500(caplog):
    client = TestClient(_app_raising(_operational(Exception("no such table: x"))))
    assert_unhandled_500(client.get("/x/boom"), caplog, sa_exc.OperationalError)


def test_the_handler_never_echoes_the_error_message():
    secret = "postgresql://homies:s3cret@db:5432/homies"
    client = TestClient(_app_raising(_operational(psycopg.OperationalError(secret))))
    r = client.get("/x/boom")
    assert r.status_code == 503 and "s3cret" not in r.text


def test_the_handler_is_async_and_registered_for_both_error_types():
    assert inspect.iscoroutinefunction(database_unavailable_handler)
    app = create_phase1_app()
    assert app.exception_handlers[sa_exc.OperationalError] is database_unavailable_handler
    assert app.exception_handlers[sa_exc.TimeoutError] is database_unavailable_handler


# --- health isolation (RA-3) -----------------------------------------------------


def test_the_ops_endpoints_never_need_a_thread_pool_token():
    """Sync endpoints wait for one of AnyIO's tokens; when the database stalls
    business requests can hold them all. The probes and the scrape must not
    queue behind them (the behaviour is shown in test_db_deadlines_pg.py)."""
    app = create_phase1_app()
    endpoints = {r.path: r.endpoint for r in app.routes if getattr(r, "path", None) in
                 ("/healthz", "/readyz", "/metrics")}
    assert set(endpoints) == {"/healthz", "/readyz", "/metrics"}
    for path, endpoint in endpoints.items():
        assert inspect.iscoroutinefunction(endpoint), f"{path} would run in the thread pool"


def test_health_answers_while_every_thread_pool_token_is_taken():
    """The whole pool is occupied (as by business requests stuck on a stalled
    database); /healthz and /metrics still answer at once."""
    import anyio.to_thread

    app = create_phase1_app()
    release = threading.Event()

    @app.get("/x/occupy")
    def occupy():
        release.wait(30)
        return {}

    with TestClient(app) as client:
        limiter = client.portal.call(anyio.to_thread.current_default_thread_limiter)
        total = int(limiter.total_tokens)
        occupiers = [threading.Thread(target=client.get, args=("/x/occupy",), daemon=True)
                     for _ in range(total + 5)]
        try:
            for t in occupiers:
                t.start()
            deadline = time.monotonic() + 10
            while limiter.borrowed_tokens < total and time.monotonic() < deadline:
                time.sleep(0.05)
            assert limiter.borrowed_tokens == total, "the pool was not saturated"
            for path in ("/healthz", "/metrics"):
                started = time.monotonic()
                assert client.get(path).status_code == 200
                assert time.monotonic() - started < 1.0, path
        finally:
            release.set()
            for t in occupiers:
                t.join(10)


# --- workers ---------------------------------------------------------------------


def test_the_worker_wait_backs_off_after_failures_and_never_drops_below_the_interval():
    assert worker_loop.next_delay(5.0, 0) == 5.0
    assert [worker_loop.next_delay(0.5, n) for n in range(1, 9)] == [
        1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]
    assert worker_loop.next_delay(3600.0, 3) == 3600.0
    assert worker_loop.next_delay(1.0, 10_000) == worker_loop.FAILURE_BACKOFF_CAP_S


def test_the_worker_loop_survives_failures_and_reports_them(monkeypatch):
    monkeypatch.setattr(worker_loop, "next_delay", lambda interval, failures: 0.01)
    stop = threading.Event()
    calls: list[int] = []

    def flaky_pass():
        calls.append(1)
        if len(calls) in (1, 2):
            raise RuntimeError("database gone")
        if len(calls) >= 4:
            stop.set()

    def sample(outcome):
        return worker_loop.PASSES.labels(worker="t-loop", outcome=outcome)._value.get()

    loop = threading.Thread(target=worker_loop.run_loop,
                            args=("t-loop", stop, flaky_pass, lambda: 0.01), daemon=True)
    loop.start()
    loop.join(5)
    assert not loop.is_alive() and len(calls) == 4
    assert sample("failed") == 2
    assert sample("ok") == 2
    assert worker_loop.CONSECUTIVE_FAILURES.labels(worker="t-loop")._value.get() == 0
    assert worker_loop.NEXT_PASS_DUE.labels(worker="t-loop")._value.get() > 0


def test_every_phase1_worker_runs_the_shared_loop():
    import ast
    from pathlib import Path

    from app.composition import phase1_workers

    names = {w.name for w in phase1_workers()}
    assert names == {"notifications", "listing-freshness", "saved-search-alerts"}
    sources = ["app/modules/events/worker.py", "app/modules/properties/freshness_worker.py",
               "app/modules/alerts/worker.py"]
    used = set()
    for src in sources:
        tree = ast.parse(Path(src).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "run_loop"
                    and isinstance(node.args[0], ast.Constant)):
                used.add(node.args[0].value)
    assert used == names


def test_readiness_on_the_loop_is_awaitable():
    from app.core import health

    assert asyncio.iscoroutinefunction(health.check_database_async)


def test_concurrent_readiness_probes_share_one_database_probe(monkeypatch):
    """Single flight: a probe storm opens one connection, not one per caller."""
    from app.core import health

    calls: list[str] = []

    async def slow_probe(conninfo):
        calls.append(conninfo)
        await asyncio.sleep(0.3)

    monkeypatch.setattr(health, "_probe_postgres_async", slow_probe)

    async def storm():
        return await asyncio.gather(*(health.check_database_async(
            "postgresql+psycopg://u:p@db.invalid:5432/d") for _ in range(20)))

    results = asyncio.run(storm(), loop_factory=asyncio.SelectorEventLoop)
    assert all(r.ok for r in results)
    assert len(calls) == 1


def test_readiness_decides_at_the_budget_without_waiting_for_the_probe(monkeypatch):
    from app.core import health

    async def hung_probe(conninfo):
        await asyncio.sleep(30)

    monkeypatch.setattr(health, "_probe_postgres_async", hung_probe)
    monkeypatch.setattr(health, "PROBE_DEADLINE_S", 0.3)

    async def probe():
        started = time.monotonic()
        result = await health.check_database_async("postgresql+psycopg://u:p@db.invalid:5432/d")
        return result, time.monotonic() - started

    result, took = asyncio.run(probe(), loop_factory=asyncio.SelectorEventLoop)
    assert result.ok is False and result.error == "TimeoutError"
    assert 0.3 <= took < 1.5


def test_startup_and_release_checks_use_the_bounded_engine(monkeypatch):
    """The one-shot engines of the startup checks (schema compatibility, ledger
    and schema privileges) hung for ever on a frozen database (Phase A E9)."""
    from sqlalchemy.pool import NullPool

    from app.core import schema

    made = []

    def spy(url, **kwargs):
        made.append(kwargs)
        return core_db.create_engine("sqlite://")

    monkeypatch.setattr(core_db, "create_bounded_engine", spy)
    schema._check_engine("postgresql+psycopg://u:p@db:5432/d")
    assert made == [{"poolclass": NullPool}]


def test_metrics_expose_pool_and_thread_pool_pressure():
    """Phase A (B §2): pool and thread-pool pressure were in no metric."""
    with TestClient(create_phase1_app()) as client:
        body = client.get("/metrics").text
    for name in ("homies_threadpool_tokens_in_use", "homies_db_pool_connections_in_use",
                 "homies_db_pool_connections_capacity"):
        assert f"\n{name} " in body, name
    assert "\nhomies_threadpool_tokens_total 40.0" in body


def test_a_database_outage_is_one_log_line_per_failed_worker_pass(monkeypatch, caplog):
    """Phase A S12: a refused database produced 126 traceback lines a second."""
    import logging

    monkeypatch.setattr(worker_loop, "next_delay", lambda interval, failures: 0.01)
    stop = threading.Event()
    calls: list[int] = []

    def outage():
        calls.append(1)
        if len(calls) == 3:
            stop.set()
        raise _operational(psycopg.OperationalError("postgresql://homies:s3cret@db/homies"))

    with caplog.at_level(logging.WARNING, logger="homies.workers"):
        worker_loop.run_loop("t-outage", stop, outage, lambda: 0.01)
    records = [r for r in caplog.records if r.name == "homies.workers"]
    assert len(records) == 3
    assert all(r.exc_info is None and r.levelno == logging.WARNING for r in records)
    assert all("database unavailable (connection)" in r.getMessage() for r in records)
    assert "s3cret" not in caplog.text
