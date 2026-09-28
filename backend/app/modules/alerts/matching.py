"""From a new public episode to matches and deliveries (TASK-014).

    work item (listing, generation)            listing_public_generations, SKIP LOCKED
      → candidate saved searches                anchor index lookup — never all searches
      → exact match                             search.evaluate_for_listing: the canonical
                                                SearchQuery filters, public clause included
      → saved_search_matches                    UNIQUE (search, listing, generation)
      → alert_deliveries                        UNIQUE (user, listing, generation, channel)

The worker never crosses every saved search with every listing: work exists
only for listings that just became public, candidates come from an indexed
necessary condition (the anchors), and the canonical query decides.

Alerts are only for NEW public episodes after the search's baseline: a search
saved at T is never notified about an episode that began at or before T.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.modules.alerts import metrics, preferences
from app.modules.alerts.models import PRODUCT, AlertDelivery, SavedSearchMatch
from app.modules.alerts.sql import insert_ignore
from app.modules.identity.models import User
from app.modules.properties import freshness, search
from app.modules.properties.models import ClassifiedOffer, ListingPublicGeneration
from app.modules.properties.search import InvalidSearchQuery
from app.modules.saved import service as saved_service
from app.modules.saved.models import SavedSearch, SavedSearchAnchor

log = logging.getLogger("homies.alerts")

STALE_CLAIM = timedelta(minutes=5)


@dataclass
class Outcome:
    outcome: str            # matched | no_match | not_public | superseded | skipped
    candidates: int = 0
    matches: int = 0
    deliveries: int = 0


def claim_work(db: Session, limit: int) -> list[tuple[str, int]]:
    """Take up to `limit` pending work items; the caller's transaction commits
    the claim. Rows another worker holds are skipped, not waited for."""
    now = freshness.db_now(db)
    rows = db.execute(
        select(ListingPublicGeneration.listing_id, ListingPublicGeneration.public_generation)
        .where(ListingPublicGeneration.alert_status == "pending")
        .order_by(ListingPublicGeneration.became_public_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    for listing_id, generation in rows:
        db.execute(
            update(ListingPublicGeneration)
            .where(ListingPublicGeneration.listing_id == listing_id,
                   ListingPublicGeneration.public_generation == generation,
                   ListingPublicGeneration.alert_status == "pending")
            .values(alert_status="processing", claimed_at=now,
                    attempts=ListingPublicGeneration.attempts + 1)
        )
    return [(r[0], r[1]) for r in rows]


def acknowledge(db: Session, listing_id: str, generation: int, status: str) -> None:
    """Finish exactly this (listing, generation) — never another generation
    of the same listing, which is its own work item."""
    db.execute(
        update(ListingPublicGeneration)
        .where(ListingPublicGeneration.listing_id == listing_id,
               ListingPublicGeneration.public_generation == generation,
               ListingPublicGeneration.alert_status.in_(("pending", "processing")))
        .values(alert_status=status, processed_at=freshness.db_now(db), claimed_at=None)
    )


def candidates(db: Session, offer: ClassifiedOffer, became_public_at: datetime) -> list[SavedSearch]:
    """Saved searches that COULD match: an anchor among the listing's keys,
    active, notifying, and saved (baselined) strictly before the episode began."""
    keys = saved_service.listing_keys(db, offer)
    hit = (select(SavedSearchAnchor.saved_search_id)
           .where(or_(*(and_(SavedSearchAnchor.kind == k, SavedSearchAnchor.value == v)
                        for k, v in keys))))
    return list(db.scalars(
        select(SavedSearch)
        .where(SavedSearch.id.in_(hit),
               SavedSearch.status == "active",
               SavedSearch.notifications_enabled.is_(True),
               SavedSearch.baseline_at < became_public_at)
        .order_by(SavedSearch.id)
    ))


def process_generation(db: Session, listing_id: str, generation: int) -> Outcome:
    """Evaluate one public episode. Idempotent: rerunning it (a retry, a
    reclaimed claim, two workers) inserts nothing new. The caller commits."""
    work = db.get(ListingPublicGeneration, (listing_id, generation))
    offer = db.get(ClassifiedOffer, listing_id)
    if work is None or offer is None:
        return Outcome("skipped")
    if offer.public_generation != generation:
        # A newer episode exists; it has its own work item. Nothing of it is
        # consumed here.
        acknowledge(db, listing_id, generation, "superseded")
        return Outcome("superseded")
    now = freshness.db_now(db)
    if not freshness.is_public(offer, now):
        acknowledge(db, listing_id, generation, "done")
        return Outcome("not_public")

    found = candidates(db, offer, work.became_public_at)
    metrics.CANDIDATES.observe(len(found))
    valid: list[tuple[SavedSearch, search.SearchQuery]] = []
    for s in found:
        try:
            valid.append((s, saved_service.load_query(db, s)))
        except InvalidSearchQuery:
            # INVALID never matches: no broadened search, no guessed criterion.
            metrics.INVALID_QUERIES.inc()
    flags = search.evaluate_for_listing(db, listing_id, [q for _, q in valid])
    matched = [s for (s, _), hit in zip(valid, flags) if hit]

    created = insert_ignore(db, SavedSearchMatch, [
        {"saved_search_id": s.id, "listing_id": listing_id, "public_generation": generation,
         "user_id": s.user_id, "created_at": now} for s in matched
    ], ["saved_search_id", "listing_id", "public_generation"])
    metrics.MATCHES_CREATED.inc(created)

    deliveries = queue_deliveries(db, listing_id, generation, sorted({s.user_id for s in matched}),
                                  now)
    acknowledge(db, listing_id, generation, "done")
    return Outcome("matched" if matched else "no_match", len(found), created, deliveries)


def queue_deliveries(db: Session, listing_id: str, generation: int, user_ids: list[str],
                     now: datetime) -> int:
    """One delivery per (user, listing, generation, channel), however many of
    the user's searches matched. EMAIL only to a verified address — and even
    then it is re-checked at send time."""
    if not user_ids:
        return 0
    channels = preferences.enabled_channels(db, user_ids, PRODUCT)
    verified = set(db.scalars(select(User.id).where(User.id.in_(user_ids),
                                                    User.email_verified_at.is_not(None))))
    rows = []
    for user_id in user_ids:
        for channel in sorted(channels[user_id]):
            if channel == "EMAIL" and user_id not in verified:
                continue
            rows.append({"id": str(uuid4()), "user_id": user_id, "listing_id": listing_id,
                         "public_generation": generation, "channel": channel,
                         "category": PRODUCT, "status": "pending", "attempts": 0,
                         "next_attempt_at": now, "outcome": "", "created_at": now})
    return insert_ignore(db, AlertDelivery, rows,
                         ["user_id", "listing_id", "public_generation", "channel"])
