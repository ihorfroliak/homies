"""Application composition — which bounded contexts a running process exposes.

The Phase-1 product is the LONG_TERM marketplace (docs/canonical/02). The
short-stay, booking and payment runtime is LEGACY_DORMANT: its code, tables and
migrations stay in the repository, but a Phase-1 process neither routes to it
nor starts its workers. This file is the single place that decides that — an
import convention alone did not (TASK-001 F-01).

`create_phase1_app()` is the only composition a deployable process uses
(`app.main:app`). The legacy routers are listed nowhere in this package; the
test harness in tests/legacy_runtime.py composes them explicitly so their
historical tests keep running without making them part of the product.
"""

import math
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings, validate_security_config
from app.core.health import check_database
from app.core.http_metrics import http_metrics_middleware
from app.core.ratelimit import client_ip, limiter, resolve_policy
from app.core.schema import ensure_schema, verify_ledger_privileges

API_V1 = "/v1"


@dataclass(frozen=True)
class BackgroundWorker:
    """A worker the process runs for its whole lifetime.

    `enabled` is read at startup, not at composition time, so configuration
    loaded after import still decides.
    """

    name: str
    start: Callable[[], None]
    stop: Callable[[], None]
    enabled: Callable[[], bool]


# Declared so the generated OpenAPI has global tag definitions (Spectral
# operation-tag-defined). Only tags of the composed routers are emitted.
TAG_DESCRIPTIONS = {
    "identity": "Registration, authentication, tokens, profiles, verification.",
    "organizations": "Agencies and companies, memberships and representation mandates.",
    "properties": "Physical objects and the free long-term listings board.",
    "conversations": "Messages between a seeker and whoever manages a listing.",
    "viewings": "Viewing windows, slots and appointments.",
    "media": "Property photos and floor plans, moderated before they are public.",
    "admin": "Operations surface: users, audit, notifications, property authority.",
    "ops": "Health and metrics.",
    # Legacy tags — only present when a legacy test composition includes them.
    "listings": "LEGACY short-stay listings and host calendar blocks.",
    "bookings": "LEGACY booking lifecycle.",
    "payments": "LEGACY Stripe webhooks and host payouts.",
}


def phase1_routers() -> list[APIRouter]:
    """The Phase-1 HTTP surface. Imported lazily so composing an app is the
    act that pulls a context into the process, not importing this module."""
    from app.modules.admin.router import router as admin_router
    from app.modules.engagement.router import router as conversations_router
    from app.modules.engagement.viewings import router as viewings_router
    from app.modules.identity.organizations import router as organizations_router
    from app.modules.identity.router import router as identity_router
    from app.modules.media.router import router as media_router
    from app.modules.properties.router import router as properties_router

    return [
        identity_router,
        organizations_router,
        properties_router,
        conversations_router,
        viewings_router,
        media_router,
        admin_router,
    ]


def phase1_workers() -> list[BackgroundWorker]:
    from app.modules.events.worker import worker as notification_worker

    return [
        BackgroundWorker(
            name="notifications",
            start=notification_worker.start,
            stop=notification_worker.stop,
            enabled=lambda: settings.notification_worker_enabled,
        )
    ]


def _json_safe(value):
    """Validation errors echo the rejected input. A NaN or ±Infinity there is
    not JSON, and FastAPI's default handler then fails while *reporting* the
    422 — the client gets a 500 for sending a bad number. Render them as text."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"detail": _json_safe(jsonable_encoder(exc.errors()))}
    )


def build_app(
    routers: Sequence[APIRouter], workers: Sequence[BackgroundWorker]
) -> FastAPI:
    """Assemble a FastAPI app from exactly the routers and workers given."""
    workers = tuple(workers)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # SEC-02: refuse to start a production-like environment with weak or
        # default secrets. No-op in local/test by design.
        validate_security_config(settings)
        started: list[BackgroundWorker] = []
        # TD-01: Alembic migrations are the single schema source of truth.
        # Tests own their engine (conftest), so nothing here runs under test.
        if settings.env != "test":
            ensure_schema()
            # B5: a production role must not be able to rewrite the ledger.
            # The ledger is dormant, its tables and the guarantee are not.
            verify_ledger_privileges()
            for worker in workers:
                if worker.enabled():
                    worker.start()
                    started.append(worker)
        app.state.started_workers = tuple(w.name for w in started)
        yield
        for worker in started:
            worker.stop()

    used_tags: list[str] = []
    for router in routers:
        for tag in router.tags:
            if isinstance(tag, str) and tag not in used_tags:
                used_tags.append(tag)
    used_tags.append("ops")

    app = FastAPI(
        title="Homies API",
        version="0.4.0",
        description=(
            "Trust-first property marketplace — Phase 1A (long-term listings). "
            "This spec is generated from the implementation (code-first) and "
            "kept in sync by a CI drift-guard — see docs/api/README.md."
        ),
        openapi_tags=[{"name": t, "description": TAG_DESCRIPTIONS[t]} for t in used_tags],
        lifespan=lifespan,
    )
    app.state.worker_names = tuple(w.name for w in workers)
    app.add_exception_handler(RequestValidationError, _validation_error)  # type: ignore[arg-type]

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Perimeter control (SEC-01). Runs before routing/auth so that
        unauthenticated floods are rejected cheaply. It never grants access —
        passing the limiter still leaves every authn/authz check in place."""
        limiter.enabled = settings.rate_limit_enabled
        policy = resolve_policy(request.method, request.url.path)
        if policy is not None:
            key = f"{policy.name}:ip:{client_ip(request, settings.trust_proxy_hops)}"
            allowed, retry_after = limiter.check(key, policy)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": str(max(1, int(retry_after)))},
                )
        return await call_next(request)

    # Registered AFTER the rate limiter, which makes it the OUTER middleware:
    # Starlette applies them in reverse order of registration. Metrics must
    # observe throttled requests too, or a rate-limit storm would show up as a
    # drop in traffic rather than a spike in 429s.
    app.middleware("http")(http_metrics_middleware)

    for router in routers:
        app.include_router(router, prefix=API_V1)

    _add_ops_routes(app)
    return app


def _add_ops_routes(app: FastAPI) -> None:
    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict:
        """Liveness. Deliberately checks nothing external — see app/core/health.py.

        A failing liveness probe restarts the container, so making this depend
        on the database would convert a database outage into a fleet-wide crash
        loop. Use /readyz to gate traffic.
        """
        return {"status": "ok", "env": settings.env}

    @app.get(
        "/readyz",
        tags=["ops"],
        responses={503: {"description": "A dependency is unavailable; do not route traffic here."}},
    )
    def readyz(response: Response) -> dict:
        """Readiness. 503 pulls this instance from the load balancer without killing it."""
        db = check_database()
        if not db.ok:
            response.status_code = 503
        return {
            "status": "ready" if db.ok else "not_ready",
            "env": settings.env,
            "checks": {
                "database": {
                    "ok": db.ok,
                    "latency_ms": db.latency_ms,
                    # Class name only — the message would carry the DSN (D-37).
                    **({"error": db.error} if db.error else {}),
                }
            },
        }

    @app.get("/metrics", tags=["ops"])
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def create_phase1_app() -> FastAPI:
    """The Phase-1A application: the only composition a deployed process runs."""
    return build_app(phase1_routers(), phase1_workers())
