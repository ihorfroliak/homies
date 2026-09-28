"""Notification preferences (Schema v1 §71; TASK-014). PRODUCT is optional:
default enabled on IN_APP and EMAIL (the user asked by saving a search);
every change is explicit and never deletes a saved search."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.alerts.models import CHANNELS, NotificationPreference
from app.modules.alerts.sql import insert_ignore

DEFAULT_ENABLED = {("PRODUCT", "IN_APP"): True, ("PRODUCT", "EMAIL"): True}


def enabled_channels(db: Session, user_ids: list[str], category: str) -> dict[str, set[str]]:
    """user → channels on which `category` is enabled right now (one query)."""
    out = {u: {c for c in CHANNELS if DEFAULT_ENABLED[(category, c)]} for u in user_ids}
    if not user_ids:
        return out
    for pref in db.scalars(select(NotificationPreference).where(
            NotificationPreference.user_id.in_(user_ids),
            NotificationPreference.category == category)):
        (out[pref.user_id].add if pref.enabled else out[pref.user_id].discard)(pref.channel)
    return out


def is_enabled(db: Session, user_id: str, category: str, channel: str) -> bool:
    return channel in enabled_channels(db, [user_id], category)[user_id]


def set_preference(db: Session, user_id: str, category: str, channel: str, enabled: bool,
                   now: datetime) -> None:
    insert_ignore(db, NotificationPreference,
                  [{"user_id": user_id, "category": category, "channel": channel,
                    "enabled": enabled, "updated_at": now}],
                  ["user_id", "category", "channel"])
    pref = db.execute(select(NotificationPreference).where(
        NotificationPreference.user_id == user_id, NotificationPreference.category == category,
        NotificationPreference.channel == channel).with_for_update()).scalar_one()
    pref.enabled = enabled
    pref.updated_at = now
    db.flush()
