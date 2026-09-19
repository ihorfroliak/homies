"""stamp commission_bps on bookings

The commission used to be read from `settings.platform_fee_bps` at PAYOUT time,
so changing the rate silently re-priced every booking that had not been paid out
yet. A host who agreed to one rate would have been paid at another. The rate is
now stamped on the booking when it is created.

Backfill: existing rows are set to 1500, which is the rate that was actually in
force when they were created (`platform_fee_bps` defaulted to 1500 until it was
changed to 800 on 2026-09-19). Writing today's rate onto yesterday's bookings
would falsify them. The backfill is verifiable: every paid-out booking already
carries its real fee in the `payout_allocated` ledger entry.

Two steps on purpose — add nullable, backfill, then SET NOT NULL — so the column
is never NOT NULL while rows are still unpopulated.

Revision ID: b910997aa651
Revises: 87cebed1635f
Create Date: 2026-09-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b910997aa651"
down_revision: str | Sequence[str] | None = "87cebed1635f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The rate in force before 2026-09-19. Hardcoded rather than read from settings:
# a migration must produce the same result whatever the config says the day it
# is run, otherwise replaying history gives a different database.
HISTORICAL_FEE_BPS = 1500


def upgrade() -> None:
    op.add_column("bookings", sa.Column("commission_bps", sa.Integer(), nullable=True))
    op.execute(f"UPDATE bookings SET commission_bps = {HISTORICAL_FEE_BPS}")
    op.alter_column("bookings", "commission_bps", nullable=False)


def downgrade() -> None:
    op.drop_column("bookings", "commission_bps")
