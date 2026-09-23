"""Spaces: the whole flat, or one room in it (Domain Schema v1 §28, §42).

A listing now points at a space, not straight at a property. Two guarantees
move into the database, where a bug cannot quietly break them:

* at most one active WHOLE_PROPERTY space per property (partial unique index) —
  two would let the same flat be let twice, as a whole, through two listings;
* a listing's space belongs to the listing's property (composite foreign key)
  — otherwise a listing could point at a room in someone else's flat and be
  published under the wrong address.

Backfill: every property gets its whole-property space, and every existing
listing is attached to it. Nothing existing was a room-level listing, so no
listing is re-scoped.

Revision ID: c9d3a5e71f28
Revises: b7e4f19a2c60
Create Date: 2026-09-23
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "c9d3a5e71f28"
down_revision = "b7e4f19a2c60"
branch_labels = None
depends_on = None

_ONE_ACTIVE_WHOLE = "space_type = 'WHOLE_PROPERTY' AND archived_at IS NULL"
_ACTIVE_ROOM = "space_type = 'ROOM' AND archived_at IS NULL"


def upgrade() -> None:
    op.create_table(
        "spaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("property_id", sa.String(36),
                  sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("space_type", sa.String(16), nullable=False),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("area_m2", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("space_type IN ('WHOLE_PROPERTY', 'ROOM')",
                           name="ck_spaces_space_type"),
        sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="ck_spaces_status"),
        sa.CheckConstraint("area_m2 IS NULL OR area_m2 > 0", name="ck_spaces_area_positive"),
        sa.CheckConstraint("space_type = 'ROOM' OR label IS NULL",
                           name="ck_spaces_label_rooms_only"),
        sa.UniqueConstraint("id", "property_id", name="uq_spaces_id_property"),
    )
    op.create_index("ix_spaces_property_id", "spaces", ["property_id"])
    op.create_index("uq_spaces_one_active_whole", "spaces", ["property_id"], unique=True,
                    postgresql_where=sa.text(_ONE_ACTIVE_WHOLE))
    op.create_index("uq_spaces_active_room_label", "spaces", ["property_id", "label"],
                    unique=True, postgresql_where=sa.text(_ACTIVE_ROOM))

    conn = op.get_bind()
    for (property_id,) in conn.execute(sa.text("SELECT id FROM properties")).fetchall():
        conn.execute(
            sa.text(
                "INSERT INTO spaces (id, property_id, space_type, status, created_at, "
                "updated_at, version) VALUES (:id, :prop, 'WHOLE_PROPERTY', 'ACTIVE', "
                "now(), now(), 1)"
            ),
            {"id": str(uuid4()), "prop": property_id},
        )

    op.add_column("classified_offers", sa.Column("space_id", sa.String(36), nullable=True))
    conn.execute(
        sa.text(
            "UPDATE classified_offers o SET space_id = s.id FROM spaces s "
            "WHERE s.property_id = o.property_id AND s.space_type = 'WHOLE_PROPERTY'"
        )
    )
    op.alter_column("classified_offers", "space_id", nullable=False)
    op.create_index("ix_classified_offers_space_id", "classified_offers", ["space_id"])
    op.create_foreign_key(
        "fk_classified_offers_space_same_property",
        "classified_offers", "spaces",
        ["space_id", "property_id"], ["id", "property_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_classified_offers_space_same_property", "classified_offers",
                       type_="foreignkey")
    op.drop_index("ix_classified_offers_space_id", table_name="classified_offers")
    op.drop_column("classified_offers", "space_id")
    op.drop_index("uq_spaces_active_room_label", table_name="spaces")
    op.drop_index("uq_spaces_one_active_whole", table_name="spaces")
    op.drop_index("ix_spaces_property_id", table_name="spaces")
    op.drop_table("spaces")
