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
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Date, and_, cast, false, func, or_, select, union
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement, Select

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
from app.modules.properties import coordination
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


# A calendar date, either computed in Python (ordinary reads) or evaluated by
# the database at the moment a protected decision is made (publication).
Today = date | ColumnElement[Any]


def _in_force(today: Today):
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


def _holder_parties(user_id: str, scope: str, today: Today | None = None,
                    within: dict[str, list] | None = None):
    """Every legal party this account may act for, for this scope.

    `within` is for the protected decision only: consider only the rows a
    locked proof names, so a link that appeared after the locks were taken
    cannot carry the decision (TASK-006, N-01)."""
    today = _today() if today is None else today
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
    if within is not None:
        personal = personal.where(
            PersonLegalParty.legal_party_id.in_(within.get("person_legal_parties") or []))
        organisational = organisational.where(
            OrganizationMembership.id.in_(within.get("organization_memberships") or []),
            Organization.id.in_(within.get("organizations") or []),
            OrganizationLegalParty.legal_party_id.in_(
                within.get("organization_legal_parties") or []),
        )
        # The exact (mandate, scope) rows that were locked, not merely the
        # locked mandates: a scope row added since is not part of the proof.
        pairs = within.get("representation_mandate_scopes") or []
        mandated = mandated.where(or_(false(), *(
            and_(RepresentationMandateScope.mandate_id == m,
                 RepresentationMandateScope.scope == s) for m, s in pairs)))
    return union(personal, organisational, mandated)


def _chains(user_id: str, scope: str, *, verified: bool, today: Today | None = None,
            within: dict[str, list] | None = None) -> Select:
    """Property ids this account may act on with `scope` — restricted to the
    rows of a locked proof when `within` is given."""
    today = _today() if today is None else today
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
            PropertyAuthority.holder_legal_party_id.in_(
                _holder_parties(user_id, scope, today, within)),
            LegalParty.status == "ACTIVE",
            _in_force(today),
        )
    )
    if within is not None:
        # Authority scope rows were locked as (authority, `scope`) for exactly
        # these authorities, so filtering the authority ids is exact for them.
        query = query.where(
            PropertyAuthority.id.in_(within.get("property_authorities") or []),
            LegalParty.id.in_(within.get("legal_parties") or []),
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


# --- the protected decision (TASK-004) ----------------------------------------
#
# `require` answers "may this account act?" as of the statement that asks. A
# privileged write that commits later — publication — needs the answer to
# still hold when it commits. TASK-003 showed it did not: a membership or a
# mandate revoked, an organisation suspended, a legal party archived, or a
# mandate expiring between the last check and the write, and the listing went
# public on a chain that no longer existed.
#
# `authorize_for_mutation` closes that gap inside the caller's transaction:
#
#   1. the caller already holds the property's coordination lock
#      (coordination.py) — this orders it against authority revoke and space
#      archive, which take the same lock first;
#   2. every row that makes a currently-valid chain valid — for every chain
#      the account has, not one — is locked FOR SHARE, table by table in the
#      order below and by id within a table;
#   3. the chains are evaluated again, after the locks, against the calendar
#      date the database reports at that moment — and ONLY through the rows
#      locked in step 2 (TASK-006, N-01).
#
# FOR SHARE conflicts with every UPDATE and DELETE of those rows, whoever
# issues it: a membership or mandate revoke, an organisation suspension, a
# legal party archival, even a direct SQL statement. Such a change either
# committed before step 2 (and step 3 sees it) or waits until this transaction
# ends (and is serialised after it).
#
# Why step 3 is restricted: the proof is read before it is locked, and step 2
# can wait (on a revoke in flight, say). A chain that became valid during that
# wait — a mandate granted, an invitation accepted — is not in the proof and
# holds no lock. TASK-005 showed a decision carried by such a chain, which was
# then revoked without waiting, and the listing went public with no valid
# chain at commit. So the decision uses only locked rows: a chain gained after
# the proof was read cannot carry this attempt (it is refused with 409, and a
# new attempt reads a proof that includes it). One pass, no loop, nothing
# unbounded.
#
# Two publications share the locks and do not block each other, except that a
# share request queues behind an UPDATE already waiting on the same row
# (PostgreSQL row-lock queueing) — a delay, never a cycle. There is no global
# lock and no in-process lock.
#
# Lock order for a publication (never acquired in reverse by any path):
#
#   properties                        (coordination row, FOR UPDATE)
#   legal_parties                     (chain holders)
#   person_legal_parties              (personal link)
#   organizations                     (organisation status)
#   organization_legal_parties        (organisation -> its legal party)
#   organization_memberships          (the acting user's membership)
#   representation_mandates           (the acting user's mandates)
#   representation_mandate_scopes
#   property_authorities
#   property_authority_scopes
#   classified_offers                 (the conditional status UPDATE)
#
# The paths that invalidate a link each lock only the row they change
# (membership revoke, mandate revoke, organisation/party status), or take the
# property lock first (authority revoke, space archive). None of them holds a
# lock publication needs while waiting for one publication holds, so no cycle
# exists. Validity dates are compared to the database's statement time, not
# to a Python date read earlier in the request.


def decision_date(db: Session) -> ColumnElement[Any]:
    """Today's UTC calendar date as the database sees it, when the statement
    runs. The same UTC date `_today()` computes in Python, so inclusive
    `effective_until` semantics are unchanged; only the clock moves to the
    decision point."""
    if db.get_bind().dialect.name == "postgresql":
        return cast(func.timezone("UTC", func.statement_timestamp()), Date)
    return func.date("now")  # SQLite (unit tests): 'YYYY-MM-DD' in UTC


def _proof(db: Session, user_id: str, property_id: str, scope: str, *,
           verified: bool) -> dict[str, list]:
    """Ids of every row that makes a currently-valid chain valid, per table.

    Read before locking; anything that changes before the lock is taken is
    seen by the re-evaluation after it. Rows of chains that are already
    invalid are not needed: they cannot authorise anything."""
    today = decision_date(db)
    authorities = select(PropertyAuthority.id, PropertyAuthority.holder_legal_party_id).join(
        LegalParty, LegalParty.id == PropertyAuthority.holder_legal_party_id
    ).join(
        PropertyAuthorityScope,
        and_(
            PropertyAuthorityScope.property_authority_id == PropertyAuthority.id,
            PropertyAuthorityScope.scope == scope,
        ),
    ).where(
        PropertyAuthority.property_id == property_id,
        PropertyAuthority.holder_legal_party_id.in_(_holder_parties(user_id, scope, today)),
        LegalParty.status == "ACTIVE",
        _in_force(today),
    )
    if verified:
        authorities = authorities.where(PropertyAuthority.verification_state == "VERIFIED")
    rows = db.execute(authorities).all()
    authority_ids = sorted({r[0] for r in rows})
    holders = sorted({r[1] for r in rows})
    if not holders:
        return {}

    personal = db.scalars(select(PersonLegalParty.legal_party_id).where(
        PersonLegalParty.linked_user_id == user_id,
        PersonLegalParty.legal_party_id.in_(holders),
    )).all()

    roles = [role for role, scopes in ROLE_SCOPES.items() if scope in scopes]
    organisational = db.execute(
        select(OrganizationMembership.id, Organization.id, OrganizationLegalParty.legal_party_id)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .join(OrganizationLegalParty,
              OrganizationLegalParty.organization_id == Organization.id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.role.in_(roles),
            Organization.status == "ACTIVE",
            OrganizationLegalParty.legal_party_id.in_(holders),
        )
    ).all()

    mandate_scopes = [m for m, scopes in MANDATE_PROPERTY_SCOPES.items() if scope in scopes]
    mandated = db.execute(
        select(RepresentationMandate.id, RepresentationMandateScope.scope)
        .join(RepresentationMandateScope,
              and_(RepresentationMandateScope.mandate_id == RepresentationMandate.id,
                   RepresentationMandateScope.scope.in_(mandate_scopes)))
        .where(
            RepresentationMandate.representative_user_id == user_id,
            RepresentationMandate.principal_legal_party_id.in_(holders),
            RepresentationMandate.status == "ACTIVE",
            RepresentationMandate.verification_state == "VERIFIED",
            RepresentationMandate.effective_from <= today,
            or_(RepresentationMandate.effective_until.is_(None),
                RepresentationMandate.effective_until >= today),
        )
    ).all()

    return {
        "legal_parties": holders,
        "person_legal_parties": sorted(set(personal)),
        "organizations": sorted({r[1] for r in organisational}),
        "organization_legal_parties": sorted({r[2] for r in organisational}),
        "organization_memberships": sorted({r[0] for r in organisational}),
        "representation_mandates": sorted({r[0] for r in mandated}),
        "representation_mandate_scopes": sorted({(r[0], r[1]) for r in mandated}),
        "property_authorities": authority_ids,
        "property_authority_scopes": [(a, scope) for a in authority_ids],
    }


def _lock_proof(db: Session, proof: dict[str, list]) -> None:
    """FOR SHARE on every proof row, in the documented order."""
    single = (
        ("legal_parties", LegalParty.id),
        ("person_legal_parties", PersonLegalParty.legal_party_id),
        ("organizations", Organization.id),
        ("organization_legal_parties", OrganizationLegalParty.legal_party_id),
        ("organization_memberships", OrganizationMembership.id),
        ("representation_mandates", RepresentationMandate.id),
    )
    for key, column in single:
        ids = proof.get(key) or []
        if ids:
            db.execute(select(column).where(column.in_(ids)).order_by(column)
                       .with_for_update(read=True))
    for mandate_id, mandate_scope in proof.get("representation_mandate_scopes") or []:
        db.execute(select(RepresentationMandateScope.mandate_id).where(
            RepresentationMandateScope.mandate_id == mandate_id,
            RepresentationMandateScope.scope == mandate_scope,
        ).with_for_update(read=True))
    ids = proof.get("property_authorities") or []
    if ids:
        db.execute(select(PropertyAuthority.id).where(PropertyAuthority.id.in_(ids))
                   .order_by(PropertyAuthority.id).with_for_update(read=True))
    for authority_id, authority_scope in proof.get("property_authority_scopes") or []:
        db.execute(select(PropertyAuthorityScope.property_authority_id).where(
            PropertyAuthorityScope.property_authority_id == authority_id,
            PropertyAuthorityScope.scope == authority_scope,
        ).with_for_update(read=True))


def authorize_for_mutation(
    db: Session, user: User, property_id: str, scope: str, *, verified: bool = True
) -> None:
    """The protected authorisation decision for a privileged write.

    Precondition: the caller holds the property's coordination lock
    (coordination.lock_property) in this transaction, and makes its write in
    the same transaction before committing. Postcondition: at least one chain
    that grants `scope` (VERIFIED when `verified`) is valid at the database's
    current time, every row of that chain is locked, and none can change until
    the caller commits. The chain is found among the locked rows only; one
    that became valid after the proof was read does not count (N-01).

    Refusals: 409 when a valid chain exists now but was not in the locked
    proof (it appeared while the locks were being taken — a new attempt will
    use it); otherwise the same as `require`: 404 when nothing is held, 403
    when only an unverified right is.

    Scopes are not pooled across chains: each chain must carry `scope` on its
    own, exactly as `require` evaluates it."""
    proof = _proof(db, user.id, property_id, scope, verified=verified)
    _lock_proof(db, proof)
    today = decision_date(db)
    protected = _chains(user.id, scope, verified=verified, today=today, within=proof).where(
        PropertyAuthority.property_id == property_id)
    if proof and db.scalar(protected.limit(1)) is not None:
        return
    # Refused. Which refusal is decided from the state as it is now; none of
    # it is protected, and none of it authorises anything.
    unprotected = _chains(user.id, scope, verified=verified, today=today).where(
        PropertyAuthority.property_id == property_id)
    if db.scalar(unprotected.limit(1)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The authority for this property changed while publishing. Try again.",
        )
    held = _chains(user.id, scope, verified=False, today=today).where(
        PropertyAuthority.property_id == property_id)
    if db.scalar(held.limit(1)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found")
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Ownership of this property has not been verified yet",
    )


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

    Takes the property's coordination lock first (properties/coordination.py),
    the lock publication takes too. A publication already holding it finishes
    first and its listing is then paused here; one that arrives later
    re-checks under the lock and finds this authority revoked (TASK-001 F-04).
    """
    coordination.lock_property(db, authority.property_id)
    # The lock expired the session: this is the authority as committed now,
    # so two admins revoking at once do the work once.
    if authority.status == "REVOKED":
        return []
    authority.status = "REVOKED"
    authority.revoked_at = datetime.now(timezone.utc)
    authority.version += 1
    db.flush()

    # "Still backed" means exactly what publication requires: in force,
    # VERIFIED, holding PUBLISH_LISTING, held by an ACTIVE legal party.
    still_backed = db.scalar(
        select(PropertyAuthority.id)
        .join(LegalParty, LegalParty.id == PropertyAuthority.holder_legal_party_id)
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
            LegalParty.status == "ACTIVE",
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
