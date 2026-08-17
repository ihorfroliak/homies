import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import require_role
from app.modules.payments import disputes, service
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
    if event["type"].startswith("charge.dispute."):
        # The event object is the Dispute, which carries the intent it disputes.
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
        # Untrusted sender: 400 is the honest status. (Stripe retries every
        # non-2xx, so this does not "stop" a retry — but a forged request is not
        # coming from Stripe in the first place.)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature") from None

    event_id = event["id"]
    existing = db.scalar(select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id))
    if existing is not None and existing.processed_at is not None:
        return {"received": True, "duplicate": True}  # already fully processed

    # H2: the raw event is committed in its OWN transaction, BEFORE dispatch.
    # It used to share one transaction with the ledger-affecting handlers and
    # only `flush()`ed here, so any handler failure (unknown intent, payment in
    # a conflicting state, refund-after-payout) rolled the audit record back
    # with it: the event vanished entirely and Stripe eventually stopped
    # retrying. Persisting first makes the audit trail durable whatever the
    # outcome, and leaves `processed_at IS NULL` as the dead-letter marker.
    if existing is None:
        db.add(
            WebhookEvent(
                stripe_event_id=event_id,
                event_type=event["type"],
                payload=dict(event),
            )
        )
        try:
            db.commit()
        except IntegrityError:
            # A concurrent delivery of the same event won the insert race
            # (stripe_event_id is unique). Its row is authoritative; continue —
            # dispatch is itself idempotent and row-locked.
            db.rollback()

    intent_id = _intent_id_of(event)
    try:
        if intent_id is not None:
            if event["type"] == "payment_intent.succeeded":
                service.process_intent_succeeded(db, intent_id)
            elif event["type"] == "payment_intent.payment_failed":
                service.process_intent_failed(db, intent_id)
            elif event["type"] == "charge.refunded":
                service.process_charge_refunded(db, intent_id)
            elif event["type"] == "charge.dispute.created":
                obj = event.get("data", {}).get("object", {})
                disputes.process_dispute_created(
                    db,
                    provider_dispute_id=obj.get("id", ""),
                    intent_id=intent_id,
                    amount=int(obj.get("amount") or 0),
                    fee=disputes.fee_from_event(obj),
                    currency=(obj.get("currency") or "").upper(),
                    reason=obj.get("reason") or "",
                )
            elif event["type"] == "charge.dispute.closed":
                obj = event.get("data", {}).get("object", {})
                disputes.process_dispute_closed(
                    db,
                    provider_dispute_id=obj.get("id", ""),
                    # Stripe closes a dispute as won | lost | warning_closed.
                    # Only an outright win returns the money.
                    won=obj.get("status") == "won",
                )

        stored = db.scalar(select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id))
        if stored is not None:
            stored.processed_at = datetime.now(timezone.utc)
        # A missing row means the racing insert did not survive after all. The
        # dispatch above still happened and is idempotent, so acknowledge rather
        # than 500 — a Stripe retry re-runs it safely.
        db.commit()
    except Exception:
        # Dispatch failed: undo only the dispatch work. The event row stays
        # committed with processed_at IS NULL, so nothing is lost and a Stripe
        # retry re-runs it. The original error still propagates, so the real
        # cause stays visible instead of being swallowed.
        db.rollback()
        raise
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
