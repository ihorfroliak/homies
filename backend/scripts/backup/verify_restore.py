"""Financial + structural verification of a restored database (D9 §6).

Connects to a target DB and proves the ledger survived restore intact:
every journal entry balances to zero, the whole system sums to zero, and
core row counts are reported for reconciliation against the source.

Usage: python verify_restore.py <sqlalchemy_url>
Exit 0 = restore is financially sound, 1 = corruption detected.
"""

import sys

from sqlalchemy import create_engine, text


def main(url: str) -> int:
    engine = create_engine(url)
    with engine.connect() as c:
        # I2: every journal entry balances to zero
        unbalanced = c.execute(
            text(
                "SELECT entry_id, SUM(amount) s FROM journal_lines "
                "GROUP BY entry_id HAVING SUM(amount) <> 0"
            )
        ).fetchall()
        # I3: the whole system sums to zero
        grand_total = c.execute(
            text("SELECT COALESCE(SUM(amount),0) FROM journal_lines")
        ).scalar()
        # Per-account balances
        balances = {
            code: int(total)
            for code, total in c.execute(
                text(
                    "SELECT a.code, COALESCE(SUM(l.amount),0) "
                    "FROM ledger_accounts a LEFT JOIN journal_lines l "
                    "ON l.account_id = a.id GROUP BY a.code"
                )
            ).fetchall()
        }
        escrow = balances.get("booking_escrow", 0)
        # I7 integrity: every paid booking has a payout_sent entry
        paid_without_payout = c.execute(
            text(
                "SELECT b.id FROM bookings b WHERE b.payout_status='paid' "
                "AND NOT EXISTS (SELECT 1 FROM journal_entries e "
                "WHERE e.booking_id=b.id AND e.kind='payout_sent')"
            )
        ).fetchall()
        counts = {
            t: c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            for t in ("users", "listings", "bookings", "payments",
                      "journal_entries", "journal_lines", "audit_log")
        }

    print(f"  counts: {counts}")
    print(f"  balances: {balances}")
    print(f"  grand_total={grand_total} escrow={escrow} "
          f"unbalanced_entries={len(unbalanced)} paid_without_payout={len(paid_without_payout)}")

    ok = (
        len(unbalanced) == 0
        and grand_total == 0
        and escrow <= 0  # liability: credit-normal, never a positive (owed-to-us) drift
        and len(paid_without_payout) == 0
    )
    print(f"  FINANCIAL RECOVERY: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
