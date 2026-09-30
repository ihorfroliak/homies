"""Engagement integrity: one active thread per requester+listing; coherent cancellation.

Revision ID: d3f5b7a9c1e4
Revises: c1e3a5b7d9f2
Create Date: 2026-09-24

TASK-001 F-09 produced two ACTIVE conversations for one tenant and one
listing; F-06 produced a viewing CONFIRMED with a cancellation time. The code
now serialises both, and the database refuses the states outright:

* uq_conversations_active_requester_listing — partial UNIQUE on
  (listing_id, requester_user_id) WHERE status = 'ACTIVE';
* ck_viewings_cancelled_state — cancelled_at is set exactly when CANCELLED.

Existing violations are reported, not repaired: merging two threads' messages
or deciding whether a viewing really took place is not a migration's call.

Operational note: the index build locks writes on conversations for its
duration (plain CREATE INDEX inside the migration transaction); see
docs/database/MIGRATION-ROLLOUT.md.
"""

import sqlalchemy as sa
from alembic import op

revision = "d3f5b7a9c1e4"
down_revision = "c1e3a5b7d9f2"
branch_labels = None
depends_on = None

INDEX = "uq_conversations_active_requester_listing"
CHECK = "ck_viewings_cancelled_state"


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(sa.text(
        "SELECT listing_id, requester_user_id, count(*) FROM conversations "
        "WHERE status = 'ACTIVE' AND listing_id IS NOT NULL "
        "GROUP BY listing_id, requester_user_id HAVING count(*) > 1"
    )).all()
    if duplicates:
        raise RuntimeError(
            f"{len(duplicates)} requester/listing pair(s) have more than one ACTIVE "
            "conversation. Close the extra threads by hand; this migration will not merge "
            f"them. First: {[(d[0], d[1]) for d in duplicates[:10]]}"
        )
    incoherent = bind.execute(sa.text(
        "SELECT id FROM viewings WHERE (status = 'CANCELLED') <> (cancelled_at IS NOT NULL) "
        "ORDER BY id"
    )).scalars().all()
    if incoherent:
        raise RuntimeError(
            f"{len(incoherent)} viewing(s) have a status that contradicts cancelled_at. "
            f"Correct them by hand. First ids: {', '.join(incoherent[:20])}"
        )

    op.create_index(
        INDEX, "conversations", ["listing_id", "requester_user_id"], unique=True,
        postgresql_where=sa.text("status = 'ACTIVE' AND listing_id IS NOT NULL"),
    )
    op.create_check_constraint(CHECK, "viewings", "(status = 'CANCELLED') = (cancelled_at IS NOT NULL)")


def downgrade() -> None:
    op.drop_constraint(CHECK, "viewings", type_="check")
    op.drop_index(INDEX, table_name="conversations")
