"""The Phase-1 application does not run the LEGACY_DORMANT runtime (TASK-001 F-01).

The static import test (test_phase1_boundaries.py) cannot see a router
registered in main, a dynamic import or a worker started at startup. These
tests look at the composed application itself: what it routes, what it
documents, which workers it starts and which modules the process loads.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.composition import create_phase1_app
from app.main import app
from tests.legacy_runtime import create_legacy_test_app
from tests.routes import served_paths, served_routes

BACKEND = Path(__file__).resolve().parents[1]

LEGACY_PREFIXES = (
    "/v1/listings",
    "/v1/bookings",
    "/v1/payments",
    "/v1/hosts",
    "/v1/admin/bookings",
    "/v1/admin/payments",
    "/v1/admin/ledger",
    "/v1/admin/kpi",
    "/v1/admin/incidents",
)

# Representative requests a legacy client would send. Each must miss routing.
LEGACY_REQUESTS = [
    ("GET", "/v1/listings"),
    ("POST", "/v1/listings"),
    ("GET", "/v1/listings/abc"),
    ("POST", "/v1/listings/abc/publish"),
    ("GET", "/v1/listings/abc/availability"),
    ("POST", "/v1/bookings"),
    ("GET", "/v1/bookings/abc"),
    ("POST", "/v1/bookings/abc/cancel"),
    ("POST", "/v1/payments/webhook/stripe"),
    ("POST", "/v1/payments/webhook/simulated"),
    ("POST", "/v1/hosts/abc/payouts/run"),
    ("POST", "/v1/hosts/onboarding"),
    ("GET", "/v1/hosts/me"),
    ("GET", "/v1/admin/bookings"),
    ("GET", "/v1/admin/payments"),
    ("GET", "/v1/admin/ledger/balances"),
    ("GET", "/v1/admin/kpi"),
    ("POST", "/v1/admin/incidents"),
]


def _is_legacy(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in LEGACY_PREFIXES)


def test_phase1_app_registers_no_legacy_route():
    legacy = sorted(p for p in served_paths(app) if _is_legacy(p))
    assert legacy == []


def test_route_walker_sees_through_included_routers():
    """Guards the walker itself: if it went blind, the test above would pass
    vacuously. The legacy composition must show the routes Phase-1 lacks."""
    phase1 = served_paths(app)
    legacy = served_paths(create_legacy_test_app())
    assert "/v1/classifieds" in phase1
    assert "/v1/properties" in phase1
    assert {"/v1/listings", "/v1/bookings", "/v1/payments/webhook/stripe"} <= legacy
    assert not {"/v1/listings", "/v1/bookings"} & phase1


def test_phase1_openapi_documents_no_legacy_operation():
    spec = app.openapi()
    assert [p for p in spec["paths"] if _is_legacy(p)] == []
    tags = {t["name"] for t in spec["tags"]}
    assert not tags & {"listings", "bookings", "payments"}
    for methods in spec["paths"].values():
        for op in methods.values():
            assert not set(op.get("tags", ())) & {"listings", "bookings", "payments"}


@pytest.mark.parametrize(("method", "path"), LEGACY_REQUESTS)
def test_legacy_endpoints_are_not_routed(client, method, path):
    response = client.request(method, path, json={})
    assert response.status_code == 404, (method, path, response.status_code)


def test_the_same_requests_do_route_in_the_legacy_composition():
    """Proves the 404s above come from composition, not from bad paths."""
    from fastapi.testclient import TestClient

    with TestClient(create_legacy_test_app()) as legacy:
        # Unauthenticated: routed endpoints answer 401/403/422, never 404.
        assert legacy.get("/v1/admin/bookings").status_code in (401, 403)
        assert legacy.post("/v1/bookings", json={}).status_code in (401, 403, 422)
        assert legacy.post("/v1/hosts/onboarding", json={}).status_code in (401, 403, 422)


def test_every_served_route_is_documented_or_deliberately_hidden():
    documented = set(app.openapi()["paths"])
    served = {p for p, _, in_schema in served_routes(app) if in_schema}
    assert served - documented == set()


def test_phase1_startup_starts_no_legacy_worker(monkeypatch):
    """Drive the real lifespan as a non-test environment would."""
    from fastapi.testclient import TestClient

    from app import composition
    from app.core.config import settings
    from app.modules.booking.expiry import worker as booking_expiry_worker
    from app.modules.events.worker import worker as notification_worker

    started: list[str] = []
    monkeypatch.setattr(settings, "env", "local")
    monkeypatch.setattr(settings, "notification_worker_enabled", True)
    monkeypatch.setattr(settings, "booking_expiry_worker_enabled", True)
    monkeypatch.setattr(composition, "ensure_schema", lambda: None)
    monkeypatch.setattr(composition, "verify_ledger_privileges", lambda: None)
    monkeypatch.setattr(notification_worker, "start", lambda: started.append("notifications"))
    monkeypatch.setattr(notification_worker, "stop", lambda: None)
    monkeypatch.setattr(booking_expiry_worker, "start", lambda: started.append("booking-expiry"))
    monkeypatch.setattr(booking_expiry_worker, "stop", lambda: None)

    fresh = create_phase1_app()
    assert fresh.state.worker_names == ("notifications",)
    with TestClient(fresh):
        assert fresh.state.started_workers == ("notifications",)
    assert started == ["notifications"]


def test_phase1_process_does_not_load_legacy_modules():
    """A fresh interpreter importing the deployable app must not import the
    dormant contexts at all — no router, model or worker of theirs is loaded."""
    probe = (
        "import sys, app.main\n"
        "legacy = ('booking', 'payments', 'ledger', 'listings')\n"
        "hits = sorted(m for m in sys.modules\n"
        "    if m.startswith('app.modules.') and m.split('.')[2] in legacy\n"
        "    or m in ('app.modules.admin.legacy', 'app.modules.identity.host_payouts',\n"
        "             'app.modules.admin.kpi'))\n"
        "print(hits)\n"
    )
    env = {**os.environ, "ENV": "test"}
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=BACKEND, env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"
