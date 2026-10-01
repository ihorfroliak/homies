"""Schema lineage: the database records its migration ancestry (PR-002).

Revision ID: 0c4e6a8b2d91
Revises: f3b5d7e9a1c2
Create Date: 2026-09-30

`schema_lineage` holds one row per applied migration: its parent and its two
compatibility declarations (schema_transition EXPAND | BARRIER,
rollback_to_previous SAFE | BLOCKED). A build compares the database's
revision with its own migration graph; for a revision newer than itself it can
only follow this table back to its own head (app/core/release.py). Revision
ids are graph nodes, never compared as strings.

Written by the migration role only: the Alembic `on_version_apply` hook in
env.py records every step applied after this one; this migration backfills
the 26 steps before it from the frozen historical classification
(app/core/lineage_registry.py — a test pins the two together). The
application role may only read it (app/core/sql/app_role.sql).

This step itself: schema_transition EXPAND — one new table the previous
release never reads; rollback_to_previous BLOCKED — the previous release
(IBB-001) still requires its database to be exactly at its own head, so it
refuses to start once this revision is applied. That is the bootstrap cost of
introducing the compatibility model, stated rather than hidden.

Downgrade (dev only) drops the table and with it the recorded lineage.
"""

import sqlalchemy as sa

from alembic import op

revision = "0c4e6a8b2d91"
down_revision = "f3b5d7e9a1c2"
branch_labels = None
depends_on = None

schema_transition = "EXPAND"
rollback_to_previous = "BLOCKED"

# Frozen: (revision, down_revision, schema_transition, rollback_to_previous),
# base first. Never edit — historical evidence.
HISTORY = [
    ("2d9d18df4688", None, "BARRIER", "BLOCKED"),
    ("87cebed1635f", "2d9d18df4688", "EXPAND", "SAFE"),
    ("b910997aa651", "87cebed1635f", "BARRIER", "BLOCKED"),
    ("f91f4ece13f6", "b910997aa651", "EXPAND", "SAFE"),
    ("c4d2e77a1b30", "f91f4ece13f6", "BARRIER", "BLOCKED"),
    ("9010d2077493", "c4d2e77a1b30", "EXPAND", "SAFE"),
    ("d3f81ba0c47e", "9010d2077493", "EXPAND", "BLOCKED"),
    ("e5a2c91b7d34", "d3f81ba0c47e", "EXPAND", "SAFE"),
    ("a1c6d2e8b407", "e5a2c91b7d34", "EXPAND", "SAFE"),
    ("b7e4f19a2c60", "a1c6d2e8b407", "EXPAND", "BLOCKED"),
    ("c9d3a5e71f28", "b7e4f19a2c60", "BARRIER", "BLOCKED"),
    ("d4e8b2c61a95", "c9d3a5e71f28", "BARRIER", "BLOCKED"),
    ("f1a7c3d9e2b4", "d4e8b2c61a95", "EXPAND", "BLOCKED"),
    ("a8b2c4d6e1f3", "f1a7c3d9e2b4", "EXPAND", "SAFE"),
    ("b3c5d7e9f1a2", "a8b2c4d6e1f3", "EXPAND", "SAFE"),
    ("c4d6e8f0a2b3", "b3c5d7e9f1a2", "EXPAND", "SAFE"),
    ("d5e7f9a1b3c4", "c4d6e8f0a2b3", "EXPAND", "SAFE"),
    ("a7c9e1f3b5d2", "d5e7f9a1b3c4", "EXPAND", "SAFE"),
    ("b8d0f2a4c6e1", "a7c9e1f3b5d2", "EXPAND", "SAFE"),
    ("c1e3a5b7d9f2", "b8d0f2a4c6e1", "EXPAND", "BLOCKED"),
    ("d3f5b7a9c1e4", "c1e3a5b7d9f2", "EXPAND", "SAFE"),
    ("e4f6a8b0c2d4", "d3f5b7a9c1e4", "BARRIER", "BLOCKED"),
    ("a7c9e1f3b5d7", "e4f6a8b0c2d4", "EXPAND", "SAFE"),
    ("b8d0f2a4c6e8", "a7c9e1f3b5d7", "EXPAND", "BLOCKED"),
    ("d0f2b4c6e8a1", "b8d0f2a4c6e8", "EXPAND", "SAFE"),
    ("f3b5d7e9a1c2", "d0f2b4c6e8a1", "EXPAND", "BLOCKED"),
]


def upgrade() -> None:
    op.create_table(
        "schema_lineage",
        sa.Column("revision", sa.String(32), primary_key=True),
        sa.Column("down_revision", sa.String(32), nullable=True),
        sa.Column("schema_transition", sa.String(16), nullable=False),
        sa.Column("rollback_to_previous", sa.String(8), nullable=False),
        sa.Column("recorded_by", sa.String(16), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("schema_transition IN ('EXPAND', 'BARRIER')",
                           name="ck_schema_lineage_transition"),
        sa.CheckConstraint("rollback_to_previous IN ('SAFE', 'BLOCKED')",
                           name="ck_schema_lineage_rollback"),
        sa.CheckConstraint("NOT (schema_transition = 'BARRIER' AND rollback_to_previous = 'SAFE')",
                           name="ck_schema_lineage_barrier_blocks_rollback"),
        sa.CheckConstraint("recorded_by IN ('BACKFILL', 'MIGRATION')",
                           name="ck_schema_lineage_recorded_by"),
    )
    lineage = sa.table("schema_lineage", sa.column("revision"), sa.column("down_revision"),
                       sa.column("schema_transition"), sa.column("rollback_to_previous"),
                       sa.column("recorded_by"))
    op.bulk_insert(lineage, [
        {"revision": r, "down_revision": d, "schema_transition": t,
          "rollback_to_previous": rb, "recorded_by": "BACKFILL"}
        for r, d, t, rb in HISTORY
    ])


def downgrade() -> None:
    op.drop_table("schema_lineage")
