"""The moderator's read side (TASK-015 Slice 3; Phase A §6.1, §6.3).

The queue groups live reports by target — there is no case entity: a target's
state is the head of its decision chain, its workload is its live reports.
Ordering is severity first (HIGH before NORMAL), then the oldest outstanding
report; severity orders the queue and does nothing else (no automatic action
from a count or a severity, 04 invariant 23).

Opening a target is the review: its OPEN reports become IN_REVIEW and
`first_reviewed_at` is set once, from the database clock — one conditional
UPDATE, so two moderators opening the same target at once set it once and a
report a decision already resolved never moves back.

The queue carries no report text, no reporter contact, no address, no
snapshot. The target detail carries what a human decision needs — including
who reported (internal user id and verification state, not email or phone)
and the report text — and is therefore audited as sensitive access (ids only).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import case, distinct, func, select, union, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.modules.identity.models import User
from app.modules.properties import freshness
from app.modules.properties.models import ClassifiedOffer
from app.modules.trust import hold
from app.modules.trust.models import (
    HOLD_ACTIONS,
    LIVE_REPORT_STATUSES,
    ModerationDecision,
    ModerationReviewRequest,
    Report,
)

_SEVERITY_RANK = case((Report.severity == "URGENT", 2), (Report.severity == "HIGH", 1), else_=0)
_RANK_SEVERITY = {2: "URGENT", 1: "HIGH", 0: "NORMAL"}


@dataclass(frozen=True)
class QueueItem:
    target_type: str
    target_id: str
    listing_id: str
    live_reports: int
    max_severity: str | None          # None: no live report (review-only work)
    oldest_report_at: datetime | None
    newest_report_at: datetime | None
    distinct_reporters: int
    phone_verified_reporters: int
    review_requested_at: datetime | None   # oldest OPEN review request
    head: ModerationDecision | None

    @property
    def held(self) -> bool:
        return self.head is not None and self.head.action in HOLD_ACTIONS

    @property
    def has_open_review_request(self) -> bool:
        return self.review_requested_at is not None


def queue(db: Session, *, limit: int, offset: int) -> tuple[list[QueueItem], int]:
    """One page of LISTING targets with moderator work, and how many there
    are. Work is a live report, or an OPEN review request (Slice 5: the owner
    asked for the hold to be reconsidered — the target is back even when every
    report was resolved). No severity is invented for review-only work.

    Order (operational, never a judgement): URGENT/HIGH reports first; then
    open review requests; then NORMAL-only reports. Within a class the oldest
    actionable item (report, or review request) first, then the target id.
    Two statements for the page and one for the heads — whatever its size."""
    reported = (
        select(
            Report.target_id.label("target_id"),
            func.count().label("live_reports"),
            func.max(_SEVERITY_RANK).label("severity"),
            func.min(Report.created_at).label("oldest"),
            func.max(Report.created_at).label("newest"),
            func.count(distinct(Report.reporter_user_id)).label("reporters"),
            func.count(distinct(case((User.phone_verified_at.is_not(None),
                                      Report.reporter_user_id)))).label("phone_verified"),
        )
        .outerjoin(User, User.id == Report.reporter_user_id)
        .where(Report.target_type == "LISTING", Report.status.in_(LIVE_REPORT_STATUSES))
        .group_by(Report.target_id)
        .subquery("reported")
    )
    reviewed = (
        select(ModerationDecision.target_id.label("target_id"),
               func.min(ModerationReviewRequest.created_at).label("review_at"))
        .join(ModerationDecision, ModerationDecision.id == ModerationReviewRequest.decision_id)
        .where(ModerationReviewRequest.status == "OPEN",
               ModerationDecision.target_type == "LISTING")
        .group_by(ModerationDecision.target_id)
        .subquery("reviewed")
    )
    targets = union(select(reported.c.target_id), select(reviewed.c.target_id)).subquery("t")
    total = db.scalar(select(func.count()).select_from(targets)) or 0
    work_class = case((reported.c.severity >= 1, 0),
                      (reviewed.c.review_at.is_not(None), 1), else_=2)
    actionable = case((work_class == 1, reviewed.c.review_at), else_=reported.c.oldest)
    rows = db.execute(
        select(targets.c.target_id, reported.c.live_reports, reported.c.severity,
               reported.c.oldest, reported.c.newest, reported.c.reporters,
               reported.c.phone_verified, reviewed.c.review_at)
        .select_from(targets)
        .outerjoin(reported, reported.c.target_id == targets.c.target_id)
        .outerjoin(reviewed, reviewed.c.target_id == targets.c.target_id)
        .order_by(work_class.asc(),
                  case((work_class == 0, reported.c.severity), else_=0).desc(),
                  actionable.asc(), targets.c.target_id.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    heads = hold.heads(db, "LISTING", [r.target_id for r in rows])
    items = [
        QueueItem(
            target_type="LISTING",
            target_id=r.target_id,
            listing_id=r.target_id,
            live_reports=r.live_reports or 0,
            max_severity=(_RANK_SEVERITY[int(r.severity)] if r.live_reports else None),
            oldest_report_at=freshness.to_utc(r.oldest) if r.oldest else None,
            newest_report_at=freshness.to_utc(r.newest) if r.newest else None,
            distinct_reporters=r.reporters or 0,
            phone_verified_reporters=r.phone_verified or 0,
            review_requested_at=freshness.to_utc(r.review_at) if r.review_at else None,
            head=heads.get(r.target_id),
        )
        for r in rows
    ]
    return items, total


@dataclass(frozen=True)
class ReviewedReport:
    report: Report
    reporter_email_verified: bool
    reporter_phone_verified: bool


@dataclass(frozen=True)
class TargetReview:
    offer: ClassifiedOffer
    is_public: bool
    head: ModerationDecision | None
    reports: list[ReviewedReport]
    moved_to_review: int
    review_request: ModerationReviewRequest | None = None


def review_listing(db: Session, *, moderator: User, listing_id: str) -> TargetReview | None:
    """Open a listing for review. None when the listing does not exist. The
    caller commits (the IN_REVIEW move and the access audit together)."""
    offer = db.get(ClassifiedOffer, listing_id)
    if offer is None:
        return None
    now = freshness.db_now(db)
    # Lock the OPEN reports in id order — the order a decision locks the
    # target's live reports in — so the two can only queue, never deadlock.
    # A second moderator waits here, then finds nothing OPEN; a report a
    # decision resolved meanwhile is not OPEN either, so it never regresses.
    open_ids = list(db.scalars(
        select(Report.id)
        .where(Report.target_type == "LISTING", Report.target_id == listing_id,
               Report.status == "OPEN")
        .order_by(Report.id)
        .with_for_update()
    ))
    moved = 0
    if open_ids:
        moved = cast(CursorResult[Any], db.execute(
            update(Report)
            .where(Report.id.in_(open_ids), Report.status == "OPEN")
            .values(status="IN_REVIEW",
                    first_reviewed_at=func.coalesce(Report.first_reviewed_at, now),
                    updated_at=now, version=Report.version + 1)
            .execution_options(synchronize_session=False)
        )).rowcount
    rows = db.execute(
        select(Report, User.email_verified_at, User.phone_verified_at)
        .outerjoin(User, User.id == Report.reporter_user_id)
        .where(Report.target_type == "LISTING", Report.target_id == listing_id,
               Report.status.in_(LIVE_REPORT_STATUSES))
        .order_by(Report.created_at, Report.id)
        .execution_options(populate_existing=True)
    ).all()
    reports = [ReviewedReport(r.Report, r.email_verified_at is not None,
                              r.phone_verified_at is not None) for r in rows]
    head = hold.head(db, "LISTING", listing_id)
    # The owner's open request on the current hold (read only: opening the
    # target does not change it; the next decision answers it).
    review_request = (db.scalar(select(ModerationReviewRequest).where(
        ModerationReviewRequest.decision_id == head.id,
        ModerationReviewRequest.status == "OPEN")) if head is not None else None)
    audit(
        db,
        actor=moderator.id,
        action="moderation.target_viewed",
        entity_type="classified_offer",
        entity_id=listing_id,
        data={"target_type": "LISTING", "report_ids": [r.report.id for r in reports],
              "review_request_id": review_request.id if review_request else None},
    )
    return TargetReview(
        offer=offer,
        is_public=freshness.is_public(offer, now),
        head=head,
        reports=reports,
        moved_to_review=moved,
        review_request=review_request,
    )
