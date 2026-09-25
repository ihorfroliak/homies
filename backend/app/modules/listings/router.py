from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import require_role
from app.modules.listings.models import HostBlock, Listing
from app.modules.properties.models import Property
from app.modules.listings.schemas import (
    BlockCreate,
    ListingCreate,
    ListingOut,
    ListingUpdate,
)

router = APIRouter(tags=["listings"])


def _owned_listing(db: Session, listing_id: str, host_id: str) -> Listing:
    listing = db.get(Listing, listing_id)
    if listing is None or listing.host_id != host_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    return listing


@router.post("/listings", response_model=ListingOut, status_code=201)
def create_listing(
    body: ListingCreate,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    # Every listing offers a physical object. Callers that already created a
    # Property pass its id; the rest get one derived from the listing body.
    #
    # The derivation is transitional. It exists so this change could move the
    # calendar without rewriting fifteen test modules and every client at the
    # same time, and it carries only what a listing actually knows — type,
    # gmina, area and room count stay empty rather than invented. When listings
    # become offers, the shim goes and property_id becomes required.
    data = body.model_dump()
    property_id = data.pop("property_id", None)
    if property_id is not None:
        prop = db.get(Property, property_id)
        if prop is None or prop.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found")
    else:
        # TASK-010: every Property has an Address. This dormant short-stay path
        # (Poland-only when it ran) records the typed text, UNSTRUCTURED — a
        # schema-compatibility change, not an extension of the legacy runtime.
        from app.modules.geography.models import Address

        address = Address(country_code="PL", unstructured_text=data["address"],
                          locality_text=data["city"], resolution="UNSTRUCTURED",
                          source="USER_INPUT", verification="UNVERIFIED")
        db.add(address)
        db.flush()
        prop = Property(
            owner_id=user.id,
            address_id=address.id,
            city=data["city"],
            address=data["address"],
            capacity=data["capacity"],
        )
        db.add(prop)
        db.flush()

    listing = Listing(host_id=user.id, property_id=prop.id, **data)
    db.add(listing)
    db.flush()
    audit(db, actor=user.id, action="listing.created", entity_type="listing", entity_id=listing.id)
    db.commit()
    return listing


@router.patch("/listings/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: str,
    body: ListingUpdate,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    listing = _owned_listing(db, listing_id, user.id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(listing, field, value)
    db.commit()
    return listing


@router.post("/listings/{listing_id}/publish", response_model=ListingOut)
def publish_listing(
    listing_id: str,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    listing = _owned_listing(db, listing_id, user.id)
    if listing.status not in ("draft", "active"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Listing is not publishable")
    listing.status = "active"
    audit(
        db, actor=user.id, action="listing.published", entity_type="listing", entity_id=listing.id
    )
    db.commit()
    return listing


@router.get("/listings", response_model=list[ListingOut])
def search_listings(
    city: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = select(Listing).where(Listing.status == "active")
    if city:
        q = q.where(Listing.city.ilike(city))
    return list(db.scalars(q.order_by(Listing.created_at.desc()).limit(limit).offset(offset)))


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: str, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if listing is None or listing.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    return listing


@router.post("/listings/{listing_id}/blocks", status_code=201)
def create_block(
    listing_id: str,
    body: BlockCreate,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    listing = _owned_listing(db, listing_id, user.id)
    # Blocked on the property: a flat closed for renovation is unavailable in
    # every mode it is offered in, not just the listing the host happened to
    # open.
    block = HostBlock(
        listing_id=listing_id,
        property_id=listing.property_id,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(block)
    db.commit()
    return {"id": block.id}
