"""Uploading, moderating, attaching and serving property photos (Schema v1 §36–§38, §48, §121).

The lifecycle of a photo:

1. An owner (MANAGE_MEDIA on the property) uploads raw image bytes and
   declares the right to publish them. The bytes are proved to be JPEG or
   PNG and rebuilt without their metadata (sanitize.py) before anything is
   stored; a file that fails is never written anywhere.
2. The asset waits in PENDING until an admin approves it. Nothing pending is
   ever shown to the public.
3. The owner attaches approved photos to a listing, in order, with at most
   one cover.
4. The public fetches a photo only through `GET /v1/media/{asset_id}`, which
   serves it only while it is approved and on at least one active listing.
   Knowing an id is not access; a photo taken off every listing stops being
   served.
"""

import hashlib
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.modules.identity.models import User
from app.modules.media import sanitize, storage
from app.modules.media.models import FileObject, ListingMedia, MediaAsset
from app.modules.properties import authority
from app.modules.properties.models import ClassifiedOffer, Space

router = APIRouter(tags=["media"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MediaAssetOut(BaseModel):
    id: str
    property_id: str
    space_id: str | None
    media_type: str
    moderation_state: str
    width_px: int | None
    height_px: int | None
    size_bytes: int | None
    mime_type: str | None
    created_at: datetime


class AttachIn(BaseModel):
    media_asset_id: str
    sort_order: int = Field(default=0, ge=0, le=1000)
    is_cover: bool = False


def _out(asset: MediaAsset) -> MediaAssetOut:
    return MediaAssetOut(
        id=asset.id, property_id=asset.property_id, space_id=asset.space_id,
        media_type=asset.media_type, moderation_state=asset.moderation_state,
        width_px=asset.width_px, height_px=asset.height_px,
        size_bytes=asset.file.size_bytes, mime_type=asset.file.mime_type,
        created_at=asset.created_at,
    )


# --- upload -------------------------------------------------------------------


@router.post("/properties/{property_id}/media", response_model=MediaAssetOut, status_code=201)
async def upload_media(
    property_id: str,
    request: Request,
    media_type: Literal["PHOTO", "FLOOR_PLAN"] = Query(default="PHOTO"),
    space_id: str | None = None,
    rights_declared: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload an image as the raw request body.

    `rights_declared=true` is required: the uploader states they may publish
    it. Video and 360° tours are in the model but not accepted yet — they
    need a processing pipeline this service does not have.
    """
    authority.require(db, user, property_id, "MANAGE_MEDIA")
    if not rights_declared:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Confirm you have the right to publish this image")
    if space_id is not None:
        space = db.get(Space, space_id)
        if space is None or space.property_id != property_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Space not found")

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.media_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large")
    raw = await request.body()
    if len(raw) > settings.media_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large")
    try:
        clean = sanitize.sanitize(raw)
    except sanitize.RejectedImage as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None

    backend = storage.storage()
    file = FileObject(
        uploader_user_id=user.id, purpose="PROPERTY_MEDIA", storage_provider=backend.provider,
        storage_bucket=backend.bucket, storage_key="pending", access_class="PRIVATE",
        mime_type=clean.mime_type, size_bytes=len(clean.data),
        sha256=hashlib.sha256(clean.data).hexdigest(), state="PROCESSING",
    )
    db.add(file)
    db.flush()
    # The key is the file's own id: nothing the uploader typed reaches a path.
    file.storage_key = f"property-media/{file.id}"
    backend.put(file.storage_key, clean.data)
    file.state = "READY"
    file.ready_at = _now()

    asset = MediaAsset(
        property_id=property_id, space_id=space_id, file_id=file.id, media_type=media_type,
        moderation_state="PENDING", width_px=clean.width, height_px=clean.height,
        rights_declared_at=_now(),
    )
    db.add(asset)
    db.flush()
    audit(db, actor=user.id, action="media.uploaded", entity_type="media_asset",
          entity_id=asset.id)
    db.commit()
    db.refresh(asset)
    return _out(asset)


@router.get("/properties/{property_id}/media", response_model=list[MediaAssetOut])
def list_media(property_id: str, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    authority.require(db, user, property_id, "MANAGE_MEDIA")
    return [_out(a) for a in db.scalars(
        select(MediaAsset).where(MediaAsset.property_id == property_id,
                                 MediaAsset.archived_at.is_(None))
        .order_by(MediaAsset.created_at))]


# --- moderation ---------------------------------------------------------------


def _moderate(db: Session, asset_id: str, admin: User, state: str) -> MediaAsset:
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media not found")
    asset.moderation_state = state
    file = db.get(FileObject, asset.file_id)
    assert file is not None
    file.access_class = "PUBLIC" if state == "APPROVED" else "PRIVATE"
    if state != "APPROVED":
        # A rejected photo comes off every listing it was on, cover included.
        for link in db.scalars(select(ListingMedia).where(ListingMedia.media_asset_id == asset.id)):
            db.delete(link)
    audit(db, actor=admin.id, action=f"media.{state.lower()}", entity_type="media_asset",
          entity_id=asset.id)
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/admin/media/{asset_id}/approve", response_model=MediaAssetOut)
def approve(asset_id: str, admin: User = Depends(require_role("admin")),
            db: Session = Depends(get_db)):
    return _out(_moderate(db, asset_id, admin, "APPROVED"))


@router.post("/admin/media/{asset_id}/reject", response_model=MediaAssetOut)
def reject(asset_id: str, admin: User = Depends(require_role("admin")),
           db: Session = Depends(get_db)):
    return _out(_moderate(db, asset_id, admin, "REJECTED"))


# --- listing media ------------------------------------------------------------


def _owned_offer(db: Session, user: User, offer_id: str) -> ClassifiedOffer:
    offer = db.get(ClassifiedOffer, offer_id)
    if offer is None or not authority.can_act(db, user.id, offer.property_id, "MANAGE_MEDIA",
                                              verified=False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return offer


@router.post("/classifieds/{offer_id}/media", status_code=201)
def attach(offer_id: str, body: AttachIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """Put an approved photo of this property on this listing."""
    offer = _owned_offer(db, user, offer_id)
    asset = db.get(MediaAsset, body.media_asset_id)
    if asset is None or asset.property_id != offer.property_id or asset.archived_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media not found")
    if asset.moderation_state != "APPROVED" or asset.file.state != "READY":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only approved photos can be shown")

    existing = db.get(ListingMedia, (offer.id, asset.id))
    if body.is_cover:
        # The new cover replaces the old one in the same transaction, so the
        # listing is never without one and never has two.
        for link in db.scalars(select(ListingMedia).where(
                ListingMedia.listing_id == offer.id, ListingMedia.is_cover.is_(True))):
            link.is_cover = False
        db.flush()
    if existing is None:
        db.add(ListingMedia(listing_id=offer.id, media_asset_id=asset.id,
                            sort_order=body.sort_order, is_cover=body.is_cover))
    else:
        existing.sort_order = body.sort_order
        existing.is_cover = body.is_cover
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "The listing already has a cover") from None
    return {"listing_id": offer.id, "media_asset_id": asset.id, "is_cover": body.is_cover}


@router.delete("/classifieds/{offer_id}/media/{asset_id}", status_code=204)
def detach(offer_id: str, asset_id: str, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    offer = _owned_offer(db, user, offer_id)
    link = db.get(ListingMedia, (offer.id, asset_id))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media not found")
    db.delete(link)
    db.commit()
    return Response(status_code=204)


# --- public -------------------------------------------------------------------


@router.get("/media/{asset_id}")
def serve(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(MediaAsset, asset_id)
    shown = db.scalar(
        select(func.count()).select_from(ListingMedia)
        .join(ClassifiedOffer, ClassifiedOffer.id == ListingMedia.listing_id)
        .where(ListingMedia.media_asset_id == asset_id, ClassifiedOffer.status == "active")
    ) if asset else 0
    if (asset is None or asset.moderation_state != "APPROVED" or asset.archived_at
            or asset.file.state != "READY" or asset.file.access_class != "PUBLIC" or not shown):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media not found")
    data = storage.storage().get(asset.file.storage_key)
    return Response(
        content=data, media_type=asset.file.mime_type or "application/octet-stream",
        headers={
            # A photo is public once served, but it must stop being served
            # the moment it comes off the listing — so caches keep it briefly.
            "Cache-Control": "public, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
