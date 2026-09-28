"""Discovery indexes (TASK-013, D-74).

Revision ID: d0f2b4c6e8a1
Revises: b8d0f2a4c6e8
Create Date: 2026-09-28

Two indexes, each justified by EXPLAIN ANALYZE on ~5 000 synthetic listings
(docs/tasks/TASK-013-search-map-marketplace-discovery.md):

* `addresses(geo_area_id)` — the search-area filter was a sequential scan of
  `addresses`; its siblings (locality, admin area, country) are indexed.
* `classified_offers(primary_price_minor)` — the base-rent range filter was
  a sequential scan discarding ~98 % of rows; the monthly total already has
  an index.

No data is changed. Plain CREATE INDEX (brief write lock on each table) —
see docs/database/MIGRATION-ROLLOUT.md for running it on a large table.
"""

from alembic import op

revision = "d0f2b4c6e8a1"
down_revision = "b8d0f2a4c6e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_addresses_geo_area", "addresses", ["geo_area_id"])
    op.create_index("ix_classified_offers_primary_price_minor", "classified_offers",
                    ["primary_price_minor"])


def downgrade() -> None:
    op.drop_index("ix_classified_offers_primary_price_minor", table_name="classified_offers")
    op.drop_index("ix_addresses_geo_area", table_name="addresses")
