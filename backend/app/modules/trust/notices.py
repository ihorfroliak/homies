"""Moderation notices (TASK-015 S3, founder D-9; S4b: viewing requesters and photos).

Inbox only (`user_notifications`), category TRANSACTIONAL: no email, no
outbox, no provider, no preference can switch them off, and TASK-014's
`alert_deliveries` is not involved.

Written by the decision service (`decisions.apply_*_decision`), in the
decision's own transaction: a rolled-back decision leaves no notice behind. Exactly once per
(decision, manager) without a new key: a decision row is created once (its
compare-and-set on the chain head refuses a retry after an unknown COMMIT,
and the database refuses a second successor of a head), and its notices are
written only by the call that inserts it — once per distinct manager.

What a notice says is the decision's public face for the owner (Phase A §9):
the listing, the action, the reason code and the date, as localisation keys
and identifiers. Never the reporter, a report count, report or moderator
text, an address, or the allegation. Legal wording (L2) is the client's
template work, not decided here.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.alerts.models import UserNotification
from app.modules.engagement.models import Viewing
from app.modules.properties import authority, freshness
from app.modules.trust.models import HOLD_ACTIONS, ModerationDecision

TRANSACTIONAL = "TRANSACTIONAL"
LISTING_HELD = "MODERATION_LISTING_HELD"
LISTING_RELEASED = "MODERATION_LISTING_RELEASED"

# The notice's data, exactly (a test pins it, with a forbidden-key list).
NOTICE_DATA_KEYS = ("listing_id", "decision_id", "action", "reason_code", "effective_from")

_KEYS = {
    LISTING_HELD: ("moderation.listing_held.title", "moderation.listing_held.body"),
    LISTING_RELEASED: ("moderation.listing_released.title", "moderation.listing_released.body"),
}


def kind(decision: ModerationDecision, was_held: bool) -> str | None:
    """Which notice a listing decision gives its managers, if any. A hold
    (new or changed) is notified; a release says the listing may be
    republished; NO_ACTION on a listing that was not held is a dismissal the
    owner never saw — nothing is sent."""
    if decision.action in HOLD_ACTIONS:
        return LISTING_HELD
    if was_held:
        return LISTING_RELEASED
    return None


def notify_listing_managers(db: Session, decision: ModerationDecision, property_id: str,
                            notice: str) -> list[str]:
    """One inbox notice per distinct manager of the listing's property (the
    accounts that may publish it). Returns the recipients."""
    title_key, body_key = _KEYS[notice]
    recipients = authority.holders(db, property_id, "PUBLISH_LISTING")
    data = {
        "listing_id": decision.listing_id,
        "decision_id": decision.id,
        "action": decision.action,
        "reason_code": decision.reason_code,
        "effective_from": freshness.canonical_instant(decision.effective_from),
    }
    for user_id in recipients:
        db.add(UserNotification(
            user_id=user_id,
            category=TRANSACTIONAL,
            notification_type=notice,
            title_key=title_key,
            body_key=body_key,
            data=dict(data),
            created_at=decision.effective_from,
        ))
    return recipients


# --- Slice 4b ------------------------------------------------------------------

VIEWING_CANCELLED = "MODERATION_VIEWING_CANCELLED"
MEDIA_RESTRICTED = "MODERATION_MEDIA_RESTRICTED"

_KEYS[VIEWING_CANCELLED] = ("moderation.viewing_cancelled.title",
                            "moderation.viewing_cancelled.body")
_KEYS[MEDIA_RESTRICTED] = ("moderation.media_restricted.title",
                           "moderation.media_restricted.body")

# What a requester learns when Homies cancels their viewing: which viewing,
# on which listing, and when. Not the decision, its action or its reason —
# the requester is not the listing's owner, and no allegation reaches them
# (Phase A §11, L11 governs the final wording).
VIEWING_NOTICE_DATA_KEYS = ("viewing_id", "listing_id", "effective_from")
MEDIA_NOTICE_DATA_KEYS = ("media_asset_id", "listing_id", "decision_id", "action",
                          "reason_code", "effective_from")


def notify_viewings_cancelled(db: Session, decision: ModerationDecision,
                              viewing_ids: list[str]) -> list[str]:
    """One notice per cancelled viewing, to its requester."""
    title_key, body_key = _KEYS[VIEWING_CANCELLED]
    rows = db.execute(select(Viewing.id, Viewing.listing_id, Viewing.requester_user_id)
                      .where(Viewing.id.in_(viewing_ids)).order_by(Viewing.id)).all()
    for row in rows:
        db.add(UserNotification(
            user_id=row.requester_user_id, category=TRANSACTIONAL,
            notification_type=VIEWING_CANCELLED, title_key=title_key, body_key=body_key,
            data={"viewing_id": row.id, "listing_id": row.listing_id,
                  "effective_from": freshness.canonical_instant(decision.effective_from)},
            created_at=decision.effective_from,
        ))
    return [r.requester_user_id for r in rows]


def notify_media_restricted(db: Session, decision: ModerationDecision,
                            property_id: str) -> list[str]:
    """One notice per distinct manager of the photo's property."""
    title_key, body_key = _KEYS[MEDIA_RESTRICTED]
    recipients = authority.holders(db, property_id, "MANAGE_MEDIA")
    data = {
        "media_asset_id": decision.target_id,
        "listing_id": decision.listing_id,
        "decision_id": decision.id,
        "action": decision.action,
        "reason_code": decision.reason_code,
        "effective_from": freshness.canonical_instant(decision.effective_from),
    }
    for user_id in recipients:
        db.add(UserNotification(
            user_id=user_id, category=TRANSACTIONAL, notification_type=MEDIA_RESTRICTED,
            title_key=title_key, body_key=body_key, data=dict(data),
            created_at=decision.effective_from,
        ))
    return recipients
