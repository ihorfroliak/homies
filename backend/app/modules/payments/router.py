import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import require_role
from app.modules.payments import service

router = APIRouter(tags=["payments"])


class SimulatedWebhook(BaseModel):
    """Stand-in for the Stripe webhook payload. The real endpoint verifies
    the Stripe-Signature header before trusting anything in the body."""

    intent_id: str
    event: str  # payment_intent.succeeded


@router.post("/payments/webhook/simulated")
def simulated_webhook(
    body: SimulatedWebhook,
    x_webhook_secret: str = Header(alias="X-Webhook-Secret", default=""),
    db: Session = Depends(get_db),
):
    # D5 hardening: an unauthenticated webhook would let anyone confirm
    # bookings without paying. Sandbox uses a shared secret; production
    # uses Stripe signature verification in the adapter.
    if not hmac.compare_digest(x_webhook_secret, settings.webhook_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")
    if body.event != "payment_intent.succeeded":
        return {"received": True, "processed": False}
    payment = service.process_intent_succeeded(db, body.intent_id)
    db.commit()
    return {"received": True, "processed": True, "payment_id": payment.id, "status": payment.status}


@router.post("/hosts/{host_id}/payouts/run")
def run_payout(
    host_id: str,
    user=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    result = service.run_host_payout(db, host_id, actor=user.id)
    db.commit()
    return result
