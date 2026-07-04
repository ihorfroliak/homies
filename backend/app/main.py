"""Homies API — modular monolith entry point.

Each bounded context lives in app/modules/<context>/ and exposes an
APIRouter. The composition happens here and only here; modules must not
import each other directly (integration goes through domain events).
See docs/adr/0001-modular-monolith.md.
"""

from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title="Homies API",
    version="0.1.0",
    description="Rental housing platform for Poland — flexible-term stays.",
)


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    return {"status": "ok", "env": settings.env}
