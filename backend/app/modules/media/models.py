"""File objects, property media and what a listing shows (Schema v1 §36–§38, §48).

Three layers, deliberately separate:

* `FileObject` — bytes in storage and what is known about them. No meaning.
* `MediaAsset` — "this file is a photo of this property", with its own
  moderation state. It belongs to the property, so it outlives any listing.
* `ListingMedia` — which approved photos a listing shows, in what order, and
  which one is the cover.

Only a READY file behind an APPROVED asset is ever served to the public, and a
listing can have at most one cover.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


FILE_PURPOSES = ("PROPERTY_MEDIA", "MESSAGE_ATTACHMENT", "SAFETY_EVIDENCE", "EPC_DOCUMENT",
                 "REPORT_EVIDENCE")
ACCESS_CLASSES = ("QUARANTINE", "PUBLIC", "PRIVATE")
FILE_STATES = ("UPLOADING", "QUARANTINED", "PROCESSING", "READY", "REJECTED", "DELETED")
MEDIA_TYPES = ("PHOTO", "FLOOR_PLAN", "VIDEO", "TOUR_360")
MODERATION_STATES = ("PENDING", "APPROVED", "REJECTED", "RESTRICTED")


class FileObject(Base):
    __tablename__ = "file_objects"
    __table_args__ = (
        CheckConstraint(_in("purpose", FILE_PURPOSES), name="ck_file_objects_purpose"),
        CheckConstraint(_in("access_class", ACCESS_CLASSES), name="ck_file_objects_access"),
        CheckConstraint(_in("state", FILE_STATES), name="ck_file_objects_state"),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_file_objects_size"),
        UniqueConstraint("storage_provider", "storage_bucket", "storage_key",
                         name="uq_file_objects_location"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    uploader_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(24))
    storage_provider: Mapped[str] = mapped_column(String(24))
    storage_bucket: Mapped[str] = mapped_column(String(120))
    storage_key: Mapped[str] = mapped_column(String(255))
    # PRIVATE until moderation approves it; there is no URL that serves bytes
    # merely because someone knows the key (§36).
    access_class: Mapped[str] = mapped_column(String(16), default="PRIVATE")
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(16), default="UPLOADING")
    # Which processing pipeline produced the stored bytes. NULL = the C8
    # structure walker, which TASK-001 showed leaks metadata; such files are
    # quarantined and never served until reprocessed (media/sanitize.py
    # PIPELINE_VERSION, app/scripts/reprocess_media.py).
    processing_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def servable(self) -> bool:
        """Bytes this service may hand out: ready, and produced by the current
        pipeline. Files from the C8 walker (processing_version NULL) never are."""
        from app.modules.media.sanitize import PIPELINE_VERSION

        return self.state == "READY" and self.processing_version == PIPELINE_VERSION


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint(_in("media_type", MEDIA_TYPES), name="ck_media_assets_type"),
        CheckConstraint(_in("moderation_state", MODERATION_STATES),
                        name="ck_media_assets_moderation"),
        CheckConstraint("visibility IN ('PUBLIC', 'PRIVATE')", name="ck_media_assets_visibility"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="RESTRICT"), index=True
    )
    space_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("spaces.id", ondelete="RESTRICT"), nullable=True
    )
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("file_objects.id",
                                                                ondelete="RESTRICT"))
    media_type: Mapped[str] = mapped_column(String(16))
    visibility: Mapped[str] = mapped_column(String(10), default="PUBLIC")
    moderation_state: Mapped[str] = mapped_column(String(16), default="PENDING")
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The uploader's statement that they may publish this picture. Stolen
    # photos of someone else's flat are the raw material of a fake listing;
    # the declaration is what makes that a lie they told rather than a
    # mistake the platform made.
    rights_declared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    file = relationship("FileObject", lazy="joined", viewonly=True)


class ListingMedia(Base):
    __tablename__ = "listing_media"
    __table_args__ = (
        Index("uq_listing_media_one_cover", "listing_id", unique=True,
              postgresql_where=text("is_cover = true"), sqlite_where=text("is_cover = 1")),
        Index("ix_listing_media_order", "listing_id", "sort_order"),
    )

    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classified_offers.id", ondelete="CASCADE"), primary_key=True
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="RESTRICT"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    asset = relationship("MediaAsset", lazy="joined", viewonly=True)
