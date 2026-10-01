"""Reports and moderation decisions — TASK-015 Slice 1 (04 §64–§65, 04a §23).

Revision ID: a3c5e7f9b1d4
Revises: 0c4e6a8b2d91
Create Date: 2026-10-01

New tables:

* `reports` — a user's signal about a target (no API until Slice 2); one live
  report per (reporter, target).
* `moderation_decisions` — immutable; one chain per target. The chain cannot
  fork: UNIQUE(supersedes_decision_id); one first decision per target (partial
  UNIQUE); a decision supersedes only a decision on the same target (composite
  foreign key). Append-only trigger `moderation_decisions_append_only`, so the
  grant convergence (app_grants.sql) withholds UPDATE/DELETE/TRUNCATE from the
  application role and the startup check verifies it.
* `moderation_review_requests` — the reconsideration seam (Slice 5).

Existing table: `user_notifications.category` admits TRANSACTIONAL (moderation
notices, D-9; written from Slice 3).

schema_transition EXPAND — tables the previous release never reads, and a CHECK
that only widens. rollback_to_previous BLOCKED — the previous release's
publication ignores moderation holds: run against this schema it would let an
owner republish a listing moderation is holding.

No backfill: there are no reports or decisions before this revision.
Downgrade (dev only) drops the three tables and narrows the CHECK again.
"""

import sqlalchemy as sa

from alembic import op

revision = "a3c5e7f9b1d4"
down_revision = "0c4e6a8b2d91"
branch_labels = None
depends_on = None

schema_transition = "EXPAND"
rollback_to_previous = "BLOCKED"

REPORT_TARGET_TYPES = ("LISTING", "USER", "MESSAGE", "MEDIA", "PROPERTY")
REPORT_CATEGORIES = (
    "FAKE", "DUPLICATE", "SCAM", "DISCRIMINATION", "ILLEGAL_CONTENT", "STOLEN_MEDIA",
    "HARASSMENT", "SAFETY", "MISLEADING_PRICE", "IMPERSONATION", "SPAM", "OTHER",
)
SEVERITIES = ("NORMAL", "HIGH", "URGENT")
REPORT_STATUSES = ("OPEN", "TRIAGED", "IN_REVIEW", "RESOLVED", "CLOSED")
DECISION_TARGET_TYPES = ("LISTING", "MEDIA", "MESSAGE", "CONVERSATION")
DECISION_ACTIONS = (
    "NO_ACTION", "WARNING", "CONTENT_EDIT_REQUIRED", "VISIBILITY_LIMITED",
    "CONTENT_REMOVED", "FEATURE_RESTRICTED", "ACCOUNT_LIMITED", "ACCOUNT_SUSPENDED",
    "ACCOUNT_TERMINATED",
)
DECISION_REASON_CODES = (*REPORT_CATEGORIES, "NOT_A_VIOLATION", "REINSTATED_REMEDIED",
                         "REINSTATED_DECISION_ERROR")
LIVE = sa.text("status IN ('OPEN', 'IN_REVIEW')")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reporter_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(8), nullable=False, server_default="NORMAL"),
        sa.Column("status", sa.String(12), nullable=False, server_default="OPEN"),
        sa.Column("external_ticket_id", sa.String(64), nullable=True),
        sa.Column("listing_id", sa.String(36), sa.ForeignKey("classified_offers.id"),
                  nullable=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id"),
                  nullable=True),
        sa.Column("snapshot", sa.JSON, nullable=True),
        sa.Column("listing_public_generation_at_report", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=_now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=_now()),
        sa.Column("first_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_decision_id", sa.String(36), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.CheckConstraint(_in("target_type", REPORT_TARGET_TYPES), name="ck_reports_target_type"),
        sa.CheckConstraint(_in("category", REPORT_CATEGORIES), name="ck_reports_category"),
        sa.CheckConstraint(_in("severity", SEVERITIES), name="ck_reports_severity"),
        sa.CheckConstraint(_in("status", REPORT_STATUSES), name="ck_reports_status"),
        sa.CheckConstraint("target_type <> 'MESSAGE' OR conversation_id IS NOT NULL",
                           name="ck_reports_message_has_conversation"),
    )
    op.create_index("uq_reports_live_per_reporter_target", "reports",
                    ["reporter_user_id", "target_type", "target_id"], unique=True,
                    postgresql_where=LIVE)
    op.create_index("ix_reports_queue", "reports", ["status", "severity", "created_at"])
    op.create_index("ix_reports_live_target", "reports", ["target_type", "target_id"],
                    postgresql_where=LIVE)

    op.create_table(
        "moderation_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reports.id"), nullable=True),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("listing_id", sa.String(36), sa.ForeignKey("classified_offers.id"),
                  nullable=True),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(32), nullable=False),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("decided_by_user_id", sa.String(36), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("supersedes_decision_id", sa.String(36), nullable=True),
        sa.Column("reclassified_category", sa.String(24), nullable=True),
        sa.Column("close_engagement", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("listing_public_generation_at_decision", sa.Integer, nullable=True),
        sa.Column("appeal_eligible", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False,
                  server_default=_now()),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=_now()),
        sa.CheckConstraint(_in("target_type", DECISION_TARGET_TYPES),
                           name="ck_moderation_decisions_target_type"),
        sa.CheckConstraint(_in("action", DECISION_ACTIONS), name="ck_moderation_decisions_action"),
        sa.CheckConstraint(_in("reason_code", DECISION_REASON_CODES),
                           name="ck_moderation_decisions_reason_code"),
        sa.CheckConstraint("reclassified_category IS NULL OR "
                           + _in("reclassified_category", REPORT_CATEGORIES),
                           name="ck_moderation_decisions_reclassified_category"),
        sa.CheckConstraint("supersedes_decision_id IS NULL OR supersedes_decision_id <> id",
                           name="ck_moderation_decisions_not_self"),
        sa.UniqueConstraint("supersedes_decision_id", name="uq_moderation_decisions_supersedes"),
        sa.UniqueConstraint("id", "target_type", "target_id",
                            name="uq_moderation_decisions_id_target"),
        sa.ForeignKeyConstraint(
            ["supersedes_decision_id", "target_type", "target_id"],
            ["moderation_decisions.id", "moderation_decisions.target_type",
             "moderation_decisions.target_id"],
            name="fk_moderation_decisions_supersedes_same_target"),
    )
    op.create_index("uq_moderation_decisions_first_per_target", "moderation_decisions",
                    ["target_type", "target_id"], unique=True,
                    postgresql_where=sa.text("supersedes_decision_id IS NULL"))
    op.create_index("ix_moderation_decisions_target", "moderation_decisions",
                    ["target_type", "target_id"])
    # Immutable at the database level, whoever connects (the trigger function
    # exists since 2d9d18df4688); the name makes the grant convergence revoke
    # UPDATE/DELETE/TRUNCATE from the application role.
    op.execute(
        "CREATE TRIGGER moderation_decisions_append_only "
        "BEFORE UPDATE OR DELETE ON moderation_decisions "
        "FOR EACH ROW EXECUTE FUNCTION forbid_mutation()"
    )

    op.create_foreign_key("fk_reports_resolution_decision", "reports", "moderation_decisions",
                          ["resolution_decision_id"], ["id"])

    op.create_table(
        "moderation_review_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("moderation_decisions.id"),
                  nullable=False),
        sa.Column("requested_by_user_id", sa.String(36), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="OPEN"),
        sa.Column("answered_by_decision_id", sa.String(36),
                  sa.ForeignKey("moderation_decisions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=_now()),
        sa.CheckConstraint("status IN ('OPEN', 'ANSWERED')",
                           name="ck_moderation_review_requests_status"),
    )
    op.create_index("uq_moderation_review_requests_open_per_decision",
                    "moderation_review_requests", ["decision_id"], unique=True,
                    postgresql_where=sa.text("status = 'OPEN'"))

    op.drop_constraint("ck_user_notifications_category", "user_notifications", type_="check")
    op.create_check_constraint("ck_user_notifications_category", "user_notifications",
                               "category IN ('PRODUCT', 'TRANSACTIONAL')")


def downgrade() -> None:
    op.drop_constraint("ck_user_notifications_category", "user_notifications", type_="check")
    op.create_check_constraint("ck_user_notifications_category", "user_notifications",
                               "category IN ('PRODUCT')")
    op.drop_table("moderation_review_requests")
    op.drop_constraint("fk_reports_resolution_decision", "reports", type_="foreignkey")
    op.execute("DROP TRIGGER IF EXISTS moderation_decisions_append_only ON moderation_decisions")
    op.drop_table("moderation_decisions")
    op.drop_table("reports")
