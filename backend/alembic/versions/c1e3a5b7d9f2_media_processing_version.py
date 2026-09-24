"""Media: record the processing pipeline; quarantine bytes from the C8 walker.

Revision ID: c1e3a5b7d9f2
Revises: b8d0f2a4c6e1
Create Date: 2026-09-24

TASK-001 F-02 showed the C8 structure walker let metadata (GPS in APP1 after
the first scan, APP2/APP14 payloads, bytes after a false EOI, a PNG iCCP name)
reach public bytes. There is no production deployment, but any environment
that ran C8 may hold such files, and approval by a moderator does not make
them safe — the moderator judged the picture, not its bytes.

So every file that no pipeline version vouches for is quarantined: state
QUARANTINED, access class QUARANTINE. The serving path requires READY and the
current processing_version, so these files are unreachable until
`python -m app.scripts.reprocess_media` decodes and re-encodes them. Nothing
is deleted and moderation decisions are kept.

Downgrade drops the column but deliberately leaves the files quarantined: it
must not turn unsafe bytes back into served ones.
"""

import sqlalchemy as sa
from alembic import op

revision = "c1e3a5b7d9f2"
down_revision = "b8d0f2a4c6e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("file_objects", sa.Column("processing_version", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE file_objects SET state = 'QUARANTINED', access_class = 'QUARANTINE' "
        "WHERE processing_version IS NULL AND purpose = 'PROPERTY_MEDIA' "
        "AND state NOT IN ('REJECTED', 'DELETED')"
    )


def downgrade() -> None:
    op.drop_column("file_objects", "processing_version")
