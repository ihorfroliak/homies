"""Saved listings, saved searches and alerts (TASK-014, D-77…D-81).

Revision ID: f3b5d7e9a1c2
Revises: d0f2b4c6e8a1
Create Date: 2026-09-28

Additive only:

* `classified_offers.public_generation` (BIGINT NOT NULL DEFAULT 0, ≥ 0) and
  `public_since` — the public-eligibility episode counter (publicity.py).
  Backfill: a listing that was ever published (`published_at IS NOT NULL`)
  has had one episode (generation 1, since its publication); a draft never
  published has none (0). No event and no work item is written for that
  history: nothing alerts about listings public before this migration.
* `listing_public_generations` — the durable work identity (listing, generation).
* `saved_listings`, `saved_searches`, `saved_search_anchors`,
  `saved_search_matches`, `alert_deliveries`, `user_notifications`,
  `notification_preferences`, `unsubscribe_tokens`.

Downgrade drops the new tables and columns — i.e. every saved listing,
saved search, match, delivery, inbox entry, preference and unsubscribe token
(TASK-014 user data). Take a backup first; see MIGRATION-ROLLOUT.md.
"""

import sqlalchemy as sa

from alembic import op

revision = "f3b5d7e9a1c2"
down_revision = "d0f2b4c6e8a1"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("classified_offers", sa.Column(
        "public_generation", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("classified_offers", sa.Column("public_since", TZ, nullable=True))
    op.create_check_constraint("ck_classified_offers_public_generation_nonnegative",
                               "classified_offers", "public_generation >= 0")
    op.execute("UPDATE classified_offers SET public_generation = 1, public_since = published_at "
               "WHERE published_at IS NOT NULL")
    op.create_index("ix_classified_offers_public_since", "classified_offers", ["public_since"])

    op.create_table(
        "listing_public_generations",
        sa.Column("listing_id", sa.String(36), sa.ForeignKey("classified_offers.id"),
                  primary_key=True),
        sa.Column("public_generation", sa.BigInteger(), primary_key=True),
        sa.Column("became_public_at", TZ, nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("alert_status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claimed_at", TZ, nullable=True),
        sa.Column("processed_at", TZ, nullable=True),
        sa.Column("last_error", sa.String(255), nullable=False, server_default=""),
        sa.CheckConstraint("public_generation >= 1", name="ck_listing_public_generations_positive"),
        sa.CheckConstraint("alert_status IN ('pending', 'processing', 'done', 'superseded')",
                           name="ck_listing_public_generations_alert_status"),
    )
    op.create_index("ix_listing_public_generations_pending", "listing_public_generations",
                    ["alert_status", "became_public_at"])

    op.create_table(
        "saved_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("listing_id", sa.String(36), sa.ForeignKey("classified_offers.id"),
                  nullable=False),
        sa.Column("saved_at", TZ, nullable=False),
        sa.UniqueConstraint("user_id", "listing_id", name="uq_saved_listings_user_listing"),
    )
    op.create_index("ix_saved_listings_user_saved_at", "saved_listings", ["user_id", "saved_at"])
    op.create_index("ix_saved_listings_listing_id", "saved_listings", ["listing_id"])

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("market_country_code", sa.String(2), nullable=True),
        sa.Column("canonical_query", sa.Text(), nullable=False),
        sa.Column("query_schema_version", sa.Integer(), nullable=False),
        sa.Column("query_fingerprint", sa.String(64), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("baseline_at", TZ, nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("user_id", "query_fingerprint",
                            name="uq_saved_searches_user_fingerprint"),
        sa.CheckConstraint("status IN ('active', 'paused')", name="ck_saved_searches_status"),
        sa.CheckConstraint("query_schema_version >= 1", name="ck_saved_searches_schema_version"),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 80", name="ck_saved_searches_name_length"),
        sa.CheckConstraint("length(query_fingerprint) = 64",
                           name="ck_saved_searches_fingerprint_length"),
    )
    op.create_index("ix_saved_searches_user_created", "saved_searches", ["user_id", "created_at"])

    op.create_table(
        "saved_search_anchors",
        sa.Column("saved_search_id", sa.String(36),
                  sa.ForeignKey("saved_searches.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kind", sa.String(1), primary_key=True),
        sa.Column("value", sa.String(36), primary_key=True),
        sa.CheckConstraint("kind IN ('L', 'G', 'A', 'C', '*')", name="ck_saved_search_anchors_kind"),
    )
    op.create_index("ix_saved_search_anchors_key", "saved_search_anchors", ["kind", "value"])

    op.create_table(
        "saved_search_matches",
        sa.Column("saved_search_id", sa.String(36),
                  sa.ForeignKey("saved_searches.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("listing_id", sa.String(36), sa.ForeignKey("classified_offers.id"),
                  primary_key=True),
        sa.Column("public_generation", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
    )
    op.create_index("ix_saved_search_matches_episode", "saved_search_matches",
                    ["listing_id", "public_generation", "user_id"])

    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("listing_id", sa.String(36), sa.ForeignKey("classified_offers.id"),
                  nullable=False),
        sa.Column("public_generation", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(8), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", TZ, nullable=False),
        sa.Column("claimed_at", TZ, nullable=True),
        sa.Column("outcome", sa.String(48), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("completed_at", TZ, nullable=True),
        sa.UniqueConstraint("user_id", "listing_id", "public_generation", "channel",
                            name="uq_alert_deliveries_user_episode_channel"),
        sa.CheckConstraint("channel IN ('IN_APP', 'EMAIL')", name="ck_alert_deliveries_channel"),
        sa.CheckConstraint("category IN ('PRODUCT')", name="ck_alert_deliveries_category"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'delivered', 'suppressed', 'failed', 'dead')",
            name="ck_alert_deliveries_status"),
    )
    op.create_index("ix_alert_deliveries_due", "alert_deliveries", ["status", "next_attempt_at"])
    op.create_index("ix_alert_deliveries_user_id", "alert_deliveries", ["user_id"])

    op.create_table(
        "user_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("notification_type", sa.String(48), nullable=False),
        sa.Column("title_key", sa.String(96), nullable=False),
        sa.Column("body_key", sa.String(96), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("delivery_id", sa.String(36), sa.ForeignKey("alert_deliveries.id"),
                  nullable=True, unique=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("read_at", TZ, nullable=True),
        sa.CheckConstraint("category IN ('PRODUCT')", name="ck_user_notifications_category"),
    )
    op.create_index("ix_user_notifications_user_created", "user_notifications",
                    ["user_id", "created_at"])

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("category", sa.String(16), primary_key=True),
        sa.Column("channel", sa.String(8), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("category IN ('PRODUCT')", name="ck_notification_preferences_category"),
        sa.CheckConstraint("channel IN ('IN_APP', 'EMAIL')",
                           name="ck_notification_preferences_channel"),
    )

    op.create_table(
        "unsubscribe_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("saved_search_id", sa.String(36),
                  sa.ForeignKey("saved_searches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("used_at", TZ, nullable=True),
        sa.CheckConstraint("scope IN ('SAVED_SEARCH', 'PRODUCT_EMAIL')",
                           name="ck_unsubscribe_tokens_scope"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_unsubscribe_tokens_hash_length"),
    )
    op.create_index("ix_unsubscribe_tokens_user_id", "unsubscribe_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("unsubscribe_tokens")
    op.drop_table("notification_preferences")
    op.drop_table("user_notifications")
    op.drop_table("alert_deliveries")
    op.drop_table("saved_search_matches")
    op.drop_table("saved_search_anchors")
    op.drop_table("saved_searches")
    op.drop_table("saved_listings")
    op.drop_table("listing_public_generations")
    op.drop_index("ix_classified_offers_public_since", table_name="classified_offers")
    op.drop_constraint("ck_classified_offers_public_generation_nonnegative", "classified_offers")
    op.drop_column("classified_offers", "public_since")
    op.drop_column("classified_offers", "public_generation")
