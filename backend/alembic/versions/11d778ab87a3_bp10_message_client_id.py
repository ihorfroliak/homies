"""Idempotent message sends — BP-10 (D-108, FE-003 §10.1 "equivalent unique key").

Revision ID: 11d778ab87a3
Revises: a3c5e7f9b1d4
Create Date: 2026-10-10

Existing table `messages` gains `client_message_id varchar(36) NULL`: the
UUID v4 a client mints for one logical send and reuses for its retries. The
partial unique index `uq_messages_sender_client_message (sender_user_id,
client_message_id) WHERE client_message_id IS NOT NULL` makes the pair the
authoritative idempotency identity — at most one message per sender per
logical send, whichever of the two send routes wrote it.

No default and no backfill: every existing row (and every SYSTEM line) keeps
NULL, which the predicate leaves out of the index: the build scans the whole
table and produces an empty index. ADD COLUMN and the non-concurrent CREATE
INDEX run in one migration transaction, so ACCESS EXCLUSIVE on `messages` is
held until it commits, index build included — application reads and writes of
`messages` wait for it (bounded by their 2 s lock_timeout → 503, and the job
by its own lock budget). Homies is not deployed.

schema_transition EXPAND — the previous release never reads the column and
its INSERTs leave it NULL. rollback_to_previous BLOCKED — the previous
release silently drops `client_message_id` from requests (its MessageIn does
not forbid extra fields), so returning to it restores the unkeyed
message-write path and reopens the duplicate-send defect (BP-10 / BB-11).

Downgrade (dev only) drops the index and the column.
"""

import sqlalchemy as sa

from alembic import op

revision = "11d778ab87a3"
down_revision = "a3c5e7f9b1d4"
branch_labels = None
depends_on = None

schema_transition = "EXPAND"
rollback_to_previous = "BLOCKED"

KEYED = "client_message_id IS NOT NULL"


def upgrade() -> None:
    op.add_column("messages", sa.Column("client_message_id", sa.String(36), nullable=True))
    op.create_index("uq_messages_sender_client_message", "messages",
                    ["sender_user_id", "client_message_id"], unique=True,
                    postgresql_where=sa.text(KEYED), sqlite_where=sa.text(KEYED))


def downgrade() -> None:
    op.drop_index("uq_messages_sender_client_message", table_name="messages")
    op.drop_column("messages", "client_message_id")
