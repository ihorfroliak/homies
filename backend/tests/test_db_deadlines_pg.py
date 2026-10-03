"""PR-003: database client deadlines against a real PostgreSQL under faults.

The database sits behind tests/pg_fault_proxy.py, which can *stop* it
(refused, reset) or *freeze* it (bytes acknowledged, nothing forwarded — a
paused VM or container, a stalled server). Every call that could hang runs in a
thread joined with a bound, so a missing deadline fails the test instead of
hanging the suite.

The engines use a fast copy of the policy so the suite stays quick; the
production values are pinned in test_db_deadlines.py. Durations are printed
(run with -s) as evidence; the bounds are generous and not an SLO.
"""

import os
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

import psycopg
import pytest
from sqlalchemy import exc as sa_exc
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core import db as core_db
from app.core import health
from app.core.config import settings
from app.core.db_deadline import DEADLINE_EXCEEDED, DatabaseDeadlineExceeded
from app.core.db_failures import unavailability_reason
from tests.pg_fault_proxy import FreezableProxy

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

FAST = core_db.DatabaseDeadlines(
    connect_timeout_s=2, pool_timeout_s=1.0, lock_timeout_ms=500, statement_timeout_ms=1500,
    idle_in_transaction_timeout_ms=10_000, client_connection_check_interval_ms=500,
    client_grace_s=1.0)
DEADLINE_S = FAST.client_deadline_s  # 2.5 s
SLACK_S = 2.0
SCHEMA = "pr003_faults"


@pytest.fixture
def proxy():
    target = make_url(TEST_DATABASE_URL)
    p = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    yield p
    p.stop()


@pytest.fixture
def probe_table():
    """A scratch table outside `public`, so no schema test ever sees it."""
    admin = core_db.create_bounded_engine(TEST_DATABASE_URL)
    with admin.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        c.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        c.execute(text(f"CREATE TABLE {SCHEMA}.marks (mark text PRIMARY KEY, n int DEFAULT 0)"))
        c.execute(text(f"INSERT INTO {SCHEMA}.marks (mark) VALUES ('locked')"))
    yield admin
    with admin.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    admin.dispose()


def _engine(url: str, **kwargs):
    kwargs.setdefault("pool_size", 2)
    kwargs.setdefault("max_overflow", 0)
    return core_db.create_bounded_engine(url, deadlines=FAST, **kwargs)


def _bounded(fn, bound_s: float):
    """Run fn in a thread; (result or exception, seconds). Fails if it hangs."""
    box: dict = {}

    def run():
        started = time.monotonic()
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 — the outcome is what is asserted
            box["value"] = exc
        box["took"] = time.monotonic() - started

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(bound_s)
    assert not t.is_alive(), f"the call was still waiting after {bound_s:.1f} s — no deadline"
    return box["value"], box["took"]


def _count(admin, mark: str) -> int:
    with admin.connect() as c:
        return c.execute(text(f"SELECT count(*) FROM {SCHEMA}.marks WHERE mark = :m"),
                         {"m": mark}).scalar_one()


def _deadline_count(operation: str) -> float:
    return DEADLINE_EXCEEDED.labels(operation=operation)._value.get()


# --- statements, pre-ping, connect --------------------------------------------


def test_a_statement_the_frozen_server_never_answers_is_abandoned_at_the_deadline(proxy):
    engine = _engine(proxy.url())
    try:
        conn = engine.connect()
        assert conn.execute(text("SELECT 1")).scalar() == 1
        before = _deadline_count("statement")
        proxy.freeze()
        outcome, took = _bounded(lambda: conn.execute(text("SELECT 1")), DEADLINE_S + SLACK_S)
        print(f"\n[PR-003] frozen mid-statement: {type(outcome).__name__} in {took:.2f} s")
        assert isinstance(outcome, sa_exc.OperationalError)
        assert isinstance(outcome.orig, DatabaseDeadlineExceeded)
        assert outcome.orig.operation == "statement"
        assert unavailability_reason(outcome) == "client_deadline"
        assert outcome.connection_invalidated, "a dead connection must not go back to the pool"
        assert DEADLINE_S - 0.1 <= took < DEADLINE_S + SLACK_S
        assert _deadline_count("statement") == before + 1
        conn.close()
        assert engine.pool.checkedout() == 0
        proxy.resume()
        with engine.connect() as c:  # the pool replaces it by itself
            assert c.execute(text("SELECT 1")).scalar() == 1
    finally:
        proxy.resume()
        engine.dispose()


def test_a_warm_pool_on_a_frozen_server_fails_bounded_and_recovers(proxy):
    """Pre-ping on a warm pooled connection (it hung for ever before PR-003),
    then the reconnect, which connect_timeout ends."""
    engine = _engine(proxy.url())
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        proxy.freeze()

        def request():
            with engine.connect() as c:
                return c.execute(text("SELECT 1")).scalar()

        bound = DEADLINE_S + FAST.connect_timeout_s + SLACK_S
        outcome, took = _bounded(request, bound)
        print(f"\n[PR-003] frozen, warm pool: {type(outcome).__name__} in {took:.2f} s")
        assert isinstance(outcome, sa_exc.OperationalError)
        assert unavailability_reason(outcome) in ("client_deadline", "connection")
        assert engine.pool.checkedout() == 0
        proxy.resume()
        outcome, _ = _bounded(request, 10)
        assert outcome == 1
    finally:
        proxy.resume()
        engine.dispose()


def test_a_stopped_server_fails_fast(proxy):
    engine = _engine(proxy.url())
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        proxy.stop()

        def request():
            with engine.connect() as c:
                return c.execute(text("SELECT 1")).scalar()

        outcome, took = _bounded(request, FAST.connect_timeout_s + SLACK_S)
        print(f"\n[PR-003] stopped: {type(outcome).__name__} in {took:.2f} s")
        assert isinstance(outcome, sa_exc.OperationalError)
        assert unavailability_reason(outcome) == "connection"
    finally:
        engine.dispose()


def test_the_wait_for_a_pooled_connection_is_bounded(proxy):
    engine = _engine(proxy.url(), pool_size=1, max_overflow=0)
    try:
        held = engine.connect()
        held.execute(text("SELECT 1"))
        outcome, took = _bounded(engine.connect, FAST.pool_timeout_s + SLACK_S)
        print(f"\n[PR-003] pool exhausted: {type(outcome).__name__} in {took:.2f} s")
        assert isinstance(outcome, sa_exc.TimeoutError)
        assert unavailability_reason(outcome) == "pool_timeout"
        assert FAST.pool_timeout_s - 0.1 <= took < FAST.pool_timeout_s + SLACK_S
        held.close()
    finally:
        engine.dispose()


# --- server-side limits keep the connection --------------------------------------


def test_a_slow_statement_is_ended_by_the_server_and_the_connection_survives(probe_table):
    engine = _engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as conn:
            before = _deadline_count("statement")
            outcome, took = _bounded(lambda: conn.execute(text("SELECT pg_sleep(30)")),
                                     DEADLINE_S + SLACK_S)
            print(f"\n[PR-003] statement_timeout: {type(outcome).__name__} in {took:.2f} s")
            assert isinstance(outcome, sa_exc.OperationalError)
            assert isinstance(outcome.orig, psycopg.errors.QueryCanceled)
            assert unavailability_reason(outcome) == "statement_timeout"
            assert took < DEADLINE_S, "the server, not the client deadline, must end it"
            assert _deadline_count("statement") == before
            assert not outcome.connection_invalidated
            conn.rollback()
            assert conn.execute(text("SELECT 1")).scalar() == 1  # same connection, usable
    finally:
        engine.dispose()


def test_a_lock_wait_is_bounded_by_lock_timeout(probe_table):
    engine = _engine(TEST_DATABASE_URL)
    holder = probe_table.connect()
    try:
        tx = holder.begin()
        holder.execute(text(f"SELECT * FROM {SCHEMA}.marks WHERE mark = 'locked' FOR UPDATE"))
        with engine.connect() as conn:
            outcome, took = _bounded(
                lambda: conn.execute(text(f"UPDATE {SCHEMA}.marks SET n = n + 1 "
                                          "WHERE mark = 'locked'")),
                FAST.statement_timeout_ms / 1000 + SLACK_S)
            print(f"\n[PR-003] lock_timeout: {type(outcome).__name__} in {took:.2f} s")
            assert isinstance(outcome, sa_exc.OperationalError)
            assert isinstance(outcome.orig, psycopg.errors.LockNotAvailable)
            assert unavailability_reason(outcome) == "lock_timeout"
            assert took < FAST.statement_timeout_ms / 1000
            conn.rollback()
            assert conn.execute(text("SELECT 1")).scalar() == 1
        tx.rollback()
    finally:
        holder.close()
        engine.dispose()


# --- transactions: what a failed call means ---------------------------------------


def test_a_statement_abandoned_inside_a_transaction_never_commits(proxy, probe_table):
    """Not committed, so a retry is safe: the server ends the session (the
    client is gone) and rolls the transaction back."""
    engine = _engine(proxy.url())
    Session = sessionmaker(bind=engine)
    try:
        def write():
            with Session() as s:
                s.execute(text(f"INSERT INTO {SCHEMA}.marks (mark) VALUES ('mid-statement')"))
                proxy.freeze_on = b"SELECT 4242"
                s.execute(text("SELECT 4242"))
                s.commit()

        outcome, took = _bounded(write, DEADLINE_S + SLACK_S + 3)
        print(f"\n[PR-003] frozen before COMMIT: {type(outcome).__name__} in {took:.2f} s")
        assert isinstance(outcome, sa_exc.OperationalError)
        assert outcome.orig.operation == "statement"  # type: ignore[union-attr]
        proxy.resume()  # the held bytes reach a server whose client has gone
        time.sleep(1.0)
        assert _count(probe_table, "mid-statement") == 0
        assert engine.pool.checkedout() == 0
    finally:
        proxy.resume()
        engine.dispose()


def test_an_abandoned_commit_is_outcome_unknown_and_may_have_committed(proxy, probe_table):
    """The COMMIT left the client; the server stopped answering before the
    reply. Here it did commit once it resumed — exactly why the client must be
    told "unknown", never "failed" (Phase A, E5/E8)."""
    engine = _engine(proxy.url())
    Session = sessionmaker(bind=engine)
    try:
        def write():
            with Session() as s:
                s.execute(text(f"INSERT INTO {SCHEMA}.marks (mark) VALUES ('at-commit')"))
                proxy.freeze_on = b"COMMIT"
                s.commit()

        before = _deadline_count("commit")
        outcome, took = _bounded(write, DEADLINE_S + SLACK_S + 3)
        print(f"\n[PR-003] frozen at COMMIT: {type(outcome).__name__} in {took:.2f} s")
        assert proxy.frozen_on_marker.is_set()
        assert isinstance(outcome, sa_exc.OperationalError)
        assert isinstance(outcome.orig, DatabaseDeadlineExceeded)
        assert outcome.orig.operation == "commit"
        assert unavailability_reason(outcome) == "commit_unknown"
        assert _deadline_count("commit") == before + 1
        proxy.resume()
        time.sleep(1.0)
        committed = _count(probe_table, "at-commit")
        print(f"[PR-003] after resume the abandoned COMMIT applied: {bool(committed)}")
        assert committed == 1
        assert engine.pool.checkedout() == 0
    finally:
        proxy.resume()
        engine.dispose()


def test_session_close_after_a_failure_does_not_replace_the_error(proxy, probe_table):
    """get_db closes quietly: the rollback on an already shut connection must
    not mask the request's own (commit-unknown) error."""
    engine = _engine(proxy.url())
    Session = sessionmaker(bind=engine)
    try:
        def request():
            db = Session()
            try:
                db.execute(text(f"INSERT INTO {SCHEMA}.marks (mark) VALUES ('close')"))
                proxy.freeze_on = b"COMMIT"
                db.commit()
            finally:
                core_db.close_quietly(db)

        outcome, _ = _bounded(request, DEADLINE_S * 2 + SLACK_S + 3)
        assert unavailability_reason(outcome) == "commit_unknown"
        assert engine.pool.checkedout() == 0
    finally:
        proxy.resume()
        engine.dispose()


def test_closing_a_session_whose_rollback_meets_a_frozen_server_is_bounded_and_quiet(proxy):
    """A request that fails for its own reasons (a 404, a validation error)
    while the database freezes: get_db's close must roll back within the
    deadline and must not raise over the request's own answer."""
    engine = _engine(proxy.url())
    Session = sessionmaker(bind=engine)
    try:
        db = Session()
        db.execute(text("SELECT 1"))  # a transaction is open
        proxy.freeze()
        before = _deadline_count("rollback")
        outcome, took = _bounded(lambda: core_db.close_quietly(db), DEADLINE_S + SLACK_S)
        print(f"\n[PR-003] close on a frozen server: {outcome!r} in {took:.2f} s")
        assert outcome is None, "close_quietly raised"
        assert _deadline_count("rollback") == before + 1
        assert engine.pool.checkedout() == 0
    finally:
        proxy.resume()
        engine.dispose()


# --- the HTTP process under a database stall (RA-3) -------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _served(app):
    import uvicorn

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                           lifespan="on"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(15)


def _get(url: str, timeout: float = 30.0) -> tuple[int, dict, float]:
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, time.monotonic() - started
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, time.monotonic() - started


def test_health_and_metrics_answer_while_a_frozen_database_saturates_the_process(
        proxy, pg_migrated_engine, monkeypatch):
    """More stuck business requests than the thread pool has tokens; the
    probes and the scrape answer anyway, every business request ends with a
    503 in bounded time, and everything recovers when the database does."""
    from app.composition import create_phase1_app
    from app.core.db import get_db

    engine = _engine(proxy.url(), pool_size=5, max_overflow=0)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            core_db.close_quietly(db)

    monkeypatch.setattr(settings, "database_url", proxy.url())  # readiness probes the proxy
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    app = create_phase1_app()
    app.dependency_overrides[get_db] = override_get_db
    business = "/v1/geo/countries"
    try:
        with _served(app) as base:
            assert _get(base + business)[0] == 200  # warms the pool
            proxy.freeze()
            results: list[tuple[int, dict, float]] = []
            lock = threading.Lock()

            def call():
                r = _get(base + business, timeout=60)
                with lock:
                    results.append(r)

            stuck = [threading.Thread(target=call, daemon=True) for _ in range(60)]
            for t in stuck:
                t.start()
            time.sleep(1.0)  # every token taken, the pool frozen
            probes = {path: _get(base + path, timeout=10)
                      for path in ("/healthz", "/metrics", "/readyz")}
            print("\n[PR-003] under saturation: " + ", ".join(
                f"{p} {s} in {d:.2f} s" for p, (s, _, d) in probes.items()))
            # That the probes never take a thread-pool token is pinned
            # structurally (tests/test_db_deadlines.py: their endpoints are
            # coroutines). Here they must answer within the client deadline
            # under saturation; a 1 s bound failed on a loaded host where 60
            # client threads compete for the CPU (1.27 s seen; PROGRAM-001 P0).
            assert probes["/healthz"][0] == 200 and probes["/healthz"][2] < DEADLINE_S
            assert probes["/metrics"][0] == 200 and probes["/metrics"][2] < DEADLINE_S
            assert probes["/readyz"][0] == 503
            assert probes["/readyz"][2] < health.PROBE_DEADLINE_S + 1.0

            for t in stuck:
                t.join(60)
            assert not any(t.is_alive() for t in stuck), "a business request never ended"
            statuses = sorted({s for s, _, _ in results})
            slowest = max(d for _, _, d in results)
            print(f"[PR-003] 60 stuck requests: statuses {statuses}, slowest {slowest:.2f} s")
            assert statuses == [503]
            assert all(h.get("retry-after") == "5" for _, h, _ in results)

            proxy.resume()
            time.sleep(0.5)
            assert _get(base + "/readyz")[0] == 200
            assert _get(base + business)[0] == 200
            # The session is closed in the dependency's teardown, which may end
            # just after the client has the response: no connection may stay out.
            deadline = time.monotonic() + 5
            while engine.pool.checkedout() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert engine.pool.checkedout() == 0
    finally:
        proxy.resume()
        app.dependency_overrides.clear()
        engine.dispose()


# --- workers ----------------------------------------------------------------------


def test_a_worker_on_a_frozen_database_fails_its_pass_keeps_running_and_recovers(
        proxy, pg_migrated_engine, monkeypatch):
    from app.core import worker_loop
    from app.modules.events import worker as notification_worker

    engine = _engine(proxy.url())
    monkeypatch.setattr(notification_worker, "SessionLocal",
                        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))
    monkeypatch.setattr(settings, "notification_worker_interval_seconds", 0.2)
    monkeypatch.setattr(worker_loop, "FAILURE_BACKOFF_BASE_S", 0.2)
    monkeypatch.setattr(worker_loop, "FAILURE_BACKOFF_CAP_S", 0.5)

    def passes(outcome):
        return worker_loop.PASSES.labels(worker="notifications", outcome=outcome)._value.get()

    def wait_for(predicate, bound_s):
        deadline = time.monotonic() + bound_s
        while not predicate() and time.monotonic() < deadline:
            time.sleep(0.05)
        return predicate()

    w = notification_worker.NotificationWorker()
    w.start()
    try:
        ok0 = passes("ok")
        assert wait_for(lambda: passes("ok") > ok0, 10), "no healthy pass"
        proxy.freeze()
        failed0 = passes("failed")
        started = time.monotonic()
        assert wait_for(lambda: passes("failed") > failed0, DEADLINE_S + FAST.connect_timeout_s
                        + SLACK_S + 2), "the pass hung on the frozen database"
        print(f"\n[PR-003] worker pass failed after {time.monotonic() - started:.2f} s")
        assert w._thread is not None and w._thread.is_alive()
        failures = worker_loop.CONSECUTIVE_FAILURES.labels(worker="notifications")._value
        assert wait_for(lambda: failures.get() >= 1, 2)
        proxy.resume()
        ok1 = passes("ok")
        assert wait_for(lambda: passes("ok") > ok1, 15), "the worker did not recover"
        assert wait_for(lambda: failures.get() == 0, 2)
    finally:
        proxy.resume()
        w.stop()
        assert w._thread is not None and not w._thread.is_alive(), "stop() left the thread"
        assert engine.pool.checkedout() == 0
        engine.dispose()


# --- transaction safety at the API: what a retry after "outcome unknown" does ----


@contextmanager
def _requests_through(proxy, pg_client):
    """Route the API's sessions through the proxy for the duration."""
    from app.core.db import get_db

    engine = _engine(proxy.url(), pool_size=2)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app = pg_client.app
    previous = app.dependency_overrides[get_db]

    def through_proxy():
        db = Session()
        try:
            yield db
        finally:
            core_db.close_quietly(db)

    app.dependency_overrides[get_db] = through_proxy
    try:
        yield
    finally:
        app.dependency_overrides[get_db] = previous
        proxy.resume()
        engine.dispose()


def _unknown_commit_then_resume(proxy, pg_client, call):
    proxy.freeze_on = b"COMMIT"
    with _requests_through(proxy, pg_client):
        response, took = _bounded(call, DEADLINE_S + SLACK_S + 5)
        assert proxy.frozen_on_marker.is_set(), (response.status_code, response.text[:300])
        proxy.resume()
    time.sleep(1.0)  # the held COMMIT reaches the server
    return response, took


def test_a_saved_search_whose_commit_is_unknown_is_resolved_by_its_natural_key(
        proxy, pg_client):
    """Ambiguous → resolved: the same search is stored once whatever happened,
    and the retry finds it (409 + Location) instead of creating a second."""
    from tests.conftest import auth, register_and_login

    token = register_and_login(pg_client, "pr003-saved@example.com", "guest")
    body = {"name": "pr003", "query": "min_rooms=2&max_rent=5000"}

    def save():
        return pg_client.post("/v1/me/saved-searches", json=body, headers=auth(token))

    first, took = _unknown_commit_then_resume(proxy, pg_client, save)
    print(f"\n[PR-003] saved search, COMMIT unanswered: {first.status_code} in {took:.2f} s")
    assert first.status_code == 503 and "outcome is unknown" in first.json()["detail"]
    retry = save()
    print(f"[PR-003] retry: {retry.status_code}")
    assert retry.status_code == 409 and retry.headers.get("Location")
    listed = pg_client.get("/v1/me/saved-searches", headers=auth(token)).json()
    assert len(listed["items"] if isinstance(listed, dict) else listed) == 1


def test_known_debt_a_property_whose_commit_is_unknown_is_duplicated_by_a_retry(
        proxy, pg_client, pg_migrated_engine):
    """CHARACTERIZATION of known debt (PR-003, no Idempotency-Key yet): the
    client is told the outcome is unknown; if it repeats the create anyway, a
    second draft property exists. Private to its owner, archivable — but a
    duplicate. When an idempotency key lands this test must flip."""
    from tests.conftest import auth, register_and_login
    from tests.saved_support import load_geo

    geo = load_geo(sessionmaker(bind=pg_migrated_engine, expire_on_commit=False))
    try:
        token = register_and_login(pg_client, "pr003-owner@example.com", "host")
        body = {"category": "APARTMENT", "area_m2": 50, "rooms": 2, "capacity": 2,
                "building_number": "7", "locality_id": geo["krakow"]}

        def create():
            return pg_client.post("/v1/properties", json=body, headers=auth(token))

        first, _ = _unknown_commit_then_resume(proxy, pg_client, create)
        assert first.status_code == 503 and "outcome is unknown" in first.json()["detail"]
        assert create().status_code == 201
        mine = pg_client.get("/v1/properties", headers=auth(token))
        assert mine.status_code == 200
        items = mine.json()["items"] if isinstance(mine.json(), dict) else mine.json()
        print(f"\n[PR-003] properties after unknown COMMIT + retry: {len(items)}")
        assert len(items) == 2
    finally:
        # The fixture geography (and its source) is not part of pg_client's
        # truncation; leave the shared database as other suites expect it.
        with pg_migrated_engine.begin() as c:
            c.execute(text("TRUNCATE geo_external_refs, addresses, geo_areas, localities, "
                           "admin_areas RESTART IDENTITY CASCADE"))
            c.execute(text("DELETE FROM geo_sources WHERE code = 'TEST_FIXTURE'"))
