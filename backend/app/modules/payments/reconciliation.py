"""Reconciliation engine (B1). Two layers:

1. payment_ledger_consistency — internal: proves the ledger and the payment
   table agree (every succeeded payment has a capture, every refund has a
   reversal, no orphans). Fully testable with no external calls.

2. stripe_ledger_reconciliation — external: compares our provider_cash
   movements to Stripe balance transactions. Requires Stripe keys; when they
   are absent it reports "unavailable" rather than a false pass.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ledger import service as ledger
from app.modules.ledger.models import JournalEntry
from app.modules.payments.models import Payment


def payment_ledger_consistency(db: Session) -> dict:
    def _capture_count(pid: str) -> int:
        return db.scalar(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.payment_id == pid, JournalEntry.kind == "payment_captured")
        )

    def _refund_count(pid: str) -> int:
        return db.scalar(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.payment_id == pid, JournalEntry.kind == "refund")
        )

    succeeded_without_capture: list[str] = []
    refunded_without_reversal: list[str] = []
    double_capture: list[str] = []
    orphan_payments: list[str] = []

    for p in db.scalars(select(Payment)):
        if p.booking_id is None:
            orphan_payments.append(p.id)
        caps = _capture_count(p.id)
        if p.status in ("succeeded", "refunded") and caps == 0:
            succeeded_without_capture.append(p.id)
        if caps > 1:
            double_capture.append(p.id)
        if p.status == "refunded" and _refund_count(p.id) == 0:
            refunded_without_reversal.append(p.id)

    led = ledger.reconcile(db)
    ok = (
        not succeeded_without_capture
        and not refunded_without_reversal
        and not double_capture
        and not orphan_payments
        and led["ok"]
    )
    return {
        "ok": ok,
        "ledger_balanced": led["ok"],
        "ledger_grand_total": led["grand_total"],
        "succeeded_without_capture": succeeded_without_capture,
        "refunded_without_reversal": refunded_without_reversal,
        "double_capture": double_capture,
        "orphan_payments": orphan_payments,
        "balances": led["balances"],
    }


def stripe_ledger_reconciliation(db: Session, provider) -> dict:
    """Compare ledger provider_cash to Stripe's balance. Only runs with a real
    Stripe provider + keys; otherwise honestly reports unavailable."""
    stripe = getattr(provider, "_stripe", None)
    if stripe is None:
        return {"available": False, "reason": "simulation provider — no Stripe balance to compare"}
    # Structure: sum captured - refunded from Stripe balance transactions and
    # compare to ledger provider_cash. Executed only in environments with keys.
    txns = stripe.BalanceTransaction.list(limit=100)
    stripe_net = sum(t["net"] for t in txns.get("data", []))
    ledger_cash = ledger.account_balance(db, ledger.PROVIDER_CASH)
    return {
        "available": True,
        "stripe_net": stripe_net,
        "ledger_provider_cash": ledger_cash,
        "match": stripe_net == ledger_cash,
    }
