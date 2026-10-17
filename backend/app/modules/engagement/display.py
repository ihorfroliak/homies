"""OD-3 display projection of unverified account text, never legal identity."""
import unicodedata
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import User

FALLBACK_NAME = "Użytkownik Homies"


def requester_display_name(full_name: str | None) -> str:
    words = (full_name or "").split()
    if not words:
        return FALLBACK_NAME
    if len(words) == 1:
        return words[0]
    last = words[-1]
    initial = last[0]
    # Keep a decomposed accent attached to the initial without changing its
    # Unicode spelling. This is a display rule, not a legal-name parser.
    for char in last[1:]:
        if not unicodedata.combining(char):
            break
        initial += char
    return f"{words[0]} {initial}."


def requester_names(db: Session, user_ids: Iterable[str]) -> dict[str, str]:
    ids = set(user_ids)
    if not ids:
        return {}
    return {user_id: requester_display_name(full_name)
            for user_id, full_name in db.execute(
                select(User.id, User.full_name).where(User.id.in_(ids)))}
