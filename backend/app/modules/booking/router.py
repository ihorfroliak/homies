from datetime import date, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.modules.booking.availability import blocked_ranges, is_available
from app.modules.booking.models import Booking
from app.modules.booking.schemas import AvailabilityOut, BookingCreate, BookingOut, DayStatus
from app.modules.listings.models import Listing
from app.modules.payments import service as payments_service
from app.modules.payments.models import Payment

router = APIRouter(tags=["bookings"])

MAX_AVAILABILITY_WINDOW_DAYS = 366


def _booking_out(booking: Booking, payment: Payment | None) -> BookingOut:
    out = BookingOut.model_validate(booking)
    if payment is not None:
        out.payment_id = payment.id
        out.payment_intent_id = payment.provider_intent_id
    return out


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(
    body: BookingCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=64),
    user=Depends(require_role("guest")),
    db: Session = Depends(get_db),
):
    # Idempotent replay: same guest + key returns the original booking.
    existing = db.scalar(
        select(Booking).where(
            Booking.guest_id == user.id, Booking.idempotency_key == idempotency_key
        )
    )
    if existing:
        payment = db.scalar(select(Payment).where(Payment.booking_id == existing.id))
        return _booking_out(existing, payment)

    if body.check_in < date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "check_in is in the past")

    # Lock the listing row: serializes concurrent bookings of the same listing
    # (no-op on SQLite; real double-booking protection requires Postgres).
    listing = db.scalar(
        select(Listing).where(Listing.id == body.listing_id).with_for_update()
    )
    if listing is None or listing.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if body.guests > listing.capacity:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Exceeds listing capacity")
    if not is_available(db, listing.id, body.check_in, body.check_out):
        raise HTTPException(status.HTTP_409_CONFLICT, "Dates are not available")

    nights = (body.check_out - body.check_in).days
    total = nights * listing.nightly_price_amount

    booking = Booking(
        listing_id=listing.id,
        guest_id=user.id,
        check_in=body.check_in,
        check_out=body.check_out,
        guests=body.guests,
        total_amount=total,
        currency=listing.currency,
        idempotency_key=idempotency_key,
    )
    db.add(booking)
    try:
        db.flush()  # excl_booking_overlap (Postgres) fires here on a lost race
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Dates are not available") from None
    payment = payments_service.create_payment_for_booking(db, booking, listing.host_id)
    audit(
        db,
        actor=user.id,
        action="booking.created",
        entity_type="booking",
        entity_id=booking.id,
        data={"total": total, "currency": listing.currency, "nights": nights},
    )
    db.commit()
    return _booking_out(booking, payment)


@router.get("/bookings", response_model=list[BookingOut])
def my_bookings(user=Depends(get_current_user), db: Session = Depends(get_db)):
    bookings = list(
        db.scalars(
            select(Booking)
            .where(Booking.guest_id == user.id)
            .order_by(Booking.created_at.desc())
        )
    )
    result = []
    for b in bookings:
        payment = db.scalar(select(Payment).where(Payment.booking_id == b.id))
        result.append(_booking_out(b, payment))
    return result


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    listing = db.get(Listing, booking.listing_id)
    is_party = user.id in (booking.guest_id, listing.host_id if listing else None)
    if not is_party and user.role != "admin":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    payment = db.scalar(select(Payment).where(Payment.booking_id == booking.id))
    return _booking_out(booking, payment)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    booking = db.get(Booking, booking_id)
    if booking is None or (booking.guest_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status not in ("pending", "confirmed"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Booking is not cancellable")
    if booking.status == "confirmed" and booking.check_in <= date.today():
        raise HTTPException(status.HTTP_409_CONFLICT, "Stay already started")

    payment = payments_service.refund_booking(db, booking, actor=user.id)
    booking.status = "cancelled"
    audit(db, actor=user.id, action="booking.cancelled", entity_type="booking", entity_id=booking.id)
    db.commit()
    return _booking_out(booking, payment)


@router.post("/bookings/{booking_id}/complete", response_model=BookingOut)
def complete_booking(
    booking_id: str, user=Depends(require_role("admin")), db: Session = Depends(get_db)
):
    """Stay finished (real system: timer at check_out + N hours; D4: admin action)."""
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status != "confirmed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only confirmed bookings can complete")
    booking.status = "completed"
    audit(db, actor=user.id, action="booking.completed", entity_type="booking", entity_id=booking.id)
    db.commit()
    payment = db.scalar(select(Payment).where(Payment.booking_id == booking.id))
    return _booking_out(booking, payment)


@router.get("/listings/{listing_id}/availability", response_model=AvailabilityOut)
def get_availability(
    listing_id: str,
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    db: Session = Depends(get_db),
):
    listing = db.get(Listing, listing_id)
    if listing is None or listing.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if date_to <= date_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "to must be after from")
    if (date_to - date_from).days > MAX_AVAILABILITY_WINDOW_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Window too large")

    ranges = blocked_ranges(db, listing_id, date_from, date_to)
    days: list[DayStatus] = []
    day = date_from
    while day < date_to:
        day_status = "available"
        for start, end, kind in ranges:
            if start <= day < end:
                day_status = kind
                break
        days.append(DayStatus(date=day, status=day_status))
        day += timedelta(days=1)
    return AvailabilityOut(listing_id=listing_id, days=days)
