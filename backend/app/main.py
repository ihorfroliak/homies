"""Homies API — modular monolith entry point.

Each bounded context lives in app/modules/<context>/ and exposes an
APIRouter. Composition happens here and only here. Allowed module
dependencies (one-way): booking -> listings, booking -> payments,
payments -> ledger, payments -> identity. Everything else integrates
through domain events (post-D4). See docs/adr/0001-modular-monolith.md.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.core.db import Base, engine
from app.modules.admin.router import router as admin_router
from app.modules.booking.router import router as booking_router
from app.modules.identity.router import router as identity_router
from app.modules.listings.router import router as listings_router
from app.modules.payments.router import router as payments_router


def _apply_postgres_guards() -> None:
    """DB-level double-booking guard (D5 invariant I1): an exclusion
    constraint makes overlapping pending/confirmed bookings physically
    impossible, regardless of application bugs. Postgres only; moves to
    Alembic with the first migration."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        exists = conn.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = 'excl_booking_overlap'")
        ).scalar()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE bookings ADD CONSTRAINT excl_booking_overlap "
                    "EXCLUDE USING gist ("
                    "listing_id WITH =, "
                    "daterange(check_in, check_out) WITH &&"
                    ") WHERE (status IN ('pending', 'confirmed'))"
                )
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # D4: create_all for local/sandbox; Alembic owns schema from the first
    # deployment to a shared environment. Tests own their engine (conftest)
    # and must never touch the real database.
    if settings.env != "test":
        Base.metadata.create_all(engine)
        _apply_postgres_guards()
    yield


app = FastAPI(
    title="Homies API",
    version="0.2.0",
    description="Managed hospitality platform — D4 vertical slice.",
    lifespan=lifespan,
)

API_V1 = "/v1"
app.include_router(identity_router, prefix=API_V1)
app.include_router(listings_router, prefix=API_V1)
app.include_router(booking_router, prefix=API_V1)
app.include_router(payments_router, prefix=API_V1)
app.include_router(admin_router, prefix=API_V1)


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    return {"status": "ok", "env": settings.env}
