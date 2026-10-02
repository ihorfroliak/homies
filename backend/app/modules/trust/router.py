"""Reports and moderation over HTTP (TASK-015 Slices 2 + 3). LISTING only;
MESSAGE targets arrive with Slice 4 as an additive widening.

    POST /v1/reports                                   file (or find) a report
    GET  /v1/me/reports                                one's own reports, coarse status
    GET  /v1/admin/moderation/queue                    targets with live reports
    GET  /v1/admin/moderation/targets/LISTING/{id}     review a target (sets IN_REVIEW)
    POST /v1/admin/moderation/decisions                decide (S1 decision service)

Every rule lives in the services (`reports`, `moderation`, `decisions`); this
module maps their refusals to HTTP. Database failures are not caught here:
PR-003's handlers answer them (503), never a misleading 4xx.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import can_moderate, get_current_user
from app.modules.properties import freshness
from app.modules.properties.router import public_listing
from app.modules.trust import decisions, moderation, reports
from app.modules.trust.models import HOLD_ACTIONS, ModerationDecision, Report

Id = Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9-]+$")]
ListingReason = Literal["SCAM", "FAKE", "MISLEADING_PRICE", "DISCRIMINATION", "SAFETY",
                        "STOLEN_MEDIA", "DUPLICATE", "OTHER"]
Category = Literal["FAKE", "DUPLICATE", "SCAM", "DISCRIMINATION", "ILLEGAL_CONTENT",
                   "STOLEN_MEDIA", "HARASSMENT", "SAFETY", "MISLEADING_PRICE", "IMPERSONATION",
                   "SPAM", "OTHER"]
ReasonCode = Literal["FAKE", "DUPLICATE", "SCAM", "DISCRIMINATION", "ILLEGAL_CONTENT",
                     "STOLEN_MEDIA", "HARASSMENT", "SAFETY", "MISLEADING_PRICE",
                     "IMPERSONATION", "SPAM", "OTHER", "NOT_A_VIOLATION",
                     "REINSTATED_REMEDIED", "REINSTATED_DECISION_ERROR"]
ListingAction = Literal["NO_ACTION", "CONTENT_EDIT_REQUIRED", "VISIBILITY_LIMITED"]

router = APIRouter(tags=["reports"])


def require_moderator(user=Depends(get_current_user)):
    """The moderator seam (`can_moderate`: today the database role `admin`)."""
    if not can_moderate(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
    return user


moderation_router = APIRouter(prefix="/admin/moderation", tags=["moderation"],
                              dependencies=[Depends(require_moderator)])


# --- reporter -------------------------------------------------------------------
class ReportIn(BaseModel):
    """What a reporter says. Everything else — who, severity, status, the
    listing's snapshot and generation — is the server's."""

    model_config = ConfigDict(extra="forbid")

    target_type: Literal["LISTING"]
    target_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9-]+$")
    reason: ListingReason
    # Plain text, up to 1000 characters once control characters are removed;
    # at least 20 for OTHER.
    text: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    """The reporter's view: never the decision, the action, other reports or
    who reviewed it (L13)."""

    id: str
    target_type: str
    target_id: str
    reason: str
    status: Literal["received", "reviewed"]
    created_at: datetime
    created: bool = False


class ReportPage(BaseModel):
    items: list[ReportOut]
    total: int
    limit: int
    offset: int


def _report_out(report: Report, created: bool = False) -> ReportOut:
    return ReportOut(id=report.id, target_type=report.target_type, target_id=report.target_id,
                     reason=report.category,
                     status=reports.REPORTER_STATUS[report.status],  # type: ignore[arg-type]
                     created_at=freshness.to_utc(report.created_at), created=created)


def _public_dict(offer, now):
    return public_listing(offer, now).model_dump(mode="json")


@router.post(
    "/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": ReportOut,
              "description": "Already reported: the reporter's live report on this target "
                             "(`created: false`) — also the answer to a retry"},
        403: {"description": "The account has no verified email or phone"},
        404: {"description": "No such listing, or not one this account may report"},
        409: {"description": "The account manages this listing"},
        422: {"description": "Invalid reason or text"},
        429: {"description": "Report quota (10 new per 24 h, 20 waiting) or rate limit; "
                             "see Retry-After"},
        503: {"description": "Database unavailable (PR-003); the retry is safe"},
    },
)
def file_report(body: ReportIn, response: Response, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Report a listing to Homies moderation. A report changes nothing about
    the listing; a moderator reviews it."""
    try:
        filed = reports.file_listing_report(db, reporter=user, listing_id=body.target_id,
                                            category=body.reason, text=body.text,
                                            public_projection=_public_dict)
    except reports.NotVerified as exc:
        db.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except reports.NotReportable as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except reports.OwnListing as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except reports.InvalidReport as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except reports.QuotaExceeded as exc:
        db.rollback()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc),
                            headers={"Retry-After": str(exc.retry_after)}) from None
    if filed.created:
        db.commit()
    else:
        db.rollback()
        response.status_code = status.HTTP_200_OK
    return _report_out(filed.report, created=filed.created)


@router.get("/me/reports", response_model=ReportPage)
def my_reports(limit: int = Query(default=50, ge=1, le=100),
               offset: int = Query(default=0, ge=0, le=10_000),
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The account's own reports, newest first, with a coarse status only."""
    mine = Report.reporter_user_id == user.id
    total = db.scalar(select(func.count()).select_from(Report).where(mine)) or 0
    rows = db.scalars(select(Report).where(mine)
                      .order_by(Report.created_at.desc(), Report.id.desc())
                      .limit(limit).offset(offset))
    return ReportPage(items=[_report_out(r) for r in rows], total=total,
                      limit=limit, offset=offset)


# --- moderator ------------------------------------------------------------------
class HeadOut(BaseModel):
    id: str
    action: str
    reason_code: str
    supersedes_decision_id: str | None
    decided_by_user_id: str
    effective_from: datetime


def _head_out(head: ModerationDecision | None) -> HeadOut | None:
    if head is None:
        return None
    return HeadOut(id=head.id, action=head.action, reason_code=head.reason_code,
                   supersedes_decision_id=head.supersedes_decision_id,
                   decided_by_user_id=head.decided_by_user_id,
                   effective_from=freshness.to_utc(head.effective_from))


class QueueItemOut(BaseModel):
    """A target and its live workload. No report text, reporter contact,
    address or snapshot."""

    target_type: str
    target_id: str
    listing_id: str
    live_reports: int
    max_severity: str
    oldest_report_at: datetime
    newest_report_at: datetime
    distinct_reporters: int
    phone_verified_reporters: int
    head_decision_id: str | None
    head_action: str | None
    held: bool


class QueuePage(BaseModel):
    items: list[QueueItemOut]
    total: int
    limit: int
    offset: int


@moderation_router.get("/queue", response_model=QueuePage,
                       responses={403: {"description": "Not a moderator"}})
def moderation_queue(limit: int = Query(default=50, ge=1, le=100),
                     offset: int = Query(default=0, ge=0, le=10_000),
                     db: Session = Depends(get_db)):
    """Targets with live reports: HIGH severity first, then the oldest
    outstanding report. Ordering only — nothing here acts on a target."""
    items, total = moderation.queue(db, limit=limit, offset=offset)
    return QueuePage(
        items=[QueueItemOut(
            target_type=i.target_type, target_id=i.target_id, listing_id=i.listing_id,
            live_reports=i.live_reports, max_severity=i.max_severity,
            oldest_report_at=i.oldest_report_at, newest_report_at=i.newest_report_at,
            distinct_reporters=i.distinct_reporters,
            phone_verified_reporters=i.phone_verified_reporters,
            head_decision_id=i.head.id if i.head else None,
            head_action=i.head.action if i.head else None, held=i.held,
        ) for i in items],
        total=total, limit=limit, offset=offset,
    )


class ModeratorReportOut(BaseModel):
    """Moderator-only: who reported (internal id, verification state — not
    email or phone), what they said, and the listing as they saw it."""

    id: str
    reporter_user_id: str | None
    reporter_email_verified: bool
    reporter_phone_verified: bool
    category: str
    severity: str
    status: str
    description: str | None
    created_at: datetime
    first_reviewed_at: datetime | None
    listing_public_generation_at_report: int | None
    snapshot: dict | None


class ListingContextOut(BaseModel):
    id: str
    property_id: str
    status: str
    is_public: bool
    public_generation: int
    current: dict


class TargetOut(BaseModel):
    target_type: str
    target_id: str
    listing: ListingContextOut
    head: HeadOut | None
    held: bool
    reports: list[ModeratorReportOut]


@moderation_router.get(
    "/targets/LISTING/{listing_id}",
    response_model=TargetOut,
    responses={403: {"description": "Not a moderator"},
               404: {"description": "No such listing"}},
)
def review_listing(listing_id: Id, moderator=Depends(require_moderator),
                   db: Session = Depends(get_db)):
    """Review a listing: its live reports move to IN_REVIEW (first review time
    set once). The access is audited (ids only)."""
    review = moderation.review_listing(db, moderator=moderator, listing_id=listing_id)
    if review is None:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    offer = review.offer
    now = freshness.db_now(db)
    current = reports.snapshot(offer, _public_dict(offer, now))
    out = TargetOut(
        target_type="LISTING",
        target_id=offer.id,
        listing=ListingContextOut(id=offer.id, property_id=offer.property_id,
                                  status=offer.status, is_public=review.is_public,
                                  public_generation=offer.public_generation, current=current),
        head=_head_out(review.head),
        held=review.head is not None and review.head.action in HOLD_ACTIONS,
        reports=[ModeratorReportOut(
            id=r.report.id, reporter_user_id=r.report.reporter_user_id,
            reporter_email_verified=r.reporter_email_verified,
            reporter_phone_verified=r.reporter_phone_verified,
            category=r.report.category, severity=r.report.severity, status=r.report.status,
            description=r.report.description,
            created_at=freshness.to_utc(r.report.created_at),
            first_reviewed_at=(freshness.to_utc(r.report.first_reviewed_at)
                               if r.report.first_reviewed_at else None),
            listing_public_generation_at_report=r.report.listing_public_generation_at_report,
            snapshot=r.report.snapshot,
        ) for r in review.reports],
    )
    db.commit()
    return out


class DecisionIn(BaseModel):
    """A decision against the target's current head. `expected_head_decision_id`
    is required (null when the target has no decision yet): a decision made
    against an older head is refused, never re-aimed."""

    model_config = ConfigDict(extra="forbid")

    target_type: Literal["LISTING"]
    target_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9-]+$")
    action: ListingAction
    reason_code: ReasonCode
    expected_head_decision_id: str | None = Field(max_length=36)
    explanation: str | None = Field(default=None, max_length=2000)
    reclassified_category: Category | None = None


class DecisionOut(BaseModel):
    decision_id: str
    target_type: str
    target_id: str
    action: str
    reason_code: str
    supersedes_decision_id: str | None
    effective_from: datetime
    listing_status: str
    held: bool
    resolved_reports: int
    notified_managers: int


@moderation_router.post(
    "/decisions",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Not a moderator, or a conflict of interest (manages the "
                             "property, or has a live report on the target)"},
        404: {"description": "No such listing"},
        409: {"description": "STALE_HEAD: the target's current decision is not the expected "
                             "one — refresh and decide again (never retried for you)"},
        422: {"description": "Invalid action or reason for the target's state"},
        503: {"description": "Database unavailable (PR-003). A retry with the same expected "
                             "head is safe: if the first attempt committed, it is refused "
                             "as STALE_HEAD"},
    },
)
def decide(body: DecisionIn, moderator=Depends(require_moderator),
           db: Session = Depends(get_db)):
    """Record a moderation decision on a listing and apply it (hold, release
    or dismissal), resolving every live report on it and notifying the
    listing's managers of a hold or a release — in one transaction."""
    try:
        applied = decisions.apply_listing_decision(
            db, actor=moderator, listing_id=body.target_id, action=body.action,
            reason_code=body.reason_code,
            expected_head_decision_id=body.expected_head_decision_id,
            explanation=reports.normalize_text(body.explanation),
            reclassified_category=body.reclassified_category,
        )
    except decisions.StaleHead as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"STALE_HEAD: the current decision is {exc.current_head_id or 'none'}; "
            "refresh and decide again",
        ) from None
    except decisions.ConflictOfInterest as exc:
        db.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"CONFLICT_OF_INTEREST: {exc}") from None
    except decisions.TargetNotFound:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found") from None
    except decisions.NotAModerator:
        db.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role") from None
    except decisions.InvalidDecision as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"INVALID_DECISION: {exc}") from None
    db.commit()
    assert applied.effective_from is not None
    return DecisionOut(
        decision_id=applied.decision_id, target_type="LISTING", target_id=body.target_id,
        action=applied.action, reason_code=body.reason_code,
        supersedes_decision_id=applied.supersedes_decision_id,
        effective_from=freshness.to_utc(applied.effective_from),
        listing_status=applied.listing_status_after, held=applied.held,
        resolved_reports=len(applied.resolved_report_ids),
        notified_managers=len(applied.notified_user_ids),
    )
