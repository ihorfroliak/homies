"""Alert delivery with send-time revalidation (TASK-014).

A queued delivery is not authority to send. Immediately before sending, the
worker re-checks — in this order — and ends the delivery `suppressed` with a
machine reason at the first check that fails:

    user_missing          the account no longer exists
    preference_disabled   PRODUCT is off on this channel (includes a global unsubscribe)
    email_not_verified    EMAIL only: no verified address to send to
    listing_not_public    the listing is not public now (paused, stale, archived, expired)
    superseded            the listing is in a newer public episode (its own delivery)
    search_deleted        none of the user's matching searches exists any more
    search_inactive       none of them is active with notifications on (includes a
                          per-search unsubscribe)
    query_invalid         every remaining search's stored query is INVALID
    no_longer_matches     the listing no longer satisfies any of them (canonical query)

The recipient address is resolved HERE, from the user's verified email — the
queue never holds an address, and a user id is never an SMTP recipient.
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.alerts import metrics, preferences
from app.modules.alerts.models import (
    PRODUCT,
    SAVED_SEARCH_MATCH,
    AlertDelivery,
    SavedSearchMatch,
    UnsubscribeToken,
    UserNotification,
)
from app.modules.alerts.sql import insert_ignore
from app.modules.events.providers import channel_for
from app.modules.events.templates import render
from app.modules.identity.models import User
from app.modules.properties import freshness, search
from app.modules.properties.models import ClassifiedOffer
from app.modules.properties.search import InvalidSearchQuery
from app.modules.saved import service as saved_service
from app.modules.saved.models import SavedSearch

log = logging.getLogger("homies.alerts")

UNSUBSCRIBE_TTL = timedelta(days=180)
STALE_CLAIM = timedelta(minutes=5)


@dataclass
class Check:
    reason: str | None
    searches: list[SavedSearch] = field(default_factory=list)


def claim_deliveries(db: Session, limit: int) -> list[str]:
    now = freshness.db_now(db)
    ids = list(db.scalars(
        select(AlertDelivery.id)
        .where(AlertDelivery.status.in_(("pending", "failed")),
               AlertDelivery.next_attempt_at <= now)
        .order_by(AlertDelivery.next_attempt_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ))
    if ids:
        db.execute(update(AlertDelivery)
                   .where(AlertDelivery.id.in_(ids),
                          AlertDelivery.status.in_(("pending", "failed")))
                   .values(status="processing", claimed_at=now,
                           attempts=AlertDelivery.attempts + 1))
    return ids


def revalidate(db: Session, d: AlertDelivery, now: datetime) -> Check:
    user = db.get(User, d.user_id)
    if user is None:
        return Check("user_missing")
    if not preferences.is_enabled(db, d.user_id, d.category, d.channel):
        return Check("preference_disabled")
    if d.channel == "EMAIL" and (not user.email or user.email_verified_at is None):
        return Check("email_not_verified")
    offer = db.get(ClassifiedOffer, d.listing_id)
    if offer is None or not freshness.is_public(offer, now):
        return Check("listing_not_public")
    if offer.public_generation != d.public_generation:
        return Check("superseded")
    linked = list(db.scalars(
        select(SavedSearch)
        .join(SavedSearchMatch, SavedSearchMatch.saved_search_id == SavedSearch.id)
        .where(SavedSearchMatch.listing_id == d.listing_id,
               SavedSearchMatch.public_generation == d.public_generation,
               SavedSearch.user_id == d.user_id)
        .order_by(SavedSearch.created_at, SavedSearch.id)
    ))
    if not linked:
        return Check("search_deleted")
    live = [s for s in linked if s.status == "active" and s.notifications_enabled]
    if not live:
        return Check("search_inactive")
    valid = []
    for s in live:
        try:
            valid.append((s, saved_service.load_query(db, s)))
        except InvalidSearchQuery:
            continue
    if not valid:
        return Check("query_invalid")
    flags = search.evaluate_for_listing(db, d.listing_id, [q for _, q in valid])
    still = [s for (s, _), hit in zip(valid, flags) if hit]
    if not still:
        return Check("no_longer_matches")
    return Check(None, still)


def deliver(db: Session, delivery_id: str) -> str:
    """Revalidate and send one claimed delivery; returns its final status.
    The caller commits."""
    d = db.execute(select(AlertDelivery).where(AlertDelivery.id == delivery_id)
                   .with_for_update()).scalar_one_or_none()
    if d is None or d.status != "processing":
        return d.status if d else "missing"  # finished elsewhere: never twice
    now = freshness.db_now(db)
    check = revalidate(db, d, now)
    if check.reason is not None:
        _finish(d, "suppressed", check.reason, now)
        return d.status
    if d.channel == "IN_APP":
        insert_ignore(db, UserNotification, [{
            "id": str(uuid4()), "user_id": d.user_id, "category": PRODUCT,
            "notification_type": SAVED_SEARCH_MATCH,
            "title_key": "alerts.saved_search_match.title",
            "body_key": "alerts.saved_search_match.body",
            "data": {"listing_id": d.listing_id,
                     "saved_search_ids": [s.id for s in check.searches]},
            "delivery_id": d.id, "created_at": now,
        }], ["delivery_id"])
        _finish(d, "delivered", "", now)
        return d.status
    return _send_email(db, d, check.searches[0], now)


def _send_email(db: Session, d: AlertDelivery, first: SavedSearch, now: datetime) -> str:
    user = db.get(User, d.user_id)
    assert user is not None and user.email_verified_at is not None
    base = settings.public_web_base_url.rstrip("/")
    one = issue_unsubscribe_token(db, d.user_id, "SAVED_SEARCH", first.id, now)
    every = issue_unsubscribe_token(db, d.user_id, "PRODUCT_EMAIL", None, now)
    message = render(SAVED_SEARCH_MATCH, "en", {
        "search_name": first.name,
        "listing_url": f"{base}/listings/{d.listing_id}",
        "unsubscribe_search_url": f"{base}/unsubscribe?token={one}",
        "unsubscribe_all_url": f"{base}/unsubscribe?token={every}",
    })
    # The verified address, resolved now — never the user id (Phase-A defect).
    result = channel_for("email").send(to=user.email, subject=message["subject"],
                                       body=message["body"], idem_key=d.id)
    if result.ok:
        _finish(d, "delivered", "", now)
    elif result.transient and d.attempts < settings.notification_max_attempts:
        d.status = "failed"
        d.outcome = "transient_failure"
        d.claimed_at = None
        d.next_attempt_at = now + timedelta(
            seconds=settings.notification_backoff_base_seconds * (2 ** d.attempts))
    else:
        _finish(d, "dead", "permanent_failure", now)
    return d.status


def _finish(d: AlertDelivery, status: str, outcome: str, now: datetime) -> None:
    d.status = status
    d.outcome = outcome
    d.claimed_at = None
    d.completed_at = now
    metrics.DELIVERIES.labels(channel=d.channel, status=status).inc()


# --- unsubscribe capability -------------------------------------------------------------------


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_unsubscribe_token(db: Session, user_id: str, scope: str, saved_search_id: str | None,
                            now: datetime) -> str:
    """A fresh 256-bit random bearer token; only its SHA-256 is stored. The
    token is random — it encodes no user, address or search."""
    token = secrets.token_urlsafe(32)
    db.add(UnsubscribeToken(token_hash=token_hash(token), user_id=user_id, scope=scope,
                            saved_search_id=saved_search_id, created_at=now,
                            expires_at=now + UNSUBSCRIBE_TTL))
    db.flush()
    return token


def unsubscribe(db: Session, token: str, now: datetime) -> str:
    """Apply a token. Returns an internal outcome for metrics only — the HTTP
    answer is the same whatever happened (no enumeration signal)."""
    row = db.execute(select(UnsubscribeToken)
                     .where(UnsubscribeToken.token_hash == token_hash(token))
                     .with_for_update()).scalar_one_or_none()
    if row is None:
        return "unknown"
    if freshness.to_utc(row.expires_at) <= now:
        return "expired"
    if row.scope == "SAVED_SEARCH":
        if row.saved_search_id is not None:
            db.execute(update(SavedSearch)
                       .where(SavedSearch.id == row.saved_search_id,
                              SavedSearch.user_id == row.user_id)
                       .values(notifications_enabled=False, updated_at=now,
                               version=SavedSearch.version + 1))
    else:
        preferences.set_preference(db, row.user_id, PRODUCT, "EMAIL", False, now)
    if row.used_at is None:
        row.used_at = now
    return "applied"
