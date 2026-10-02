"""The current moderation state of a target — the head of its decision chain.

Kept free of other trust imports so the publication seam
(`properties.publicity.make_public`) can ask "is this listing held?" without
pulling the decision service into the properties module.

A listing is HELD while its head is CONTENT_EDIT_REQUIRED or
VISIBILITY_LIMITED (04a §23). Nothing is stored twice: there is no hold flag
and no hold table. Read it under the listing's row lock (`make_public`,
`decisions.apply_listing_decision`): every decision on a listing is written
under that same lock, so the head read there cannot change before commit.
"""

from collections.abc import Iterable

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, aliased

from app.modules.trust.models import HOLD_ACTIONS, ModerationDecision


class ForkedChain(RuntimeError):
    """More than one head: impossible under the database constraints, so it
    is never resolved by picking one — the caller fails closed."""


def head(db: Session, target_type: str, target_id: str) -> ModerationDecision | None:
    """The decision of this target that no other decision supersedes."""
    successor = aliased(ModerationDecision)
    heads = db.scalars(
        select(ModerationDecision).where(
            ModerationDecision.target_type == target_type,
            ModerationDecision.target_id == target_id,
            ~exists().where(successor.supersedes_decision_id == ModerationDecision.id),
        ).limit(2)
    ).all()
    if len(heads) > 1:
        raise ForkedChain(f"{target_type} {target_id} has more than one moderation head")
    return heads[0] if heads else None


def listing_held(db: Session, listing_id: str) -> bool:
    current = head(db, "LISTING", listing_id)
    return current is not None and current.action in HOLD_ACTIONS


def heads(db: Session, target_type: str,
          target_ids: Iterable[str]) -> dict[str, ModerationDecision]:
    """The heads of many targets in one statement — for pages of listings
    (the owner's list, the moderator queue), never one query per row. A
    target without decisions is absent from the result. Fails closed on a
    fork, like `head`."""
    ids = list(dict.fromkeys(target_ids))
    if not ids:
        return {}
    successor = aliased(ModerationDecision)
    out: dict[str, ModerationDecision] = {}
    for decision in db.scalars(
        select(ModerationDecision).where(
            ModerationDecision.target_type == target_type,
            ModerationDecision.target_id.in_(ids),
            ~exists().where(successor.supersedes_decision_id == ModerationDecision.id),
        )
    ):
        if decision.target_id in out:
            raise ForkedChain(f"{target_type} {decision.target_id} has more than one "
                              "moderation head")
        out[decision.target_id] = decision
    return out
