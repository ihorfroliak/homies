"""Financial + structural verification of a restored database (D9 §6).

Proves the ledger survived a restore intact: every journal entry balances to
zero, the whole system sums to zero, escrow never drifts positive, and every
paid booking still has its payout entry.

The table list is read from the database, never written down here. The first
version of this file named seven tables by hand; five more tables were added to
the schema afterwards and none of them were checked, so a restore that silently
dropped `contact_reveals` or `verification_codes` would have reported PASS. A
hand-maintained list in a disaster-recovery check is a list that is wrong
exactly when it matters.

Used two ways, deliberately sharing one implementation:
  * `dr_drill.sh` — the manual drill, run by a human against a real artifact;
  * `tests/test_dr_restore_pg.py` — the automated cycle that runs in CI.
Two copies of these rules would drift, and the copy that drifts is the one
nobody runs until the night they need it.

Usage: python verify_restore.py <sqlalchemy_url>
Exit 0 = restore is financially sound, 1 = corruption detected.
"""

import sys
from dataclasses import dataclass, field

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

# Tables that exist to support the checks rather than to be checked. Nothing is
# excluded from the COUNT sweep — this is only about what a reader is shown
# first.
_HEADLINE = ("users", "bookings", "payments", "journal_entries", "journal_lines")


@dataclass
class Report:
    counts: dict[str, int] = field(default_factory=dict)
    balances: dict[str, int] = field(default_factory=dict)
    grand_total: int = 0
    escrow: int = 0
    unbalanced_entries: int = 0
    paid_without_payout: int = 0
    alembic_version: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.unbalanced_entries == 0
            and self.grand_total == 0
            # A liability account is credit-normal. A positive balance would
            # mean the platform is holding guest money it has already paid out.
            and self.escrow <= 0
            and self.paid_without_payout == 0
        )


def table_names(conn: Connection) -> list[str]:
    """Every base table in `public`, as the database currently has it."""
    return list(
        conn.scalars(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "ORDER BY table_name"
            )
        )
    )


def row_counts(conn: Connection) -> dict[str, int]:
    """Exact counts, not the planner's estimate from pg_class.reltuples.

    An estimate is fine for a dashboard and useless here: it is stale after a
    restore until ANALYZE runs, so it would report a difference that is not
    there, or hide one that is.
    """
    return {
        name: conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one()
        for name in table_names(conn)
    }


def collect(conn: Connection) -> Report:
    report = Report()
    report.counts = row_counts(conn)

    # I2: every journal entry balances to zero.
    report.unbalanced_entries = len(
        conn.execute(
            text(
                "SELECT entry_id FROM journal_lines "
                "GROUP BY entry_id HAVING SUM(amount) <> 0"
            )
        ).fetchall()
    )
    # I3: the whole system sums to zero.
    report.grand_total = int(
        conn.execute(text("SELECT COALESCE(SUM(amount), 0) FROM journal_lines")).scalar_one()
    )
    report.balances = {
        code: int(total)
        for code, total in conn.execute(
            text(
                "SELECT a.code, COALESCE(SUM(l.amount), 0) "
                "FROM ledger_accounts a LEFT JOIN journal_lines l ON l.account_id = a.id "
                "GROUP BY a.code"
            )
        ).fetchall()
    }
    report.escrow = report.balances.get("booking_escrow", 0)
    # I7: every paid-out booking still has the entry that paid it.
    report.paid_without_payout = len(
        conn.execute(
            text(
                "SELECT b.id FROM bookings b WHERE b.payout_status = 'paid' "
                "AND NOT EXISTS (SELECT 1 FROM journal_entries e "
                "WHERE e.booking_id = b.id AND e.kind = 'payout_sent')"
            )
        ).fetchall()
    )
    # A restore that lands at a different migration than the source is a
    # restore into a schema the application will refuse to start against.
    report.alembic_version = conn.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()
    return report


def verify(url: str) -> Report:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return collect(conn)
    finally:
        engine.dispose()


def _print(report: Report) -> None:
    headline = {k: report.counts[k] for k in _HEADLINE if k in report.counts}
    others = {k: v for k, v in report.counts.items() if k not in headline}
    print(f"  counts: {headline}")
    print(f"  other tables ({len(others)}): {others}")
    print(f"  balances: {report.balances}")
    print(
        f"  grand_total={report.grand_total} escrow={report.escrow} "
        f"unbalanced_entries={report.unbalanced_entries} "
        f"paid_without_payout={report.paid_without_payout} "
        f"alembic={report.alembic_version}"
    )
    print(f"  FINANCIAL RECOVERY: {'PASS' if report.ok else 'FAIL'}")


def main(url: str) -> int:
    report = verify(url)
    _print(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
