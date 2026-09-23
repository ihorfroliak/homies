"""Who may act on a property (Domain Schema v1 §30–§32).

One place decides it, so no route grows its own idea of "owner". Every write on
a property or its listings asks `require(...)` with the scope it needs.

The chains Schema v1 names:

* personal:      User → linked PERSON LegalParty → PropertyAuthority
* organisation:  User → membership → Organization → its LegalParty → authority
* mandate:       User → verified RepresentationMandate → LegalParty → authority

Only the personal chain exists yet. Organisations and mandates arrive with the
agency cycle; they extend `_chains`, not the routes.
"""

from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.audit import audit
from app.modules.identity.models import LegalParty, PersonLegalParty, User
from app.modules.identity.parties import has_legal_name, personal_party
from app.modules.properties.models import (
    OWNER_PHASE1_SCOPES,
    ClassifiedOffer,
    Property,
    PropertyAuthority,
    PropertyAuthorityScope,
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _in_force(today: date):
    """ACTIVE and inside its dates. A revoked or expired authority authorises
    nothing new, whatever its verification state (Schema v1 §81.14)."""
    return and_(
        PropertyAuthority.status == "ACTIVE",
        PropertyAuthority.effective_from <= today,
        or_(
            PropertyAuthority.effective_until.is_(None),
            PropertyAuthority.effective_until >= today,
        ),
    )


def _chains(user_id: str, scope: str, *, verified: bool) -> Select:
    """Property ids this account may act on with `scope`."""
    query = (
        select(PropertyAuthority.property_id)
        .join(LegalParty, LegalParty.id == PropertyAuthority.holder_legal_party_id)
        .join(PersonLegalParty, PersonLegalParty.legal_party_id == LegalParty.id)
        .join(
            PropertyAuthorityScope,
            and_(
                PropertyAuthorityScope.property_authority_id == PropertyAuthority.id,
                PropertyAuthorityScope.scope == scope,
            ),
        )
        .where(
            PersonLegalParty.linked_user_id == user_id,
            LegalParty.status == "ACTIVE",
            _in_force(_today()),
        )
    )
    if verified:
        query = query.where(PropertyAuthority.verification_state == "VERIFIED")
    return query


def authorized_property_ids(user_id: str, scope: str, *, verified: bool = False) -> Select:
    return _chains(user_id, scope, verified=verified)


def can_act(db: Session, user_id: str, property_id: str, scope: str, *, verified: bool) -> bool:
    query = _chains(user_id, scope, verified=verified).where(
        PropertyAuthority.property_id == property_id
    )
    return db.scalar(query.limit(1)) is not None


def require(
    db: Session, user: User, property_id: str, scope: str, *, verified: bool = False
) -> Property:
    """The property, or the right refusal.

    404 when the caller holds nothing on it — "not yours" and "does not exist"
    must be indistinguishable, or this becomes an oracle for which ids are
    real. 403 only when they do hold an authority that is not yet verified:
    they already know the property exists, and they need to know why the
    button did nothing.
    """
    prop = db.get(Property, property_id)
    if prop is None or not can_act(db, user.id, property_id, scope, verified=False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found")
    if verified and not can_act(db, user.id, property_id, scope, verified=True):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Ownership of this property has not been verified yet",
        )
    return prop


def grant_owner(db: Session, user: User, property_id: str) -> PropertyAuthority:
    """What registering your own flat gives you: an ACTIVE, UNVERIFIED claim.

    Enough to prepare every part of the listing. Not enough to publish it.
    """
    party = personal_party(db, user)
    authority = PropertyAuthority(
        property_id=property_id,
        holder_legal_party_id=party.id,
        authority_type="OWNER",
        status="ACTIVE",
        verification_state="UNVERIFIED",
        effective_from=_today(),
        created_by_user_id=user.id,
    )
    db.add(authority)
    db.flush()
    db.add_all(
        PropertyAuthorityScope(property_authority_id=authority.id, scope=scope)
        for scope in OWNER_PHASE1_SCOPES
    )
    db.flush()
    return authority


def scopes_of(db: Session, authority_id: str) -> list[str]:
    return sorted(
        db.scalars(
            select(PropertyAuthorityScope.scope).where(
                PropertyAuthorityScope.property_authority_id == authority_id
            )
        )
    )


def authorities_of(db: Session, property_id: str) -> list[PropertyAuthority]:
    return list(
        db.scalars(
            select(PropertyAuthority)
            .where(PropertyAuthority.property_id == property_id)
            .order_by(PropertyAuthority.created_at)
        )
    )


class AuthorityStateError(Exception):
    """A transition the authority's current state does not allow."""


def verify(db: Session, authority: PropertyAuthority, actor_id: str) -> None:
    """Mark a claim checked. Only a claim in force can be verified, and only
    one whose holder has given a legal name — ownership is checked against a
    land-register entry, and that entry names a legal person."""
    if authority.status != "ACTIVE":
        raise AuthorityStateError(f"cannot verify an authority that is {authority.status}")
    if not has_legal_name(db, authority.holder_legal_party_id):
        raise AuthorityStateError(
            "the holder has not provided a legal first and last name"
        )
    authority.verification_state = "VERIFIED"
    authority.version += 1
    audit(
        db,
        actor=actor_id,
        action="property_authority.verified",
        entity_type="property_authority",
        entity_id=authority.id,
    )


def revoke(db: Session, authority: PropertyAuthority, actor_id: str) -> list[str]:
    """Withdraw a right, and take down what it alone was keeping up.

    Revoking stops new publication by definition. It must also stop the
    listings already live on that right: a fake owner whose authority has been
    revoked must not keep their listing on the board until they choose to
    remove it. Listings stay up only if some other verified authority can
    still publish that property. Returns the ids of the offers paused.
    """
    if authority.status == "REVOKED":
        return []
    authority.status = "REVOKED"
    authority.revoked_at = datetime.now(timezone.utc)
    authority.version += 1
    db.flush()

    still_backed = db.scalar(
        select(PropertyAuthority.id)
        .join(
            PropertyAuthorityScope,
            and_(
                PropertyAuthorityScope.property_authority_id == PropertyAuthority.id,
                PropertyAuthorityScope.scope == "PUBLISH_LISTING",
            ),
        )
        .where(
            PropertyAuthority.property_id == authority.property_id,
            PropertyAuthority.verification_state == "VERIFIED",
            _in_force(_today()),
        )
        .limit(1)
    )
    paused: list[str] = []
    if still_backed is None:
        for offer in db.scalars(
            select(ClassifiedOffer).where(
                ClassifiedOffer.property_id == authority.property_id,
                ClassifiedOffer.status == "active",
            )
        ):
            offer.status = "paused"
            paused.append(offer.id)

    audit(
        db,
        actor=actor_id,
        action="property_authority.revoked",
        entity_type="property_authority",
        entity_id=authority.id,
    )
    return paused
