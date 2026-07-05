from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LedgerImmutabilityError(RuntimeError):
    pass


class LedgerAccount(Base):
    """Chart of accounts. Sign convention: amounts are signed integers in
    minor units; debit positive, credit negative. Every journal entry's
    lines sum to exactly zero (closed double-entry system).

    Account codes:
      provider_cash            asset     — funds held at the payment provider (Stripe mirror)
      booking_escrow           liability — guest money held for not-yet-paid-out bookings
      host_payable:{host_id}   liability — allocated, not yet transferred to the host
      platform_revenue         income    — managed fee / commission earned
    """

    __tablename__ = "ledger_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16))  # asset | liability | income
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # payment_captured | refund | payout_allocated | payout_sent
    kind: Mapped[str] = mapped_column(String(32), index=True)
    booking_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entry_id: Mapped[str] = mapped_column(String(36), ForeignKey("journal_entries.id"), index=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ledger_accounts.id"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer)  # signed minor units; debit>0, credit<0


# D5 hardening (invariant I4): the ledger is append-only. Corrections are new
# compensating entries, never edits. DB-level REVOKE lands with Alembic (P1);
# this guard stops the whole application layer today.
def _forbid(mapper, connection, target):  # noqa: ARG001
    raise LedgerImmutabilityError(
        f"{type(target).__name__} is append-only: post a compensating entry instead"
    )


for _model in (JournalEntry, JournalLine):
    event.listen(_model, "before_update", _forbid)
    event.listen(_model, "before_delete", _forbid)
