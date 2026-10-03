"""What a moderation decision does to conversations and viewings (TASK-015 S4b).

Two effects, both written in the decision's own transaction:

* closing a conversation — status CLOSED and one neutral SYSTEM line. The
  line is a stable key the client renders ("Closed by Homies"); it never
  carries a reporter, an allegation, a reason or a moderator's words (L11
  governs the final wording, not this module);
* cancelling a listing's future viewings — REQUESTED or CONFIRMED viewings
  that start after the decision become CANCELLED, with `cancelled_at` set to
  the decision's database instant. That instant is what marks a viewing as
  cancelled by Homies (`cancelled_by_homies`): a user's cancellation can
  never carry exactly the instant of a close-engagement decision on the
  same listing, because both are written under the viewing's row lock.

Lock order (Phase A §14): the caller already holds property → listing; here
conversations are locked in id order, then viewings in id order. Every path
that writes a conversation (send, start) or a viewing (request, confirm)
either takes the listing row first or locks only its own row, so none of
them can wait on a listing while holding a row this module needs.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.modules.engagement.models import Conversation, Message, Viewing
from app.modules.events import facts
from app.modules.properties import freshness
from app.modules.trust.models import ModerationDecision

# The SYSTEM line a closed conversation ends with — a client string key.
CLOSED_BY_HOMIES = "system.conversation_closed_by_homies"
# Viewing states a close-engagement decision cancels (the viewing is ahead).
CANCELLABLE = ("REQUESTED", "CONFIRMED")
# close_engagement is only for these policy reasons (Phase A §6.2).
CLOSE_ENGAGEMENT_REASONS = ("SCAM", "FAKE", "SAFETY")


def close_conversation(db: Session, conv: Conversation, decision: ModerationDecision) -> bool:
    """Close one locked conversation with the neutral SYSTEM line. False when
    it was not ACTIVE (already closed or archived): nothing is written."""
    if conv.status != "ACTIVE":
        return False
    # The line is the conversation's last word. The decision's instant is its
    # transaction's start, which can precede a message that committed while
    # the decision waited for this row — so never before the last message.
    # Read under the conversation lock: no message can commit after it.
    at = _utc(decision.effective_from)
    last = _utc(db.scalar(select(func.max(Message.created_at))
                          .where(Message.conversation_id == conv.id)))
    if at is not None and last is not None and last >= at:
        at = last + timedelta(microseconds=1)
    conv.status = "CLOSED"
    conv.version += 1
    conv.last_message_at = at
    db.add(Message(conversation_id=conv.id, message_type="SYSTEM", body=CLOSED_BY_HOMIES,
                   created_at=at))
    return True


def lock_conversation(db: Session, conversation_id: str) -> Conversation | None:
    """The conversation as committed now, locked for the transaction."""
    return db.scalar(select(Conversation).where(Conversation.id == conversation_id)
                     .with_for_update().execution_options(populate_existing=True))


def close_listing_engagement(db: Session, listing_id: str,
                             decision: ModerationDecision) -> tuple[list[str], list[str]]:
    """Close every ACTIVE conversation of the listing and cancel its future
    REQUESTED/CONFIRMED viewings. Returns (closed conversation ids, cancelled
    viewing ids). The caller holds the property and listing row locks."""
    effective: datetime = decision.effective_from
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.listing_id == listing_id, Conversation.status == "ACTIVE")
        .order_by(Conversation.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    closed = [c.id for c in conversations if close_conversation(db, c, decision)]

    viewings = db.execute(
        select(Viewing.id, Viewing.status)
        .where(Viewing.listing_id == listing_id, Viewing.status.in_(CANCELLABLE),
               Viewing.starts_at > effective)
        .order_by(Viewing.id)
        .with_for_update()
    ).all()
    viewing_ids = [v.id for v in viewings]
    if viewing_ids:
        db.execute(
            update(Viewing)
            .where(Viewing.id.in_(viewing_ids), Viewing.status.in_(CANCELLABLE))
            .values(status="CANCELLED", cancelled_at=effective, version=Viewing.version + 1)
            .execution_options(synchronize_session=False)
        )
        for v in viewings:
            facts.viewing_cancelled(
                db, viewing_id=v.id, listing_id=listing_id, prior_status=v.status,
                cancelled_by="HOMIES", moderation_decision_id=decision.id,
                cancelled_at=freshness.canonical_instant(effective))
    if closed or viewing_ids:
        audit(db, actor=decision.decided_by_user_id, action="moderation.engagement_closed",
              entity_type="classified_offer", entity_id=listing_id,
              data={"decision_id": decision.id, "conversation_ids": closed,
                    "viewing_ids": viewing_ids})
    return closed, viewing_ids


def cancelled_by_homies(db: Session, viewings: list[Viewing]) -> set[str]:
    """Ids of the given CANCELLED viewings that a close-engagement decision on
    their listing cancelled — one statement for the whole list."""
    cancelled = [v for v in viewings if v.status == "CANCELLED" and v.cancelled_at is not None]
    if not cancelled:
        return set()
    listing_ids = {v.listing_id for v in cancelled}
    instants = {(r.listing_id, _utc(r.effective_from)) for r in db.execute(
        select(ModerationDecision.listing_id, ModerationDecision.effective_from)
        .where(ModerationDecision.target_type == "LISTING",
               ModerationDecision.listing_id.in_(listing_ids),
               ModerationDecision.close_engagement.is_(True))
    )}
    return {v.id for v in cancelled if (v.listing_id, _utc(v.cancelled_at)) in instants}


def _utc(value: datetime | None) -> datetime | None:
    # SQLite hands back naive UTC; PostgreSQL aware. Compare instants.
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else \
        value.astimezone(timezone.utc)
