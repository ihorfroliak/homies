"""Viewings: when a flat can be seen, and who is coming (Domain Schema v1 §57–§60).

The provider says when viewings are possible — weekly windows and one-off
dates, in the listing's own time zone — and blocks out times it cannot. The
service turns that into concrete slots. A tenant requests one; the provider
confirms it, or it is confirmed at once if the listing takes instant bookings.

Two rules carry the weight:

* A request must be for a slot the provider actually offers. A viewing is a
  stranger at someone's door; the time is the provider's to set, not the
  requester's to invent.
* Capacity is checked where it can race. Two tenants confirming the last
  place in the same slot at the same moment would both see it free; the
  listing's settings row is locked for the check, so one of them waits and
  then sees it taken (§60 leaves overlap to the application transaction).

Times are stored as UTC instants. Local wall-clock times exist only in the
windows, and are resolved through the zone's own rules, so a window of 10:00
stays 10:00 across the change to and from summer time.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import get_current_user
from app.modules.engagement.models import (
    Viewing,
    ViewingBlackout,
    ViewingSettings,
    ViewingWindow,
)
from app.modules.identity.models import User
from app.modules.properties import authority
from app.modules.properties.models import ClassifiedOffer

router = APIRouter(tags=["viewings"])

HELD = ("REQUESTED", "CONFIRMED")
MAX_SLOT_DAYS = 31


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --- schemas ------------------------------------------------------------------


class SettingsIn(BaseModel):
    booking_mode: Literal["INSTANT_BOOKING", "REQUEST_APPROVAL"] = "REQUEST_APPROVAL"
    timezone: str = "Europe/Warsaw"
    duration_minutes: int = Field(default=30, ge=10, le=240)
    minimum_notice_minutes: int = Field(default=120, ge=0, le=60 * 24 * 14)
    buffer_before_minutes: int = Field(default=0, ge=0, le=240)
    buffer_after_minutes: int = Field(default=0, ge=0, le=240)
    max_concurrent_bookings: int = Field(default=1, ge=1, le=20)
    enabled: bool = True

    @field_validator("timezone")
    @classmethod
    def real_zone(cls, v: str) -> str:
        """An IANA name, never an offset: "UTC+1" is wrong half the year in
        Poland, and every slot would be an hour off from April to October."""
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("timezone must be an IANA zone such as Europe/Warsaw") from None
        return v


class SettingsOut(SettingsIn):
    listing_id: str


class WindowIn(BaseModel):
    window_type: Literal["WEEKLY", "ONE_OFF"]
    weekday: int | None = Field(default=None, ge=0, le=6)
    local_date: date | None = None
    local_start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    local_end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def shape(self):
        if self.local_end_time <= self.local_start_time:
            raise ValueError("local_end_time must be after local_start_time")
        if self.window_type == "WEEKLY" and (self.weekday is None or self.local_date):
            raise ValueError("a WEEKLY window needs a weekday and no date")
        if self.window_type == "ONE_OFF" and (self.local_date is None or self.weekday is not None):
            raise ValueError("a ONE_OFF window needs a date and no weekday")
        return self


class WindowOut(BaseModel):
    id: str
    window_type: str
    weekday: int | None
    local_date: date | None
    local_start_time: str
    local_end_time: str


class BlackoutIn(BaseModel):
    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def order(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class ViewingRequest(BaseModel):
    starts_at: datetime
    attendee_count: int = Field(default=1, ge=1, le=10)
    note: str | None = Field(default=None, max_length=1000)


class ViewingOut(BaseModel):
    id: str
    listing_id: str
    starts_at: datetime
    ends_at: datetime
    status: str
    attendee_count: int

    model_config = {"from_attributes": True}


class ProviderViewingOut(ViewingOut):
    requester_user_id: str
    requester_note: str | None


class OutcomeIn(BaseModel):
    outcome: Literal["COMPLETED", "NO_SHOW"]


# --- access -------------------------------------------------------------------


def _listing(db: Session, listing_id: str) -> ClassifiedOffer:
    offer = db.get(ClassifiedOffer, listing_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return offer


def _provider_listing(db: Session, user: User, listing_id: str) -> ClassifiedOffer:
    offer = _listing(db, listing_id)
    if not authority.can_act(db, user.id, offer.property_id, "MANAGE_VIEWINGS", verified=False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return offer


def _is_provider(db: Session, user: User, offer: ClassifiedOffer) -> bool:
    return authority.can_act(db, user.id, offer.property_id, "MANAGE_VIEWINGS", verified=False)


# --- slots --------------------------------------------------------------------


def _hm(value: str):
    hours, minutes = value.split(":")
    return int(hours), int(minutes)


def _windows_for(windows: list[ViewingWindow], day: date) -> list[ViewingWindow]:
    out = []
    for w in windows:
        if w.valid_from and day < w.valid_from:
            continue
        if w.valid_until and day > w.valid_until:
            continue
        if w.window_type == "WEEKLY" and w.weekday == day.weekday():
            out.append(w)
        elif w.window_type == "ONE_OFF" and w.local_date == day:
            out.append(w)
    return out


def _held_overlapping(db: Session, listing_id: str, start: datetime, end: datetime,
                      statuses=("CONFIRMED",), exclude_id: str | None = None) -> int:
    query = select(func.count()).select_from(Viewing).where(
        Viewing.listing_id == listing_id,
        Viewing.status.in_(statuses),
        Viewing.starts_at < end,
        Viewing.ends_at > start,
    )
    if exclude_id:
        query = query.where(Viewing.id != exclude_id)
    return db.scalar(query) or 0


def slots(db: Session, settings: ViewingSettings, first: date, days: int) -> list[datetime]:
    """Offered slot start times (UTC), in order."""
    if not settings.enabled:
        return []
    zone = ZoneInfo(settings.timezone)
    step = timedelta(minutes=settings.duration_minutes)
    earliest = _now() + timedelta(minutes=settings.minimum_notice_minutes)
    windows = list(db.scalars(select(ViewingWindow).where(
        ViewingWindow.listing_id == settings.listing_id)))
    blackouts = [(_aware(b.starts_at), _aware(b.ends_at)) for b in db.scalars(
        select(ViewingBlackout).where(ViewingBlackout.listing_id == settings.listing_id))]
    # Every viewing, booked or candidate, keeps its buffers clear. Two such
    # padded intervals overlap exactly when the candidate, widened by BOTH
    # buffers on each side, overlaps the booked viewing as stored. Widening the
    # candidate by its own buffers only would miss the booked viewing's
    # after-buffer and offer the slot straight after it.
    clearance = timedelta(
        minutes=settings.buffer_before_minutes + settings.buffer_after_minutes
    )

    found: list[datetime] = []
    for offset in range(days):
        day = first + timedelta(days=offset)
        for w in _windows_for(windows, day):
            sh, sm = _hm(w.local_start_time.strftime("%H:%M"))
            eh, em = _hm(w.local_end_time.strftime("%H:%M"))
            cursor = datetime(day.year, day.month, day.day, sh, sm, tzinfo=zone)
            end_local = datetime(day.year, day.month, day.day, eh, em, tzinfo=zone)
            while cursor + step <= end_local:
                start = cursor.astimezone(timezone.utc)
                end = start + step
                cursor += step
                if start < earliest:
                    continue
                if any(start < b_end and end > b_start for b_start, b_end in blackouts):
                    continue
                if _held_overlapping(db, settings.listing_id, start - clearance,
                                     end + clearance) >= settings.max_concurrent_bookings:
                    continue
                found.append(start)
    return sorted(set(found))


def _settings(db: Session, listing_id: str, lock: bool = False) -> ViewingSettings | None:
    query = select(ViewingSettings).where(ViewingSettings.listing_id == listing_id)
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


# --- provider configuration ---------------------------------------------------


@router.put("/classifieds/{listing_id}/viewing-settings", response_model=SettingsOut)
def put_settings(listing_id: str, body: SettingsIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _provider_listing(db, user, listing_id)
    current = _settings(db, listing_id)
    if current is None:
        current = ViewingSettings(listing_id=listing_id)
        db.add(current)
    else:
        current.version += 1
    for field, value in body.model_dump().items():
        setattr(current, field, value)
    db.commit()
    return SettingsOut(listing_id=listing_id, **body.model_dump())


@router.post("/classifieds/{listing_id}/viewing-windows", response_model=WindowOut,
             status_code=201)
def add_window(listing_id: str, body: WindowIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    from datetime import time as clock

    _provider_listing(db, user, listing_id)
    sh, sm = _hm(body.local_start_time)
    eh, em = _hm(body.local_end_time)
    window = ViewingWindow(
        listing_id=listing_id, window_type=body.window_type, weekday=body.weekday,
        local_date=body.local_date, local_start_time=clock(sh, sm),
        local_end_time=clock(eh, em), valid_from=body.valid_from, valid_until=body.valid_until,
    )
    db.add(window)
    db.commit()
    return WindowOut(id=window.id, window_type=window.window_type, weekday=window.weekday,
                     local_date=window.local_date, local_start_time=body.local_start_time,
                     local_end_time=body.local_end_time)


@router.post("/classifieds/{listing_id}/viewing-blackouts", status_code=201)
def add_blackout(listing_id: str, body: BlackoutIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _provider_listing(db, user, listing_id)
    blackout = ViewingBlackout(listing_id=listing_id, starts_at=body.starts_at,
                               ends_at=body.ends_at, reason=body.reason)
    db.add(blackout)
    db.commit()
    return {"id": blackout.id}


# --- slots and requests -------------------------------------------------------


@router.get("/classifieds/{listing_id}/viewing-slots")
def list_slots(listing_id: str, start: date | None = None,
               days: int = Query(default=14, ge=1, le=MAX_SLOT_DAYS),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    offer = _listing(db, listing_id)
    if offer.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    settings = _settings(db, listing_id)
    if settings is None:
        return {"slots": [], "duration_minutes": None}
    first = start or _now().astimezone(ZoneInfo(settings.timezone)).date()
    return {"slots": slots(db, settings, first, days),
            "duration_minutes": settings.duration_minutes}


@router.post("/classifieds/{listing_id}/viewings", response_model=ViewingOut,
             status_code=201)
def request_viewing(listing_id: str, body: ViewingRequest,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    offer = _listing(db, listing_id)
    if offer.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    if _is_provider(db, user, offer):
        raise HTTPException(status.HTTP_409_CONFLICT, "This is your own listing")
    # Locked: capacity is read and then relied on, and two requests for the
    # last place must not both read it free.
    settings = _settings(db, listing_id, lock=True)
    if settings is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This listing takes no viewings yet")

    starts_at = _aware(body.starts_at).astimezone(timezone.utc)
    local_day = starts_at.astimezone(ZoneInfo(settings.timezone)).date()
    if starts_at not in slots(db, settings, local_day, 1):
        raise HTTPException(status.HTTP_409_CONFLICT, "That time is not an offered slot")

    already = db.scalar(select(Viewing.id).where(
        Viewing.listing_id == listing_id, Viewing.requester_user_id == user.id,
        Viewing.status.in_(HELD), Viewing.ends_at > _now()))
    if already is not None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "You already have a viewing of this flat booked")

    instant = settings.booking_mode == "INSTANT_BOOKING"
    viewing = Viewing(
        listing_id=listing_id, requester_user_id=user.id, starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=settings.duration_minutes),
        status="CONFIRMED" if instant else "REQUESTED",
        attendee_count=body.attendee_count, requester_note=body.note,
        responded_at=_now() if instant else None,
    )
    db.add(viewing)
    db.flush()
    audit(db, actor=user.id, action="viewing.requested", entity_type="viewing",
          entity_id=viewing.id)
    db.commit()
    return viewing


def _viewing_for(db: Session, user: User, viewing_id: str) -> tuple[Viewing, bool]:
    """(viewing, caller_is_provider). 404 for anyone who is neither side."""
    viewing = db.get(Viewing, viewing_id)
    if viewing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Viewing not found")
    offer = _listing(db, viewing.listing_id)
    provider = _is_provider(db, user, offer)
    if not provider and viewing.requester_user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Viewing not found")
    return viewing, provider


def _respond(db: Session, user: User, viewing_id: str, confirm: bool) -> Viewing:
    viewing, provider = _viewing_for(db, user, viewing_id)
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Viewing not found")
    if viewing.status != "REQUESTED":
        raise HTTPException(status.HTTP_409_CONFLICT, f"The viewing is {viewing.status}")
    if confirm:
        settings = _settings(db, viewing.listing_id, lock=True)
        if _aware(viewing.starts_at) <= _now():
            raise HTTPException(status.HTTP_409_CONFLICT, "That viewing time has passed")
        capacity = settings.max_concurrent_bookings if settings else 1
        clearance = timedelta(minutes=(
            settings.buffer_before_minutes + settings.buffer_after_minutes) if settings else 0)
        taken = _held_overlapping(db, viewing.listing_id,
                                  _aware(viewing.starts_at) - clearance,
                                  _aware(viewing.ends_at) + clearance, exclude_id=viewing.id)
        if taken >= capacity:
            raise HTTPException(status.HTTP_409_CONFLICT, "That slot is already full")
    viewing.status = "CONFIRMED" if confirm else "DECLINED"
    viewing.responded_at = _now()
    viewing.confirmed_by_user_id = user.id if confirm else None
    viewing.version += 1
    audit(db, actor=user.id, action=f"viewing.{viewing.status.lower()}",
          entity_type="viewing", entity_id=viewing.id)
    db.commit()
    return viewing


@router.post("/viewings/{viewing_id}/confirm", response_model=ViewingOut)
def confirm(viewing_id: str, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    return _respond(db, user, viewing_id, confirm=True)


@router.post("/viewings/{viewing_id}/decline", response_model=ViewingOut)
def decline(viewing_id: str, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    return _respond(db, user, viewing_id, confirm=False)


@router.post("/viewings/{viewing_id}/cancel", response_model=ViewingOut)
def cancel(viewing_id: str, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """Either side may call it off before it happens."""
    viewing, _ = _viewing_for(db, user, viewing_id)
    if viewing.status not in HELD:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The viewing is {viewing.status}")
    viewing.status = "CANCELLED"
    viewing.cancelled_at = _now()
    viewing.version += 1
    audit(db, actor=user.id, action="viewing.cancelled", entity_type="viewing",
          entity_id=viewing.id)
    db.commit()
    return viewing


@router.post("/viewings/{viewing_id}/outcome", response_model=ViewingOut)
def record_outcome(viewing_id: str, body: OutcomeIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """What happened, recorded by the provider once the time has come."""
    viewing, provider = _viewing_for(db, user, viewing_id)
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Viewing not found")
    if viewing.status != "CONFIRMED":
        raise HTTPException(status.HTTP_409_CONFLICT, f"The viewing is {viewing.status}")
    if _aware(viewing.starts_at) > _now():
        raise HTTPException(status.HTTP_409_CONFLICT, "The viewing has not happened yet")
    viewing.status = body.outcome
    viewing.completed_at = _now()
    viewing.version += 1
    db.commit()
    return viewing


@router.get("/classifieds/{listing_id}/viewings", response_model=list[ProviderViewingOut])
def provider_viewings(listing_id: str, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _provider_listing(db, user, listing_id)
    return list(db.scalars(select(Viewing).where(Viewing.listing_id == listing_id)
                           .order_by(Viewing.starts_at)))


@router.get("/me/viewings", response_model=list[ViewingOut])
def my_viewings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Viewing).where(Viewing.requester_user_id == user.id)
                           .order_by(Viewing.starts_at)))

