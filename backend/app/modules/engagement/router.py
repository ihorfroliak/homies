"""Conversations about a listing (Domain Schema v1 §53–§55, §113–§114).

The renter's way to reach an owner who chose "messages only", and everyone's
way to talk before a viewing. Who may read and write:

* the tenant who started the conversation;
* on the provider side, whoever holds MANAGE_MESSAGES over the listing's
  property right now — decided by `properties.authority`, so access follows
  the right, not a list copied when the conversation began.

Anyone else gets 404: a conversation's existence is nobody else's business.

A tenant may start a bounded number of new conversations per rolling 24 hours.
Messaging is the channel for people who have not verified a phone, so it is
also the cheapest way to blast every owner on the board with the same scam;
the cap makes that expensive without getting in the way of someone looking
for a flat.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.modules.engagement.models import (
    PROVIDER_STAGES,
    Conversation,
    ConversationParticipant,
    Message,
)
from app.modules.identity.models import (
    OrganizationLegalParty,
    OrganizationMembership,
    PersonLegalParty,
    User,
)
from app.modules.properties import authority
from app.modules.properties.models import ClassifiedOffer, PropertyAuthority

router = APIRouter(tags=["conversations"])

CONVERSATION_WINDOW = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- schemas ------------------------------------------------------------------


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a message cannot be blank")
        return v.strip()


class MessageOut(BaseModel):
    id: str
    sender_user_id: str | None
    sender_organization_id: str | None
    message_type: str
    body: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


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
    if conv.listing_id is None:
        return None
    offer = db.get(ClassifiedOffer, conv.listing_id)
    return offer.property_id if offer else None


def _side(db: Session, user: User, conv: Conversation) -> str | None:
    if conv.requester_user_id == user.id:
        return "tenant"
    prop = _property_of(db, conv)
    if prop and authority.can_act(db, user.id, prop, "MANAGE_MESSAGES", verified=False):
        return "provider"
    return None


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


def _post(db: Session, user: User, conv: Conversation, side: str, body: str) -> Message:
    message = Message(
        conversation_id=conv.id, sender_user_id=user.id, message_type="USER", body=body,
        sender_organization_id=_sender_organization(db, user, conv) if side == "provider"
        else None,
    )
    db.add(message)
    conv.last_message_at = _now()
    if side == "provider" and conv.provider_stage == "NEW":
        conv.provider_stage = "REPLIED"
    db.flush()
    return message


# --- routes -------------------------------------------------------------------


def _active_thread(db: Session, listing_id: str, requester_id: str) -> Conversation | None:
    return db.scalar(select(Conversation).where(
        Conversation.listing_id == listing_id, Conversation.requester_user_id == requester_id,
        Conversation.status == "ACTIVE",
    ))


@router.post("/classifieds/{offer_id}/conversations", response_model=ConversationDetail,
             status_code=201)
def start_conversation(
    offer_id: str,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offer = db.get(ClassifiedOffer, offer_id)
    if offer is None or offer.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    if authority.can_act(db, user.id, offer.property_id, "MANAGE_MESSAGES", verified=False):
        raise HTTPException(status.HTTP_409_CONFLICT, "This is your own listing")

    # Serialise this sender's conversation starts (TASK-001 F-09): looking for
    # an existing thread, counting today's new ones and creating one are one
    # decision. The sender's users row is the coordination point — FOR NO KEY
    # UPDATE, so FK checks on the inserts below are not blocked by it. The
    # partial unique index on active (listing, requester) is the backstop.
    db.execute(select(User.id).where(User.id == user.id).with_for_update(key_share=True))

    # One conversation per tenant per listing: writing again continues it.
    conv = _active_thread(db, offer.id, user.id)
    if conv is None:
        started = db.scalar(
            select(func.count()).select_from(Conversation).where(
                Conversation.requester_user_id == user.id,
                Conversation.created_at >= _now() - CONVERSATION_WINDOW,
            )
        ) or 0
        if started >= settings.conversation_daily_quota:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Daily limit of new conversations reached. Existing ones stay open.",
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
                raise
            conv = existing
            message = _post(db, user, conv, "tenant", body.body)
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

    message = _post(db, user, conv, "tenant", body.body)
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


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut,
             status_code=201)
def send_message(
    conversation_id: str,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv, side = _load(db, user, conversation_id)
    if conv.status != "ACTIVE":
        raise HTTPException(status.HTTP_409_CONFLICT, "This conversation is closed")
    message = _post(db, user, conv, side, body.body)
    db.commit()
    return message


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
    conv.provider_stage = body.provider_stage
    conv.version += 1
    db.commit()
    return _out(conv, "provider")

