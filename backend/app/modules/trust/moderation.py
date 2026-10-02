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

from sqlalchemy import case, distinct, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.modules.identity.models import User
from app.modules.properties import freshness
from app.modules.properties.models import ClassifiedOffer
from app.modules.trust import hold
from app.modules.trust.models import HOLD_ACTIONS, LIVE_REPORT_STATUSES, ModerationDecision, Report

_SEVERITY_RANK = case((Report.severity == "URGENT", 2), (Report.severity == "HIGH", 1), else_=0)
_RANK_SEVERITY = {2: "URGENT", 1: "HIGH", 0: "NORMAL"}


@dataclass(frozen=True)
class QueueItem:
    target_type: str
    target_id: str
    listing_id: str
    live_reports: int
    max_severity: str
    oldest_report_at: datetime
    newest_report_at: datetime
    distinct_reporters: int
    phone_verified_reporters: int
    head: ModerationDecision | None

    @property
    def held(self) -> bool:
        return self.head is not None and self.head.action in HOLD_ACTIONS


def queue(db: Session, *, limit: int, offset: int) -> tuple[list[QueueItem], int]:
    """One page of LISTING targets with live reports, and how many there are.
    Two statements for the page and one for the heads — whatever its size."""
    live = (Report.target_type == "LISTING", Report.status.in_(LIVE_REPORT_STATUSES))
    total = db.scalar(select(func.count(distinct(Report.target_id))).where(*live)) or 0
    severity = func.max(_SEVERITY_RANK).label("severity")
    oldest = func.min(Report.created_at).label("oldest")
    rows = db.execute(
        select(
            Report.target_id,
            func.count().label("live_reports"),
            severity,
            oldest,
            func.max(Report.created_at).label("newest"),
            func.count(distinct(Report.reporter_user_id)).label("reporters"),
            func.count(distinct(case((User.phone_verified_at.is_not(None),
                                      Report.reporter_user_id)))).label("phone_verified"),
        )
        .outerjoin(User, User.id == Report.reporter_user_id)
        .where(*live)
        .group_by(Report.target_id)
        .order_by(severity.desc(), oldest.asc(), Report.target_id.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    heads = hold.heads(db, "LISTING", [r.target_id for r in rows])
    items = [
        QueueItem(
            target_type="LISTING",
            target_id=r.target_id,
            listing_id=r.target_id,
            live_reports=r.live_reports,
            max_severity=_RANK_SEVERITY[int(r.severity)],
            oldest_report_at=freshness.to_utc(r.oldest),
            newest_report_at=freshness.to_utc(r.newest),
            distinct_reporters=r.reporters,
            phone_verified_reporters=r.phone_verified,
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
    audit(
        db,
        actor=moderator.id,
        action="moderation.target_viewed",
        entity_type="classified_offer",
        entity_id=listing_id,
        data={"target_type": "LISTING", "report_ids": [r.report.id for r in reports]},
    )
    return TargetReview(
        offer=offer,
        is_public=freshness.is_public(offer, now),
        head=hold.head(db, "LISTING", listing_id),
        reports=reports,
        moved_to_review=moved,
    )
