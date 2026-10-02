"""Counting what commits — and only what commits.

A Prometheus counter incremented inside a transaction that later rolls back
would count something that never happened. `count_on_commit` queues the
increment on the session; `after_commit` applies it, `after_soft_rollback`
drops it. Each entry remembers the (possibly nested) transaction it was made
in, so a rolled-back savepoint drops only its own entries, not earlier ones
of the enclosing transaction.

Used by `homies_moderation_decisions_total` and `homies_reports_created_total`
(TASK-015). Labels are bounded codes only — never an id or text.
"""

from prometheus_client import Counter
from sqlalchemy import event
from sqlalchemy.orm import Session

_PENDING = "trust.committed_counts"


def count_on_commit(db: Session, counter: Counter, **labels: str) -> None:
    tx = db.get_nested_transaction() or db.get_transaction()
    db.info.setdefault(_PENDING, []).append((tx, counter, labels))


def _within(tx, ancestor) -> bool:
    while tx is not None:
        if tx is ancestor:
            return True
        tx = tx.parent
    return False


@event.listens_for(Session, "after_commit")
def _count_committed(session: Session) -> None:
    for _tx, counter, labels in session.info.pop(_PENDING, ()):
        counter.labels(**labels).inc()


@event.listens_for(Session, "after_soft_rollback")
def _forget_rolled_back(session: Session, previous_transaction) -> None:
    pending = session.info.get(_PENDING)
    if pending:
        session.info[_PENDING] = [entry for entry in pending
                                  if not _within(entry[0], previous_transaction)]
