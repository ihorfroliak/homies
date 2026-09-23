"""Who may act on a property (Domain Schema v1 §30–§32).

One place decides it, so no route grows its own idea of "owner". Every write on
a property or its listings asks `require(...)` with the scope it needs.

The chains Schema v1 names (§32), all three live:

* personal:      User → linked PERSON LegalParty → PropertyAuthority
* organisation:  User → ACTIVE membership, in a role that carries the scope →
                 ACTIVE Organization → its ORGANIZATION LegalParty → authority
* mandate:       User → ACTIVE, VERIFIED, in-date RepresentationMandate that
                 carries the scope → principal LegalParty → authority

Every chain ends at the same authority check — in force, holding the scope,
and VERIFIED where the action needs it. So a membership or a mandate can pass
on only what the legal party at its end actually holds; neither can create a
right that party does not have.
"""

from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, union
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.audit import audit
from app.modules.identity.models import (
    LegalParty,
    Organization,
    OrganizationLegalParty,
    OrganizationMembership,
    PersonLegalParty,
    RepresentationMandate,
    RepresentationMandateScope,
    User,
)
from app.modules.identity.parties import has_legal_name, personal_party
from app.modules.properties.models import (
    AUTHORITY_SCOPES,
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


# What a membership role may do, through its organisation, to the
# organisation's properties. A VIEWER sees the workspace and acts on nothing; a
# FINANCE member reads money and publishes nothing.
ROLE_SCOPES: dict[str, frozenset[str]] = {
    "OWNER": frozenset(AUTHORITY_SCOPES),
    "ADMIN": frozenset(AUTHORITY_SCOPES),
    "AGENT": frozenset(
        {"EDIT_PROPERTY", "PUBLISH_LISTING", "MANAGE_MEDIA", "MANAGE_VIEWINGS", "MANAGE_MESSAGES"}
    ),
    "FINANCE": frozenset({"VIEW_FINANCIALS"}),
    "VIEWER": frozenset(),
}

# What each mandate scope lets its holder do to the principal's properties.
MANDATE_PROPERTY_SCOPES: dict[str, frozenset[str]] = {
    "MANAGE_PROPERTY": frozenset({"EDIT_PROPERTY", "MANAGE_MEDIA"}),
    "PUBLISH_LISTING": frozenset({"PUBLISH_LISTING"}),
    "MANAGE_VIEWINGS": frozenset({"MANAGE_VIEWINGS"}),
    "MANAGE_MESSAGES": frozenset({"MANAGE_MESSAGES"}),
    "MANAGE_APPLICATIONS": frozenset({"MANAGE_APPLICATIONS"}),
    "SIGN_CONTRACTS": frozenset({"SIGN_CONTRACT"}),
    "VIEW_FINANCIALS": frozenset({"VIEW_FINANCIALS"}),
    "MANAGE_PAYOUTS": frozenset(),
}


def _holder_parties(user_id: str, scope: str):
    """Every legal party this account may act for, for this scope."""
    today = _today()
    personal = select(PersonLegalParty.legal_party_id).where(
        PersonLegalParty.linked_user_id == user_id
    )
    roles = [role for role, scopes in ROLE_SCOPES.items() if scope in scopes]
    organisational = (
        select(OrganizationLegalParty.legal_party_id)
        .join(Organization, Organization.id == OrganizationLegalParty.organization_id)
        .join(
            OrganizationMembership,
            OrganizationMembership.organization_id == Organization.id,
        )
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.role.in_(roles),
            Organization.status == "ACTIVE",
        )
    )
    mandate_scopes = [m for m, scopes in MANDATE_PROPERTY_SCOPES.items() if scope in scopes]
    mandated = (
        select(RepresentationMandate.principal_legal_party_id)
        .join(
            RepresentationMandateScope,
            and_(
                RepresentationMandateScope.mandate_id == RepresentationMandate.id,
                RepresentationMandateScope.scope.in_(mandate_scopes),
            ),
        )
        .where(
            RepresentationMandate.representative_user_id == user_id,
            RepresentationMandate.status == "ACTIVE",
            RepresentationMandate.verification_state == "VERIFIED",
            RepresentationMandate.effective_from <= today,
            or_(
                RepresentationMandate.effective_until.is_(None),
                RepresentationMandate.effective_until >= today,
            ),
        )
    )
    return union(personal, organisational, mandated)


def _chains(user_id: str, scope: str, *, verified: bool) -> Select:
    """Property ids this account may act on with `scope`."""
    query = (
        select(PropertyAuthority.property_id)
        .join(LegalParty, LegalParty.id == PropertyAuthority.holder_legal_party_id)
        .join(
            PropertyAuthorityScope,
            and_(
                PropertyAuthorityScope.property_authority_id == PropertyAuthority.id,
                PropertyAuthorityScope.scope == scope,
            ),
        )
        .where(
            PropertyAuthority.holder_legal_party_id.in_(_holder_parties(user_id, scope)),
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


def grant_owner(
    db: Session,
    user: User,
    property_id: str,
    *,
    holder_legal_party_id: str | None = None,
    authority_type: str = "OWNER",
) -> PropertyAuthority:
    """What registering a flat gives the registrant: an ACTIVE, UNVERIFIED
    claim — held by their own legal person, or by the organisation they
    registered it for.

    Enough to prepare every part of the listing. Not enough to publish it.
    """
    holder = holder_legal_party_id or personal_party(db, user).id
    authority = PropertyAuthority(
        property_id=property_id,
        holder_legal_party_id=holder,
        authority_type=authority_type,
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
