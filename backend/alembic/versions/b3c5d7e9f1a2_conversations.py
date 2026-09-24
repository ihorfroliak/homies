"""Conversations, participants and messages (Domain Schema v1 §53–§55).

The first message channel on the board — the one an owner who chose
"messages only" has been waiting for. Nothing to backfill.

Revision ID: b3c5d7e9f1a2
Revises: a8b2c4d6e1f3
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from alembic import op

revision = "b3c5d7e9f1a2"
down_revision = "a8b2c4d6e1f3"
branch_labels = None
depends_on = None

STAGES = ("NEW", "REPLIED", "VIEWING", "APPLICATION", "SHORTLISTED", "ACCEPTED",
          "REJECTED", "ARCHIVED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _fk(name: str, target: str, nullable: bool = False, ondelete: str = "RESTRICT"):
    return sa.Column(name, sa.String(36), sa.ForeignKey(target, ondelete=ondelete),
                     nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        _fk("listing_id", "classified_offers.id", nullable=True),
        sa.Column("viewing_id", sa.String(36), nullable=True),
        _fk("requester_user_id", "users.id"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider_stage", sa.String(16), nullable=True),
        _fk("assigned_to_user_id", "users.id", nullable=True),
        _ts("created_at"), _ts("updated_at"), _ts("last_message_at", nullable=True),
        _ts("archived_at", nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_in("status", ("ACTIVE", "ARCHIVED", "CLOSED")),
                           name="ck_conversations_status"),
        sa.CheckConstraint(f"provider_stage IS NULL OR {_in('provider_stage', STAGES)}",
                           name="ck_conversations_provider_stage"),
        sa.CheckConstraint("listing_id IS NOT NULL OR viewing_id IS NOT NULL",
                           name="ck_conversations_has_context"),
    )
    op.create_index("ix_conversations_listing_id", "conversations", ["listing_id"])
    op.create_index("ix_conversations_requester_user_id", "conversations", ["requester_user_id"])

    op.create_table(
        "conversation_participants",
        sa.Column("id", sa.String(36), primary_key=True),
        _fk("conversation_id", "conversations.id", ondelete="CASCADE"),
        sa.Column("participant_type", sa.String(16), nullable=False),
        _fk("user_id", "users.id", nullable=True),
        _fk("organization_id", "organizations.id", nullable=True),
        _ts("joined_at"), _ts("left_at", nullable=True),
        sa.CheckConstraint(_in("participant_type", ("USER", "ORGANIZATION")),
                           name="ck_conversation_participants_type"),
        sa.CheckConstraint(
            "(participant_type = 'USER' AND user_id IS NOT NULL AND organization_id IS NULL) "
            "OR (participant_type = 'ORGANIZATION' AND organization_id IS NOT NULL "
            "AND user_id IS NULL)",
            name="ck_conversation_participants_one_identity",
        ),
    )
    op.create_index("ix_conversation_participants_conversation_id",
                    "conversation_participants", ["conversation_id"])
    op.create_index("ix_conversation_participants_user_id", "conversation_participants",
                    ["user_id"])
    op.create_index("uq_conversation_participants_user", "conversation_participants",
                    ["conversation_id", "user_id"], unique=True,
                    postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_conversation_participants_organization", "conversation_participants",
                    ["conversation_id", "organization_id"], unique=True,
                    postgresql_where=sa.text("organization_id IS NOT NULL"))

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        _fk("conversation_id", "conversations.id"),
        _fk("sender_user_id", "users.id", nullable=True),
        _fk("sender_organization_id", "organizations.id", nullable=True),
        sa.Column("message_type", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        _ts("created_at"), _ts("edited_at", nullable=True), _ts("redacted_at", nullable=True),
        sa.Column("redaction_reason_code", sa.String(40), nullable=True),
        sa.CheckConstraint(_in("message_type", ("USER", "SYSTEM")), name="ck_messages_type"),
        sa.CheckConstraint("message_type = 'SYSTEM' OR sender_user_id IS NOT NULL",
                           name="ck_messages_user_message_has_sender"),
    )
    op.create_index("ix_messages_conversation_created", "messages",
                    ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    for name in ("uq_conversation_participants_organization", "uq_conversation_participants_user",
                 "ix_conversation_participants_user_id",
                 "ix_conversation_participants_conversation_id"):
        op.drop_index(name, table_name="conversation_participants")
    op.drop_table("conversation_participants")
    op.drop_index("ix_conversations_requester_user_id", table_name="conversations")
    op.drop_index("ix_conversations_listing_id", table_name="conversations")
    op.drop_table("conversations")
