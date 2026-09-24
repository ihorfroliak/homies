"""Reprocess quarantined property media through the current pipeline.

Files written by the C8 structure walker were quarantined by migration
c1e3a5b7d9f2 (TASK-002 R3): their bytes may carry metadata the walker let
through. This decodes each one with media/sanitize.py and replaces the stored
bytes with the re-encoded image. A file that no longer decodes is marked
REJECTED; nothing is deleted.

Moderation decisions are kept: an APPROVED asset whose file reprocesses
cleanly becomes servable again, because approval judged what the picture
shows, and re-encoding does not change that.

Usage: python -m app.scripts.reprocess_media
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.media import sanitize, storage
from app.modules.media.models import FileObject, MediaAsset


@dataclass
class Report:
    reprocessed: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


def reprocess(db: Session) -> Report:
    report = Report()
    store = storage.storage()
    quarantined = db.scalars(
        select(FileObject).where(
            FileObject.purpose == "PROPERTY_MEDIA", FileObject.state == "QUARANTINED"
        )
    ).all()
    for file in quarantined:
        asset = db.scalar(select(MediaAsset).where(MediaAsset.file_id == file.id))
        try:
            clean = sanitize.sanitize(store.get(file.storage_key))
        except (sanitize.RejectedImage, FileNotFoundError):
            file.state = "REJECTED"
            file.access_class = "PRIVATE"
            file.rejected_at = datetime.now(timezone.utc)
            report.rejected.append(file.id)
            continue
        store.put(file.storage_key, clean.data)
        file.mime_type = clean.mime_type
        file.size_bytes = len(clean.data)
        file.sha256 = hashlib.sha256(clean.data).hexdigest()
        file.processing_version = sanitize.PIPELINE_VERSION
        file.state = "READY"
        approved = asset is not None and asset.moderation_state == "APPROVED"
        file.access_class = "PUBLIC" if approved else "PRIVATE"
        if asset is not None:
            asset.width_px, asset.height_px = clean.width, clean.height
        report.reprocessed.append(file.id)
    db.commit()
    return report


def main() -> None:
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        report = reprocess(db)
    print(f"reprocessed {len(report.reprocessed)}, rejected {len(report.rejected)}")


if __name__ == "__main__":
    main()
