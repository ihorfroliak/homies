"""TST-01 — OpenAPI contract alignment + drift guard.

The committed spec (docs/api/openapi.json) is generated from the app. These
tests fail the build if it drifts from the implementation or if an endpoint is
served without appearing in the contract — so the spec can never silently rot
again (the state the audit found: hand-written specs covered ~11 of 35 real
paths with mismatched names).
"""

import json
from pathlib import Path

from app.main import app
from app.scripts.export_openapi import SPEC_PATH, serialise
from tests.routes import served_routes


def test_committed_spec_matches_the_implementation():
    """The drift guard. If this fails, run:
    python -m app.scripts.export_openapi"""
    assert SPEC_PATH.exists(), "docs/api/openapi.json is missing — run the exporter"
    committed = SPEC_PATH.read_text(encoding="utf-8")
    generated = serialise(app.openapi())
    assert committed == generated, (
        "docs/api/openapi.json is out of date. Regenerate with "
        "`python -m app.scripts.export_openapi`."
    )


def test_every_served_route_is_in_the_contract():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    documented = set(spec["paths"])
    # app.routes lists _IncludedRouter wrappers on current FastAPI; reading
    # r.path there saw only the ops routes, so this test was vacuous until
    # TASK-002. served_routes() walks through the wrappers.
    served = {
        path
        for path, _, in_schema in served_routes(app)
        if in_schema and path not in ("/openapi.json",)
    }
    assert "/v1/classifieds" in served, "route walker went blind"
    # docs/redoc/openapi UI routes are excluded from the schema by FastAPI.
    undocumented = served - documented
    assert not undocumented, f"served but undocumented endpoints: {sorted(undocumented)}"


def test_spec_is_openapi_31_with_expected_shape():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["openapi"].startswith("3.1")
    assert spec["info"]["title"] == "Homies API"
    # every operation carries an operationId and at least one tag (Spectral errors)
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            assert "operationId" in op, f"{method} {path} missing operationId"
            assert op.get("tags"), f"{method} {path} missing tags"


def test_no_stale_hand_written_openapi_files_remain():
    """The drifted per-domain specs were retired in favour of the generated one;
    keeping both would reintroduce the divergence."""
    api_dir = Path(SPEC_PATH).parent
    stale = list(api_dir.glob("*.openapi.yaml"))
    assert stale == [], f"stale hand-written OpenAPI files still present: {stale}"


def test_core_endpoints_are_present():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    for path in (
        "/v1/auth/register", "/v1/auth/login", "/v1/properties", "/v1/classifieds",
        "/v1/classifieds/{offer_id}/publish", "/v1/admin/property-authorities/{authority_id}/revoke",
    ):
        assert path in spec["paths"], f"missing from contract: {path}"
    # The Phase-1 contract carries no legacy short-stay/booking/payment surface
    # (TASK-002 R1). Their absence from routing is tested in test_phase1_runtime.
    for path in ("/v1/bookings", "/v1/listings", "/v1/payments/webhook/stripe",
                 "/v1/hosts/{host_id}/payouts/run", "/v1/admin/ledger/reconciliation"):
        assert path not in spec["paths"], f"legacy path in the Phase-1 contract: {path}"
