"""Verified email and phone.

The board discloses an owner's personal number. Until now the only thing
standing between that number and a bulk collector was an account, and an
account cost a throwaway address. `users.phone` — unique, written only after a
code proved control — makes it cost a SIM, per account.

Revision ID: d3f81ba0c47e
Revises: 9010d2077493
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa

revision = "d3f81ba0c47e"
down_revision = "9010d2077493"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=32), nullable=True))
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    # NULL is not unique in Postgres, so every unverified account coexists while
    # a proven number can back exactly one.
    op.create_index("uq_users_phone", "users", ["phone"], unique=True)

    op.create_table(
        "verification_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=8), nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verification_codes_user_id", "verification_codes", ["user_id"], unique=False
    )
    # The lookup every confirm makes: newest live code for this user+channel.
    op.create_index(
        "ix_verification_codes_user_channel",
        "verification_codes",
        ["user_id", "channel"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_verification_codes_user_channel", table_name="verification_codes")
    op.drop_index("ix_verification_codes_user_id", table_name="verification_codes")
    op.drop_table("verification_codes")
    op.drop_index("uq_users_phone", table_name="users")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "phone")
