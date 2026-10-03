"""Applying a moderation decision — the only place moderation changes anything
(04 invariant 23: reports never mutate their target; 04a §23).

Slice 1 implements LISTING decisions, the ones the publication hold needs:

    NO_ACTION               resolves; superseding a hold RELEASES it (no
                            republish — the owner republishes through
                            `make_public`, which opens a new public episode)
    CONTENT_EDIT_REQUIRED   hold: the listing is paused and cannot become
    VISIBILITY_LIMITED      active while this decision is the chain head;
                            with `close_engagement` (SCAM, FAKE or SAFETY
                            only — Slice 4b) it also closes the listing's
                            ACTIVE conversations and cancels its future
                            viewings (trust/effects.py)

Slice 4a adds MESSAGE decisions, Slice 4b CONVERSATION (FEATURE_RESTRICTED:
closed, with a neutral SYSTEM line) and MEDIA (CONTENT_REMOVED: RESTRICTED,
non-destructive) — each below, with its own lock order.

One transaction, in the coordination lock order (properties → … → offers):

    property lock → listing row lock → compare the expected head with the head
    → insert the decision (superseding the head) → pause (hold actions)
    → resolve the target's live reports → answer the owner's open review
    request on the superseded hold → audit → managers' inbox notices
    → ModerationDecisionRecorded

The compare-and-set on the head is what makes a retry safe after an unknown
COMMIT (PR-003): if the first attempt committed, the retry's expected head is
no longer the head and it gets `StaleHead` — never a second branch. The
database refuses a fork even without the lock (UNIQUE supersedes_decision_id,
one first decision per target).

The caller commits. `homies_moderation_decisions_total` counts a decision only
when its transaction commits.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from prometheus_client import Counter
from sqlalchemy import exists, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import lock_row
from app.core.security import can_moderate
from app.modules.engagement import access as conversation_access
from app.modules.engagement.models import Conversation, Message
from app.modules.events import facts
from app.modules.events import service as events
from app.modules.identity.models import User
from app.modules.media.models import ListingMedia, MediaAsset
from app.modules.properties import authority, coordination, freshness
from app.modules.properties.models import AUTHORITY_SCOPES, PAUSABLE_FROM, ClassifiedOffer
from app.modules.trust import committed, effects, hold, notices, reviews
from app.modules.trust.models import (
    DECISION_ACTIONS,
    DECISION_TARGET_TYPES,
    HOLD_ACTIONS,
    LIVE_REPORT_STATUSES,
    NOT_A_VIOLATION,
    RELEASE_REASONS,
    REPORT_CATEGORIES,
    ModerationDecision,
    Report,
)

MODERATION_DECISION_RECORDED = "ModerationDecisionRecorded"
# The event payload, exactly. Identifiers, closed codes and the database
# instant — never the reporter, report or explanation text, an address, a
# coordinate, a message body or a contact (Phase A §9, §12).
EVENT_PAYLOAD_KEYS = (
    "decision_id", "target_type", "target_id", "listing_id", "action", "reason_code",
    "supersedes_decision_id", "effective_from",
)

# Actions Slice 1 can apply to a listing.
LISTING_ACTIONS = ("NO_ACTION", *HOLD_ACTIONS)
# Slice 4a: a message is dismissed or removed (redacted for participants).
MESSAGE_ACTIONS = ("NO_ACTION", "CONTENT_REMOVED")
# Slice 4b: a conversation is dismissed or closed by Homies; a photo is
# dismissed or restricted.
CONVERSATION_ACTIONS = ("NO_ACTION", "FEATURE_RESTRICTED")
MEDIA_ACTIONS = ("NO_ACTION", "CONTENT_REMOVED")

DECISIONS = Counter(
    "homies_moderation_decisions_total",
    "Committed moderation decisions by target type and action",
    ["target_type", "action"],
)
for _target in DECISION_TARGET_TYPES:
    for _action in DECISION_ACTIONS:
        DECISIONS.labels(target_type=_target, action=_action)

class DecisionRefused(Exception):
    """The decision cannot be applied; nothing was written."""

    code = "DECISION_REFUSED"


class NotAModerator(DecisionRefused):
    code = "NOT_A_MODERATOR"


class ConflictOfInterest(DecisionRefused):
    code = "CONFLICT_OF_INTEREST"


class TargetNotFound(DecisionRefused):
    code = "TARGET_NOT_FOUND"


class InvalidDecision(DecisionRefused):
    code = "INVALID_DECISION"


class StaleHead(DecisionRefused):
    """The caller decided on a head that is no longer current — another
    decision (perhaps the caller's own earlier attempt) superseded it."""

    code = "STALE_HEAD"

    def __init__(self, current_head_id: str | None):
        super().__init__(f"the current decision is {current_head_id or 'none'}")
        self.current_head_id = current_head_id


@dataclass(frozen=True)
class AppliedDecision:
    decision_id: str
    supersedes_decision_id: str | None
    action: str
    listing_status_before: str
    listing_status_after: str
    held: bool                     # the listing is held after this decision
    resolved_report_ids: tuple[str, ...]
    notified_user_ids: tuple[str, ...] = ()
    effective_from: datetime | None = None
    answered_review_request_id: str | None = None
    # Slice 4b effects: conversations closed and viewings cancelled.
    closed_conversation_ids: tuple[str, ...] = ()
    cancelled_viewing_ids: tuple[str, ...] = ()


def apply_listing_decision(
    db: Session,
    *,
    actor: User,
    listing_id: str,
    action: str,
    reason_code: str,
    expected_head_decision_id: str | None,
    report_id: str | None = None,
    explanation: str | None = None,
    reclassified_category: str | None = None,
    close_engagement: bool = False,
) -> AppliedDecision:
    """Record and apply one decision on a listing. The caller commits (or
    rolls back on `DecisionRefused`)."""
    if not can_moderate(actor):
        raise NotAModerator("only a moderator can decide")
    if action not in LISTING_ACTIONS:
        raise InvalidDecision(f"{action} is not a listing action in this slice")
    if reclassified_category is not None and reclassified_category not in REPORT_CATEGORIES:
        raise InvalidDecision("unknown category")
    # Correctable holds never destroy engagement: only a visibility limit for
    # a scam, a fake or a safety risk may close it (Phase A §6.2).
    if close_engagement and not (action == "VISIBILITY_LIMITED"
                                 and reason_code in effects.CLOSE_ENGAGEMENT_REASONS):
        raise InvalidDecision("close_engagement needs VISIBILITY_LIMITED with reason "
                              "SCAM, FAKE or SAFETY")

    offer = db.get(ClassifiedOffer, listing_id)
    if offer is None:
        raise TargetNotFound("listing not found")
    # Coordination order: the property row first (publish, confirm, revoke and
    # space archive take it too), then the listing row.
    if coordination.lock_property(db, offer.property_id) is None:
        raise TargetNotFound("listing not found")
    row = db.execute(
        select(ClassifiedOffer.status, ClassifiedOffer.property_id,
               ClassifiedOffer.public_generation)
        .where(ClassifiedOffer.id == listing_id)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise TargetNotFound("listing not found")

    # Conflict of interest: whoever can act on the property decides nothing on
    # it, and neither does anyone with a live report on the target — any of
    # them, not one the caller names (TASK-015 S3). Re-checked under the
    # report row locks in `_resolve_reports`. Participants: Slice 4.
    if any(authority.can_act(db, actor.id, row.property_id, scope, verified=False)
           for scope in AUTHORITY_SCOPES):
        raise ConflictOfInterest("the moderator manages this property")
    if db.scalar(select(exists().where(
            Report.target_type == "LISTING", Report.target_id == listing_id,
            Report.reporter_user_id == actor.id,
            Report.status.in_(LIVE_REPORT_STATUSES)))):
        raise ConflictOfInterest("the moderator reported this listing")

    current = hold.head(db, "LISTING", listing_id)
    current_id = current.id if current else None
    if current_id != expected_head_decision_id:
        raise StaleHead(current_id)
    currently_held = current is not None and current.action in HOLD_ACTIONS
    _validate_reason(action, reason_code, currently_held)

    report = _report(db, report_id, listing_id, actor) if report_id else None

    decision = ModerationDecision(
        report_id=report.id if report else None,
        target_type="LISTING",
        target_id=listing_id,
        listing_id=listing_id,
        action=action,
        reason_code=reason_code,
        explanation=explanation,
        decided_by_user_id=actor.id,
        supersedes_decision_id=current_id,
        reclassified_category=reclassified_category,
        close_engagement=close_engagement,
        listing_public_generation_at_decision=row.public_generation,
    )
    db.add(decision)
    db.flush()  # the database refuses a fork here even if the lock were missing
    db.refresh(decision, attribute_names=["effective_from"])

    status_after = row.status
    if action in HOLD_ACTIONS:
        status_after = _pause(db, listing_id, row.status)
        facts.listing_status_changed(
            db, listing_id=listing_id, property_id=row.property_id, from_status=row.status,
            to_status=status_after, reason_code="MODERATION_HOLD",
            public_generation=row.public_generation)
    closed: list[str] = []
    cancelled: list[str] = []
    if close_engagement:
        # Lock order continues: … listing → conversations → viewings (id order).
        closed, cancelled = effects.close_listing_engagement(db, listing_id, decision)

    resolved = _resolve_reports(db, "LISTING", listing_id, decision.id, actor.id)
    # The owner's open review request on the superseded hold is answered by
    # this decision — in this transaction, so never ANSWERED by a decision
    # that did not commit, and never left OPEN on a hold that is not current.
    answered = reviews.answer_open_request(db, current_id, decision.id)
    audit(
        db,
        actor=actor.id,
        action=f"moderation.{action.lower()}",
        entity_type="classified_offer",
        entity_id=listing_id,
        data={
            "decision_id": decision.id,
            "reason_code": reason_code,
            "supersedes_decision_id": current_id,
            "status_before": row.status,
            "status_after": status_after,
        },
    )
    notice = notices.kind(decision, currently_held)
    notified = (notices.notify_listing_managers(db, decision, row.property_id, notice)
                if notice else [])
    if cancelled:
        notices.notify_viewings_cancelled(db, decision, cancelled)
    _emit(db, decision)
    committed.count_on_commit(db, DECISIONS, target_type="LISTING", action=action)
    return AppliedDecision(
        decision_id=decision.id,
        supersedes_decision_id=current_id,
        action=action,
        listing_status_before=row.status,
        listing_status_after=status_after,
        held=action in HOLD_ACTIONS,
        resolved_report_ids=resolved,
        notified_user_ids=tuple(notified),
        effective_from=decision.effective_from,
        answered_review_request_id=answered,
        closed_conversation_ids=tuple(closed),
        cancelled_viewing_ids=tuple(cancelled),
    )


def _validate_reason(action: str, reason_code: str, currently_held: bool) -> None:
    if action in HOLD_ACTIONS:
        if reason_code not in REPORT_CATEGORIES:
            raise InvalidDecision("a hold needs a policy reason (a report category)")
        return
    # NO_ACTION: a release when a hold is current, otherwise a dismissal.
    if currently_held:
        if reason_code not in RELEASE_REASONS:
            raise InvalidDecision("releasing a hold needs REINSTATED_REMEDIED or "
                                  "REINSTATED_DECISION_ERROR")
    elif reason_code != NOT_A_VIOLATION:
        raise InvalidDecision("NO_ACTION on a listing that is not held is NOT_A_VIOLATION")


def _report(db: Session, report_id: str, listing_id: str, actor: User) -> Report:
    report = db.get(Report, report_id)
    if (report is None or report.target_type != "LISTING" or report.target_id != listing_id
            or report.status not in LIVE_REPORT_STATUSES):
        raise InvalidDecision("the report is not a live report on this listing")
    if report.reporter_user_id == actor.id:
        raise ConflictOfInterest("the moderator filed this report")
    return report


def _pause(db: Session, listing_id: str, status_before: str) -> str:
    """The hold's effect through the existing lifecycle: `paused` is not
    public on every path, for this release and for the previous one."""
    paused = cast(CursorResult, db.execute(
        update(ClassifiedOffer)
        .where(ClassifiedOffer.id == listing_id, ClassifiedOffer.status.in_(PAUSABLE_FROM))
        .values(status="paused")
        .execution_options(synchronize_session=False)
    ))
    # archived stays archived (never public again); the hold still stands.
    return "paused" if paused.rowcount == 1 else status_before


def _resolve_reports(db: Session, target_type: str, target_id: str,
                     decision_id: str, actor_id: str) -> tuple[str, ...]:
    """Every report live at the decision is resolved by it; a report filed
    after this commit stays OPEN for the next review. A moderator never
    resolves a report of their own — checked here, under the row locks, so a
    report they filed while the decision was being made is caught too."""
    rows = db.execute(
        select(Report.id, Report.reporter_user_id)
        .where(Report.target_type == target_type,
               Report.target_id == target_id,
               Report.status.in_(LIVE_REPORT_STATUSES))
        .order_by(Report.id)
        .with_for_update()
    ).all()
    if any(r.reporter_user_id == actor_id for r in rows):
        raise ConflictOfInterest("the moderator reported this listing")
    ids = tuple(r.id for r in rows)
    if ids:
        now = freshness.db_now(db)
        db.execute(
            update(Report).where(Report.id.in_(ids))
            .values(status="RESOLVED", resolved_at=now, updated_at=now,
                    resolution_decision_id=decision_id, version=Report.version + 1)
            .execution_options(synchronize_session=False)
        )
    return ids


def event_payload(decision: ModerationDecision) -> dict:
    return {
        "decision_id": decision.id,
        "target_type": decision.target_type,
        "target_id": decision.target_id,
        "listing_id": decision.listing_id,
        "action": decision.action,
        "reason_code": decision.reason_code,
        "supersedes_decision_id": decision.supersedes_decision_id,
        "effective_from": freshness.canonical_instant(decision.effective_from),
    }


def _emit(db: Session, decision: ModerationDecision) -> None:
    # Not routed: ModerationDecisionRecorded is not in events.ROUTING, whose
    # recipient resolution is booking-era. A new decision id cannot collide.
    if not events.emit(db, MODERATION_DECISION_RECORDED, decision.id, event_payload(decision),
                       f"{MODERATION_DECISION_RECORDED}:{decision.id}"):
        raise RuntimeError("moderation decision event emitted twice")



# --- MESSAGE decisions (Slice 4a) ------------------------------------------------
#
#     NO_ACTION        resolves the live reports; the message is untouched.
#                      Only while the message is not removed: S4a defines no
#                      restoration — a removed message is never shown again.
#     CONTENT_REMOVED  redacts the message for the conversation's participants
#                      (`redacted_at`, `redaction_reason_code`); the stored body
#                      stays, as evidence read only through the audited
#                      moderator path. Nothing else changes: no conversation
#                      closure, no listing hold, no viewing or account effect.
#
# Lock order: the listing (FOR KEY SHARE, S4b) → conversation row → message
# row → head CAS → insert → redaction → the target's live reports (FOR
# UPDATE, id order) → audit → event — the listing → conversation order of
# close_engagement (see `_share_listing_of`).


def apply_message_decision(
    db: Session,
    *,
    actor: User,
    message_id: str,
    action: str,
    reason_code: str,
    expected_head_decision_id: str | None,
    explanation: str | None = None,
    reclassified_category: str | None = None,
) -> AppliedDecision:
    """Record and apply one decision on a message. The caller commits (or
    rolls back on `DecisionRefused`)."""
    if not can_moderate(actor):
        raise NotAModerator("only a moderator can decide")
    if action not in MESSAGE_ACTIONS:
        raise InvalidDecision(f"{action} is not a message action in this slice")
    if reclassified_category is not None and reclassified_category not in REPORT_CATEGORIES:
        raise InvalidDecision("unknown category")

    message = db.get(Message, message_id)
    if message is None:
        raise TargetNotFound("message not found")
    _share_listing_of(db, message.conversation_id)
    conv = db.execute(select(Conversation).where(Conversation.id == message.conversation_id)
                      .with_for_update()).scalar_one_or_none()
    row = db.execute(select(Message.redacted_at, Message.sender_user_id)
                     .where(Message.id == message_id).with_for_update()).one_or_none()
    if conv is None or row is None:
        raise TargetNotFound("message not found")

    # Conflict of interest: a current side of the conversation (its tenant, or
    # whoever holds MANAGE_MESSAGES on the listing's property now), anyone with
    # authority over that property, the message's own sender, or a moderator
    # with a live report on it. A former provider with no current right is not
    # conflicted by history alone.
    if conversation_access.side(db, actor.id, conv) is not None:
        raise ConflictOfInterest("the moderator is a participant of this conversation")
    prop = conversation_access.property_of(db, conv)
    if prop is not None and any(authority.can_act(db, actor.id, prop, scope, verified=False)
                                for scope in AUTHORITY_SCOPES):
        raise ConflictOfInterest("the moderator manages this listing's property")
    if row.sender_user_id == actor.id:
        raise ConflictOfInterest("the moderator wrote this message")
    if db.scalar(select(exists().where(
            Report.target_type == "MESSAGE", Report.target_id == message_id,
            Report.reporter_user_id == actor.id,
            Report.status.in_(LIVE_REPORT_STATUSES)))):
        raise ConflictOfInterest("the moderator reported this message")

    current = hold.head(db, "MESSAGE", message_id)
    current_id = current.id if current else None
    if current_id != expected_head_decision_id:
        raise StaleHead(current_id)
    removed = row.redacted_at is not None or (
        current is not None and current.action == "CONTENT_REMOVED")
    if removed:
        raise InvalidDecision("the message was removed; removal is not reversed in this slice")
    if action == "CONTENT_REMOVED":
        if reason_code not in REPORT_CATEGORIES:
            raise InvalidDecision("a removal needs a policy reason (a report category)")
    elif reason_code != NOT_A_VIOLATION:
        raise InvalidDecision("NO_ACTION on a message is NOT_A_VIOLATION")

    decision = ModerationDecision(
        target_type="MESSAGE",
        target_id=message_id,
        listing_id=conv.listing_id,
        action=action,
        reason_code=reason_code,
        explanation=explanation,
        decided_by_user_id=actor.id,
        supersedes_decision_id=current_id,
        reclassified_category=reclassified_category,
        close_engagement=False,  # Slice 4b
    )
    db.add(decision)
    db.flush()  # the database refuses a fork here even if the lock were missing
    db.refresh(decision, attribute_names=["effective_from"])

    if action == "CONTENT_REMOVED":
        redacted = cast(CursorResult, db.execute(
            update(Message)
            .where(Message.id == message_id, Message.redacted_at.is_(None))
            .values(redacted_at=decision.effective_from, redaction_reason_code=reason_code)
            .execution_options(synchronize_session=False)
        ))
        if redacted.rowcount != 1:
            raise InvalidDecision("the message was removed meanwhile")

    resolved = _resolve_reports(db, "MESSAGE", message_id, decision.id, actor.id)
    audit(
        db,
        actor=actor.id,
        action=f"moderation.message_{action.lower()}",
        entity_type="message",
        entity_id=message_id,
        data={
            "decision_id": decision.id,
            "reason_code": reason_code,
            "supersedes_decision_id": current_id,
            "conversation_id": conv.id,
        },
    )
    _emit(db, decision)
    committed.count_on_commit(db, DECISIONS, target_type="MESSAGE", action=action)
    return AppliedDecision(
        decision_id=decision.id,
        supersedes_decision_id=current_id,
        action=action,
        listing_status_before="",
        listing_status_after="",
        held=False,
        resolved_report_ids=resolved,
        effective_from=decision.effective_from,
    )


# --- CONVERSATION decisions (Slice 4b) -------------------------------------------
#
#     NO_ACTION           dismissal (NOT_A_VIOLATION); only while not restricted
#     FEATURE_RESTRICTED  the conversation is CLOSED with a neutral SYSTEM line
#                         (both sides see "closed by Homies"); the requester may
#                         not open another conversation on the listing for the
#                         same public generation (founder G-14). Terminal: canon
#                         defines no reopening.
#
# Lock order: the listing (FOR KEY SHARE) → conversation row → head CAS →
# insert → close → audit → event — listing before conversation, as in
# close_engagement. Live MESSAGE reports in the conversation are separate
# targets and stay as they are.


def apply_conversation_decision(
    db: Session,
    *,
    actor: User,
    conversation_id: str,
    action: str,
    reason_code: str,
    expected_head_decision_id: str | None,
    explanation: str | None = None,
    reclassified_category: str | None = None,
) -> AppliedDecision:
    """Record and apply one decision on a conversation. The caller commits
    (or rolls back on `DecisionRefused`)."""
    if not can_moderate(actor):
        raise NotAModerator("only a moderator can decide")
    if action not in CONVERSATION_ACTIONS:
        raise InvalidDecision(f"{action} is not a conversation action")
    if reclassified_category is not None and reclassified_category not in REPORT_CATEGORIES:
        raise InvalidDecision("unknown category")

    _share_listing_of(db, conversation_id)
    conv = effects.lock_conversation(db, conversation_id)
    if conv is None:
        raise TargetNotFound("conversation not found")

    if conversation_access.side(db, actor.id, conv) is not None:
        raise ConflictOfInterest("the moderator is a participant of this conversation")
    prop = conversation_access.property_of(db, conv)
    if prop is not None and any(authority.can_act(db, actor.id, prop, scope, verified=False)
                                for scope in AUTHORITY_SCOPES):
        raise ConflictOfInterest("the moderator manages this listing's property")
    if db.scalar(select(exists().where(
            Report.conversation_id == conversation_id, Report.reporter_user_id == actor.id,
            Report.status.in_(LIVE_REPORT_STATUSES)))):
        raise ConflictOfInterest("the moderator reported a message of this conversation")

    current = hold.head(db, "CONVERSATION", conversation_id)
    current_id = current.id if current else None
    if current_id != expected_head_decision_id:
        raise StaleHead(current_id)
    if current is not None and current.action == "FEATURE_RESTRICTED":
        raise InvalidDecision("the conversation was closed by Homies; it is not reopened")
    _validate_removal(action, "FEATURE_RESTRICTED", reason_code, "a restriction")
    if action == "FEATURE_RESTRICTED" and conv.status != "ACTIVE":
        # The G-14 bar is recorded against the listing's current publication,
        # which is this conversation's own only while it is active.
        raise InvalidDecision("only an active conversation can be restricted")

    generation = db.scalar(select(ClassifiedOffer.public_generation)
                           .where(ClassifiedOffer.id == conv.listing_id)) \
        if conv.listing_id else None
    decision = ModerationDecision(
        target_type="CONVERSATION",
        target_id=conversation_id,
        listing_id=conv.listing_id,
        action=action,
        reason_code=reason_code,
        explanation=explanation,
        decided_by_user_id=actor.id,
        supersedes_decision_id=current_id,
        reclassified_category=reclassified_category,
        close_engagement=False,
        listing_public_generation_at_decision=generation,
    )
    db.add(decision)
    db.flush()
    db.refresh(decision, attribute_names=["effective_from"])

    closed: tuple[str, ...] = ()
    if action == "FEATURE_RESTRICTED" and effects.close_conversation(db, conv, decision):
        closed = (conv.id,)
    resolved = _resolve_reports(db, "CONVERSATION", conversation_id, decision.id, actor.id)
    audit(
        db,
        actor=actor.id,
        action=f"moderation.conversation_{action.lower()}",
        entity_type="conversation",
        entity_id=conversation_id,
        data={"decision_id": decision.id, "reason_code": reason_code,
              "supersedes_decision_id": current_id, "closed": bool(closed)},
    )
    _emit(db, decision)
    committed.count_on_commit(db, DECISIONS, target_type="CONVERSATION", action=action)
    return AppliedDecision(
        decision_id=decision.id,
        supersedes_decision_id=current_id,
        action=action,
        listing_status_before="",
        listing_status_after="",
        held=False,
        resolved_report_ids=resolved,
        effective_from=decision.effective_from,
        closed_conversation_ids=closed,
    )


# --- MEDIA decisions (Slice 4b) ----------------------------------------------------
#
#     NO_ACTION        dismissal (NOT_A_VIOLATION); only while not restricted
#     CONTENT_REMOVED  moderation_state = RESTRICTED. Non-destructive: the file,
#                      the asset, every listing link, the bytes and the history
#                      stay; the public serve and projection already refuse
#                      anything not APPROVED. Terminal in this slice.
#
# Never `media.router._moderate`: its rejection deletes listing links.
# Lock order: media asset row → head CAS → insert → state → audit → notices →
# event. `attach` takes the asset row (FOR SHARE) and re-reads its state, so a
# restricted photo is never attached after the restriction commits.


def apply_media_decision(
    db: Session,
    *,
    actor: User,
    media_asset_id: str,
    action: str,
    reason_code: str,
    expected_head_decision_id: str | None,
    listing_id: str | None = None,
    explanation: str | None = None,
    reclassified_category: str | None = None,
) -> AppliedDecision:
    """Record and apply one decision on a photo. `listing_id` (optional) is
    the listing the moderator saw it on — context only, and it must show the
    photo. The caller commits (or rolls back on `DecisionRefused`)."""
    if not can_moderate(actor):
        raise NotAModerator("only a moderator can decide")
    if action not in MEDIA_ACTIONS:
        raise InvalidDecision(f"{action} is not a media action")
    if reclassified_category is not None and reclassified_category not in REPORT_CATEGORIES:
        raise InvalidDecision("unknown category")

    asset = lock_row(db, MediaAsset, media_asset_id)
    if asset is None:
        raise TargetNotFound("media not found")
    if listing_id is not None and db.get(ListingMedia, (listing_id, media_asset_id)) is None:
        raise InvalidDecision("the photo is not on that listing")

    if any(authority.can_act(db, actor.id, asset.property_id, scope, verified=False)
           for scope in AUTHORITY_SCOPES):
        raise ConflictOfInterest("the moderator manages this property")
    if db.scalar(select(exists().where(
            Report.target_type == "MEDIA", Report.target_id == media_asset_id,
            Report.reporter_user_id == actor.id, Report.status.in_(LIVE_REPORT_STATUSES)))):
        raise ConflictOfInterest("the moderator reported this photo")

    current = hold.head(db, "MEDIA", media_asset_id)
    current_id = current.id if current else None
    if current_id != expected_head_decision_id:
        raise StaleHead(current_id)
    if asset.moderation_state == "RESTRICTED" or (
            current is not None and current.action == "CONTENT_REMOVED"):
        raise InvalidDecision("the photo is restricted; restriction is not reversed in this slice")
    _validate_removal(action, "CONTENT_REMOVED", reason_code, "a removal")

    decision = ModerationDecision(
        target_type="MEDIA",
        target_id=media_asset_id,
        listing_id=listing_id,
        action=action,
        reason_code=reason_code,
        explanation=explanation,
        decided_by_user_id=actor.id,
        supersedes_decision_id=current_id,
        reclassified_category=reclassified_category,
        close_engagement=False,
    )
    db.add(decision)
    db.flush()
    db.refresh(decision, attribute_names=["effective_from"])

    notified: list[str] = []
    if action == "CONTENT_REMOVED":
        restricted = cast(CursorResult, db.execute(
            update(MediaAsset)
            .where(MediaAsset.id == media_asset_id, MediaAsset.moderation_state != "RESTRICTED")
            .values(moderation_state="RESTRICTED")
            .execution_options(synchronize_session=False)
        ))
        if restricted.rowcount != 1:
            raise InvalidDecision("the photo was restricted meanwhile")
        notified = notices.notify_media_restricted(db, decision, asset.property_id)
    resolved = _resolve_reports(db, "MEDIA", media_asset_id, decision.id, actor.id)
    audit(
        db,
        actor=actor.id,
        action=f"moderation.media_{action.lower()}",
        entity_type="media_asset",
        entity_id=media_asset_id,
        data={"decision_id": decision.id, "reason_code": reason_code,
              "supersedes_decision_id": current_id, "listing_id": listing_id},
    )
    _emit(db, decision)
    committed.count_on_commit(db, DECISIONS, target_type="MEDIA", action=action)
    return AppliedDecision(
        decision_id=decision.id,
        supersedes_decision_id=current_id,
        action=action,
        listing_status_before="",
        listing_status_after="",
        held=False,
        resolved_report_ids=resolved,
        notified_user_ids=tuple(notified),
        effective_from=decision.effective_from,
    )


def _share_listing_of(db: Session, conversation_id: str) -> None:
    """The conversation's listing FOR KEY SHARE, before the conversation row.

    A conversation or message decision inserts a decision referencing the
    listing; that foreign-key check takes FOR KEY SHARE on it. Taken there —
    after the conversation lock — it closed a cycle with close_engagement
    (listing FOR UPDATE → conversations), a deadlock found in the S4b
    adversarial review. Taken first, every path orders listing → conversation.
    The listing id of a conversation never changes, so reading it unlocked is
    safe."""
    listing_id = db.scalar(select(Conversation.listing_id)
                           .where(Conversation.id == conversation_id))
    if listing_id is not None:
        db.execute(select(ClassifiedOffer.id).where(ClassifiedOffer.id == listing_id)
                   .with_for_update(read=True, key_share=True))


def _validate_removal(action: str, removal: str, reason_code: str, what: str) -> None:
    if action == removal:
        if reason_code not in REPORT_CATEGORIES:
            raise InvalidDecision(f"{what} needs a policy reason (a report category)")
    elif reason_code != NOT_A_VIOLATION:
        raise InvalidDecision("a dismissal is NOT_A_VIOLATION")
