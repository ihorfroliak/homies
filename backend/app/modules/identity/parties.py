"""The legal person behind an account (Domain Schema v1 §16–§17).

An account gets its PERSON LegalParty lazily — the first time it does something
that needs a legal actor, such as registering a property. Creating one for
every signup would fill the table with parties for people who only ever
browse.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.models import (
    PARTY_STATUSES,
    LegalParty,
    OrganizationLegalParty,
    PersonLegalParty,
    User,
)


def find_personal_party(db: Session, user_id: str) -> LegalParty | None:
    return db.scalar(
        select(LegalParty)
        .join(PersonLegalParty, PersonLegalParty.legal_party_id == LegalParty.id)
        .where(PersonLegalParty.linked_user_id == user_id)
    )


def personal_party(db: Session, user: User) -> LegalParty:
    """The account's PERSON party, created on first use.

    Two first uses can race — the same person registering two flats at once —
    and `person_legal_parties.linked_user_id` is unique, so the loser's insert
    fails. A savepoint contains that failure and the loser reads the winner's
    row instead of turning a harmless race into a 500.
    """
    existing = find_personal_party(db, user.id)
    if existing is not None:
        return existing

    try:
        with db.begin_nested():
            party = LegalParty(
                party_type="PERSON",
                display_name=user.full_name or user.email,
            )
            db.add(party)
            db.flush()
            db.add(PersonLegalParty(legal_party_id=party.id, linked_user_id=user.id))
            db.flush()
        return party
    except IntegrityError:
        winner = find_personal_party(db, user.id)
        if winner is None:  # pragma: no cover — the constraint fired for another reason
            raise
        return winner


def set_legal_party_status(db: Session, legal_party_id: str, new_status: str) -> LegalParty:
    """Change a legal party's status — the only supported way to archive one.
    No endpoint exposes it yet (TASK-004 adds no workflow).

    Locked first; a publication resting on this party holds it FOR SHARE until
    it commits (authority.authorize_for_mutation), so the change is ordered
    before or after it. Any other UPDATE of the row waits the same way.
    """
    if new_status not in PARTY_STATUSES:
        raise ValueError(f"unknown legal party status {new_status!r}")
    party = db.scalar(
        select(LegalParty).where(LegalParty.id == legal_party_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if party is None:
        raise LookupError(legal_party_id)
    party.status = new_status
    db.flush()
    return party


def has_legal_name(db: Session, legal_party_id: str) -> bool:
    person = db.get(PersonLegalParty, legal_party_id)
    if person is not None:
        return bool(person.legal_first_name and person.legal_last_name)
    organisation = db.get(OrganizationLegalParty, legal_party_id)
    if organisation is not None:
        return bool(organisation.legal_name.strip())
    return False
