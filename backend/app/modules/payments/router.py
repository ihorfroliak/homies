import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import require_role
from app.modules.payments import service
from app.modules.payments.models import WebhookEvent
from app.modules.payments.provider import (
    StripeConnectProvider,
    WebhookVerificationError,
    provider,
)

router = APIRouter(tags=["payments"])


class SimulatedWebhook(BaseModel):
    """Stand-in for the Stripe webhook payload (kept for hermetic tests).
    The production endpoint is /payments/webhook/stripe below."""

    intent_id: str
    event: str  # payment_intent.succeeded


@router.post("/payments/webhook/simulated")
def simulated_webhook(
    body: SimulatedWebhook,
    x_webhook_secret: str = Header(alias="X-Webhook-Secret", default=""),
    db: Session = Depends(get_db),
):
    if not hmac.compare_digest(x_webhook_secret, settings.webhook_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")
    if body.event != "payment_intent.succeeded":
        return {"received": True, "processed": False}
    payment = service.process_intent_succeeded(db, body.intent_id)
    db.commit()
    return {"received": True, "processed": True, "payment_id": payment.id, "status": payment.status}


# Event types we translate into ledger effects. Unknown types are stored
# (audit) and acknowledged, never acted on.
def _intent_id_of(event: dict) -> str | None:
    obj = event.get("data", {}).get("object", {})
    if event["type"].startswith("payment_intent."):
        return obj.get("id")
    if event["type"] == "charge.refunded":
        return obj.get("payment_intent")
    return None


@router.post("/payments/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Production Stripe webhook. Verifies the signature (trust boundary),
    persists the raw event (audit), dedupes by Stripe event id (idempotency),
    then dispatches to ledger-affecting handlers. Every step is idempotent."""
    if not isinstance(provider, StripeConnectProvider):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe provider not configured")

    payload = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = provider.construct_event(payload, sig)
    except WebhookVerificationError:
        # Untrusted sender — a 400 tells Stripe not to retry, which is correct.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature") from None
    # Anything else (a trusted event we failed to process) intentionally
    # propagates as a 5xx so Stripe retries and the real cause stays visible,
    # instead of being mislabelled as a forged request.

    event_id = event["id"]
    existing = db.scalar(select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id))
    if existing is not None and existing.processed_at is not None:
        return {"received": True, "duplicate": True}  # already fully processed

    if existing is None:
        db.add(
            WebhookEvent(
                stripe_event_id=event_id,
                event_type=event["type"],
                payload=dict(event),
            )
        )
        db.flush()

    intent_id = _intent_id_of(event)
    if intent_id is not None:
        if event["type"] == "payment_intent.succeeded":
            service.process_intent_succeeded(db, intent_id)
        elif event["type"] == "payment_intent.payment_failed":
            service.process_intent_failed(db, intent_id)
        elif event["type"] == "charge.refunded":
            service.process_charge_refunded(db, intent_id)

    stored = db.scalar(select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id))
    from datetime import datetime, timezone

    stored.processed_at = datetime.now(timezone.utc)
    db.commit()
    return {"received": True, "type": event["type"]}


@router.post("/hosts/{host_id}/payouts/run")
def run_payout(
    host_id: str,
    user=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    result = service.run_host_payout(db, host_id, actor=user.id)
    db.commit()
    return result
