"""Organizations and representation mandates (Domain Schema v1 §18–§22, §114).

Two ways for one person to act for another legal party:

* **Membership.** An agency is an Organization; its people are members with a
  role. The organisation's ORGANIZATION legal party holds rights over the
  flats it manages, and members exercise them as far as their role allows.
* **Mandate.** An owner lets a specific person act for them — list the flat,
  show it — without that person joining anything. The owner grants it from
  their own account, and can take it back.

Neither creates a right. Both only open a path to rights the legal party at
the end already holds; `properties.authority` walks those paths.

Invitations and mandates are addressed by email, and the answer is the same
whether or not the address has an account. Otherwise these endpoints would be
a way to ask "is this person on Homies?" about anybody.
"""

from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import get_current_user
from app.modules.identity.models import (
    ORGANIZATION_STATUSES,
    LegalParty,
    Organization,
    OrganizationLegalParty,
    OrganizationMembership,
    RepresentationMandate,
    RepresentationMandateScope,
    User,
)
from app.modules.identity.parties import personal_party

router = APIRouter(tags=["organizations"])

# Roles that may register properties for the organisation and invite people.
REGISTERING_ROLES = ("OWNER", "ADMIN", "AGENT")
MANAGING_ROLES = ("OWNER", "ADMIN")

MandateScope = Literal[
    "MANAGE_PROPERTY", "PUBLISH_LISTING", "MANAGE_VIEWINGS", "MANAGE_MESSAGES",
    "MANAGE_APPLICATIONS", "SIGN_CONTRACTS", "VIEW_FINANCIALS", "MANAGE_PAYOUTS",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- schemas ------------------------------------------------------------------


class OrganizationCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    legal_name: str = Field(min_length=1, max_length=255)
    registration_number: str | None = Field(default=None, max_length=40)
    registration_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")


class OrganizationOut(BaseModel):
    id: str
    display_name: str
    slug: str
    status: str
    legal_party_id: str
    my_role: str


class MemberInvite(BaseModel):
    email: EmailStr
    # OWNER is not handed out by invitation: ownership of a workspace is not
    # something a single admin should be able to give away.
    role: Literal["ADMIN", "AGENT", "FINANCE", "VIEWER"]


class MemberOut(BaseModel):
    user_id: str
    role: str
    status: str


class MandateCreate(BaseModel):
    representative_email: EmailStr
    scopes: list[MandateScope] = Field(min_length=1)
    effective_from: date | None = None
    effective_until: date | None = None


class MandateOut(BaseModel):
    id: str
    principal_legal_party_id: str
    representative_user_id: str
    status: str
    verification_state: str
    effective_from: date
    effective_until: date | None
    scopes: list[str]


ACCEPTED = {"status": "accepted", "detail": "If the address has an account, it has been sent."}


# --- helpers ------------------------------------------------------------------


def organization_party(db: Session, organization_id: str) -> OrganizationLegalParty | None:
    return db.scalar(
        select(OrganizationLegalParty).where(
            OrganizationLegalParty.organization_id == organization_id
        )
    )


def set_organization_status(db: Session, organization_id: str, new_status: str) -> Organization:
    """Change an organisation's status — the only supported way to suspend or
    archive one. No endpoint exposes it yet (TASK-004 adds no workflow).

    The row is locked first. A publication resting on this organisation holds
    it FOR SHARE until it commits (authority.authorize_for_mutation), so the
    change waits for it or is seen by it. The guarantee does not depend on
    this function: any UPDATE of the row, however issued, waits the same way.
    """
    if new_status not in ORGANIZATION_STATUSES:
        raise ValueError(f"unknown organization status {new_status!r}")
    org = db.scalar(
        select(Organization).where(Organization.id == organization_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if org is None:
        raise LookupError(organization_id)
    org.status = new_status
    db.flush()
    return org


def active_membership(
    db: Session, organization_id: str, user_id: str
) -> OrganizationMembership | None:
    return db.scalar(
        select(OrganizationMembership)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "ACTIVE",
            Organization.status == "ACTIVE",
        )
    )


def _require_role(db: Session, organization_id: str, user: User, roles) -> OrganizationMembership:
    """404 for non-members: an organisation's existence is not a stranger's
    business."""
    membership = active_membership(db, organization_id, user.id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if membership.role not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role does not allow this")
    return membership


def _user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def _out(db: Session, org: Organization, role: str) -> OrganizationOut:
    party = organization_party(db, org.id)
    assert party is not None
    return OrganizationOut(
        id=org.id, display_name=org.display_name, slug=org.slug, status=org.status,
        legal_party_id=party.legal_party_id, my_role=role,
    )


# --- organizations ------------------------------------------------------------


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
def create_organization(
    body: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A workspace, its legal party, and its creator as OWNER — one
    transaction, so none of the three can exist without the others."""
    org = Organization(display_name=body.display_name, slug=body.slug,
                       created_by_user_id=user.id)
    db.add(org)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That slug is taken") from None

    party = LegalParty(party_type="ORGANIZATION", display_name=body.legal_name)
    db.add(party)
    db.flush()
    db.add(OrganizationLegalParty(
        legal_party_id=party.id, organization_id=org.id, legal_name=body.legal_name,
        registration_number=body.registration_number,
        registration_country=body.registration_country,
    ))
    db.add(OrganizationMembership(
        organization_id=org.id, user_id=user.id, role="OWNER", status="ACTIVE",
        joined_at=_now(),
    ))
    audit(db, actor=user.id, action="organization.created", entity_type="organization",
          entity_id=org.id)
    db.commit()
    return _out(db, org, "OWNER")


@router.get("/organizations", response_model=list[OrganizationOut])
def my_organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Organization, OrganizationMembership.role)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == user.id,
               OrganizationMembership.status == "ACTIVE")
    ).all()
    return [_out(db, org, role) for org, role in rows]


@router.post("/organizations/{organization_id}/members", status_code=202)
def invite_member(
    organization_id: str,
    body: MemberInvite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_role(db, organization_id, user, MANAGING_ROLES)
    invitee = _user_by_email(db, body.email)
    if invitee is not None and invitee.id != user.id:
        existing = db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == invitee.id,
            )
        )
        if existing is None:
            db.add(OrganizationMembership(
                organization_id=organization_id, user_id=invitee.id, role=body.role,
                status="INVITED", invited_by_user_id=user.id,
            ))
        elif existing.status == "REVOKED":
            existing.status = "INVITED"
            existing.role = body.role
            existing.revoked_at = None
            existing.invited_by_user_id = user.id
            existing.version += 1
        audit(db, actor=user.id, action="organization.member_invited",
              entity_type="organization", entity_id=organization_id)
        db.commit()
    return ACCEPTED


@router.post("/organizations/{organization_id}/membership/accept", response_model=MemberOut)
def accept_invitation(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Locked before it is read, like revoke_member (TASK-006, N-02). Read
    # unlocked, an admin's revoke could commit between this read and the
    # write, and the write would turn the REVOKED row back into ACTIVE —
    # the revoke answered 200 and the invitee got the role anyway. Locked,
    # the two are ordered: a revoke already committed is seen here and the
    # invitation is gone; a revoke arriving later waits and revokes the
    # membership this accept made ACTIVE.
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        ).with_for_update().execution_options(populate_existing=True)
    )
    if membership is None or membership.status != "INVITED":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    membership.status = "ACTIVE"
    membership.joined_at = _now()
    membership.version += 1
    audit(db, actor=user.id, action="organization.member_joined",
          entity_type="organization", entity_id=organization_id)
    db.commit()
    return MemberOut(user_id=user.id, role=membership.role, status=membership.status)


@router.get("/organizations/{organization_id}/members", response_model=list[MemberOut])
def list_members(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_role(db, organization_id, user, MANAGING_ROLES)
    rows = db.scalars(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id
        )
    )
    return [MemberOut(user_id=m.user_id, role=m.role, status=m.status) for m in rows]


@router.post("/organizations/{organization_id}/members/{member_user_id}/revoke",
             response_model=MemberOut)
def revoke_member(
    organization_id: str,
    member_user_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Take a person's access away. The last OWNER cannot be removed: an
    organisation with nobody able to manage it is one nobody can repair."""
    _require_role(db, organization_id, user, MANAGING_ROLES)
    # Locked before it is read (TASK-004): a publication resting on this
    # membership holds it FOR SHARE until it commits, so the revoke either
    # happens before that publication decides (and it is refused) or after it
    # commits — never in between. See authority.authorize_for_mutation.
    target = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == member_user_id,
        ).with_for_update().execution_options(populate_existing=True)
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if target.role == "OWNER" and target.status == "ACTIVE":
        owners = db.scalar(
            select(func.count()).select_from(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.role == "OWNER",
                OrganizationMembership.status == "ACTIVE",
            )
        )
        if (owners or 0) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "An organization must keep at least one owner")
    target.status = "REVOKED"
    target.revoked_at = _now()
    target.version += 1
    audit(db, actor=user.id, action="organization.member_revoked",
          entity_type="organization", entity_id=organization_id)
    db.commit()
    return MemberOut(user_id=target.user_id, role=target.role, status=target.status)


# --- mandates -----------------------------------------------------------------


def _mandate_out(db: Session, m: RepresentationMandate) -> MandateOut:
    scopes = sorted(db.scalars(
        select(RepresentationMandateScope.scope).where(
            RepresentationMandateScope.mandate_id == m.id)
    ))
    return MandateOut(
        id=m.id, principal_legal_party_id=m.principal_legal_party_id,
        representative_user_id=m.representative_user_id, status=m.status,
        verification_state=m.verification_state, effective_from=m.effective_from,
        effective_until=m.effective_until, scopes=scopes,
    )


@router.post("/me/mandates", status_code=202)
def grant_mandate(
    body: MandateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Let someone act for you. The principal is always the caller's own legal
    person — nobody can grant a mandate over anyone else, and a representative
    cannot pass theirs on.

    VERIFIED at once, because the principal's own signed-in account granting it
    is the consent a mandate needs. A mandate arriving any other way — an
    uploaded power of attorney — would start UNVERIFIED and wait for review.
    """
    start = body.effective_from or datetime.now(timezone.utc).date()
    if body.effective_until is not None and body.effective_until < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "effective_until is before effective_from")
    representative = _user_by_email(db, body.representative_email)
    if representative is not None and representative.id != user.id:
        principal = personal_party(db, user)
        mandate = RepresentationMandate(
            principal_legal_party_id=principal.id, representative_user_id=representative.id,
            status="ACTIVE", verification_state="VERIFIED", effective_from=start,
            effective_until=body.effective_until, granted_by_user_id=user.id,
        )
        db.add(mandate)
        db.flush()
        db.add_all(RepresentationMandateScope(mandate_id=mandate.id, scope=s)
                   for s in sorted(set(body.scopes)))
        audit(db, actor=user.id, action="mandate.granted", entity_type="mandate",
              entity_id=mandate.id)
        db.commit()
    return ACCEPTED


@router.get("/me/mandates", response_model=list[MandateOut])
def my_mandates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mandates you granted, and mandates granted to you."""
    principal = personal_party(db, user)
    db.commit()  # personal_party may have created the party on first use
    rows = db.scalars(
        select(RepresentationMandate).where(
            (RepresentationMandate.principal_legal_party_id == principal.id)
            | (RepresentationMandate.representative_user_id == user.id)
        ).order_by(RepresentationMandate.created_at)
    )
    return [_mandate_out(db, m) for m in rows]


@router.post("/me/mandates/{mandate_id}/revoke", response_model=MandateOut)
def revoke_mandate(
    mandate_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Only the principal can take a mandate back. To the representative and
    to anyone else, somebody else's mandate does not exist."""
    principal = personal_party(db, user)
    # Locked before it is read, for the same reason as a membership revoke
    # (TASK-004): an in-flight publication using this mandate finishes first,
    # or sees the revocation.
    mandate = db.scalar(
        select(RepresentationMandate).where(RepresentationMandate.id == mandate_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if mandate is None or mandate.principal_legal_party_id != principal.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mandate not found")
    if mandate.status != "REVOKED":
        mandate.status = "REVOKED"
        mandate.revoked_at = _now()
        mandate.version += 1
        audit(db, actor=user.id, action="mandate.revoked", entity_type="mandate",
              entity_id=mandate.id)
    db.commit()
    return _mandate_out(db, mandate)
