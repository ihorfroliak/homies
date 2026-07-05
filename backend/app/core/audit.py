"""Append-only audit log. Every financial or state-changing action records
who did what to which entity. Never updated, never deleted."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor: Mapped[str] = mapped_column(String(64))  # user id or "system"
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def _forbid(mapper, connection, target):  # noqa: ARG001
    raise RuntimeError("audit_log is append-only")


event.listen(AuditLog, "before_update", _forbid)
event.listen(AuditLog, "before_delete", _forbid)


def audit(
    db: Session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    data: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data or {},
        )
    )
