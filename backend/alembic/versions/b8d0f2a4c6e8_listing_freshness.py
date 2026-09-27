"""Listing freshness and a closed status vocabulary (TASK-012, D-59–D-62).

Revision ID: b8d0f2a4c6e8
Revises: a7c9e1f3b5d7
Create Date: 2026-09-27

Additive:

* `classified_offers.last_confirmed_available_at` (04 §43) — when someone with
  authority last confirmed the offer is still current. `reconfirm_at` and
  `stale_at` are derived from it by policy, never stored (D-60).
* CHECK on `classified_offers.status`: draft | active | paused | stale |
  archived. `stale` is new (04 §43 STALE). The migration refuses to run if a
  row holds any other value, rather than guess what it meant.
* index (status, last_confirmed_available_at) for the visibility rule and the
  sweep.

Backfill: `last_confirmed_available_at = published_at` wherever a publication
is on record — the only confirmation evidence that exists. Nothing newer is
invented; never-published rows stay NULL.

No lifecycle transition happens here (D-62). A listing whose evidence is older
than the policy window stops being *shown* the moment the new code runs (the
visibility rule is evaluated on read), but its status is changed only by the
freshness sweep, run deliberately. Before deploying onto real inventory, run
`python -m app.scripts.listing_freshness preflight` to see what would leave
the board (docs/database/MIGRATION-ROLLOUT.md).

Downgrade: `stale` rows become `paused` (not public either way; the previous
code does not know `stale`), then the column, index and CHECK are dropped.
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d0f2a4c6e8"
down_revision = "a7c9e1f3b5d7"
branch_labels = None
depends_on = None

STATUSES = ("draft", "active", "paused", "stale", "archived")
CHECK = "ck_classified_offers_status"
INDEX = "ix_classified_offers_status_confirmed"


def upgrade() -> None:
    bind = op.get_bind()
    unknown = [row[0] for row in bind.execute(sa.text(
        "SELECT DISTINCT status FROM classified_offers WHERE status NOT IN "
        "('draft', 'active', 'paused', 'stale', 'archived')"))]
    if unknown:
        raise RuntimeError(
            f"classified_offers.status holds values outside {STATUSES}: {unknown}. "
            "Resolve them explicitly before this migration; it will not guess.")
    op.add_column("classified_offers", sa.Column(
        "last_confirmed_available_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE classified_offers SET last_confirmed_available_at = published_at "
               "WHERE published_at IS NOT NULL")
    op.create_check_constraint(
        CHECK, "classified_offers",
        "status IN ('draft', 'active', 'paused', 'stale', 'archived')")
    op.create_index(INDEX, "classified_offers", ["status", "last_confirmed_available_at"])


def downgrade() -> None:
    op.execute("UPDATE classified_offers SET status = 'paused' WHERE status = 'stale'")
    op.drop_index(INDEX, table_name="classified_offers")
    op.drop_constraint(CHECK, "classified_offers", type_="check")
    op.drop_column("classified_offers", "last_confirmed_available_at")
