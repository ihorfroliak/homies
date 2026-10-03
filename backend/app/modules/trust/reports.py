"""Filing a report on a listing (TASK-015 Slice 2) or a message (Slice 4a;
Phase A §5; 04a §23).

A report is a signal for a moderator. It never changes its target (04
invariant 23): no status, no visibility, no ranking — whatever the count or
severity. Only a moderator decision (`decisions.apply_listing_decision`) acts.

Who may report a listing:

* a signed-in account with a verified email or phone (identity truth:
  `users.email_verified_at` / `phone_verified_at`);
* not about a listing on a property it may act on (the authority chain, never
  `owner_id`) — 409: the account knows the listing exists;
* only a listing that is public now, or one the account has dealt with: a
  conversation it started, a viewing it requested, or the owner's number it
  was given. Anything else is 404 — "hidden" and "does not exist" must be
  indistinguishable (no inventory oracle).

Exactly-once, without a general Idempotency-Key (Phase A §13, C): one live
report per (reporter, target) — the S1 partial UNIQUE. Asking again returns
the live report (`created = False`); that includes a retry after an unknown
COMMIT (PR-003) whose first attempt did commit. If it did not, the retry
creates it.

Quota (founder D-4): at most 10 new reports per rolling 24 hours of database
time and at most 20 live, per account. Exact under concurrency: the
reporter's own users row is the coordination point (FOR NO KEY UPDATE, as the
contact-reveal quota does), taken before anything is counted. Lock order: the
users row, then the reports insert; this path locks no property, listing or
report row, so it cannot close a cycle with a decision (property → listing →
reports). A duplicate is answered before the quota: it costs nothing.

Text is plain: control and format characters are removed (newlines kept),
nothing is interpreted. It is stored for the moderator only — never logged,
counted, put in an event, an audit entry, an owner surface or a notice.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

from prometheus_client import Counter
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.engagement import access as conversation_access
from app.modules.engagement.models import Conversation, Message, Viewing
from app.modules.identity.models import User
from app.modules.properties import authority, freshness
from app.modules.properties.models import AUTHORITY_SCOPES, ClassifiedOffer, ContactReveal
from app.modules.trust import committed
from app.modules.trust.models import LIVE_REPORT_STATUSES, REPORT_CATEGORIES, Report

# What a user may report a listing for (Phase A §5.3, founder D-3). The UI
# labels: scam · not real / lister not entitled · price or key details
# misleading · discriminatory · unsafe property · photos stolen / not this
# place · duplicate or spam · other. ILLEGAL_CONTENT, IMPERSONATION and SPAM
# are moderator-only on listings (reclassification).
LISTING_REASONS = (
    "SCAM", "FAKE", "MISLEADING_PRICE", "DISCRIMINATION", "SAFETY", "STOLEN_MEDIA",
    "DUPLICATE", "OTHER",
)
# Slice 4a (Phase A §5.3): what a conversation participant may report a
# message for.
MESSAGE_REASONS = ("HARASSMENT", "SCAM", "DISCRIMINATION", "SAFETY", "SPAM", "OTHER")
# Derived on the server, never accepted from the client. It orders the queue
# and does nothing else.
HIGH_SEVERITY = ("SAFETY", "SCAM", "FAKE", "DISCRIMINATION", "HARASSMENT")

TEXT_MAX = 1000
OTHER_TEXT_MIN = 20
DAILY_LIMIT = 10
LIVE_LIMIT = 20
WINDOW = timedelta(hours=24)

# What the reporter sees: coarse on purpose (L13 — no outcome disclosure).
REPORTER_STATUS = {"OPEN": "received", "IN_REVIEW": "reviewed", "RESOLVED": "reviewed",
                   "TRIAGED": "received", "CLOSED": "reviewed"}

# The listing's public face at report time (Phase A §5.4): an explicit
# allowlist over the public projection (`ClassifiedOut`), which itself never
# carries the street, unit, postcode, exact point, owner or contact.
SNAPSHOT_KEYS = (
    "title", "description", "status", "space_type", "city", "district", "place",
    "public_location", "rent_amount", "currency", "admin_fee", "utilities_amount",
    "utilities_included", "utilities_basis", "parking_fee", "deposit_amount", "other_costs",
    "monthly_total_estimate", "move_in_total",
)

REPORTS_CREATED = Counter(
    "homies_reports_created_total",
    "Committed new reports by target type and category",
    ["target_type", "category"],
)
for _category in REPORT_CATEGORIES:
    REPORTS_CREATED.labels(target_type="LISTING", category=_category)
    REPORTS_CREATED.labels(target_type="MESSAGE", category=_category)


class ReportRefused(Exception):
    """Nothing was written."""


class NotVerified(ReportRefused):
    pass


class NotReportable(ReportRefused):
    """Does not exist, or this account may not report it — indistinguishable."""


class OwnListing(ReportRefused):
    pass


class UnreportableMessage(ReportRefused):
    """A SYSTEM message, or the reporter's own message (409)."""


class InvalidReport(ReportRefused):
    pass


class QuotaExceeded(ReportRefused):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class Filed:
    report: Report
    created: bool


def severity(category: str) -> str:
    return "HIGH" if category in HIGH_SEVERITY else "NORMAL"


_SPACES = re.compile(r"\s+")


def normalize_text(raw: str | None) -> str | None:
    """Deterministic plain text: NFC; CR/CRLF → LF; tab → space; every other
    control (Cc) or format (Cf: zero-width, bidi overrides) character removed;
    outer whitespace stripped. Empty → None."""
    if raw is None:
        return None
    text = unicodedata.normalize("NFC", raw).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ")
    text = "".join(ch for ch in text
                   if ch == "\n" or unicodedata.category(ch) not in ("Cc", "Cf"))
    text = text.strip()
    return text or None


def meaningful_length(text: str | None) -> int:
    return len(_SPACES.sub(" ", text)) if text else 0


def reporter_verified(user: User) -> bool:
    return user.email_verified_at is not None or user.phone_verified_at is not None


def manages(db: Session, user_id: str, property_id: str) -> bool:
    return any(authority.can_act(db, user_id, property_id, scope, verified=False)
               for scope in AUTHORITY_SCOPES)


def interacted(db: Session, user_id: str, listing_id: str) -> bool:
    """A relationship the account had with the listing, from the domain
    records themselves (not analytics)."""
    return bool(db.scalar(select(or_(
        exists().where(Conversation.listing_id == listing_id,
                       Conversation.requester_user_id == user_id),
        exists().where(Viewing.listing_id == listing_id,
                       Viewing.requester_user_id == user_id),
        exists().where(ContactReveal.offer_id == listing_id,
                       ContactReveal.viewer_id == user_id),
    ))))


def snapshot(offer: ClassifiedOffer, public: dict) -> dict:
    """`public` is the listing's public projection (`ClassifiedOut`, JSON
    mode). Only allowlisted keys are kept; media is reduced to the cover's id."""
    out = {key: public.get(key) for key in SNAPSHOT_KEYS}
    cover = next((m for m in public.get("media") or [] if m.get("is_cover")), None)
    out["cover_media_id"] = cover["id"] if cover else None
    out["public_generation"] = offer.public_generation
    return out


def live_report(db: Session, reporter_id: str, target_type: str, target_id: str) -> Report | None:
    return db.scalar(select(Report).where(
        Report.reporter_user_id == reporter_id, Report.target_type == target_type,
        Report.target_id == target_id, Report.status.in_(LIVE_REPORT_STATUSES)))


def file_listing_report(db: Session, *, reporter: User, listing_id: str, category: str,
                        text: str | None, public_projection) -> Filed:
    """File (or find) the reporter's live report on a listing. The caller
    commits. `public_projection(offer, now)` returns the listing's public
    shape as a dict (the properties module owns it)."""
    clean = _validated(reporter, category, LISTING_REASONS, "a listing", text)

    offer = db.get(ClassifiedOffer, listing_id)
    if offer is None:
        raise NotReportable("Listing not found")
    if manages(db, reporter.id, offer.property_id):
        raise OwnListing("You cannot report a listing you manage")
    # Their own live report is theirs to see, even if the listing has since
    # gone out of public view (a retry after an unknown COMMIT, for one).
    existing = live_report(db, reporter.id, "LISTING", listing_id)
    if existing is not None:
        return Filed(existing, created=False)
    now = freshness.db_now(db)
    if not (freshness.is_public(offer, now) or interacted(db, reporter.id, listing_id)):
        raise NotReportable("Listing not found")

    def make() -> Report:
        return Report(
            reporter_user_id=reporter.id, target_type="LISTING", target_id=listing_id,
            listing_id=listing_id, category=category, description=clean,
            severity=severity(category), status="OPEN",
            snapshot=snapshot(offer, public_projection(offer, now)),
            listing_public_generation_at_report=offer.public_generation,
        )
    return _serialised_insert(db, reporter, "LISTING", listing_id, category, make)


def file_message_report(db: Session, *, reporter: User, message_id: str, category: str,
                        text: str | None) -> Filed:
    """File (or find) the reporter's live report on a message (Slice 4a).

    Only a current side of the message's conversation may report it — the
    conversation's own access rule (`engagement.access.side`: the tenant who
    started it, or whoever holds MANAGE_MESSAGES now), whatever the listing's
    publicity or the conversation's status. Everyone else, and a message that
    does not exist, get the same 404. A SYSTEM message, or one the reporter
    sent (`sender_user_id` — never inferred from a side or an organisation),
    is 409. Access is checked again after the reporter lock is granted: a
    right revoked before that point no longer counts.

    No body is copied: messages are not editable, so the message row itself is
    the evidence, read by moderators through the audited evidence path."""
    clean = _validated(reporter, category, MESSAGE_REASONS, "a message", text)

    message = db.get(Message, message_id)
    conv = db.get(Conversation, message.conversation_id) if message is not None else None
    if message is None or conv is None or conversation_access.side(db, reporter.id, conv) is None:
        raise NotReportable("Message not found")
    if message.message_type != "USER":
        raise UnreportableMessage("A system message cannot be reported")
    if message.sender_user_id == reporter.id:
        raise UnreportableMessage("You cannot report your own message")
    existing = live_report(db, reporter.id, "MESSAGE", message_id)
    if existing is not None:
        return Filed(existing, created=False)

    def recheck() -> None:
        # The listing FOR KEY SHARE before the insert's foreign-key checks, so
        # the listing is always taken before the conversation (S4b lock order,
        # whatever order the database fires the two checks in).
        if conv.listing_id is not None:
            db.execute(select(ClassifiedOffer.id).where(ClassifiedOffer.id == conv.listing_id)
                       .with_for_update(read=True, key_share=True))
        if conversation_access.side(db, reporter.id, conv) is None:
            raise NotReportable("Message not found")

    def make() -> Report:
        return Report(
            reporter_user_id=reporter.id, target_type="MESSAGE", target_id=message_id,
            listing_id=conv.listing_id, conversation_id=conv.id, category=category,
            description=clean, severity=severity(category), status="OPEN",
        )
    return _serialised_insert(db, reporter, "MESSAGE", message_id, category, make,
                              after_lock=recheck)


def _validated(reporter: User, category: str, allowed: tuple[str, ...], what: str,
               text: str | None) -> str | None:
    if not reporter_verified(reporter):
        raise NotVerified("Verify your email or phone before reporting")
    if category not in allowed:
        raise InvalidReport(f"This reason is not available for {what}")
    clean = normalize_text(text)
    if clean is not None and len(clean) > TEXT_MAX:
        raise InvalidReport(f"The description is limited to {TEXT_MAX} characters")
    if category == "OTHER" and meaningful_length(clean) < OTHER_TEXT_MIN:
        raise InvalidReport(f"Describe the problem in at least {OTHER_TEXT_MIN} characters")
    return clean


def _serialised_insert(db: Session, reporter: User, target_type: str, target_id: str,
                       category: str, make, after_lock=None) -> Filed:
    """Duplicate check, both quota counts and the insert under the reporter's
    lock — shared by every target, so LISTING and MESSAGE reports spend one
    account quota."""
    # Serialise this reporter's filing: duplicate check, both quota counts and
    # the insert see one consistent picture (FOR NO KEY UPDATE: the KEY SHARE
    # the reports FK check takes is not blocked by it).
    db.execute(select(User.id).where(User.id == reporter.id).with_for_update(key_share=True))
    if after_lock is not None:
        after_lock()

    existing = live_report(db, reporter.id, target_type, target_id)
    if existing is not None:
        return Filed(existing, created=False)

    # The window from the database clock as of now, after the lock was granted
    # (a wait for it must not stretch the window into the past).
    now = freshness.db_now(db)
    since = now - WINDOW
    recent = db.scalars(
        select(Report.created_at)
        .where(Report.reporter_user_id == reporter.id, Report.created_at >= since)
        .order_by(Report.created_at)
    ).all()
    if len(recent) >= DAILY_LIMIT:
        frees = freshness.to_utc(recent[0]) + WINDOW
        raise QuotaExceeded("Daily limit of reports reached",
                            max(1, int((frees - freshness.to_utc(now)).total_seconds())))
    live = db.scalar(select(func.count()).select_from(Report).where(
        Report.reporter_user_id == reporter.id, Report.status.in_(LIVE_REPORT_STATUSES))) or 0
    if live >= LIVE_LIMIT:
        raise QuotaExceeded("Too many of your reports are still waiting for review",
                            int(WINDOW.total_seconds()))

    report = make()
    try:
        with db.begin_nested():
            db.add(report)
            db.flush()
    except IntegrityError:
        # Unreachable while every filing takes the reporter lock above; if a
        # path ever skipped it, the partial UNIQUE still decides — and the
        # error, whose parameters carry the report text, is never re-raised
        # into a traceback or a log.
        existing = live_report(db, reporter.id, target_type, target_id)
        if existing is not None:
            return Filed(existing, created=False)
        raise RuntimeError("report insert refused by a database constraint") from None
    db.refresh(report, attribute_names=["created_at"])
    committed.count_on_commit(db, REPORTS_CREATED, target_type=target_type, category=category)
    return Filed(report, created=True)
