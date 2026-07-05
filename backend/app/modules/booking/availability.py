"""Availability = absence of overlapping booking facts and host blocks.

Interval model (ADR-0008 direction): bookings and blocks are ranges with
exclusive end dates; a day-by-day calendar is only a read projection.
Overlap rule for [a_start, a_end) vs [b_start, b_end): a_start < b_end
AND b_start < a_end.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.booking.models import Booking
from app.modules.listings.models import HostBlock

BLOCKING_STATUSES = ("pending", "confirmed")


def blocked_ranges(
    db: Session, listing_id: str, date_from: date, date_to: date
) -> list[tuple[date, date, str]]:
    """All ranges overlapping the window, as (start, end, kind)."""
    ranges: list[tuple[date, date, str]] = []
    bookings = db.scalars(
        select(Booking).where(
            Booking.listing_id == listing_id,
            Booking.status.in_(BLOCKING_STATUSES),
            Booking.check_in < date_to,
            Booking.check_out > date_from,
        )
    )
    ranges.extend((b.check_in, b.check_out, "booked") for b in bookings)
    blocks = db.scalars(
        select(HostBlock).where(
            HostBlock.listing_id == listing_id,
            HostBlock.start_date < date_to,
            HostBlock.end_date > date_from,
        )
    )
    ranges.extend((bl.start_date, bl.end_date, "blocked") for bl in blocks)
    return ranges


def is_available(db: Session, listing_id: str, check_in: date, check_out: date) -> bool:
    return not blocked_ranges(db, listing_id, check_in, check_out)
