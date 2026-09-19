"""Homies API — modular monolith entry point.

Each bounded context lives in app/modules/<context>/ and exposes an
APIRouter. Composition happens here and only here. Allowed module
dependencies (one-way): booking -> listings, booking -> payments,
payments -> ledger, payments -> identity. Everything else integrates
through domain events (post-D4). See docs/adr/0001-modular-monolith.md.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings, validate_security_config
from app.core.health import check_database
from app.core.http_metrics import http_metrics_middleware
from app.core.ratelimit import client_ip, limiter, resolve_policy
from app.core.schema import ensure_schema
from app.modules.admin.router import router as admin_router
from app.modules.booking.expiry import worker as booking_expiry_worker
from app.modules.booking.router import router as booking_router
from app.modules.events.worker import worker as notification_worker
from app.modules.identity.router import router as identity_router
from app.modules.listings.router import router as listings_router
from app.modules.payments.router import router as payments_router
from app.modules.properties.router import router as properties_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SEC-02: refuse to start a production-like environment with weak or
    # default secrets. No-op in local/test by design.
    validate_security_config(settings)
    # TD-01: Alembic migrations are the single schema source of truth. The app
    # does not build schema from ORM metadata — ensure_schema() applies
    # migrations in local dev and only verifies head elsewhere. Tests own their
    # engine (conftest).
    if settings.env != "test":
        ensure_schema()
        if settings.notification_worker_enabled:
            notification_worker.start()
        if settings.booking_expiry_worker_enabled:
            booking_expiry_worker.start()
    yield
    notification_worker.stop()
    booking_expiry_worker.stop()


# Declared so the generated OpenAPI has global tag definitions (Spectral
# operation-tag-defined). Router tags must match these names.
OPENAPI_TAGS = [
    {"name": "identity", "description": "Registration, authentication, tokens, profiles."},
    {"name": "listings", "description": "Property listings and host calendar blocks."},
    {"name": "bookings", "description": "Booking lifecycle, availability, check-in, state."},
    {"name": "payments", "description": "Stripe webhooks and host payout execution."},
    {"name": "properties", "description": "Physical objects and the free long-term listings board."},
    {"name": "admin", "description": "Read-only operations surface, incidents, reconciliation."},
    {"name": "ops", "description": "Health and metrics."},
]

app = FastAPI(
    title="Homies API",
    version="0.3.0",
    description=(
        "Managed hospitality platform. This spec is generated from the "
        "implementation (code-first) and kept in sync by a CI drift-guard — "
        "see docs/api/README.md."
    ),
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

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
# Starlette applies them in reverse order of registration. That ordering is
# deliberate — metrics must observe throttled requests too, or a rate-limit
# storm would show up as a drop in traffic rather than a spike in 429s.
app.middleware("http")(http_metrics_middleware)


API_V1 = "/v1"
app.include_router(identity_router, prefix=API_V1)
app.include_router(listings_router, prefix=API_V1)
app.include_router(booking_router, prefix=API_V1)
app.include_router(payments_router, prefix=API_V1)
app.include_router(properties_router, prefix=API_V1)
app.include_router(admin_router, prefix=API_V1)


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    """Liveness. Deliberately checks nothing external — see app/core/health.py.

    A failing liveness probe restarts the container, so making this depend on
    the database would convert a database outage into a fleet-wide crash loop.
    Use /readyz to gate traffic.
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
