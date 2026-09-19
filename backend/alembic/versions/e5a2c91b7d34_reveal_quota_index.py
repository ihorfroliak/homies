"""Index the rows the reveal quota reads.

The quota asks one question before every disclosure: how many DIFFERENT owners
has this account uncovered in the last 24 hours? On `viewer_id` alone that
means reading a heavy user's entire history each time — and a heavy user is
precisely the account the quota exists to slow down.

Revision ID: e5a2c91b7d34
Revises: d3f81ba0c47e
Create Date: 2026-09-20
"""

from alembic import op

revision = "e5a2c91b7d34"
down_revision = "d3f81ba0c47e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_contact_reveals_viewer_time",
        "contact_reveals",
        ["viewer_id", "revealed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_contact_reveals_viewer_time", table_name="contact_reveals")
