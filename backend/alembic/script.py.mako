"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

# Compatibility declarations (PR-002, docs/production/RELEASE-AND-MIGRATION.md).
# Decide both; the defaults are the fail-closed ones.
#   schema_transition: EXPAND  — the previous release keeps working on the new schema;
#                      BARRIER — it does not (drop, one-step NOT NULL, incompatible state).
#   rollback_to_previous: SAFE — the previous release may run on / return to this schema
#                         without reopening a fixed defect or losing an invariant; else BLOCKED.
#                         A BARRIER is always BLOCKED.
schema_transition = "BARRIER"
rollback_to_previous = "BLOCKED"


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
