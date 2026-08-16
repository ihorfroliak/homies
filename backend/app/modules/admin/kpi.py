"""Ledger-backed KPI queries (OBS-07).

The founder KPI framework (docs/strategy/06) had no data source. OBS-03 gave it
event *counts* via Prometheus but deliberately stopped there: money must not
live in a resettable counter (D-38). This module is the other half — the
monetary rows, answered from the ledger.

Why the ledger and not the `bookings` table: a refunded or cancelled booking
still carries its `total_amount`, so summing that column reports money the
business does not have. The ledger is append-only, balances to zero per entry,
is reconciled, and records what actually moved. It is the only defensible
source for GMV, and using anything else would recreate the exact class of bug
H1 closed.

Three constraints shape every query here:

* **Currency is always scoped.** H1's defect was summing balances across
  currencies with no scoping. A KPI query that repeated that would be the same
  bug wearing a different hat, so the currency filter is mandatory, not
  optional.
* **Money stays in integer minor units** (ADR-0002), and ratios are returned in
  basis points rather than floats — no KPI is worth a rounding drift in money.
* **The window is half-open** `[from, to)`. Month-boundary double counting is
  the classic reporting bug: December's last day must not appear in both
  December and January.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.booking.models import Booking
from app.modules.ledger.models import JournalEntry, JournalLine, LedgerAccount
from app.modules.ledger.service import PLATFORM_REVENUE, PROVIDER_CASH

# KPIs the framework asks for that this system genuinely cannot answer yet.
# Returned in the payload rather than silently omitted: an endpoint that shows
# six numbers looks complete, and the founder would have no way to tell that
# CM2 is missing because the data does not exist rather than because it is zero.
UNAVAILABLE: list[dict[str, str]] = [
    {
        "kpi": "CM2 per object",
        "reason": "cleaning and operations costs are not modelled anywhere in the system",
        "unblocked_by": "an operations-cost ledger account or a cost table",
    },
    {
        "kpi": "Occupancy / RevPAU",
        "reason": "no inventory model of *available* nights per listing to divide by",
        "unblocked_by": "a listing availability calendar",
    },
    {
        "kpi": "NPS / CSAT",
        "reason": "no survey or review data is collected",
        "unblocked_by": "the reviews context (not built)",
    },
    {
        "kpi": "CAC, runway, DSO",
        "reason": "no spend, cash or invoice data exists in this system",
        "unblocked_by": "finance data outside the platform",
    },
    {
        "kpi": "Chargeback / dispute rate",
        "reason": "disputes have no ledger representation",
        "unblocked_by": "FIN-03",
    },
]


@dataclass(frozen=True)
class Window:
    start: date
    end: date  # exclusive

    def bounds(self) -> tuple[datetime, datetime]:
        return (
            datetime.combine(self.start, time.min, tzinfo=timezone.utc),
            datetime.combine(self.end, time.min, tzinfo=timezone.utc),
        )


@dataclass
class KpiReport:
    currency: str
    window: Window
    money: dict[str, int] = field(default_factory=dict)
    ratios_bps: dict[str, int] = field(default_factory=dict)
    bookings: dict[str, int] = field(default_factory=dict)
    nights_sold: int = 0
    adr_minor_units: int = 0


def _entry_sum(db: Session, *, kind: str, account: str, currency: str, window: Window) -> int:
    """Signed sum of one account's lines across entries of one kind in the window."""
    start, end = window.bounds()
    total = db.scalar(
        select(func.coalesce(func.sum(JournalLine.amount), 0))
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .join(LedgerAccount, LedgerAccount.id == JournalLine.account_id)
        .where(
            JournalEntry.kind == kind,
            LedgerAccount.code == account,
            JournalEntry.currency == currency,
            JournalEntry.created_at >= start,
            JournalEntry.created_at < end,
        )
    )
    return int(total or 0)


def _bps(part: int, whole: int) -> int:
    """Ratio in basis points, rounded half-up. Zero denominator yields 0."""
    if whole <= 0:
        return 0
    return (part * 10_000 + whole // 2) // whole


def compute(db: Session, *, currency: str, window: Window) -> KpiReport:
    # Sign convention (ledger models): debit positive, credit negative.
    #   payment_captured : provider_cash +amount
    #   refund           : provider_cash -amount
    #   payout_allocated : platform_revenue -fee
    #   payout_sent      : provider_cash -net
    gmv_captured = _entry_sum(
        db, kind="payment_captured", account=PROVIDER_CASH, currency=currency, window=window
    )
    refunded = -_entry_sum(
        db, kind="refund", account=PROVIDER_CASH, currency=currency, window=window
    )
    # Commission is recognised at payout_allocated, not at capture: a booking
    # that has been paid but whose stay has not completed has earned the
    # platform nothing yet. Deriving it as `gmv * fee_bps` would book revenue
    # the business is not entitled to keep, since the guest can still cancel.
    commission = -_entry_sum(
        db, kind="payout_allocated", account=PLATFORM_REVENUE, currency=currency, window=window
    )
    payouts_sent = -_entry_sum(
        db, kind="payout_sent", account=PROVIDER_CASH, currency=currency, window=window
    )
    gmv_net = gmv_captured - refunded

    report = KpiReport(currency=currency, window=window)
    report.money = {
        "gmv_captured": gmv_captured,
        "refunded": refunded,
        "gmv_net": gmv_net,
        "commission_recognised": commission,
        "payouts_sent": payouts_sent,
    }
    report.ratios_bps = {
        # Against captured, not net: the question "what share of money taken
        # came back" is what the 5% KPI threshold is about.
        "refund_rate": _bps(refunded, gmv_captured),
        "take_rate": _bps(commission, gmv_net),
    }
    report.bookings = _booking_counts(db, currency=currency, window=window)
    report.nights_sold = _nights_sold(db, currency=currency, window=window)
    report.adr_minor_units = gmv_net // report.nights_sold if report.nights_sold else 0
    return report


def _booking_counts(db: Session, *, currency: str, window: Window) -> dict[str, int]:
    """Bookings created in the window, by their current status.

    Deliberately a snapshot of *current* status rather than a transition log:
    the system does not store status history, so an honest count is "of the
    bookings created then, here is where they stand now". Prometheus holds the
    transition rates (OBS-03).
    """
    start, end = window.bounds()
    rows = db.execute(
        select(Booking.status, func.count())
        .where(
            Booking.currency == currency,
            Booking.created_at >= start,
            Booking.created_at < end,
        )
        .group_by(Booking.status)
    ).all()
    return {str(status): int(count) for status, count in rows}


def _nights_sold(db: Session, *, currency: str, window: Window) -> int:
    """Nights on bookings whose payment was captured in the window.

    Anchored to capture rather than to stay dates so that it divides the same
    money GMV counts — an ADR mixing one window's revenue with another's nights
    is not a price.
    """
    start, end = window.bounds()
    bookings = db.scalars(
        select(Booking)
        .join(JournalEntry, JournalEntry.booking_id == Booking.id)
        .where(
            JournalEntry.kind == "payment_captured",
            JournalEntry.currency == currency,
            JournalEntry.created_at >= start,
            JournalEntry.created_at < end,
        )
        .distinct()
    ).all()
    return sum((b.check_out - b.check_in).days for b in bookings)


def as_payload(report: KpiReport) -> dict:
    return {
        "window": {
            "from": report.window.start.isoformat(),
            "to": report.window.end.isoformat(),
            "end_exclusive": True,
        },
        "currency": report.currency,
        "source": "ledger",
        "money_minor_units": report.money,
        "ratios_bps": report.ratios_bps,
        "bookings_by_status": report.bookings,
        "nights_sold": report.nights_sold,
        "adr_minor_units": report.adr_minor_units,
        "unavailable": UNAVAILABLE,
    }
