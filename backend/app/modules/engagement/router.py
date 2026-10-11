"""Conversations about a listing (Domain Schema v1 §53–§55, §113–§114).

The renter's way to reach an owner who chose "messages only", and everyone's
way to talk before a viewing. Who may read and write:

* the tenant who started the conversation;
* on the provider side, whoever holds MANAGE_MESSAGES over the listing's
  property right now — decided by `properties.authority`, so access follows
  the right, not a list copied when the conversation began.

Anyone else gets 404: a conversation's existence is nobody else's business.

Closure (TASK-015 S4b). A conversation Homies closed — on its own
(FEATURE_RESTRICTED) or with its listing (close_engagement) — takes no
message once the closure has committed. `send_message` locks the
conversation row first (the first lock of every moderation path on it) and
reads its status under that lock. Starting a conversation reads the listing
row FOR SHARE first, so it waits for a listing decision in progress and then
sees its outcome; continuing an existing thread locks that thread too. After
FEATURE_RESTRICTED the requester cannot open a new thread on the listing for
the same public generation (founder G-14).

A tenant may start a bounded number of new conversations per rolling 24 hours.
Messaging is the channel for people who have not verified a phone, so it is
also the cheapest way to blast every owner on the board with the same scam;
the cap makes that expensive without getting in the way of someone looking
for a flat.

Idempotent sends (BP-10, D-108). Both send routes take a `client_message_id`
— a UUID v4 the client mints for one logical send and repeats on every retry
of it. (sender, client_message_id) is the identity of that send, shared by
the two routes, and the database holds at most one message for it
(`uq_messages_sender_client_message`). A retry that finds the send already
committed is answered from the current rows with the same 201 and writes
nothing; the same key with another body or target is 409
IDEMPOTENCY_KEY_REUSED. Each send first takes a transaction-scoped advisory
lock on its (sender, key) — before any row lock and before any refusal — and
then looks the key up in a separate statement: while a send of that key is in
flight, a retry waits for its outcome instead of being refused (the thread
closed meanwhile, the quota filled) for a message that was in fact delivered.
Access comes first on append: a key never opens a conversation the caller no
longer sees.
"""

import hashlib
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    UUID4,
    BaseModel,
    Field,
    WithJsonSchema,
    field_validator,
    model_validator,
)
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.business_metrics import record_message_idempotency
from app.core.config import settings
from app.core.db import get_db, lock_row
from app.core.security import get_current_user
from app.modules.engagement import access
from app.modules.engagement.models import (
    PROVIDER_STAGES,
    Conversation,
    ConversationParticipant,
    Message,
)
from app.modules.events import facts
from app.modules.identity.models import (
    OrganizationLegalParty,
    OrganizationMembership,
    PersonLegalParty,
    User,
)
from app.modules.properties import authority, freshness
from app.modules.properties.models import ClassifiedOffer, PropertyAuthority
from app.modules.trust import hold

CONVERSATION_CLOSED = "CONVERSATION_CLOSED"
RECONTACT_BLOCKED = "RECONTACT_BLOCKED"
# Stable refusal codes (FE-003 BP-1): the client reads the "CODE: " prefix of
# `detail`, never the English text after it.
OWN_LISTING = "OWN_LISTING"
CONVERSATION_QUOTA = "CONVERSATION_QUOTA"
IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"

# The advisory-lock class of message sends (BP-10): "BP10" as a signed int4.
# Two-int advisory keys are a key space of their own; the repository's only
# other advisory lock is the migration job's single bigint key
# (app/scripts/migrate.py), which can never collide with it.
SEND_LOCK_CLASS = 0x42503130
_SEND_LOCK_DOMAIN = b"bp10.message-send\0"

log = logging.getLogger("homies.engagement")

router = APIRouter(tags=["conversations"])

CONVERSATION_WINDOW = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- schemas ------------------------------------------------------------------


ClientMessageId = Annotated[UUID4, WithJsonSchema({
    "type": "string", "format": "uuid",
    "description": "UUID v4 the client mints when the user sends one message, and repeats "
                   "unchanged on every retry of that same send; a new message gets a new id. "
                   "Never shown to the other side of the conversation.",
})]


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    client_message_id: ClientMessageId

    @field_validator("body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a message cannot be blank")
        return v.strip()


class MessageOut(BaseModel):
    """A message as a conversation participant sees it. A message removed by
    Homies moderation (TASK-015 S4a) has `body: null` and `moderation_state:
    REMOVED` — the client renders "Removed by Homies" from its own strings. The
    stored body is kept as evidence for moderators only: this model drops it
    whenever the row is redacted, however the model is built, so no route can
    hand it to a participant by accident."""

    id: str
    sender_user_id: str | None
    sender_organization_id: str | None
    message_type: str
    body: str | None
    moderation_state: Literal["NONE", "REMOVED"] = "NONE"
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _redacted_has_no_body(cls, data):
        if isinstance(data, dict):
            redacted = data.get("redacted_at") is not None or data.get(
                "moderation_state") == "REMOVED"
            if redacted:
                return {**data, "body": None, "moderation_state": "REMOVED"}
            return data
        if getattr(data, "redacted_at", None) is not None:
            return {
                "id": data.id, "sender_user_id": data.sender_user_id,
                "sender_organization_id": data.sender_organization_id,
                "message_type": data.message_type, "body": None,
                "moderation_state": "REMOVED", "created_at": data.created_at,
            }
        return data


class ConversationOut(BaseModel):
    """What both sides see."""

    id: str
    listing_id: str | None
    status: str
    created_at: datetime
    last_message_at: datetime | None
    my_side: Literal["tenant", "provider"]


class ProviderConversationOut(ConversationOut):
    """Plus the provider's own lead-handling fields, which the tenant never
    sees: how an agency ranks a lead is not the lead's business."""

    requester_user_id: str
    provider_stage: str | None
    assigned_to_user_id: str | None


class ConversationDetail(BaseModel):
    conversation: ConversationOut | ProviderConversationOut
    messages: list[MessageOut]


class AssignIn(BaseModel):
    user_id: str


class StageIn(BaseModel):
    provider_stage: str

    @field_validator("provider_stage")
    @classmethod
    def known(cls, v: str) -> str:
        if v not in PROVIDER_STAGES:
            raise ValueError(f"provider_stage must be one of {', '.join(PROVIDER_STAGES)}")
        return v


# --- access -------------------------------------------------------------------


def _property_of(db: Session, conv: Conversation) -> str | None:
    return access.property_of(db, conv)


def _side(db: Session, user: User, conv: Conversation) -> str | None:
    return access.side(db, user.id, conv)


def _load(db: Session, user: User, conversation_id: str) -> tuple[Conversation, str]:
    conv = db.get(Conversation, conversation_id)
    side = _side(db, user, conv) if conv else None
    if conv is None or side is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv, side


def _out(conv: Conversation, side: str):
    base = {
        "id": conv.id, "listing_id": conv.listing_id, "status": conv.status,
        "created_at": conv.created_at, "last_message_at": conv.last_message_at,
        "my_side": side,
    }
    if side == "provider":
        return ProviderConversationOut.model_validate({
            **base, "requester_user_id": conv.requester_user_id,
            "provider_stage": conv.provider_stage, "assigned_to_user_id": conv.assigned_to_user_id,
        })
    return ConversationOut.model_validate(base)


def _provider_participant(db: Session, property_id: str) -> ConversationParticipant | None:
    """Who the conversation is recorded as being with, on the provider side:
    the organisation, when one holds the publishing right; else the person."""
    holder = db.scalar(
        select(PropertyAuthority.holder_legal_party_id)
        .where(PropertyAuthority.property_id == property_id,
               PropertyAuthority.status == "ACTIVE")
        .order_by(PropertyAuthority.verification_state.desc(), PropertyAuthority.created_at)
        .limit(1)
    )
    if holder is None:
        return None
    org = db.scalar(select(OrganizationLegalParty.organization_id).where(
        OrganizationLegalParty.legal_party_id == holder))
    if org is not None:
        return ConversationParticipant(participant_type="ORGANIZATION", organization_id=org)
    person = db.scalar(select(PersonLegalParty.linked_user_id).where(
        PersonLegalParty.legal_party_id == holder))
    if person is not None:
        return ConversationParticipant(participant_type="USER", user_id=person)
    return None


def _sender_organization(db: Session, user: User, conv: Conversation) -> str | None:
    """When a member answers for their organisation, the message says so —
    and still names the member (§55)."""
    org_ids = db.scalars(
        select(ConversationParticipant.organization_id).where(
            ConversationParticipant.conversation_id == conv.id,
            ConversationParticipant.organization_id.is_not(None),
        )
    )
    for org_id in org_ids:
        member = db.scalar(select(OrganizationMembership.id).where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == "ACTIVE",
        ))
        if member is not None:
            return org_id
    return None


def _post(db: Session, user: User, conv: Conversation, side: str, body: str,
          client_message_id: str) -> Message:
    """The one writer of USER messages, and so of the send key (BP-10)."""
    message = Message(
        conversation_id=conv.id, sender_user_id=user.id, message_type="USER", body=body,
        client_message_id=client_message_id,
        sender_organization_id=_sender_organization(db, user, conv) if side == "provider"
        else None,
    )
    db.add(message)
    conv.last_message_at = _now()
    if side == "provider" and conv.provider_stage == "NEW":
        conv.provider_stage = "REPLIED"
    db.flush()
    return message


# --- idempotent sends (BP-10, D-108) ------------------------------------------


def send_lock_key(user_id: str, client_message_id: str) -> int:
    """The int4 half of the advisory key for (sender, client_message_id):
    signed, so it always fits PostgreSQL `integer`. Only the sender and the
    key go in — never the route or target, which would split the one
    namespace both send routes share."""
    digest = hashlib.sha256(_SEND_LOCK_DOMAIN + user_id.encode() + b"\0"
                            + client_message_id.encode()).digest()
    return int.from_bytes(digest[:4], "big", signed=True)


def _serialise_send(db: Session, user_id: str, client_message_id: str) -> None:
    """Wait for any other send of this key to finish, then hold it until this
    transaction ends.

    Taken before any row lock — so a request waiting here holds none, and the
    lock adds no edge to the listing → users → conversation → message order —
    and before any refusal, so a retry never refuses a send that commits while
    it waits. Transaction-scoped and never inside a savepoint: rolling a
    savepoint back would release it. The lookup that follows is a separate
    statement, so under READ COMMITTED it sees whatever the other send
    committed. SQLite (the unit suite) has no advisory locks and one
    connection; the PostgreSQL suite proves this."""
    if db.in_nested_transaction():
        raise RuntimeError("the message-send lock belongs to the top-level transaction")
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(text("SELECT pg_advisory_xact_lock(CAST(:cls AS integer), CAST(:obj AS integer))"),
               {"cls": SEND_LOCK_CLASS, "obj": send_lock_key(user_id, client_message_id)})


def _keyed(db: Session, user_id: str, client_message_id: str) -> Message | None:
    """The committed message of this sender's send, read fresh, unlocked."""
    return db.scalar(
        select(Message).where(Message.sender_user_id == user_id,
                              Message.client_message_id == client_message_id)
        .execution_options(populate_existing=True))


def _reused() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT,
                         f"{IDEMPOTENCY_KEY_REUSED}: this client_message_id already sent "
                         "a different message")


def _replay_start(db: Session, user_id: str, offer_id: str, body: str, message: Message,
                  outcome: str) -> "ConversationDetail":
    """The same start again: the thread as it is now, and that message. Only
    the requester can replay a start, so its view is always the tenant's."""
    conv = db.get(Conversation, message.conversation_id, populate_existing=True)
    if (conv is None or conv.listing_id != offer_id or conv.requester_user_id != user_id
            or message.body != body):
        record_message_idempotency("start", "conflict")
        raise _reused()
    record_message_idempotency("start", outcome)
    return ConversationDetail(conversation=_out(conv, "tenant"),
                              messages=[MessageOut.model_validate(message)])


def _replay_append(conversation_id: str, body: str, message: Message, outcome: str) -> Message:
    if message.conversation_id != conversation_id or message.body != body:
        record_message_idempotency("append", "conflict")
        raise _reused()
    record_message_idempotency("append", outcome)
    return message


def _integrity_failure(exc: IntegrityError) -> tuple[str, str]:
    """SQLSTATE and constraint name — all that may leave an integrity error.
    Its message and DETAIL carry the failing row: the body, the key."""
    orig = exc.orig
    diag = getattr(orig, "diag", None)
    return (str(getattr(orig, "sqlstate", None) or "unknown"),
            str(getattr(diag, "constraint_name", None) or "unknown"))


def _winner_of_lost_race(db: Session, route: str, user_id: str, client_message_id: str,
                         failure: tuple[str, str]) -> Message:
    """After a send's write failed and its transaction was rolled back: the
    committed message of the same key, if that is what it collided with. If
    there is none, the failure was not about the key — a sanitized error, so
    neither the original exception nor its DETAIL reaches a log."""
    message = _keyed(db, user_id, client_message_id)
    if message is None:
        log.warning("message send integrity failure: route=%s sqlstate=%s constraint=%s",
                    route, *failure)
        raise RuntimeError(f"integrity: {failure[1]}")
    return message


# --- routes -------------------------------------------------------------------


def _active_thread(db: Session, listing_id: str, requester_id: str) -> Conversation | None:
    """The requester's ACTIVE thread on the listing, locked and re-read — a
    moderator may have closed it while we looked (S4b)."""
    conv = db.scalar(select(Conversation).where(
        Conversation.listing_id == listing_id, Conversation.requester_user_id == requester_id,
        Conversation.status == "ACTIVE",
    ))
    if conv is None:
        return None
    locked = _lock(db, conv.id)
    return locked if locked is not None and locked.status == "ACTIVE" else None


def _lock(db: Session, conversation_id: str) -> Conversation | None:
    return db.scalar(select(Conversation).where(Conversation.id == conversation_id)
                     .with_for_update().execution_options(populate_existing=True))


def _closed() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT,
                         f"{CONVERSATION_CLOSED}: this conversation is closed")


def _refuse_recontact(db: Session, offer: ClassifiedOffer, user: User) -> None:
    if hold.recontact_blocked(db, offer.id, user.id, offer.public_generation):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{RECONTACT_BLOCKED}: Homies closed your conversation about this "
                            "listing; a new one is not possible for this publication")


def _quota_retry_after(db: Session, requester_id: str, started: int, now: datetime) -> int:
    """Seconds until a new conversation fits under the rolling 24 h quota: the
    start that must age out is the (started − quota + 1)-th oldest in the
    window, counted on the same clock and rows as the quota itself."""
    rows = list(db.scalars(
        select(Conversation.created_at).where(
            Conversation.requester_user_id == requester_id,
            Conversation.created_at >= now - CONVERSATION_WINDOW,
        ).order_by(Conversation.created_at)
    ))
    index = min(max(started - settings.conversation_daily_quota, 0), len(rows) - 1)
    if index < 0:
        return 1
    oldest = rows[index]
    oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=timezone.utc)
    return max(1, math.ceil((oldest + CONVERSATION_WINDOW - now).total_seconds()))


_RETRY_AFTER = {"Retry-After": {"description": "Seconds until a retry can succeed.",
                                "schema": {"type": "integer"}}}
_SEND_SAFE_TO_RETRY = (
    "Database unavailable (PR-003); the outcome of the send may be unknown. Retrying the "
    "same logical send with the same `client_message_id` is safe: it is answered with the "
    "message if it was written, and writes it once if it was not.")
_REUSED = ("`IDEMPOTENCY_KEY_REUSED`: this `client_message_id` already sent a message with "
           "another body or to another conversation or listing (the earlier message is "
           "unchanged and its own retry still succeeds)")
_INVALID_SEND = ("Invalid body (1–4000 characters, not blank) or `client_message_id` "
                 "(missing, or not a UUID v4).")
# The validation error body is the standard one; naming the 422 here must not
# drop it from the contract (FastAPI replaces the default entry).
_INVALID_SEND_RESPONSE = {
    "description": _INVALID_SEND,
    "content": {"application/json": {
        "schema": {"$ref": "#/components/schemas/HTTPValidationError"}}},
}


@router.post(
    "/classifieds/{offer_id}/conversations", response_model=ConversationDetail,
    status_code=201,
    responses={
        201: {"description": "The message was sent — by this request, or by an earlier one "
                             "with the same `client_message_id` (then nothing new is written "
                             "and the thread is shown as it is now)."},
        404: {"description": "No public listing with this id."},
        409: {"description": "Stable codes: `OWN_LISTING` (the caller manages this listing); "
                             "`RECONTACT_BLOCKED` (G-14: Homies closed the caller's conversation "
                             f"for this publication); {_REUSED}."},
        422: _INVALID_SEND_RESPONSE,
        429: {"description": "`CONVERSATION_QUOTA`: the daily limit of new conversations is "
                             "reached (existing threads continue), or the rate limit (no code). "
                             "Both send `Retry-After`.",
              "headers": _RETRY_AFTER},
        503: {"description": _SEND_SAFE_TO_RETRY, "headers": _RETRY_AFTER},
    },
)
def start_conversation(
    offer_id: str,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # BP-10: an earlier send of this key is answered before anything that
    # would refuse a new one — the listing withdrawn, a G-14 block or the
    # quota since then do not undo a message that was sent.
    user_id, key = user.id, str(body.client_message_id)
    _serialise_send(db, user_id, key)
    earlier = _keyed(db, user_id, key)
    if earlier is not None:
        return _replay_start(db, user_id, offer_id, body.body, earlier, "replay")
    try:
        return _start(db, offer_id, body.body, key, user)
    except IntegrityError as exc:
        failure = _integrity_failure(exc)
    # The whole transaction, never a savepoint: a new thread, its participants
    # and its audit row go with the message that lost.
    db.rollback()
    winner = _winner_of_lost_race(db, "start", user_id, key, failure)
    return _replay_start(db, user_id, offer_id, body.body, winner, "race_recovered")


def _start(db: Session, offer_id: str, body: str, key: str, user: User) -> "ConversationDetail":
    # The listing row FOR SHARE first (S4b): a listing decision holds it FOR
    # UPDATE while it closes engagement, so a start waits for that decision
    # and then sees its outcome — never a thread opened behind a closure.
    offer = lock_row(db, ClassifiedOffer, offer_id, shared=True)
    # The one public-visibility rule (freshness.py): a stale listing takes no
    # new conversation, exactly like an unpublished one.
    if offer is None or not freshness.is_public(offer, freshness.db_now(db)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    if authority.can_act(db, user.id, offer.property_id, "MANAGE_MESSAGES", verified=False):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{OWN_LISTING}: this is your own listing")

    # Serialise this sender's conversation starts (TASK-001 F-09): looking for
    # an existing thread, counting today's new ones and creating one are one
    # decision. The sender's users row is the coordination point — FOR NO KEY
    # UPDATE, so FK checks on the inserts below are not blocked by it. The
    # partial unique index on active (listing, requester) is the backstop.
    db.execute(select(User.id).where(User.id == user.id).with_for_update(key_share=True))

    # One conversation per tenant per listing: writing again continues it.
    conv = _active_thread(db, offer.id, user.id)
    if conv is None:
        _refuse_recontact(db, offer, user)
        now = _now()
        started = db.scalar(
            select(func.count()).select_from(Conversation).where(
                Conversation.requester_user_id == user.id,
                Conversation.created_at >= now - CONVERSATION_WINDOW,
            )
        ) or 0
        if started >= settings.conversation_daily_quota:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"{CONVERSATION_QUOTA}: daily limit of new conversations reached. "
                "Existing ones stay open.",
                headers={"Retry-After": str(_quota_retry_after(db, user.id, started, now))},
            )
        conv = Conversation(listing_id=offer.id, requester_user_id=user.id)
        try:
            with db.begin_nested():
                db.add(conv)
                db.flush()
        except IntegrityError:
            # Another start for the same thread won despite the lock (a write
            # that did not come through here). Continue the thread it made.
            existing = _active_thread(db, offer.id, user.id)
            if existing is None:
                _refuse_recontact(db, offer, user)
                raise
            conv = existing
            message = _post(db, user, conv, "tenant", body, key)
            db.commit()
            return ConversationDetail(conversation=_out(conv, "tenant"),
                                      messages=[MessageOut.model_validate(message)])
        db.add(ConversationParticipant(conversation_id=conv.id, participant_type="USER",
                                       user_id=user.id))
        provider = _provider_participant(db, offer.property_id)
        if provider is not None and provider.user_id != user.id:
            provider.conversation_id = conv.id
            db.add(provider)
        audit(db, actor=user.id, action="conversation.started", entity_type="conversation",
              entity_id=conv.id)

    message = _post(db, user, conv, "tenant", body, key)
    db.commit()
    return ConversationDetail(conversation=_out(conv, "tenant"),
                              messages=[MessageOut.model_validate(message)])


@router.get("/conversations", response_model=list[ConversationOut | ProviderConversationOut])
def inbox(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Conversations you started, and those about listings you answer for."""
    mine = authority.authorized_property_ids(user.id, "MANAGE_MESSAGES")
    rows = db.scalars(
        select(Conversation)
        .outerjoin(ClassifiedOffer, ClassifiedOffer.id == Conversation.listing_id)
        .where(or_(Conversation.requester_user_id == user.id,
                   ClassifiedOffer.property_id.in_(mine)))
        .order_by(Conversation.last_message_at.desc())
    )
    return [_out(c, "tenant" if c.requester_user_id == user.id else "provider") for c in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def read_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv, side = _load(db, user, conversation_id)
    messages = db.scalars(
        select(Message).where(Message.conversation_id == conv.id)
        .order_by(Message.created_at, Message.id)
    )
    return ConversationDetail(conversation=_out(conv, side),
                              messages=[MessageOut.model_validate(m) for m in messages])


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201,
    responses={
        201: {"description": "The message was sent — by this request, or by an earlier one "
                             "with the same `client_message_id` (then nothing new is written "
                             "and the message is shown as it is now)."},
        404: {"description": "No conversation this account is a side of (also for a retry "
                             "of a send, once the account is no longer a side)."},
        409: {"description": "Stable codes: `CONVERSATION_CLOSED` (Homies closed it); "
                             f"{_REUSED}."},
        422: _INVALID_SEND_RESPONSE,
        429: {"description": "Rate limit (no code); see `Retry-After`.",
              "headers": _RETRY_AFTER},
        503: {"description": _SEND_SAFE_TO_RETRY, "headers": _RETRY_AFTER},
    },
)
def send_message(
    conversation_id: str,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Access first (D-108): a key replays only inside a conversation the
    # caller is a side of now — it is never a capability.
    conv, side = _load(db, user, conversation_id)
    user_id, conv_id, key = user.id, conv.id, str(body.client_message_id)
    _serialise_send(db, user_id, key)
    earlier = _keyed(db, user_id, key)
    if earlier is not None:
        return _replay_append(conv_id, body.body, earlier, "replay")
    try:
        # The conversation row first, then its status under the lock: a
        # closure that committed before this point is seen; one that comes
        # later waits for this message (S4b, invariant I-1).
        locked = _lock(db, conv_id)
        if locked is None or locked.status != "ACTIVE":
            raise _closed()
        message = _post(db, user, locked, side, body.body, key)
        db.commit()
        return message
    except IntegrityError as exc:
        failure = _integrity_failure(exc)
    db.rollback()
    winner = _winner_of_lost_race(db, "append", user_id, key, failure)
    return _replay_append(conv_id, body.body, winner, "race_recovered")


@router.post("/conversations/{conversation_id}/assign",
             response_model=ProviderConversationOut)
def assign(
    conversation_id: str,
    body: AssignIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hand a lead to a colleague. The colleague must themselves be able to
    answer for the listing — assigning to someone who cannot read it would
    hide the lead, not route it."""
    conv, side = _load(db, user, conversation_id)
    if side != "provider":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    prop = _property_of(db, conv)
    if prop is None or not authority.can_act(db, body.user_id, prop, "MANAGE_MESSAGES",
                                             verified=False):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "That person cannot answer for this listing")
    # Locked and re-read, so the version bump never overwrites a closure's.
    conv = _lock(db, conv.id) or conv
    conv.assigned_to_user_id = body.user_id
    conv.version += 1
    db.commit()
    return _out(conv, "provider")


@router.post("/conversations/{conversation_id}/stage", response_model=ProviderConversationOut)
def set_stage(
    conversation_id: str,
    body: StageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv, side = _load(db, user, conversation_id)
    if side != "provider":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    conv = _lock(db, conv.id) or conv
    before = conv.provider_stage
    conv.provider_stage = body.provider_stage
    conv.version += 1
    facts.conversation_stage_changed(db, conv, before)
    db.commit()
    return _out(conv, "provider")

