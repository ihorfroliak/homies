"""Test-only composition of the LEGACY_DORMANT runtime.

The Phase-1 application (app/composition.py) does not route to the short-stay,
booking or payment contexts. Their historical tests still guard real
engineering — ledger balance, Stripe signature checks, webhook idempotency,
booking concurrency — so they run against this composition instead: the
Phase-1 routers plus the legacy ones, exactly as the process was composed
before TASK-002.

Nothing outside tests/ may import this module; a legacy route reachable from a
deployed process is the defect TASK-001 F-01 found.
"""

from fastapi import APIRouter, FastAPI

from app.composition import BackgroundWorker, build_app, phase1_routers, phase1_workers


def legacy_routers() -> list[APIRouter]:
    from app.modules.admin.legacy import router as legacy_admin_router
    from app.modules.booking.router import router as booking_router
    from app.modules.identity.host_payouts import router as host_payouts_router
    from app.modules.listings.router import router as listings_router
    from app.modules.payments.router import router as payments_router

    return [
        listings_router,
        booking_router,
        payments_router,
        host_payouts_router,
        legacy_admin_router,
    ]


def legacy_workers() -> list[BackgroundWorker]:
    from app.core.config import settings
    from app.modules.booking.expiry import worker as booking_expiry_worker

    return [
        BackgroundWorker(
            name="booking-expiry",
            start=booking_expiry_worker.start,
            stop=booking_expiry_worker.stop,
            enabled=lambda: settings.booking_expiry_worker_enabled,
        )
    ]


def create_legacy_test_app() -> FastAPI:
    return build_app(
        phase1_routers() + legacy_routers(), phase1_workers() + legacy_workers()
    )
