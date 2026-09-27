"""Listing freshness: is this published offer still current? (TASK-012, D-59–D-62)

Freshness is not the lifecycle status, not the property's existence and not
the move-in date. It answers one question — when did someone with authority
over the property last confirm that the offer is still current? — from one
stored fact, `classified_offers.last_confirmed_available_at` (04 §43), plus
the policy below and the database's clock at the moment of decision.
`reconfirm_at` and `stale_at` are derived, never stored: a change of policy
applies to every listing at once, with no backfill and no drift.

    age = decision time − last confirmation
    age < 14 days          FRESH
    14 days ≤ age < 21     RECONFIRM_DUE   (still public; the owner is asked)
    age ≥ 21 days          STALE           (not public)

A listing is public only while it is `active` AND not stale. That rule lives
here once — as SQL for queries and as Python for a loaded row — and every
public path uses it, so the moment a listing turns 21 days old it stops being
shown, whether or not the maintenance sweep has run yet. The sweep then moves
it to the canonical `stale` status (so the owner sees why) and records the
events a reminder will later be sent from.

Publication counts as confirmation. `stale → active` happens only through an
authorised confirmation that passes every publication check; `archived` is
never touched.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import and_, bindparam, func, literal, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement
from sqlalchemy.types import DateTime, Interval

from app.modules.events import service as events
from app.modules.properties.models import ClassifiedOffer

# --- policy (mutable Phase-1A business policy, not domain law — D-60) ---------------

CONFIRMATION_VALID_FOR = timedelta(days=14)
STALE_GRACE_PERIOD = timedelta(days=7)
AUTO_PAUSE_AFTER = CONFIRMATION_VALID_FOR + STALE_GRACE_PERIOD  # 21 days

State = Literal["FRESH", "RECONFIRM_DUE", "STALE"]
FRESH: State = "FRESH"
RECONFIRM_DUE: State = "RECONFIRM_DUE"
STALE: State = "STALE"

# Domain events (the existing CamelCase convention of events.service). No
# routing yet: they are the seam a reminder channel will subscribe to.
LISTING_CONFIRMED = "ListingConfirmed"
LISTING_REACTIVATED = "ListingReactivated"
LISTING_RECONFIRMATION_DUE = "ListingReconfirmationDue"
LISTING_AUTO_PAUSED_STALE = "ListingAutoPausedStale"


# --- the clock -------------------------------------------------------------------------


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def db_now(db: Session) -> datetime:
    """The database's current time — the authoritative decision instant. On
    SQLite (unit tests only) the process clock in UTC stands in."""
    if db.get_bind().dialect.name == "postgresql":
        value = db.scalar(select(func.statement_timestamp()))
        assert value is not None
        return _aware(value)
    return datetime.now(timezone.utc)


def _now_sql(db: Session, as_of: datetime | None) -> ColumnElement[Any]:
    if as_of is not None:
        return literal(as_of, DateTime(timezone=True))
    if db.get_bind().dialect.name == "postgresql":
        return func.statement_timestamp()
    return literal(datetime.now(timezone.utc), DateTime(timezone=True))


def _minus(db: Session, now: ColumnElement[Any], delta: timedelta) -> ColumnElement[Any]:
    if db.get_bind().dialect.name == "postgresql":
        return now - bindparam(None, delta, type_=Interval())
    # SQLite has no interval arithmetic; the bound instant is computed here.
    value = getattr(now, "value", None)
    base = value if isinstance(value, datetime) else datetime.now(timezone.utc)
    return literal(base - delta, DateTime(timezone=True))


# --- derived state ---------------------------------------------------------------------


def state(last_confirmed: datetime | None, now: datetime) -> State | None:
    """FRESH / RECONFIRM_DUE / STALE, or None when never confirmed."""
    if last_confirmed is None:
        return None
    age = _aware(now) - _aware(last_confirmed)
    if age < CONFIRMATION_VALID_FOR:
        return FRESH
    if age < AUTO_PAUSE_AFTER:
        return RECONFIRM_DUE
    return STALE


def reconfirm_at(last_confirmed: datetime | None) -> datetime | None:
    return None if last_confirmed is None else _aware(last_confirmed) + CONFIRMATION_VALID_FOR


def stale_at(last_confirmed: datetime | None) -> datetime | None:
    return None if last_confirmed is None else _aware(last_confirmed) + AUTO_PAUSE_AFTER


# --- the one public-visibility rule -------------------------------------------------------


def public_clause(db: Session, as_of: datetime | None = None) -> ColumnElement[bool]:
    """SQL: the offer may be shown to the public right now."""
    cutoff = _minus(db, _now_sql(db, as_of), AUTO_PAUSE_AFTER)
    return and_(
        ClassifiedOffer.status == "active",
        ClassifiedOffer.last_confirmed_available_at.is_not(None),
        ClassifiedOffer.last_confirmed_available_at > cutoff,
    )


def is_public(offer: ClassifiedOffer, now: datetime) -> bool:
    """The same rule for a loaded row, at a decision instant from db_now()."""
    return offer.status == "active" and state(offer.last_confirmed_available_at, now) in (
        FRESH, RECONFIRM_DUE)


# --- events ------------------------------------------------------------------------------


def _payload(offer_id: str, property_id: str, last_confirmed: datetime | None) -> dict:
    # Privacy-safe by construction: identifiers and times only — never an
    # address, a coordinate or a contact detail.
    return {
        "listing_id": offer_id,
        "property_id": property_id,
        "last_confirmed_available_at": (
            _aware(last_confirmed).isoformat() if last_confirmed else None),
        "confirmation_valid_days": CONFIRMATION_VALID_FOR.days,
        "auto_pause_after_days": AUTO_PAUSE_AFTER.days,
    }


def emit(db: Session, event_type: str, offer_id: str, property_id: str,
         last_confirmed: datetime | None) -> bool:
    """Emit once per (event, listing, confirmation cycle). A concurrent
    duplicate loses on the unique dedup key inside a savepoint, so it can never
    abort the caller's transaction."""
    stamp = _aware(last_confirmed).isoformat() if last_confirmed else "none"
    key = f"{event_type}:{offer_id}:{stamp}"[:96]
    try:
        with db.begin_nested():
            return events.emit(db, event_type, offer_id,
                               _payload(offer_id, property_id, last_confirmed), key)
    except IntegrityError:
        return False


# --- maintenance ---------------------------------------------------------------------------


@dataclass
class SweepResult:
    staled: list[str] = field(default_factory=list)
    reminded: list[str] = field(default_factory=list)


def sweep(db: Session, *, limit: int = 500, as_of: datetime | None = None) -> SweepResult:
    """One idempotent maintenance pass. The caller commits.

    * active listings whose confirmation is ≥ 21 days old become `stale`;
    * active listings between 14 and 21 days get one reconfirmation-due event
      per confirmation cycle (`limit` bounds only the transitions).

    The transition is one conditional UPDATE: it re-reads status and
    confirmation time on the row as committed when it takes the row lock, so a
    confirmation that committed first always wins. Rows another transaction
    holds (a confirmation in flight) are skipped, not waited for — the next
    pass sees them. Nothing here can publish, unarchive or reactivate.
    """
    result = SweepResult()
    now = _now_sql(db, as_of)
    stale_cutoff = _minus(db, now, AUTO_PAUSE_AFTER)
    due_cutoff = _minus(db, now, CONFIRMATION_VALID_FOR)

    candidates = (
        select(ClassifiedOffer.id)
        .where(ClassifiedOffer.status == "active",
               ClassifiedOffer.last_confirmed_available_at <= stale_cutoff)
        .order_by(ClassifiedOffer.last_confirmed_available_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    staled = db.execute(
        update(ClassifiedOffer)
        .where(ClassifiedOffer.id.in_(candidates),
               ClassifiedOffer.status == "active",
               ClassifiedOffer.last_confirmed_available_at <= stale_cutoff)
        .values(status="stale")
        .returning(ClassifiedOffer.id, ClassifiedOffer.property_id,
                   ClassifiedOffer.last_confirmed_available_at)
        .execution_options(synchronize_session=False)
    ).all()
    for offer_id, property_id, last in staled:
        emit(db, LISTING_AUTO_PAUSED_STALE, offer_id, property_id, last)
        result.staled.append(offer_id)

    due = db.execute(
        select(ClassifiedOffer.id, ClassifiedOffer.property_id,
               ClassifiedOffer.last_confirmed_available_at)
        .where(ClassifiedOffer.status == "active",
               ClassifiedOffer.last_confirmed_available_at <= due_cutoff,
               ClassifiedOffer.last_confirmed_available_at > stale_cutoff)
        .order_by(ClassifiedOffer.last_confirmed_available_at)
    ).all()  # every due listing: a reminder already sent this cycle dedups to a no-op
    for offer_id, property_id, last in due:
        if emit(db, LISTING_RECONFIRMATION_DUE, offer_id, property_id, last):
            result.reminded.append(offer_id)
    return result


def preflight(db: Session, as_of: datetime | None = None) -> list[dict]:
    """Active listings that are not public under the freshness rule right now —
    what a deployment would take off the board at once (D-62 runbook)."""
    rows = db.execute(
        select(ClassifiedOffer.id, ClassifiedOffer.property_id,
               ClassifiedOffer.published_at, ClassifiedOffer.last_confirmed_available_at)
        .where(ClassifiedOffer.status == "active",
               ~public_clause(db, as_of).self_group())
        .order_by(ClassifiedOffer.last_confirmed_available_at)
    ).all()
    return [{"listing_id": r[0], "property_id": r[1],
             "published_at": _aware(r[2]).isoformat() if r[2] else None,
             "last_confirmed_available_at": _aware(r[3]).isoformat() if r[3] else None}
            for r in rows]
