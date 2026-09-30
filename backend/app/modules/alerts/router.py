"""User inbox, notification preferences and unsubscribe (TASK-014).

The inbox is `/v1/me/inbox` — the canonical user-facing notification
(category, type, localisation keys, safe data, read state). The older
`GET /v1/me/notifications` is the booking-era delivery-queue feed; it is left
exactly as it was, so no existing consumer breaks.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.modules.alerts import delivery, metrics, preferences
from app.modules.alerts.models import CHANNELS, PRODUCT, UserNotification
from app.modules.properties import freshness

router = APIRouter(tags=["notifications"])

Id = Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9-]+$")]


class NotificationOut(BaseModel):
    """Localisation keys and safe identifiers only — the client renders the
    text and loads the listing through the public API (which applies the
    public rule again)."""

    id: str
    category: str
    notification_type: str
    title_key: str
    body_key: str
    data: dict
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int
    limit: int
    offset: int


class PreferenceOut(BaseModel):
    category: Literal["PRODUCT"]
    channel: Literal["IN_APP", "EMAIL"]
    enabled: bool


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["PRODUCT"]
    channel: Literal["IN_APP", "EMAIL"]
    enabled: bool


class UnsubscribeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=128)


class UnsubscribeOut(BaseModel):
    status: Literal["ok"] = "ok"


def _out(n: UserNotification) -> NotificationOut:
    return NotificationOut(id=n.id, category=n.category, notification_type=n.notification_type,
                           title_key=n.title_key, body_key=n.body_key, data=n.data or {},
                           created_at=n.created_at, read_at=n.read_at)


@router.get("/me/inbox", response_model=NotificationPage)
def my_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = select(UserNotification).where(UserNotification.user_id == user.id)
    if unread_only:
        base = base.where(UserNotification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    unread = db.scalar(select(func.count()).select_from(UserNotification).where(
        UserNotification.user_id == user.id, UserNotification.read_at.is_(None))) or 0
    rows = db.scalars(base.order_by(UserNotification.created_at.desc(),
                                    UserNotification.id.desc()).limit(limit).offset(offset))
    return NotificationPage(items=[_out(n) for n in rows], total=total, unread=unread,
                            limit=limit, offset=offset)


@router.post("/me/inbox/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: Id, user=Depends(get_current_user),
              db: Session = Depends(get_db)):
    n = db.scalar(select(UserNotification).where(UserNotification.id == notification_id,
                                                 UserNotification.user_id == user.id))
    if n is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    if n.read_at is None:
        n.read_at = freshness.db_now(db)
        db.commit()
    return _out(n)


@router.get("/me/notification-preferences", response_model=list[PreferenceOut])
def my_preferences(user=Depends(get_current_user), db: Session = Depends(get_db)):
    enabled = preferences.enabled_channels(db, [user.id], PRODUCT)[user.id]
    return [PreferenceOut(category=PRODUCT, channel=c, enabled=c in enabled)  # type: ignore[arg-type]
            for c in CHANNELS]


@router.put("/me/notification-preferences", response_model=list[PreferenceOut])
def set_my_preference(body: PreferenceUpdate, user=Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """PRODUCT is optional and separate from any marketing consent. Turning
    it off stops queued alerts too (they are revalidated at send time); it
    never deletes a saved search."""
    preferences.set_preference(db, user.id, body.category, body.channel, body.enabled,
                               freshness.db_now(db))
    db.commit()
    return my_preferences(user, db)


@router.post("/notifications/unsubscribe", response_model=UnsubscribeOut)
def unsubscribe(body: UnsubscribeIn, db: Session = Depends(get_db)):
    """One-click unsubscribe with the token from an alert email. No account
    needed. The answer is the same for a valid, used, expired or unknown
    token — it confirms nothing about any account."""
    outcome = delivery.unsubscribe(db, body.token, freshness.db_now(db))
    db.commit()
    metrics.UNSUBSCRIBES.labels(outcome=outcome).inc()
    return UnsubscribeOut()
