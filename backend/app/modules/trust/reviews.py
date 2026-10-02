"""Review requests — the owner's reconsideration seam (TASK-015 Slice 5;
04a §23; Phase A §7.3).

Not an appeal system and not a case: a manager of a held listing asks for the
hold to be looked at again. The request changes nothing about the listing.
The answer is the next immutable moderation decision on the listing — keep
the hold (a new hold decision) or release it (NO_ACTION) — written through
`decisions.apply_listing_decision`, which marks the request ANSWERED in the
same transaction. There is no answer endpoint and no second state machine.

Rules (the server decides; the client names only the listing):

* the caller may act on the listing's property with PUBLISH_LISTING through
  the authority chain — else the same 404 as a missing listing;
* the listing's current decision head is a hold that is `appeal_eligible` —
  else 409;
* at most one OPEN request per hold decision (partial UNIQUE) — else 409;
* at most 3 requests per **continuous hold episode**: the run of hold
  decisions that ends at the current head, walking `supersedes_decision_id`
  back while each decision is a hold. A hold superseding a hold (the answer
  "keep the hold") continues the episode; a release ends it; a later hold
  starts a new one. Derived from the chain — nothing stored.

Serialisation is the decision path's: property coordination lock → listing
row lock → head → count and insert. Every decision on the listing and every
request takes the same two locks first, so the head, the episode and the
open request read here cannot change before commit.

The note is plain text (the report normaliser), ≤ 500 characters, for the
moderator only: never in an audit entry, event, notice, metric or log.

Retry after an unknown COMMIT (PR-003): if the first attempt committed, the
retry is refused 409 (already open) — a 409 does not mean the first attempt
failed. That is the accepted Phase A semantics; no general Idempotency-Key.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.audit import audit
from app.modules.identity.models import User
from app.modules.properties import authority, coordination
from app.modules.properties.models import ClassifiedOffer
from app.modules.trust import hold
from app.modules.trust.models import HOLD_ACTIONS, ModerationDecision, ModerationReviewRequest
from app.modules.trust.reports import normalize_text

NOTE_MAX = 500
EPISODE_CAP = 3


class ReviewRefused(Exception):
    """Nothing was written."""


class ListingNotFound(ReviewRefused):
    """Missing, or not the caller's to manage — indistinguishable."""


class NotHeld(ReviewRefused):
    pass


class AlreadyOpen(ReviewRefused):
    pass


class CapReached(ReviewRefused):
    pass


class InvalidReview(ReviewRefused):
    pass


@dataclass(frozen=True)
class Requested:
    request: ModerationReviewRequest
    listing_id: str


def episode_decision_ids(db: Session, head: ModerationDecision) -> list[str]:
    """The current continuous hold episode: the head (a hold) and every hold
    it supersedes without a non-hold in between. One recursive statement."""
    md = ModerationDecision
    episode = (select(md.id, md.supersedes_decision_id)
               .where(md.id == head.id, md.action.in_(HOLD_ACTIONS))
               .cte("hold_episode", recursive=True))
    earlier = aliased(md)
    episode = episode.union_all(
        select(earlier.id, earlier.supersedes_decision_id)
        .join(episode, earlier.id == episode.c.supersedes_decision_id)
        .where(earlier.action.in_(HOLD_ACTIONS))
    )
    return list(db.scalars(select(episode.c.id)))


def open_request(db: Session, decision_id: str) -> ModerationReviewRequest | None:
    return db.scalar(select(ModerationReviewRequest).where(
        ModerationReviewRequest.decision_id == decision_id,
        ModerationReviewRequest.status == "OPEN"))


def request_review(db: Session, *, requester: User, listing_id: str,
                   note: str | None) -> Requested:
    """File a review request against the listing's current hold. The caller
    commits."""
    clean = normalize_text(note)
    if clean is not None and len(clean) > NOTE_MAX:
        raise InvalidReview(f"The note is limited to {NOTE_MAX} characters")

    offer = db.get(ClassifiedOffer, listing_id)
    # Authorised before any lock is taken: a stranger never queues on the
    # property's coordination lock, and learns nothing about the listing.
    if offer is None or not authority.can_act(db, requester.id, offer.property_id,
                                              "PUBLISH_LISTING", verified=False):
        raise ListingNotFound("Offer not found")
    if coordination.lock_property(db, offer.property_id) is None:
        raise ListingNotFound("Offer not found")
    if db.execute(select(ClassifiedOffer.id).where(ClassifiedOffer.id == listing_id)
                  .with_for_update()).one_or_none() is None:
        raise ListingNotFound("Offer not found")
    # Again under the lock: an authority revoked while we waited (revoke takes
    # the same property lock) no longer counts.
    if not authority.can_act(db, requester.id, offer.property_id, "PUBLISH_LISTING",
                             verified=False):
        raise ListingNotFound("Offer not found")

    current = hold.head(db, "LISTING", listing_id)
    if current is None or current.action not in HOLD_ACTIONS:
        raise NotHeld("This listing is not on hold by Homies moderation")
    if not current.appeal_eligible:
        raise NotHeld("This hold cannot be reviewed")
    if open_request(db, current.id) is not None:
        raise AlreadyOpen("A review of this hold has already been requested")
    episode = episode_decision_ids(db, current)
    used = db.scalar(select(func.count()).select_from(ModerationReviewRequest).where(
        ModerationReviewRequest.decision_id.in_(episode))) or 0
    if used >= EPISODE_CAP:
        raise CapReached(f"At most {EPISODE_CAP} reviews can be requested for one hold")

    request = ModerationReviewRequest(decision_id=current.id, requested_by_user_id=requester.id,
                                      note=clean, status="OPEN")
    try:
        with db.begin_nested():
            db.add(request)
            db.flush()
    except IntegrityError:
        # The partial UNIQUE (one OPEN per decision) decides if a path ever
        # skipped the locks above; the error carries the note, so it is never
        # re-raised into a traceback or a log.
        raise AlreadyOpen("A review of this hold has already been requested") from None
    db.refresh(request, attribute_names=["created_at"])
    audit(
        db,
        actor=requester.id,
        action="moderation.review_requested",
        entity_type="classified_offer",
        entity_id=listing_id,
        data={"decision_id": current.id, "review_request_id": request.id},
    )
    return Requested(request, listing_id)


def answer_open_request(db: Session, superseded_id: str | None,
                        answering_decision_id: str) -> str | None:
    """Called by the decision service, under the listing row lock, in the
    decision's transaction: the OPEN request on the head the new decision
    supersedes is answered by it. Returns the request id, if any."""
    if superseded_id is None:
        return None
    request = db.scalar(select(ModerationReviewRequest).where(
        ModerationReviewRequest.decision_id == superseded_id,
        ModerationReviewRequest.status == "OPEN").with_for_update())
    if request is None:
        return None
    request.status = "ANSWERED"
    request.answered_by_decision_id = answering_decision_id
    db.flush()
    return request.id


def review_states(db: Session, heads: dict[str, ModerationDecision]) -> dict[str, str]:
    """For the owner's page: per listing whose head is a hold, OPEN when that
    hold has an OPEN request, ANSWERED when that hold is the answer to a
    request, else NONE. One statement for the page."""
    held = {lid: d.id for lid, d in heads.items() if d.action in HOLD_ACTIONS}
    if not held:
        return {}
    ids = list(held.values())
    rows = db.execute(select(ModerationReviewRequest.decision_id,
                             ModerationReviewRequest.status,
                             ModerationReviewRequest.answered_by_decision_id)
                      .where((ModerationReviewRequest.decision_id.in_(ids))
                             | (ModerationReviewRequest.answered_by_decision_id.in_(ids)))).all()
    open_on = {r.decision_id for r in rows if r.status == "OPEN"}
    answered_by = {r.answered_by_decision_id for r in rows if r.status == "ANSWERED"}
    return {lid: "OPEN" if did in open_on else "ANSWERED" if did in answered_by else "NONE"
            for lid, did in held.items()}
