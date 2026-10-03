"""Measurement facts in the outbox (GROWTH-001; 06 Phase 1A: server-side outcome
events via the outbox).

Only facts the operational tables overwrite or never record get an event —
what can be rebuilt exactly from the tables (a conversation's start, its
messages, contact reveals, a publication's start) does not
(docs/growth/EVENTS-v1.md):

    ListingStatusChanged       every write of a listing's status: when a public
                               episode ends is otherwise lost
    ViewingRequested           the booking mode at request time (it is mutable)
    ViewingResponded           confirmed / declined by the provider
    ViewingCancelled           who cancelled — requester, provider or Homies
    ViewingOutcomeRecorded     COMPLETED / NO_SHOW (the strongest outcome proxy)
    ConversationStageChanged   the provider's lead stage (overwritten in place)

Rules (as for ModerationDecisionRecorded, Phase A §12): identifiers, closed
codes and database instants only — never a body, a note, an address, a price,
a coordinate or a contact; unrouted (not in `events.ROUTING`, so nobody is
notified); written in the transaction that makes the change, so a rolled-back
change leaves no fact; payloads only gain optional keys — a breaking change
gets a new event name, so there is no version key inside the payload.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.modules.events import service as events
from app.modules.properties import freshness

LISTING_STATUS_CHANGED = "ListingStatusChanged"
VIEWING_REQUESTED = "ViewingRequested"
VIEWING_RESPONDED = "ViewingResponded"
VIEWING_CANCELLED = "ViewingCancelled"
VIEWING_OUTCOME_RECORDED = "ViewingOutcomeRecorded"
CONVERSATION_STAGE_CHANGED = "ConversationStageChanged"

FACTS = (LISTING_STATUS_CHANGED, VIEWING_REQUESTED, VIEWING_RESPONDED, VIEWING_CANCELLED,
         VIEWING_OUTCOME_RECORDED, CONVERSATION_STAGE_CHANGED)

# Why a listing's status changed — the closed set.
STATUS_REASONS = ("PUBLISHED", "RECONFIRMED", "OWNER_PAUSE", "MODERATION_HOLD",
                  "AUTHORITY_LOST", "SPACE_ARCHIVED", "STALE_SWEEP")
CANCELLED_BY = ("REQUESTER", "PROVIDER", "HOMIES")

# Each event's payload, exactly (a test pins them, with a forbidden-key list).
PAYLOAD_KEYS = {
    LISTING_STATUS_CHANGED: ("listing_id", "property_id", "from_status", "to_status",
                             "reason_code", "public_generation", "changed_at"),
    VIEWING_REQUESTED: ("viewing_id", "listing_id", "booking_mode", "initial_status",
                        "starts_at", "requested_at"),
    VIEWING_RESPONDED: ("viewing_id", "listing_id", "to_status", "responded_at"),
    VIEWING_CANCELLED: ("viewing_id", "listing_id", "prior_status", "cancelled_by",
                        "moderation_decision_id", "cancelled_at"),
    VIEWING_OUTCOME_RECORDED: ("viewing_id", "listing_id", "outcome", "starts_at",
                               "recorded_at"),
    CONVERSATION_STAGE_CHANGED: ("conversation_id", "listing_id", "from_stage", "to_stage",
                                 "changed_at"),
}


def _now(db: Session) -> str:
    return freshness.canonical_instant(freshness.db_now(db))


def _emit(db: Session, event_type: str, correlation_id: str, payload: dict,
          dedup_key: str) -> None:
    assert tuple(payload) == PAYLOAD_KEYS[event_type], event_type
    if not events.emit(db, event_type, correlation_id, payload, dedup_key[:96]):
        raise RuntimeError(f"{event_type} emitted twice ({dedup_key})")


def listing_status_changed(db: Session, *, listing_id: str, property_id: str,
                           from_status: str, to_status: str, reason_code: str,
                           public_generation: int) -> None:
    assert reason_code in STATUS_REASONS, reason_code
    if from_status == to_status:
        return
    _emit(db, LISTING_STATUS_CHANGED, listing_id, {
        "listing_id": listing_id, "property_id": property_id, "from_status": from_status,
        "to_status": to_status, "reason_code": reason_code,
        "public_generation": public_generation, "changed_at": _now(db),
    }, f"{LISTING_STATUS_CHANGED}:{listing_id}:{uuid4()}")


def viewing_requested(db: Session, viewing, booking_mode: str) -> None:
    _emit(db, VIEWING_REQUESTED, viewing.id, {
        "viewing_id": viewing.id, "listing_id": viewing.listing_id,
        "booking_mode": booking_mode, "initial_status": viewing.status,
        "starts_at": freshness.canonical_instant(viewing.starts_at),
        "requested_at": _now(db),
    }, f"{VIEWING_REQUESTED}:{viewing.id}")


def viewing_responded(db: Session, viewing) -> None:
    _emit(db, VIEWING_RESPONDED, viewing.id, {
        "viewing_id": viewing.id, "listing_id": viewing.listing_id,
        "to_status": viewing.status, "responded_at": _now(db),
    }, f"{VIEWING_RESPONDED}:{viewing.id}")


def viewing_cancelled(db: Session, *, viewing_id: str, listing_id: str, prior_status: str,
                      cancelled_by: str, moderation_decision_id: str | None = None,
                      cancelled_at: str | None = None) -> None:
    assert cancelled_by in CANCELLED_BY, cancelled_by
    _emit(db, VIEWING_CANCELLED, viewing_id, {
        "viewing_id": viewing_id, "listing_id": listing_id, "prior_status": prior_status,
        "cancelled_by": cancelled_by, "moderation_decision_id": moderation_decision_id,
        "cancelled_at": cancelled_at or _now(db),
    }, f"{VIEWING_CANCELLED}:{viewing_id}")


def viewing_outcome_recorded(db: Session, viewing) -> None:
    _emit(db, VIEWING_OUTCOME_RECORDED, viewing.id, {
        "viewing_id": viewing.id, "listing_id": viewing.listing_id,
        "outcome": viewing.status,
        "starts_at": freshness.canonical_instant(viewing.starts_at),
        "recorded_at": _now(db),
    }, f"{VIEWING_OUTCOME_RECORDED}:{viewing.id}")


def conversation_stage_changed(db: Session, conv, from_stage: str | None) -> None:
    if from_stage == conv.provider_stage:
        return
    _emit(db, CONVERSATION_STAGE_CHANGED, conv.id, {
        "conversation_id": conv.id, "listing_id": conv.listing_id,
        "from_stage": from_stage, "to_stage": conv.provider_stage, "changed_at": _now(db),
    }, f"{CONVERSATION_STAGE_CHANGED}:{conv.id}:{conv.version}")
