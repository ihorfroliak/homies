"""Money is bigint (Schema v1 §8).

Every monetary column was int4: a ceiling of 2 147 483 647 minor units, i.e.
21 474 836,47 zł. Enough for a month's rent, not for a sale price — and SALE
is in scope. A Warsaw penthouse at 25 mln zł would not merely be rejected; the
insert would raise "integer out of range" deep inside a transaction, which is a
500 to the person listing it.

Cheap now and expensive later: ALTER ... TYPE rewrites the table, and the cost
of that rewrite grows with every row the business adds.

The ledger's append-only triggers are not in the way. They fire on row UPDATE
and DELETE; a type change is a table rewrite by the owner, not a row update.

Revision ID: a1c6d2e8b407
Revises: e5a2c91b7d34
Create Date: 2026-09-23
"""

import sqlalchemy as sa
from alembic import op

revision = "a1c6d2e8b407"
down_revision = "e5a2c91b7d34"
branch_labels = None
depends_on = None

MONEY = [
    ("bookings", "total_amount"),
    ("classified_offers", "rent_amount"),
    ("classified_offers", "admin_fee"),
    ("classified_offers", "utilities_amount"),
    ("classified_offers", "parking_fee"),
    ("classified_offers", "deposit_amount"),
    ("disputes", "amount"),
    ("disputes", "fee"),
    ("journal_lines", "amount"),
    ("listings", "nightly_price_amount"),
    ("payments", "amount"),
]


def upgrade() -> None:
    for table, column in MONEY:
        op.alter_column(
            table, column, type_=sa.BigInteger(), existing_type=sa.Integer()
        )


def downgrade() -> None:
    # Narrowing fails loudly if any value no longer fits — which is the right
    # outcome: a downgrade must not silently truncate money.
    for table, column in MONEY:
        op.alter_column(
            table, column, type_=sa.Integer(), existing_type=sa.BigInteger()
        )
