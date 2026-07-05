"""Ledger service — the ONLY way money state changes in the system.

Rules (docs/business + ADR-0002):
- append-only: entries are never updated or deleted;
- every entry balances to zero;
- payouts can only be derived from ledger balances, never from payments directly.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ledger.models import JournalEntry, JournalLine, LedgerAccount

PROVIDER_CASH = "provider_cash"
BOOKING_ESCROW = "booking_escrow"
PLATFORM_REVENUE = "platform_revenue"


def host_payable_code(host_id: str) -> str:
    return f"host_payable:{host_id}"


_ACCOUNT_KINDS = {
    PROVIDER_CASH: "asset",
    BOOKING_ESCROW: "liability",
    PLATFORM_REVENUE: "income",
}


def ensure_account(db: Session, code: str) -> LedgerAccount:
    account = db.scalar(select(LedgerAccount).where(LedgerAccount.code == code))
    if account is None:
        kind = _ACCOUNT_KINDS.get(code, "liability")  # host_payable:* are liabilities
        account = LedgerAccount(code=code, kind=kind)
        db.add(account)
        db.flush()
    return account


class UnbalancedEntryError(ValueError):
    pass


def post_entry(
    db: Session,
    kind: str,
    lines: list[tuple[str, int]],  # (account_code, signed_amount)
    currency: str,
    booking_id: str | None = None,
    payment_id: str | None = None,
    description: str = "",
) -> JournalEntry:
    if sum(amount for _, amount in lines) != 0:
        raise UnbalancedEntryError(f"Journal entry '{kind}' does not balance: {lines}")
    if any(amount == 0 for _, amount in lines):
        raise UnbalancedEntryError(f"Journal entry '{kind}' has a zero-amount line")
    entry = JournalEntry(
        kind=kind,
        booking_id=booking_id,
        payment_id=payment_id,
        currency=currency,
        description=description,
    )
    db.add(entry)
    db.flush()
    for code, amount in lines:
        account = ensure_account(db, code)
        db.add(JournalLine(entry_id=entry.id, account_id=account.id, amount=amount))
    return entry


def account_balance(db: Session, code: str) -> int:
    account = db.scalar(select(LedgerAccount).where(LedgerAccount.code == code))
    if account is None:
        return 0
    total = db.scalar(
        select(func.coalesce(func.sum(JournalLine.amount), 0)).where(
            JournalLine.account_id == account.id
        )
    )
    return int(total or 0)


def all_balances(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(LedgerAccount.code, func.coalesce(func.sum(JournalLine.amount), 0))
        .join(JournalLine, JournalLine.account_id == LedgerAccount.id, isouter=True)
        .group_by(LedgerAccount.code)
    ).all()
    return {code: int(total or 0) for code, total in rows}


def reconcile(db: Session) -> dict:
    """Verify ledger integrity: every entry balances, whole system sums to zero."""
    unbalanced = [
        str(entry_id)
        for entry_id, total in db.execute(
            select(JournalLine.entry_id, func.sum(JournalLine.amount)).group_by(
                JournalLine.entry_id
            )
        ).all()
        if int(total) != 0
    ]
    grand_total = int(
        db.scalar(select(func.coalesce(func.sum(JournalLine.amount), 0))) or 0
    )
    return {
        "ok": not unbalanced and grand_total == 0,
        "unbalanced_entries": unbalanced,
        "grand_total": grand_total,
        "balances": all_balances(db),
    }
