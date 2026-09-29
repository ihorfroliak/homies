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
import socket
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core import db as core_db
from app.core import health
from app.core.config import settings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

BOUND_S = health.PROBE_DEADLINE_S + 1.5
# Freeze after the connection is established: the decision budget, then the
# driver's own finite clean-up (cancel attempt + drain), plus scheduling slack.
# Measured ~13 s when the cancel request is frozen too (PR-001RA RA-1).
AFTER_CONNECT_BOUND_S = health.PROBE_DEADLINE_S + health.PROBE_DRIVER_CLEANUP_S + 3.0
# PostgreSQL ReadyForQuery, status idle: 'Z', length 5, 'I'. Seen once the
# startup/authentication exchange is complete.
READY_FOR_QUERY = b"Z\x00\x00\x00\x05I"


class FreezableProxy:
    def __init__(self, upstream: tuple[str, int]):
        self.upstream = upstream
        self.running = threading.Event()
        self.running.set()  # cleared = frozen
        self.stopped = False
        # freeze_after_ready: freeze everything at the first client bytes sent
        # on a connection whose handshake has completed (i.e. the query).
        self.freeze_after_ready = False
        self.frozen_mid_query = threading.Event()
        self.sockets: list[socket.socket] = []
        self.lock = threading.Lock()
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(64)
        self.port = self.listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _track(self, *socks):
        with self.lock:
            self.sockets.extend(socks)

    def _accept(self):
        # Polling accept: on Linux, closing a listener does not wake a thread
        # blocked in accept(), and the socket would keep accepting.
        self.listener.settimeout(0.1)
        while not self.stopped:
            try:
                client, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            client.settimeout(None)
            try:
                upstream = socket.create_connection(self.upstream, timeout=5)
                upstream.settimeout(None)
            except OSError:
                client.close()
                continue
            self._track(client, upstream)
            state = {"ready": False}
            for src, dst, direction in ((client, upstream, "c2s"), (upstream, client, "s2c")):
                threading.Thread(target=self._pump, args=(src, dst, state, direction),
                                 daemon=True).start()

    def _pump(self, src, dst, state, direction):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                if direction == "s2c" and READY_FOR_QUERY in data:
                    state["ready"] = True  # set before the client can answer it
                if (direction == "c2s" and self.freeze_after_ready and state["ready"]
                        and not self.frozen_mid_query.is_set()):
                    self.running.clear()
                    self.frozen_mid_query.set()
                while not self.running.wait(0.1):  # frozen: hold the bytes
                    if self.stopped:
                        return
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def freeze(self):
        self.running.clear()

    def resume(self):
        self.running.set()

    def stop(self):
        self.stopped = True
        self.running.set()
        time.sleep(0.3)  # let the accept loop observe `stopped`
        self.listener.close()
        with self.lock:
            for s in self.sockets:
                try:
                    s.close()
                except OSError:
                    pass

    def url(self) -> str:
        return make_url(TEST_DATABASE_URL).set(
            host="127.0.0.1", port=self.port).render_as_string(hide_password=False)


@pytest.fixture
def proxy():
    target = make_url(TEST_DATABASE_URL)
    p = FreezableProxy((target.host or "127.0.0.1", target.port or 5432))
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
    """Shaped like the application's engine (app/core/db.py), with a small
    pool so exhaustion would be visible."""
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=0, pool_timeout=2,
                         connect_args=core_db._connect_args(url))


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
    """The PR-001A case. The warmed application pool really does hang on the
    frozen server (shown with a bounded wait), while readiness answers 503 in
    bounded time, leaves the pool as it found it, and recovers."""
    url = proxy.url()
    app_engine = _app_like_engine(url)
    try:
        conns = [app_engine.connect() for _ in range(2)]  # warm both slots
        for c in conns:
            c.execute(text("SELECT 1"))
            c.close()
        assert app_engine.pool.checkedin() == 2

        proxy.freeze()

        # The defect this replaces: the application path blocks (pre-ping on a
        # warm connection waits for a reply that never comes).
        outcome: list[object] = []

        def app_query():
            try:
                with app_engine.connect() as c:
                    outcome.append(c.execute(text("SELECT 1")).scalar())
            except Exception as exc:  # noqa: BLE001
                outcome.append(exc)

        stuck = threading.Thread(target=app_query, daemon=True)
        stuck.start()
        stuck.join(BOUND_S)
        assert stuck.is_alive() and not outcome, "the warm application path should hang"

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
        # The probes took nothing from the pool: only the deliberately stuck
        # application thread holds a connection.
        assert app_engine.pool.checkedout() == 1

        proxy.resume()
        started = time.monotonic()
        resp = client.get("/readyz")
        print(f"[F11] recovered: /readyz {resp.status_code} "
              f"{(time.monotonic() - started) * 1000:.0f} ms")
        assert resp.status_code == 200
        stuck.join(10)
        assert outcome == [1], "the application query completes once the server resumes"
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
