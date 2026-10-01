"""Readiness under database faults, against a real PostgreSQL (PR-001R F11).

The database sits behind a small TCP proxy the test can *stop* (connections
refused and reset) or *freeze* (connections still accepted and bytes still
acknowledged by the kernel, but nothing forwarded — what a paused container or
a stalled server looks like to a client). A frozen server is the case that no
TCP-level timeout ends, and the one PR-001A showed hanging `/readyz` once the
application pool was warm.

Durations are printed (run with -s) as evidence; the assertions use generous
bounds and are not a production SLO.
"""

import json
import os
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core import db as core_db
from app.core.db import DEADLINES
from app.core import health
from app.core.config import settings
from tests.pg_fault_proxy import FreezableProxy

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

BOUND_S = health.PROBE_DEADLINE_S + 1.5
# Freeze after the connection is established: the decision budget, then the
# driver's own finite clean-up (cancel attempt + drain), plus scheduling slack.
# Measured ~13 s when the cancel request is frozen too (PR-001RA RA-1).
AFTER_CONNECT_BOUND_S = health.PROBE_DEADLINE_S + health.PROBE_DRIVER_CLEANUP_S + 3.0
@pytest.fixture
def proxy():
    target = make_url(TEST_DATABASE_URL)
    p = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    yield p
    p.stop()


@pytest.fixture
def app_pool_untouched(monkeypatch):
    """Readiness on PostgreSQL must never reach the application engine."""

    def forbidden(*a, **k):
        raise AssertionError("readiness used the application pool")

    monkeypatch.setattr(health.engine, "connect", forbidden)


def _timed(url):
    started = time.monotonic()
    result = health.check_database(url)
    return result, time.monotonic() - started


def _app_like_engine(url):
    """The application's engine (app/core/db.py, PR-003 deadlines included),
    with a small pool so exhaustion would be visible."""
    return core_db.create_bounded_engine(url, pool_size=2, max_overflow=0, pool_timeout=2)


def test_healthy_database_is_ready(proxy, app_pool_untouched):
    result, took = _timed(proxy.url())
    print(f"\n[F11] healthy: ok={result.ok} {took * 1000:.0f} ms")
    assert result.ok is True


def test_stopped_database_is_a_bounded_503(proxy, app_pool_untouched):
    url = proxy.url()
    proxy.stop()
    result, took = _timed(url)
    print(f"\n[F11] stopped: ok={result.ok} error={result.error} {took * 1000:.0f} ms")
    assert result.ok is False and took < BOUND_S


def test_frozen_database_without_a_warm_pool_is_a_bounded_503(proxy, app_pool_untouched):
    proxy.freeze()
    result, took = _timed(proxy.url())
    print(f"\n[F11] frozen, cold: ok={result.ok} error={result.error} {took * 1000:.0f} ms")
    assert result.ok is False and took < BOUND_S


def test_frozen_database_after_the_pool_is_warm(proxy, monkeypatch):
    """The PR-001A case. Until PR-003 the warmed application pool hung on the
    frozen server for ever; now its pre-ping is abandoned at the client
    deadline and the reconnect fails at connect_timeout. Readiness answers 503
    in bounded time without the application pool, and both recover."""
    url = proxy.url()
    app_engine = _app_like_engine(url)
    try:
        conns = [app_engine.connect() for _ in range(2)]  # warm both slots
        for c in conns:
            c.execute(text("SELECT 1"))
            c.close()
        assert app_engine.pool.checkedin() == 2

        proxy.freeze()

        # PR-003: the application path no longer blocks for ever (before, the
        # pre-ping on a warm connection waited for a reply that never came).
        outcome: list[object] = []

        def app_query():
            try:
                with app_engine.connect() as c:
                    outcome.append(c.execute(text("SELECT 1")).scalar())
            except Exception as exc:  # noqa: BLE001
                outcome.append(exc)

        app_bound_s = DEADLINES.client_deadline_s + DEADLINES.connect_timeout_s + 3.0
        started = time.monotonic()
        stuck = threading.Thread(target=app_query, daemon=True)
        stuck.start()
        stuck.join(app_bound_s)
        took = time.monotonic() - started
        assert not stuck.is_alive(), f"the warm application path hung past {app_bound_s:.0f} s"
        assert len(outcome) == 1 and isinstance(outcome[0], Exception), outcome
        print(f"\n[PR-003] frozen, warm pool: application query failed in {took:.2f} s "
              f"({type(outcome[0]).__name__})")
        assert app_engine.pool.checkedout() == 0, "the failed connection was not given back"

        # Readiness: bounded, repeatedly, without the application pool.
        monkeypatch.setattr(settings, "database_url", url)
        monkeypatch.setattr(health.engine, "connect", lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("readiness used the application pool")))
        client = TestClient(_readiness_app())
        durations = []
        for _ in range(6):
            started = time.monotonic()
            resp = client.get("/readyz")
            durations.append(time.monotonic() - started)
            assert resp.status_code == 503
            assert resp.json()["checks"]["database"]["ok"] is False
        print(f"\n[F11] frozen, warm pool: /readyz 503 x6, max {max(durations) * 1000:.0f} ms")
        assert max(durations) < BOUND_S
        # The probes took nothing from the pool.
        assert app_engine.pool.checkedout() == 0

        proxy.resume()
        started = time.monotonic()
        resp = client.get("/readyz")
        print(f"[F11] recovered: /readyz {resp.status_code} "
              f"{(time.monotonic() - started) * 1000:.0f} ms")
        assert resp.status_code == 200
        with app_engine.connect() as c:  # the pool recovers by itself
            assert c.execute(text("SELECT 1")).scalar() == 1
        assert app_engine.pool.checkedout() == 0
    finally:
        proxy.resume()
        app_engine.dispose()


def test_a_freeze_after_the_connection_is_established_is_a_finite_503(
        proxy, monkeypatch, app_pool_untouched):
    """PR-001RA RA-1: the connection is up, the query is in flight, then the
    server stops making progress — and so does the cancel request (a truly
    frozen server). No connect or TCP timeout can end this; only the probe's
    decision deadline does. Without it (PR-001RA mutation m12) the probe waits
    for ever; with it, /readyz answers 503 after the budget plus the driver's
    finite clean-up. Triggered by the protocol, not by sleeps."""
    monkeypatch.setattr(settings, "database_url", proxy.url())
    proxy.freeze_after_ready = True
    client = TestClient(_readiness_app())
    outcome: dict = {}

    def call():
        started = time.monotonic()
        response = client.get("/readyz")
        outcome.update(status=response.status_code, body=response.json(),
                       elapsed=time.monotonic() - started)

    worker = threading.Thread(target=call, daemon=True)
    worker.start()
    worker.join(AFTER_CONNECT_BOUND_S + 5)
    finished = not worker.is_alive()
    proxy.resume()  # release the frozen bytes so nothing lingers after the test
    worker.join(30)

    assert proxy.frozen_mid_query.is_set(), "the freeze must happen after the handshake"
    assert finished, (f"/readyz did not answer within {AFTER_CONNECT_BOUND_S + 5:.0f} s of a "
                      "freeze after connect — the decision deadline is missing")
    print(f"\n[F11] frozen after connect: /readyz {outcome['status']} "
          f"in {outcome['elapsed'] * 1000:.0f} ms")
    assert outcome["status"] == 503
    database = outcome["body"]["checks"]["database"]
    assert database["ok"] is False and database["error"] == "TimeoutError"
    # The deadline really decided it: not an early connect failure …
    assert outcome["elapsed"] >= health.PROBE_DEADLINE_S
    # … and the endpoint completed within the documented, measured bound.
    assert outcome["elapsed"] < AFTER_CONNECT_BOUND_S
    for leak in ("postgresql", "homies:", str(proxy.port)):
        assert leak not in json.dumps(outcome["body"])


def test_repeated_failed_probes_do_not_exhaust_the_application_pool(proxy):
    url = proxy.url()
    app_engine = _app_like_engine(url)
    try:
        with app_engine.connect() as c:
            c.execute(text("SELECT 1"))
        proxy.freeze()
        for _ in range(8):
            result, took = _timed(url)
            assert result.ok is False and took < BOUND_S
        assert app_engine.pool.checkedout() == 0
        proxy.resume()
        # Full pool capacity is still there after the storm.
        conns = [app_engine.connect() for _ in range(2)]
        assert all(c.execute(text("SELECT 1")).scalar() == 1 for c in conns)
        for c in conns:
            c.close()
        assert health.check_database(url).ok is True
    finally:
        proxy.resume()
        app_engine.dispose()


def _readiness_app():
    from app.composition import build_app

    return build_app([], [])
