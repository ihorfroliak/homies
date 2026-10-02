"""Applying a moderation decision — the only place moderation changes anything
(04 invariant 23: reports never mutate their target; 04a §23).

Slice 1 implements LISTING decisions, the ones the publication hold needs:

    NO_ACTION               resolves; superseding a hold RELEASES it (no
                            republish — the owner republishes through
                            `make_public`, which opens a new public episode)
    CONTENT_EDIT_REQUIRED   hold: the listing is paused and cannot become
    VISIBILITY_LIMITED      active while this decision is the chain head

One transaction, in the coordination lock order (properties → … → offers):

    property lock → listing row lock → compare the expected head with the head
    → insert the decision (superseding the head) → pause (hold actions)
    → resolve the target's live reports → audit → managers' inbox notices
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
from app.core.security import can_moderate
from app.modules.events import service as events
from app.modules.identity.models import User
from app.modules.properties import authority, coordination, freshness
from app.modules.properties.models import AUTHORITY_SCOPES, PAUSABLE_FROM, ClassifiedOffer
from app.modules.trust import committed, hold, notices
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

# Actions Slice 1 can apply to a listing (MEDIA/MESSAGE/CONVERSATION: Slice 4).
LISTING_ACTIONS = ("NO_ACTION", *HOLD_ACTIONS)

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
) -> AppliedDecision:
    """Record and apply one decision on a listing. The caller commits (or
    rolls back on `DecisionRefused`)."""
    if not can_moderate(actor):
        raise NotAModerator("only a moderator can decide")
    if action not in LISTING_ACTIONS:
        raise InvalidDecision(f"{action} is not a listing action in this slice")
    if reclassified_category is not None and reclassified_category not in REPORT_CATEGORIES:
        raise InvalidDecision("unknown category")

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
        close_engagement=False,  # Slice 4
        listing_public_generation_at_decision=row.public_generation,
    )
    db.add(decision)
    db.flush()  # the database refuses a fork here even if the lock were missing
    db.refresh(decision, attribute_names=["effective_from"])

    status_after = row.status
    if action in HOLD_ACTIONS:
        status_after = _pause(db, listing_id, row.status)

    resolved = _resolve_reports(db, "LISTING", listing_id, decision.id, actor.id)
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
