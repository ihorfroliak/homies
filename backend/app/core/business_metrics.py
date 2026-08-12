"""Business event counters (OBS-03).

The audit records that the founder KPI framework (docs/strategy/06) has no data
source. Most of what it asks for is a **count of things that happened** —
registrations, bookings by outcome, payment success and failure, refunds,
payouts — and those are exactly what a Prometheus counter is for: monotonic,
rate-able, alertable, cheap.

One category is deliberately absent: **monetary totals** (GMV, commission, net
revenue, CM2, take rate). They must not be Prometheus counters.

    A Prometheus counter resets when the process restarts, is only observed at
    the scrape interval, and cannot be recomputed for a past window. Money in
    this system already has a source of truth — an append-only ledger, checked
    by invariant I5 and reconciled to zero — and putting GMV in a counter would
    create a second, lossy, unreconcilable financial record. When the two
    disagreed (and they would, after any restart), neither could be trusted.
    Monetary KPIs are queries against the ledger. See D-38.

So this module counts *events*, and the amount stays in the ledger. Conversion
rates are ratios of these counters, computed at query time — not stored.

Labels are closed sets (a booking has a fixed list of outcomes), which keeps
cardinality bounded by construction.
"""

from prometheus_client import Counter
from sqlalchemy import event
from sqlalchemy.orm import Session

REGISTRATIONS = Counter(
    "homies_registrations_total",
    "User registrations by role",
    ["role"],
)

BOOKINGS = Counter(
    "homies_bookings_total",
    "Booking lifecycle transitions",
    # created -> confirmed | payment_failed | expired | cancelled | completed
    ["outcome"],
)

PAYMENTS = Counter(
    "homies_payments_total",
    "Payment lifecycle transitions (counts, never amounts — see module docstring)",
    ["outcome"],
)

PAYOUTS = Counter(
    "homies_payouts_total",
    "Host payout runs by outcome",
    ["outcome"],
)


# --- commit-scoped recording -------------------------------------------------
#
# A Prometheus counter cannot be decremented, so it must only ever move on a
# fact that is durably true. The domain services here mutate state but do not
# commit — the router does — so incrementing at the transition would count
# rollbacks as successes: a payment that raced and lost, or any handler that
# raised after the transition, would permanently inflate "succeeded". These
# helpers therefore queue increments on the session and flush them from
# `after_commit`, discarding them on rollback.

_PENDING = "homies_pending_metrics"


def _queue(db: Session, counter: Counter, label: str) -> None:
    if not db.in_transaction():
        # Nothing to undo: no unit of work is open, so the fact being recorded
        # is already durable (the expiry sweep, for instance, records after its
        # own commit). Queueing here would be a bug — SQLAlchemy emits no
        # rollback event for a session with no active transaction, so the entry
        # would survive and be flushed by some later, unrelated commit.
        counter.labels(label).inc()
        return
    db.info.setdefault(_PENDING, []).append((counter, label))


@event.listens_for(Session, "after_commit")
def _flush_pending(session: Session) -> None:
    for counter, label in session.info.pop(_PENDING, []):
        counter.labels(label).inc()


@event.listens_for(Session, "after_rollback")
@event.listens_for(Session, "after_soft_rollback")
def _discard_pending(session: Session, *args: object) -> None:
    session.info.pop(_PENDING, None)


def record_registration(db: Session, role: str) -> None:
    _queue(db, REGISTRATIONS, role)


def record_booking(db: Session, outcome: str) -> None:
    _queue(db, BOOKINGS, outcome)


def record_payment(db: Session, outcome: str) -> None:
    _queue(db, PAYMENTS, outcome)


def record_payout(db: Session, outcome: str) -> None:
    _queue(db, PAYOUTS, outcome)
