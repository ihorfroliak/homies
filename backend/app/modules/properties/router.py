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

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.modules.properties.models import ClassifiedOffer, ContactReveal, Property
from app.modules.properties.schemas import (
    ClassifiedCreate,
    ClassifiedOut,
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


@router.get("/classifieds", response_model=list[ClassifiedOut])
def list_classifieds(
    city: str | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Public board. Only active offers, and never a phone number."""
    stmt = (
        select(ClassifiedOffer)
        .join(Property, Property.id == ClassifiedOffer.property_id)
        .where(ClassifiedOffer.status == "active")
        .order_by(ClassifiedOffer.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if city:
        stmt = stmt.where(Property.city == city)
    return [_public(o) for o in db.scalars(stmt)]


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
