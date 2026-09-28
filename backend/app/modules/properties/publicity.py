"""Public eligibility episodes — `public_generation` (TASK-014, D-77).

A saved-search alert must fire when a listing *becomes* public — not every
time something about a public listing is touched. So each listing counts its
public episodes:

    never public                    generation 0
    first not-public → public       generation 1
    public → public                 unchanged   (reconfirmation, republish of
                                                 an already public listing)
    public → not-public → public    generation + 1

"Public" is the one TASK-012 rule (`freshness.is_public`: `active` and
confirmed within 21 days), evaluated on the row as locked at the decision, at
the database's decision instant — never the status label alone. A listing
whose confirmation silently expired is not public even while it still says
`active`, so confirming it opens a new episode.

Every authoritative way to become public — publish (from draft, paused,
stale, or of an active listing) and confirm (of an active or stale listing) —
goes through `make_public`, which in ONE transaction, under the row lock:

1. reads the prior status and confirmation instant,
2. decides whether the listing was public at the decision instant,
3. applies the transition (a conditional UPDATE, compare-and-set on the
   status and generation it read),
4. if it was not public: increments the generation, stamps `public_since`,
   appends the `ListingBecamePublic` event (dedup key = listing + generation)
   and the durable work item `(listing_id, public_generation)`.

A failure anywhere rolls all of it back: an episode never exists without its
event and work item, nor the reverse. Transitions to not-public (pause,
stale, archive, space archive, authority loss, silent expiry) need no
bookkeeping: the next `make_public` reads the prior state and decides.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.modules.events import service as events
from app.modules.properties import freshness
from app.modules.properties.models import ClassifiedOffer, ListingPublicGeneration

LISTING_BECAME_PUBLIC = "ListingBecamePublic"


@dataclass(frozen=True)
class Transition:
    applied: bool         # the listing was in an allowed state and was updated
    prior_status: str | None
    became_public: bool   # a new public episode began
    generation: int


def was_public(status: str, last_confirmed: datetime | None, now: datetime) -> bool:
    """The TASK-012 public rule on the values the row had at the decision."""
    return status == "active" and freshness.state(last_confirmed, now) in (
        freshness.FRESH, freshness.RECONFIRM_DUE)


def make_public(db: Session, offer_id: str, *, allowed_from: tuple[str, ...],
                values: dict, now: datetime) -> Transition:
    """Move the listing to a public state (`values` must make it `active` and
    confirmed at `now`), counting a new episode when it was not public.
    The caller commits; `now` is the request's `freshness.db_now`."""
    row = db.execute(
        select(ClassifiedOffer.status, ClassifiedOffer.last_confirmed_available_at,
               ClassifiedOffer.public_generation, ClassifiedOffer.property_id)
        .where(ClassifiedOffer.id == offer_id)
        .with_for_update()
    ).one_or_none()
    if row is None or row.status not in allowed_from:
        return Transition(False, row.status if row else None, False,
                          row.public_generation if row else 0)
    opening = not was_public(row.status, row.last_confirmed_available_at, now)
    generation = row.public_generation + 1 if opening else row.public_generation
    changes = dict(values)
    if opening:
        changes.update(public_generation=generation, public_since=now)
    done = cast(CursorResult, db.execute(
        update(ClassifiedOffer)
        .where(ClassifiedOffer.id == offer_id,
               ClassifiedOffer.status == row.status,
               ClassifiedOffer.public_generation == row.public_generation)
        .values(**changes)
        .execution_options(synchronize_session=False)
    ))
    if done.rowcount != 1:  # unreachable under the row lock; never half-apply
        raise RuntimeError("listing changed under its own row lock")
    if opening:
        _open_episode(db, offer_id, row.property_id, generation, now)
    return Transition(True, row.status, opening, generation)


def _open_episode(db: Session, offer_id: str, property_id: str, generation: int,
                  now: datetime) -> None:
    # Identifiers and the database instant only — never an address, a
    # coordinate, a price or anyone's contact (privacy by construction).
    payload = {
        "listing_id": offer_id,
        "property_id": property_id,
        "public_generation": generation,
        "became_public_at": freshness.canonical_instant(now),
    }
    emitted = events.emit(db, LISTING_BECAME_PUBLIC, offer_id, payload,
                          f"{LISTING_BECAME_PUBLIC}:{offer_id}:{generation}")
    if not emitted:  # the dedup key exists: the generation was already opened
        raise RuntimeError("public generation opened twice")
    event_id = db.scalar(select(events.DomainEvent.id).where(
        events.DomainEvent.dedup_key == f"{LISTING_BECAME_PUBLIC}:{offer_id}:{generation}"))
    db.add(ListingPublicGeneration(
        listing_id=offer_id, public_generation=generation, became_public_at=now,
        event_id=event_id, alert_status="pending",
    ))
    db.flush()
