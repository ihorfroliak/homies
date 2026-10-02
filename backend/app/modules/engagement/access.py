"""Who may read a conversation — the one rule, for the conversation routes and
for moderation (TASK-015 S4a: who may report a message, and which moderator
is a participant).

* the tenant who started it (`requester_user_id`);
* on the provider side, whoever holds MANAGE_MESSAGES over the listing's
  property right now — decided by `properties.authority`, never by the
  participant rows copied when the conversation began.
"""

from sqlalchemy.orm import Session

from app.modules.engagement.models import Conversation
from app.modules.properties import authority
from app.modules.properties.models import ClassifiedOffer


def property_of(db: Session, conv: Conversation) -> str | None:
    if conv.listing_id is None:
        return None
    offer = db.get(ClassifiedOffer, conv.listing_id)
    return offer.property_id if offer else None


def side(db: Session, user_id: str, conv: Conversation) -> str | None:
    """'tenant', 'provider', or None (no access)."""
    if conv.requester_user_id == user_id:
        return "tenant"
    prop = property_of(db, conv)
    if prop and authority.can_act(db, user_id, prop, "MANAGE_MESSAGES", verified=False):
        return "provider"
    return None
