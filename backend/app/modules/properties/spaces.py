"""Spaces: the whole flat, or one room in it (Domain Schema v1 §28, §81–§83).

Listings point at a space. The rules that matter live here rather than in the
routes:

* every property has one active WHOLE_PROPERTY space from the moment it is
  registered, created in the same transaction (§83);
* rooms are added by label, unique among the property's active rooms;
* an archived space takes no new listing, and archiving takes down the ones
  already live on it (§81.15) — a room that no longer exists must not stay on
  the board.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.modules.properties.models import ClassifiedOffer, Space


class DuplicateRoomLabel(Exception):
    """An active room with this label already exists on the property."""


class SpaceArchived(Exception):
    """The space is archived and cannot carry a new listing."""


def create_whole(db: Session, property_id: str) -> Space:
    space = Space(property_id=property_id, space_type="WHOLE_PROPERTY", status="ACTIVE")
    db.add(space)
    db.flush()
    return space


def whole_space(db: Session, property_id: str) -> Space | None:
    return db.scalar(
        select(Space).where(
            Space.property_id == property_id,
            Space.space_type == "WHOLE_PROPERTY",
            Space.archived_at.is_(None),
        )
    )


def spaces_of(db: Session, property_id: str) -> list[Space]:
    return list(
        db.scalars(
            select(Space)
            .where(Space.property_id == property_id)
            .order_by(Space.space_type.desc(), Space.label, Space.created_at)
        )
    )


def add_room(db: Session, property_id: str, label: str, area_m2: Decimal | None) -> Space:
    """The unique index decides duplicates, not a SELECT beforehand: two
    requests adding "Pokój 1" at once would both pass a check and both insert.
    A savepoint turns the loser's violation into a clean refusal."""
    room = Space(
        property_id=property_id,
        space_type="ROOM",
        label=label.strip(),
        area_m2=area_m2,
        status="ACTIVE",
    )
    try:
        with db.begin_nested():
            db.add(room)
            db.flush()
    except IntegrityError:
        raise DuplicateRoomLabel(label) from None
    return room


def ensure_listable(space: Space) -> None:
    if space.status != "ACTIVE" or space.archived_at is not None:
        raise SpaceArchived(space.id)


def archive(db: Session, space: Space, actor_id: str) -> list[str]:
    """Archive a space and take down what was live on it. Returns the ids of
    the offers paused, so the caller can tell the owner what came off the board.
    """
    if space.archived_at is not None:
        return []
    space.status = "ARCHIVED"
    space.archived_at = datetime.now(timezone.utc)
    space.version += 1

    paused: list[str] = []
    for offer in db.scalars(
        select(ClassifiedOffer).where(
            ClassifiedOffer.space_id == space.id, ClassifiedOffer.status == "active"
        )
    ):
        offer.status = "paused"
        paused.append(offer.id)

    audit(db, actor=actor_id, action="space.archived", entity_type="space", entity_id=space.id)
    return paused
