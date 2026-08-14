"""OBS-01: readiness/liveness split, and the properties that make it worth having.

The previous /healthz asserted `status == "ok"` against a hardcoded literal, so
it passed with the database on fire. These tests are written to fail if the
split is removed or inverted.

`check_database()` deliberately uses the real module-level engine (that is the
point — it exercises the actual connection pool), so these tests point that
engine at an in-memory SQLite rather than overriding the `get_db` dependency.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from app.core import db as core_db
from app.core import health
from app.core.config import settings
from app.main import app

client = TestClient(app)


@pytest.fixture
def database_up(monkeypatch):
    """Point the probe at a live in-memory database."""
    probe_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(health, "engine", probe_engine)
    return probe_engine


@pytest.fixture
def database_down(monkeypatch):
    """Make every pool checkout fail the way an unreachable Postgres does."""

    def _boom(*args, **kwargs):
        raise OperationalError(
            # Deliberately embeds a password: the redaction test below is only
            # meaningful if the raw exception actually carries one.
            "SELECT 1",
            {},
            Exception("could not connect to postgresql://homies:s3cret@db:5432/homies"),
        )

    monkeypatch.setattr(health.engine, "connect", _boom)


def test_readyz_reports_ready_when_database_answers(database_up):
    resp = client.get("/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["database"]["latency_ms"] >= 0


def test_readyz_returns_503_when_database_is_unreachable(database_down):
    """The whole point: readiness must actually observe the dependency."""
    resp = client.get("/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["ok"] is False
    assert body["checks"]["database"]["error"] == "OperationalError"


def test_healthz_stays_200_when_database_is_unreachable(database_down):
    """Anti-amplification, and the reason /healthz is not merely /readyz.

    A failing liveness probe restarts the container. If liveness tracked the
    database, one database outage would restart every replica simultaneously
    and stampede the database on recovery. A live process with a dead
    dependency is unready, not unhealthy.
    """
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_does_not_leak_credentials_in_the_error(database_down):
    """/readyz is unauthenticated and rate-limit exempt; the DSN must not escape."""
    body = client.get("/readyz").text
    assert "s3cret" not in body
    assert "postgresql://" not in body
    assert "db:5432" not in body


def test_probes_are_exempt_from_rate_limiting():
    """An orchestrator probing every few seconds must never be throttled into
    a false readiness failure."""
    from app.core import ratelimit as rl

    assert rl.resolve_policy("GET", "/readyz") is None
    assert rl.resolve_policy("GET", "/healthz") is None


def test_probe_bounds_the_query_on_postgres(monkeypatch):
    """A hung query must not hold a pool connection indefinitely."""
    executed: list[str] = []

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _FakeConn(_Ctx):
        dialect = type("D", (), {"name": "postgresql"})()

        def execute(self, stmt):
            executed.append(str(stmt))

        def begin(self):
            return _Ctx()

    monkeypatch.setattr(health.engine, "connect", lambda: _FakeConn())

    assert health.check_database().ok is True
    assert any("statement_timeout" in s for s in executed), executed
    assert any("SELECT 1" in s for s in executed), executed


def test_postgres_connections_bound_the_tcp_connect():
    """statement_timeout cannot bound a connect: there is no session yet.

    Regression test for the hang this cycle found — a blackholed database host
    stalled the probe for the OS TCP timeout instead of reporting not-ready.
    """
    assert core_db._connect_args("postgresql+psycopg://u:p@h:5432/d")["connect_timeout"] > 0
    # SQLite takes no such argument; passing one would break every test run.
    assert core_db._connect_args("sqlite://") == {}


def test_healthz_still_reports_env():
    """Kept from the original suite — the ops surface contract did not change."""
    assert client.get("/healthz").json()["env"] == settings.env


# --- OBS-06: the readiness result must be alertable ---------------------------


def test_readiness_publishes_database_gauge(database_up):
    """Prometheus cannot read an HTTP probe; without this the most important
    dependency in the system has no alertable signal."""
    from prometheus_client import REGISTRY

    client.get("/readyz")
    assert REGISTRY.get_sample_value("homies_database_up") == 1.0
    assert REGISTRY.get_sample_value("homies_database_last_check_timestamp_seconds") > 0


def test_database_gauge_goes_to_zero_when_unreachable(database_down):
    from prometheus_client import REGISTRY

    client.get("/readyz")
    assert REGISTRY.get_sample_value("homies_database_up") == 0.0


def test_alert_rules_only_reference_metrics_the_code_exposes():
    """Ties ops/monitoring/rules to reality.

    The classic alert-rule bug is a metric name that never existed, discovered
    during the outage the rule was written for. promtool cannot catch it — it
    validates syntax, not whether the series is ever produced.
    """
    import re
    from pathlib import Path

    from prometheus_client import REGISTRY

    rules = Path(__file__).resolve().parents[2] / "ops/monitoring/rules/homies.rules.yml"
    referenced = set(re.findall(r"\bhomies_[a-z0-9_]+", rules.read_text(encoding="utf-8")))

    exposed = set()
    for metric in REGISTRY.collect():
        exposed.add(metric.name)
        for suffix in ("_total", "_bucket", "_count", "_sum"):
            exposed.add(metric.name + suffix)

    missing = referenced - exposed
    assert not missing, f"alert rules reference metrics the app never exposes: {sorted(missing)}"
