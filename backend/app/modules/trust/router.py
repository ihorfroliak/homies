"""Reports and moderation over HTTP (TASK-015 Slices 2–5, 4a, 4b).

    POST /v1/reports                                   file (or find) a report
    GET  /v1/me/reports                                one's own reports, coarse status
    GET  /v1/admin/moderation/queue                    targets with live reports
    GET  /v1/admin/moderation/targets/LISTING/{id}     review a target (sets IN_REVIEW)
    GET  /v1/admin/moderation/targets/MESSAGE/{id}     message evidence (S4a, audited)
    GET  /v1/admin/moderation/targets/MEDIA/{id}       a photo's moderation state (S4b)
    GET  /v1/admin/moderation/media/{id}/content       the photo itself, for moderators (S4b)
    POST /v1/admin/moderation/decisions                decide: LISTING, MESSAGE,
                                                       CONVERSATION, MEDIA
    POST /v1/classifieds/{id}/moderation-review        a manager asks for a hold to be reviewed

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

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import can_moderate, get_current_user
from app.modules.media import storage
from app.modules.media.models import ListingMedia, MediaAsset
from app.modules.media.router import is_servable
from app.modules.properties import freshness
from app.modules.properties.router import public_listing
from app.modules.trust import decisions, hold, moderation, reports, reviews
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
MessageReason = Literal["HARASSMENT", "SCAM", "DISCRIMINATION", "SAFETY", "SPAM", "OTHER"]
# LISTING: NO_ACTION, CONTENT_EDIT_REQUIRED, VISIBILITY_LIMITED; MESSAGE (S4a)
# and MEDIA (S4b): NO_ACTION, CONTENT_REMOVED; CONVERSATION (S4b): NO_ACTION,
# FEATURE_RESTRICTED — the service refuses an action of another target type.
DecisionAction = Literal["NO_ACTION", "CONTENT_EDIT_REQUIRED", "VISIBILITY_LIMITED",
                         "CONTENT_REMOVED", "FEATURE_RESTRICTED"]

router = APIRouter(tags=["reports"])


def require_moderator(user=Depends(get_current_user)):
    """The moderator seam (`can_moderate`: today the database role `admin`)."""
    if not can_moderate(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
    return user


moderation_router = APIRouter(prefix="/admin/moderation", tags=["moderation"],
                              dependencies=[Depends(require_moderator)])


# --- reporter -------------------------------------------------------------------
class ListingReportIn(BaseModel):
    """What a reporter says about a listing. Everything else — who, severity,
    status, the listing's snapshot and generation — is the server's."""

    model_config = ConfigDict(extra="forbid")

    target_type: Literal["LISTING"]
    target_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9-]+$")
    reason: ListingReason
    # Plain text, up to 1000 characters once control characters are removed;
    # at least 20 for OTHER.
    text: str | None = Field(default=None, max_length=2000)


class MessageReportIn(BaseModel):
    """What a conversation participant says about another participant's
    message (Slice 4a). The conversation, listing, severity and status are
    the server's; no part of the conversation is copied."""

    model_config = ConfigDict(extra="forbid")

    target_type: Literal["MESSAGE"]
    target_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9-]+$")
    reason: MessageReason
    text: str | None = Field(default=None, max_length=2000)


ReportIn = Annotated[ListingReportIn | MessageReportIn, Field(discriminator="target_type")]


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
        403: {"description": "LISTING only: the account has no verified email or phone. "
                             "A MESSAGE report needs no verified contact (D-105)."},
        404: {"description": "No such listing or message, or not one this account may "
                             "report (MESSAGE: not a current side of its conversation) — "
                             "indistinguishable"},
        409: {"description": "LISTING: the account manages it. MESSAGE: a SYSTEM message, "
                             "or the account's own message"},
        422: {"description": "Invalid reason or text"},
        429: {"description": "Report quota (10 new per 24 h, 20 waiting) or rate limit; "
                             "see Retry-After"},
        503: {"description": "Database unavailable (PR-003); the retry is safe"},
    },
)
def file_report(body: ReportIn, response: Response, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Report a listing, or a message in one of your conversations, to Homies
    moderation. A report changes nothing about its target; a moderator
    reviews it."""
    try:
        if isinstance(body, MessageReportIn):
            filed = reports.file_message_report(db, reporter=user, message_id=body.target_id,
                                                category=body.reason, text=body.text)
        else:
            filed = reports.file_listing_report(db, reporter=user, listing_id=body.target_id,
                                                category=body.reason, text=body.text,
                                                public_projection=_public_dict)
    except reports.NotVerified as exc:
        db.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except reports.NotReportable as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except (reports.OwnListing, reports.UnreportableMessage) as exc:
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
    listing_id: str | None
    conversation_id: str | None = None   # MESSAGE targets: the conversation's id only
    live_reports: int
    # None when the target is here only for an open review request: no
    # severity is invented for it.
    max_severity: str | None
    oldest_report_at: datetime | None
    newest_report_at: datetime | None
    distinct_reporters: int
    phone_verified_reporters: int
    has_open_review_request: bool
    review_requested_at: datetime | None
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
    """Targets with moderator work — live reports or an owner's open review
    request: URGENT/HIGH reports first, then open review requests, then
    NORMAL reports; oldest work first within each. Ordering only — nothing
    here acts on a target."""
    items, total = moderation.queue(db, limit=limit, offset=offset)
    return QueuePage(
        items=[QueueItemOut(
            target_type=i.target_type, target_id=i.target_id, listing_id=i.listing_id,
            conversation_id=i.conversation_id, live_reports=i.live_reports, max_severity=i.max_severity,
            oldest_report_at=i.oldest_report_at, newest_report_at=i.newest_report_at,
            distinct_reporters=i.distinct_reporters,
            phone_verified_reporters=i.phone_verified_reporters,
            has_open_review_request=i.has_open_review_request,
            review_requested_at=i.review_requested_at,
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


class ModeratorReviewRequestOut(BaseModel):
    """Moderator-only: the manager's request to reconsider the current hold —
    internal requester id and their plain-text note; not their email/phone."""

    id: str
    decision_id: str
    requested_by_user_id: str
    note: str | None
    status: str
    created_at: datetime


class ListingMediaOut(BaseModel):
    """Every photo linked to the listing, whatever its state — the ids a
    moderator decides on (S4b). The photo itself: /media/{id}/content."""

    media_asset_id: str
    moderation_state: str
    is_cover: bool
    sort_order: int


class ListingContextOut(BaseModel):
    id: str
    property_id: str
    status: str
    is_public: bool
    public_generation: int
    current: dict
    media: list[ListingMediaOut] = []


class TargetOut(BaseModel):
    target_type: str
    target_id: str
    listing: ListingContextOut
    head: HeadOut | None
    held: bool
    reports: list[ModeratorReportOut]
    review_request: ModeratorReviewRequestOut | None = None


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
    media = [ListingMediaOut(media_asset_id=r.id, moderation_state=r.moderation_state,
                             is_cover=r.is_cover, sort_order=r.sort_order)
             for r in db.execute(
                 select(MediaAsset.id, MediaAsset.moderation_state, ListingMedia.is_cover,
                        ListingMedia.sort_order)
                 .join(ListingMedia, ListingMedia.media_asset_id == MediaAsset.id)
                 .where(ListingMedia.listing_id == offer.id)
                 .order_by(ListingMedia.is_cover.desc(), ListingMedia.sort_order,
                           MediaAsset.id))]
    out = TargetOut(
        target_type="LISTING",
        target_id=offer.id,
        listing=ListingContextOut(id=offer.id, property_id=offer.property_id,
                                  status=offer.status, is_public=review.is_public,
                                  public_generation=offer.public_generation, current=current,
                                  media=media),
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
        review_request=_review_request_out(review.review_request),
    )
    db.commit()
    return out


class EvidenceMessageOut(BaseModel):
    """One message of the bounded evidence window — moderator-only. `body` is
    the STORED body, including the original of a message removed for the
    participants; ids only for people (no email, phone or profile)."""

    id: str
    is_target: bool
    sender_user_id: str | None
    sender_organization_id: str | None
    message_type: str
    body: str | None
    created_at: datetime
    redacted_at: datetime | None
    redaction_reason_code: str | None


class ConversationContextOut(BaseModel):
    id: str
    listing_id: str | None
    status: str


class MessageTargetOut(BaseModel):
    target_type: Literal["MESSAGE"]
    target_id: str
    conversation: ConversationContextOut
    # The reported message and at most 2 messages before and 2 after it, from
    # the same conversation, oldest first.
    evidence: list[EvidenceMessageOut]
    head: HeadOut | None
    removed: bool
    reports: list[ModeratorReportOut]


@moderation_router.get(
    "/targets/MESSAGE/{message_id}",
    response_model=MessageTargetOut,
    responses={403: {"description": "Not a moderator"},
               404: {"description": "No such message"}},
)
def review_message(message_id: Id, moderator=Depends(require_moderator),
                   db: Session = Depends(get_db)):
    """Review a reported message with the narrowest private evidence: the
    message and up to two messages either side, from its own conversation.
    Its live reports move to IN_REVIEW (first review time set once). Every
    access is audited as `moderation.message_evidence_viewed` (ids only).
    Legal/privacy validation of moderator access to private messages (L9) is
    open: technically implemented, launch validation required."""
    review = moderation.review_message(db, moderator=moderator, message_id=message_id)
    if review is None:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    out = MessageTargetOut(
        target_type="MESSAGE",
        target_id=review.message.id,
        conversation=ConversationContextOut(id=review.conversation.id,
                                            listing_id=review.conversation.listing_id,
                                            status=review.conversation.status),
        evidence=[EvidenceMessageOut(
            id=m.id, is_target=m.id == review.message.id, sender_user_id=m.sender_user_id,
            sender_organization_id=m.sender_organization_id, message_type=m.message_type,
            body=m.body, created_at=freshness.to_utc(m.created_at),
            redacted_at=freshness.to_utc(m.redacted_at) if m.redacted_at else None,
            redaction_reason_code=m.redaction_reason_code,
        ) for m in review.evidence],
        head=_head_out(review.head),
        removed=review.message.redacted_at is not None,
        reports=[_moderator_report_out(r) for r in review.reports],
    )
    db.commit()
    return out


def _moderator_report_out(r) -> ModeratorReportOut:
    return ModeratorReportOut(
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
    )


def _review_request_out(request) -> ModeratorReviewRequestOut | None:
    if request is None:
        return None
    return ModeratorReviewRequestOut(
        id=request.id, decision_id=request.decision_id,
        requested_by_user_id=request.requested_by_user_id, note=request.note,
        status=request.status, created_at=freshness.to_utc(request.created_at))


class DecisionIn(BaseModel):
    """A decision against the target's current head. `expected_head_decision_id`
    is required (null when the target has no decision yet): a decision made
    against an older head is refused, never re-aimed.

    `close_engagement` (LISTING, VISIBILITY_LIMITED with SCAM, FAKE or SAFETY
    only): also close the listing's ACTIVE conversations and cancel its future
    viewings. `listing_id` (MEDIA only): the listing the photo was seen on."""

    model_config = ConfigDict(extra="forbid")

    target_type: Literal["LISTING", "MESSAGE", "CONVERSATION", "MEDIA"]
    target_id: str = Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9-]+$")
    action: DecisionAction
    reason_code: ReasonCode
    expected_head_decision_id: str | None = Field(max_length=36)
    explanation: str | None = Field(default=None, max_length=2000)
    reclassified_category: Category | None = None
    close_engagement: bool = False
    listing_id: str | None = Field(default=None, min_length=1, max_length=36,
                                   pattern=r"^[A-Za-z0-9-]+$")


class DecisionOut(BaseModel):
    decision_id: str
    target_type: str
    target_id: str
    action: str
    reason_code: str
    supersedes_decision_id: str | None
    effective_from: datetime
    listing_status: str | None   # LISTING targets
    held: bool
    resolved_reports: int
    notified_managers: int
    # The owner's review request this decision answered (Slice 5), if any.
    answered_review_request_id: str | None = None
    # Slice 4b effects.
    closed_conversations: int = 0
    cancelled_viewings: int = 0


@moderation_router.post(
    "/decisions",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Not a moderator, or a conflict of interest (manages the "
                             "property, has a live report on the target; MESSAGE: is a "
                             "current side of the conversation or wrote the message)"},
        404: {"description": "No such listing, message, conversation or photo"},
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
    """Record a moderation decision and apply it, in one transaction.
    LISTING: hold, release or dismissal — resolving its live reports,
    answering the owner's open review request on the hold it supersedes and
    notifying the listing's managers of a hold or a release. MESSAGE (S4a):
    CONTENT_REMOVED redacts the message for the participants (the stored body
    is kept as evidence) or NO_ACTION dismisses — resolving its live reports;
    nothing else about the conversation changes. CONVERSATION (S4b):
    FEATURE_RESTRICTED closes it with a neutral SYSTEM line (terminal). MEDIA
    (S4b): CONTENT_REMOVED restricts the photo without detaching it."""
    if body.close_engagement and body.target_type != "LISTING":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "INVALID_DECISION: close_engagement is for listings")
    if body.listing_id is not None and body.target_type != "MEDIA":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "INVALID_DECISION: listing_id is for photos")
    try:
        if body.target_type == "CONVERSATION":
            applied = decisions.apply_conversation_decision(
                db, actor=moderator, conversation_id=body.target_id, action=body.action,
                reason_code=body.reason_code,
                expected_head_decision_id=body.expected_head_decision_id,
                explanation=reports.normalize_text(body.explanation),
                reclassified_category=body.reclassified_category,
            )
        elif body.target_type == "MEDIA":
            applied = decisions.apply_media_decision(
                db, actor=moderator, media_asset_id=body.target_id, action=body.action,
                reason_code=body.reason_code,
                expected_head_decision_id=body.expected_head_decision_id,
                listing_id=body.listing_id,
                explanation=reports.normalize_text(body.explanation),
                reclassified_category=body.reclassified_category,
            )
        elif body.target_type == "MESSAGE":
            applied = decisions.apply_message_decision(
                db, actor=moderator, message_id=body.target_id, action=body.action,
                reason_code=body.reason_code,
                expected_head_decision_id=body.expected_head_decision_id,
                explanation=reports.normalize_text(body.explanation),
                reclassified_category=body.reclassified_category,
            )
        else:
            applied = decisions.apply_listing_decision(
                db, actor=moderator, listing_id=body.target_id, action=body.action,
                reason_code=body.reason_code,
                expected_head_decision_id=body.expected_head_decision_id,
                explanation=reports.normalize_text(body.explanation),
                reclassified_category=body.reclassified_category,
                close_engagement=body.close_engagement,
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
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"{_TARGET_NAMES[body.target_type]} not found") from None
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
        decision_id=applied.decision_id, target_type=body.target_type, target_id=body.target_id,
        action=applied.action, reason_code=body.reason_code,
        supersedes_decision_id=applied.supersedes_decision_id,
        effective_from=freshness.to_utc(applied.effective_from),
        listing_status=(applied.listing_status_after if body.target_type == "LISTING"
                        else None), held=applied.held,
        resolved_reports=len(applied.resolved_report_ids),
        notified_managers=len(applied.notified_user_ids),
        answered_review_request_id=applied.answered_review_request_id,
        closed_conversations=len(applied.closed_conversation_ids),
        cancelled_viewings=len(applied.cancelled_viewing_ids),
    )


_TARGET_NAMES = {"LISTING": "Listing", "MESSAGE": "Message", "CONVERSATION": "Conversation",
                 "MEDIA": "Media"}


# --- moderator: photos (Slice 4b) -------------------------------------------------


class MediaTargetOut(BaseModel):
    target_type: Literal["MEDIA"]
    target_id: str
    property_id: str
    moderation_state: str
    listing_ids: list[str]
    head: HeadOut | None
    content_available: bool


@moderation_router.get(
    "/targets/MEDIA/{media_asset_id}",
    response_model=MediaTargetOut,
    responses={403: {"description": "Not a moderator"}, 404: {"description": "No such photo"}},
)
def review_media(media_asset_id: Id, moderator=Depends(require_moderator),
                 db: Session = Depends(get_db)):
    """A photo's moderation state and the listings it is on (ids only)."""
    asset = db.get(MediaAsset, media_asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media not found")
    listing_ids = list(db.scalars(select(ListingMedia.listing_id)
                                  .where(ListingMedia.media_asset_id == asset.id)
                                  .order_by(ListingMedia.listing_id)))
    return MediaTargetOut(target_type="MEDIA", target_id=asset.id, property_id=asset.property_id,
                          moderation_state=asset.moderation_state, listing_ids=listing_ids,
                          head=_head_out(hold.head(db, "MEDIA", asset.id)),
                          content_available=is_servable(asset.file))


@moderation_router.get(
    "/media/{media_asset_id}/content",
    responses={200: {"content": {"image/*": {}}, "description": "The photo"},
               403: {"description": "Not a moderator"},
               404: {"description": "No such photo, or its bytes are not servable"}},
)
def media_content(media_asset_id: Id, moderator=Depends(require_moderator),
                  db: Session = Depends(get_db)):
    """The photo, whatever its moderation state, for moderators only — the
    public serve refuses anything not APPROVED, so a restricted or held
    listing's photos are otherwise invisible to the people reviewing them.
    Only sanitised, servable bytes (never a quarantined original); never
    cached; every access audited (ids only)."""
    asset = db.get(MediaAsset, media_asset_id)
    if asset is None or not is_servable(asset.file):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media not found")
    audit(db, actor=moderator.id, action="moderation.media_viewed", entity_type="media_asset",
          entity_id=asset.id, data={"media_asset_id": asset.id})
    db.commit()
    data = storage.storage().get(asset.file.storage_key)
    return Response(content=data, media_type=asset.file.mime_type or "application/octet-stream",
                    headers={"Cache-Control": "private, no-store",
                             "X-Content-Type-Options": "nosniff"})


# --- owner: review request (Slice 5) ---------------------------------------------
class ReviewRequestIn(BaseModel):
    """Only an optional note: the hold it concerns is the listing's current
    one, decided by the server."""

    model_config = ConfigDict(extra="forbid")

    # Plain text, up to 500 characters once control characters are removed.
    note: str | None = Field(default=None, max_length=1000)


class ReviewRequestOut(BaseModel):
    id: str
    listing_id: str
    status: Literal["OPEN"]
    created_at: datetime


@router.post(
    "/classifieds/{listing_id}/moderation-review",
    response_model=ReviewRequestOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "No such listing, or the caller may not manage it — "
                             "deliberately indistinguishable"},
        409: {"description": "Not on hold (or the hold cannot be reviewed); a review of "
                             "this hold is already open; or the 3 reviews of this hold "
                             "episode are used. After an unknown COMMIT, 'already open' "
                             "may mean the first attempt succeeded"},
        422: {"description": "Invalid note"},
        503: {"description": "Database unavailable (PR-003)"},
    },
)
def request_moderation_review(listing_id: Id, body: ReviewRequestIn,
                              user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Ask Homies moderation to reconsider the hold on a listing you manage.
    Nothing about the listing changes; a moderator answers with a new
    decision (keep the hold, or release it — then you republish)."""
    try:
        requested = reviews.request_review(db, requester=user, listing_id=listing_id,
                                           note=body.note)
    except reviews.ListingNotFound as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except (reviews.NotHeld, reviews.AlreadyOpen, reviews.CapReached) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except reviews.InvalidReview as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    db.commit()
    request = requested.request
    return ReviewRequestOut(id=request.id, listing_id=requested.listing_id, status="OPEN",
                            created_at=freshness.to_utc(request.created_at))
