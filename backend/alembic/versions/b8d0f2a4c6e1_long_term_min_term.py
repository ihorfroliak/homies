"""LONG_TERM minimum term: NULL (open-ended) or at least one month.

Revision ID: b8d0f2a4c6e1
Revises: a7c9e1f3b5d2
Create Date: 2026-09-24

Founder decision 2026-09-24 (TASK-002 §23): LONG_TERM is not defined by a
six-month floor. The API's floor drops from 6 to 1; this makes the database
agree that zero and negative terms are not terms. Rows below one month could
only have been written around the API; they are reported, not rewritten.
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d0f2a4c6e1"
down_revision = "a7c9e1f3b5d2"
branch_labels = None
depends_on = None

NAME = "ck_classified_offers_min_term_positive"


def upgrade() -> None:
    bad = op.get_bind().execute(
        sa.text("SELECT id FROM classified_offers WHERE min_term_months < 1 ORDER BY id")
    ).scalars().all()
    if bad:
        raise RuntimeError(
            f"{len(bad)} listing(s) have a minimum term below one month; correct them by "
            f"hand. First ids: {', '.join(bad[:20])}"
        )
    op.create_check_constraint(
        NAME, "classified_offers", "min_term_months IS NULL OR min_term_months >= 1"
    )


def downgrade() -> None:
    op.drop_constraint(NAME, "classified_offers", type_="check")
