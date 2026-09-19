"""Properties and the free long-term classifieds board.

Homies is not a party to anything on this board: no booking, no payment, no
deposit, no dispute resolution. The only thing the platform does here is connect
two people and protect the owner's phone number while doing it.

That protection is the security-relevant part of this module:

* the public response shape (`ClassifiedOut`) has no phone field, so a leak
  needs someone to deliberately add one back;
* the number is disclosed only through `POST /classifieds/{id}/contact`, which
  requires an authenticated account;
* every disclosure is recorded in `ContactReveal`, which is what makes a daily
  quota, an owner-facing "who asked for my number" view, and a scraping signal
  possible later. Recording from day one costs nothing; reconstructing it
  afterwards is impossible.

Known gap, stated rather than hidden: PRODUCT_MODEL requires a *verified* email
and phone before a reveal. Verification does not exist yet, so the gate today is
only authentication. That is strictly better than public, and weaker than the
target — it must close before the board is advertised.
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.modules.properties.models import ClassifiedOffer, ContactReveal, Property
from app.modules.properties.schemas import (
    ClassifiedCreate,
    ClassifiedOut,
    ClassifiedPage,
    ContactRevealOut,
    PropertyCreate,
    PropertyOut,
)

router = APIRouter(tags=["properties"])


def _monthly_total(offer: ClassifiedOffer) -> int:
    """What the tenant pays each month, deposit excluded (it is returned)."""
    total = offer.rent_amount + offer.admin_fee + offer.parking_fee
    if not offer.utilities_included:
        total += offer.utilities_amount
    return total


def _public(offer: ClassifiedOffer) -> ClassifiedOut:
    return ClassifiedOut(
        **{
            k: getattr(offer, k)
            for k in ClassifiedOut.model_fields
            if k != "monthly_total_estimate"
        },
        monthly_total_estimate=_monthly_total(offer),
    )


def _owned_property(db: Session, property_id: str, owner_id: str) -> Property:
    prop = db.get(Property, property_id)
    # 404 rather than 403 for someone else's property: an authorization error
    # that distinguishes "not yours" from "does not exist" is an enumeration
    # oracle.
    if prop is None or prop.owner_id != owner_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found")
    return prop


def _owned_offer(db: Session, offer_id: str, owner_id: str) -> ClassifiedOffer:
    offer = db.get(ClassifiedOffer, offer_id)
    if offer is None or offer.owner_id != owner_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return offer


# --- properties ---------------------------------------------------------------


@router.post("/properties", response_model=PropertyOut, status_code=201)
def create_property(
    body: PropertyCreate,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    """Register a physical object. It exists once, whatever is later done with it.

    `municipality` (gmina) is required: the Polish tourist tax is set per gmina
    and charged per night, so a short-stay price cannot be computed without it.
    """
    prop = Property(owner_id=user.id, **body.model_dump())
    db.add(prop)
    db.flush()
    audit(db, actor=user.id, action="property.created", entity_type="property", entity_id=prop.id)
    db.commit()
    return prop


@router.get("/properties", response_model=list[PropertyOut])
def my_properties(user=Depends(require_role("host")), db: Session = Depends(get_db)):
    return list(db.scalars(select(Property).where(Property.owner_id == user.id)))


# --- classifieds (free long-term board) ---------------------------------------


@router.post("/properties/{property_id}/classifieds", response_model=ClassifiedOut, status_code=201)
def create_classified(
    property_id: str,
    body: ClassifiedCreate,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    """Post a free long-term listing against one of your properties.

    The board starts at six months. Anything shorter is a Homies booking — paid
    and commissioned — and must not arrive here relabelled.
    """
    prop = _owned_property(db, property_id, user.id)
    offer = ClassifiedOffer(property_id=prop.id, owner_id=user.id, **body.model_dump())
    db.add(offer)
    db.flush()
    audit(
        db,
        actor=user.id,
        action="classified.created",
        entity_type="classified_offer",
        entity_id=offer.id,
    )
    db.commit()
    return _public(offer)


@router.post("/classifieds/{offer_id}/publish", response_model=ClassifiedOut)
def publish_classified(
    offer_id: str,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    offer = _owned_offer(db, offer_id, user.id)
    offer.status = "active"
    offer.published_at = datetime.now(timezone.utc)
    audit(
        db,
        actor=user.id,
        action="classified.published",
        entity_type="classified_offer",
        entity_id=offer.id,
    )
    db.commit()
    return _public(offer)


@router.post("/classifieds/{offer_id}/pause", response_model=ClassifiedOut)
def pause_classified(
    offer_id: str,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    offer = _owned_offer(db, offer_id, user.id)
    offer.status = "paused"
    db.commit()
    return _public(offer)


# Sorting is an allowlist, never a column name from the query string. Passing
# user input into order_by() exposes every column in the table and, with a
# string-built query, worse.
SORTS = {
    "newest": ClassifiedOffer.published_at.desc(),
    "price_asc": None,  # filled in below: the total, not the rent
    "price_desc": None,
    "size_desc": Property.area_m2.desc(),
}


def _monthly_total_sql():
    """The tenant's real monthly cost, as SQL, so it can be filtered and sorted.

    Deliberately not `rent_amount`. Two offers at 3 000 zł rent are not the same
    price when one adds 600 zł of building fees and the other does not, and a
    tenant who filters "up to 3 000" and is shown a 3 600 zł flat has been
    misled by the search, not by the owner. The deposit is excluded — it comes
    back.
    """
    utilities = case(
        (ClassifiedOffer.utilities_included.is_(True), 0),
        else_=ClassifiedOffer.utilities_amount,
    )
    return ClassifiedOffer.rent_amount + ClassifiedOffer.admin_fee + (
        ClassifiedOffer.parking_fee + utilities
    )


@router.get("/classifieds", response_model=ClassifiedPage)
def list_classifieds(
    city: str | None = None,
    district: str | None = None,
    # Budget is expressed against the TOTAL, which is what the tenant pays.
    max_monthly_total: int | None = Query(default=None, ge=0),
    min_monthly_total: int | None = Query(default=None, ge=0),
    min_rooms: int | None = Query(default=None, ge=0),
    min_area_m2: int | None = Query(default=None, ge=0),
    furnished: str | None = None,
    parking: str | None = None,
    pets_allowed: bool | None = None,
    has_elevator: bool | None = None,
    # "I can move by this date" — offers available then or sooner, plus those
    # with no date set, which means available now.
    available_by: date | None = None,
    max_term_months: int | None = Query(default=None, ge=0),
    sort: str = "newest",
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Search the free board. Only active offers, and never a phone number."""
    if sort not in SORTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"sort must be one of {', '.join(sorted(SORTS))}",
        )

    total_expr = _monthly_total_sql()
    filters = [ClassifiedOffer.status == "active"]
    if city:
        filters.append(Property.city == city)
    if district:
        filters.append(Property.district == district)
    if max_monthly_total is not None:
        filters.append(total_expr <= max_monthly_total)
    if min_monthly_total is not None:
        filters.append(total_expr >= min_monthly_total)
    if min_rooms is not None:
        filters.append(Property.rooms >= min_rooms)
    if min_area_m2 is not None:
        filters.append(Property.area_m2 >= min_area_m2)
    if furnished:
        filters.append(Property.furnished == furnished)
    if parking:
        filters.append(Property.parking == parking)
    if pets_allowed is not None:
        filters.append(Property.pets_allowed.is_(pets_allowed))
    if has_elevator is not None:
        filters.append(Property.has_elevator.is_(has_elevator))
    if available_by is not None:
        # A missing date means "available now", so it must not be filtered out.
        filters.append(
            or_(
                ClassifiedOffer.available_from.is_(None),
                ClassifiedOffer.available_from <= available_by,
            )
        )
    if max_term_months is not None:
        # An open-ended offer commits the tenant to nothing, so it satisfies any
        # "I can stay at most N months" filter.
        filters.append(
            or_(
                ClassifiedOffer.open_ended.is_(True),
                ClassifiedOffer.min_term_months <= max_term_months,
            )
        )

    base = select(ClassifiedOffer).join(
        Property, Property.id == ClassifiedOffer.property_id
    ).where(*filters)

    order = SORTS[sort]
    if sort == "price_asc":
        order = total_expr.asc()
    elif sort == "price_desc":
        order = total_expr.desc()

    total = db.scalar(
        select(func.count())
        .select_from(ClassifiedOffer)
        .join(Property, Property.id == ClassifiedOffer.property_id)
        .where(*filters)
    )
    rows = db.scalars(base.order_by(order).limit(limit).offset(offset))
    return ClassifiedPage(
        items=[_public(o) for o in rows],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get("/classifieds/{offer_id}", response_model=ClassifiedOut)
def get_classified(offer_id: str, db: Session = Depends(get_db)):
    offer = db.get(ClassifiedOffer, offer_id)
    if offer is None or offer.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return _public(offer)


@router.post("/classifieds/{offer_id}/contact", response_model=ContactRevealOut)
def reveal_contact(
    offer_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disclose the owner's phone number to a signed-in account, and record it.

    Sign-in is the gate that makes bulk collection attributable: a scraper has
    to hold an account, and every number it takes leaves a row with its name on
    it. Anonymous visitors get the message channel instead.
    """
    offer = db.get(ClassifiedOffer, offer_id)
    if offer is None or offer.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    if offer.contact_mode != "phone" or not offer.contact_phone:
        # The owner chose messages. Saying so is not a leak, and pretending the
        # offer does not exist would be a lie.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This owner accepts messages only, not phone calls"
        )

    db.add(ContactReveal(offer_id=offer.id, viewer_id=user.id))
    try:
        db.flush()
    except IntegrityError:
        # Same viewer asking twice. Not a second disclosure — they already have
        # the number — so keep one row and do not inflate the risk signal.
        db.rollback()
    else:
        audit(
            db,
            actor=user.id,
            action="classified.contact_revealed",
            entity_type="classified_offer",
            entity_id=offer.id,
        )
        db.commit()
    return ContactRevealOut(offer_id=offer.id, contact_phone=offer.contact_phone)
