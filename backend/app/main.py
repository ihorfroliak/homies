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
    """Postgres-only DB-level guards for local/dev create_all. In shared and
    production environments the identical guards ship via Alembic
    (alembic/versions/*_initial_schema.py) — that migration is the source of
    truth. Kept here so a create_all'd dev DB matches production behaviour.

    - I1 (D5/D6): exclusion constraint => overlapping pending/confirmed
      bookings are physically impossible.
    - B5 (D7): append-only triggers on ledger/audit => even direct SQL from
      an admin cannot tamper financial records (owner-proof, unlike REVOKE).
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        if not conn.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = 'excl_booking_overlap'")
        ).scalar():
            conn.execute(
                text(
                    "ALTER TABLE bookings ADD CONSTRAINT excl_booking_overlap "
                    "EXCLUDE USING gist ("
                    "listing_id WITH =, "
                    "daterange(check_in, check_out) WITH &&"
                    ") WHERE (status IN ('pending', 'confirmed'))"
                )
            )
        conn.execute(
            text(
                "CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$ "
                "BEGIN RAISE EXCEPTION 'append-only table %: % is not permitted', "
                "TG_TABLE_NAME, TG_OP; END; $$ LANGUAGE plpgsql"
            )
        )
        for table in ("journal_entries", "journal_lines", "audit_log", "domain_events"):
            if not conn.execute(
                text("SELECT 1 FROM pg_trigger WHERE tgname = :n"),
                {"n": f"{table}_append_only"},
            ).scalar():
                conn.execute(
                    text(
                        f"CREATE TRIGGER {table}_append_only "
                        f"BEFORE UPDATE OR DELETE ON {table} "
                        f"FOR EACH ROW EXECUTE FUNCTION forbid_mutation()"
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
