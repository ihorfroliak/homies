"""File objects, media assets and listing media (Domain Schema v1 §36–§38, §48).

Revision ID: d5e7f9a1b3c4
Revises: c4d6e8f0a2b3
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e7f9a1b3c4"
down_revision = "c4d6e8f0a2b3"
branch_labels = None
depends_on = None

PURPOSES = ("PROPERTY_MEDIA", "MESSAGE_ATTACHMENT", "SAFETY_EVIDENCE", "EPC_DOCUMENT",
            "REPORT_EVIDENCE")
STATES = ("UPLOADING", "QUARANTINED", "PROCESSING", "READY", "REJECTED", "DELETED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "file_objects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("uploader_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("storage_provider", sa.String(24), nullable=False),
        sa.Column("storage_bucket", sa.String(120), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("access_class", sa.String(16), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(80), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        _ts("created_at"), _ts("ready_at", nullable=True), _ts("rejected_at", nullable=True),
        _ts("deleted_at", nullable=True),
        sa.CheckConstraint(_in("purpose", PURPOSES), name="ck_file_objects_purpose"),
        sa.CheckConstraint(_in("access_class", ("QUARANTINE", "PUBLIC", "PRIVATE")),
                           name="ck_file_objects_access"),
        sa.CheckConstraint(_in("state", STATES), name="ck_file_objects_state"),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_file_objects_size"),
        sa.UniqueConstraint("storage_provider", "storage_bucket", "storage_key",
                            name="uq_file_objects_location"),
    )
    op.create_index("ix_file_objects_uploader_user_id", "file_objects", ["uploader_user_id"])
    op.create_index("ix_file_objects_sha256", "file_objects", ["sha256"])

    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("property_id", sa.String(36),
                  sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("space_id", sa.String(36), sa.ForeignKey("spaces.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("file_objects.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("media_type", sa.String(16), nullable=False),
        sa.Column("visibility", sa.String(10), nullable=False),
        sa.Column("moderation_state", sa.String(16), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        _ts("rights_declared_at", nullable=True), _ts("created_at"),
        _ts("archived_at", nullable=True),
        sa.CheckConstraint(_in("media_type", ("PHOTO", "FLOOR_PLAN", "VIDEO", "TOUR_360")),
                           name="ck_media_assets_type"),
        sa.CheckConstraint(_in("moderation_state",
                               ("PENDING", "APPROVED", "REJECTED", "RESTRICTED")),
                           name="ck_media_assets_moderation"),
        sa.CheckConstraint("visibility IN ('PUBLIC', 'PRIVATE')", name="ck_media_assets_visibility"),
    )
    op.create_index("ix_media_assets_property_id", "media_assets", ["property_id"])

    op.create_table(
        "listing_media",
        sa.Column("listing_id", sa.String(36),
                  sa.ForeignKey("classified_offers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("media_asset_id", sa.String(36),
                  sa.ForeignKey("media_assets.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_cover", sa.Boolean(), nullable=False),
        _ts("created_at"),
    )
    op.create_index("uq_listing_media_one_cover", "listing_media", ["listing_id"], unique=True,
                    postgresql_where=sa.text("is_cover = true"))
    op.create_index("ix_listing_media_order", "listing_media", ["listing_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_listing_media_order", table_name="listing_media")
    op.drop_index("uq_listing_media_one_cover", table_name="listing_media")
    op.drop_table("listing_media")
    op.drop_index("ix_media_assets_property_id", table_name="media_assets")
    op.drop_table("media_assets")
    op.drop_index("ix_file_objects_sha256", table_name="file_objects")
    op.drop_index("ix_file_objects_uploader_user_id", table_name="file_objects")
    op.drop_table("file_objects")
