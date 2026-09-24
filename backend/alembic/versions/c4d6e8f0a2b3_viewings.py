"""Viewing settings, windows, blackouts and viewings (Domain Schema v1 §57–§60).

Revision ID: c4d6e8f0a2b3
Revises: b3c5d7e9f1a2
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from alembic import op

revision = "c4d6e8f0a2b3"
down_revision = "b3c5d7e9f1a2"
branch_labels = None
depends_on = None

STATUSES = ("REQUESTED", "CONFIRMED", "DECLINED", "CANCELLED", "COMPLETED", "NO_SHOW")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _listing(primary: bool = False, ondelete: str = "CASCADE") -> sa.Column:
    return sa.Column("listing_id", sa.String(36),
                     sa.ForeignKey("classified_offers.id", ondelete=ondelete),
                     primary_key=primary, nullable=False)


def _user(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"),
                     nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "viewing_settings",
        _listing(primary=True),
        sa.Column("booking_mode", sa.String(20), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("minimum_notice_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_before_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_after_minutes", sa.Integer(), nullable=False),
        sa.Column("max_concurrent_bookings", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        _ts("created_at"), _ts("updated_at"),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_in("booking_mode", ("INSTANT_BOOKING", "REQUEST_APPROVAL")),
                           name="ck_viewing_settings_mode"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_viewing_settings_duration"),
        sa.CheckConstraint("minimum_notice_minutes >= 0", name="ck_viewing_settings_notice"),
        sa.CheckConstraint("buffer_before_minutes >= 0 AND buffer_after_minutes >= 0",
                           name="ck_viewing_settings_buffers"),
        sa.CheckConstraint("max_concurrent_bookings >= 1", name="ck_viewing_settings_capacity"),
    )
    op.create_table(
        "viewing_windows",
        sa.Column("id", sa.String(36), primary_key=True),
        _listing(),
        sa.Column("window_type", sa.String(10), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=True),
        sa.Column("local_date", sa.Date(), nullable=True),
        sa.Column("local_start_time", sa.Time(), nullable=False),
        sa.Column("local_end_time", sa.Time(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        _ts("created_at"),
        sa.CheckConstraint(_in("window_type", ("WEEKLY", "ONE_OFF")),
                           name="ck_viewing_windows_type"),
        sa.CheckConstraint("local_end_time > local_start_time", name="ck_viewing_windows_order"),
        sa.CheckConstraint(
            "(window_type = 'WEEKLY' AND weekday BETWEEN 0 AND 6 AND local_date IS NULL) "
            "OR (window_type = 'ONE_OFF' AND local_date IS NOT NULL AND weekday IS NULL)",
            name="ck_viewing_windows_shape"),
        sa.CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
                           name="ck_viewing_windows_validity"),
    )
    op.create_index("ix_viewing_windows_listing_id", "viewing_windows", ["listing_id"])
    op.create_table(
        "viewing_blackouts",
        sa.Column("id", sa.String(36), primary_key=True),
        _listing(),
        _ts("starts_at"), _ts("ends_at"),
        sa.Column("reason", sa.String(200), nullable=True),
        _ts("created_at"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_viewing_blackouts_order"),
    )
    op.create_index("ix_viewing_blackouts_listing_id", "viewing_blackouts", ["listing_id"])
    op.create_table(
        "viewings",
        sa.Column("id", sa.String(36), primary_key=True),
        _listing(ondelete="RESTRICT"),
        _user("requester_user_id"),
        _ts("starts_at"), _ts("ends_at"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attendee_count", sa.SmallInteger(), nullable=False),
        sa.Column("requester_note", sa.String(1000), nullable=True),
        _user("confirmed_by_user_id", nullable=True),
        _ts("created_at"), _ts("responded_at", nullable=True), _ts("cancelled_at", nullable=True),
        _ts("completed_at", nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_viewings_status"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_viewings_order"),
        sa.CheckConstraint("attendee_count > 0", name="ck_viewings_attendees"),
    )
    op.create_index("ix_viewings_listing_starts", "viewings", ["listing_id", "starts_at"])
    op.create_index("ix_viewings_requester_starts", "viewings", ["requester_user_id", "starts_at"])
    op.create_index("ix_viewings_status_starts", "viewings", ["status", "starts_at"])


def downgrade() -> None:
    for name in ("ix_viewings_status_starts", "ix_viewings_requester_starts",
                 "ix_viewings_listing_starts"):
        op.drop_index(name, table_name="viewings")
    op.drop_table("viewings")
    op.drop_index("ix_viewing_blackouts_listing_id", table_name="viewing_blackouts")
    op.drop_table("viewing_blackouts")
    op.drop_index("ix_viewing_windows_listing_id", table_name="viewing_windows")
    op.drop_table("viewing_windows")
    op.drop_table("viewing_settings")
