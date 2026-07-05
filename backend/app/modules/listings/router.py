from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import require_role
from app.modules.listings.models import HostBlock, Listing
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
    listing = Listing(host_id=user.id, **body.model_dump())
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
    _owned_listing(db, listing_id, user.id)
    block = HostBlock(listing_id=listing_id, start_date=body.start_date, end_date=body.end_date)
    db.add(block)
    db.commit()
    return {"id": block.id}
