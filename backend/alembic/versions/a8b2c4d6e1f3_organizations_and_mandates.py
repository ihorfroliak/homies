"""Organizations, memberships and representation mandates (Domain Schema v1 §18–§22).

Opens the two remaining paths by which a person acts for a legal party other
than their own: membership of an organisation that holds rights, and a mandate
from an owner. Nothing is backfilled — no organisation or mandate existed
before this revision.

Revision ID: a8b2c4d6e1f3
Revises: f1a7c3d9e2b4
Create Date: 2026-09-23
"""

import sqlalchemy as sa
from alembic import op

revision = "a8b2c4d6e1f3"
down_revision = "f1a7c3d9e2b4"
branch_labels = None
depends_on = None

MANDATE_SCOPES = (
    "MANAGE_PROPERTY", "PUBLISH_LISTING", "MANAGE_VIEWINGS", "MANAGE_MESSAGES",
    "MANAGE_APPLICATIONS", "SIGN_CONTRACTS", "VIEW_FINANCIALS", "MANAGE_PAYOUTS",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _user_fk(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"),
                     nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("default_locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        _user_fk("created_by_user_id"),
        _ts("created_at"), _ts("updated_at"), _ts("archived_at", nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_in("status", ("ACTIVE", "SUSPENDED", "ARCHIVED")),
                           name="ck_organizations_status"),
    )
    op.create_table(
        "organization_legal_parties",
        sa.Column("legal_party_id", sa.String(36),
                  sa.ForeignKey("legal_parties.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("organization_id", sa.String(36),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True,
                  unique=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("registration_country", sa.String(2), nullable=True),
        sa.Column("registration_number", sa.String(40), nullable=True),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        _user_fk("user_id"),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        _user_fk("invited_by_user_id", nullable=True),
        _ts("joined_at", nullable=True), _ts("revoked_at", nullable=True),
        _ts("created_at"), _ts("updated_at"),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_in("role", ("OWNER", "ADMIN", "AGENT", "FINANCE", "VIEWER")),
                           name="ck_organization_memberships_role"),
        sa.CheckConstraint(_in("status", ("INVITED", "ACTIVE", "REVOKED")),
                           name="ck_organization_memberships_status"),
        sa.UniqueConstraint("organization_id", "user_id",
                            name="uq_organization_memberships_member"),
    )
    op.create_index("ix_organization_memberships_organization_id", "organization_memberships",
                    ["organization_id"])
    op.create_index("ix_organization_memberships_user_id", "organization_memberships",
                    ["user_id"])
    op.create_table(
        "representation_mandates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("principal_legal_party_id", sa.String(36),
                  sa.ForeignKey("legal_parties.id", ondelete="RESTRICT"), nullable=False),
        _user_fk("representative_user_id"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("verification_state", sa.String(16), nullable=False),
        _user_fk("granted_by_user_id", nullable=True),
        _ts("created_at"), _ts("updated_at"), _ts("revoked_at", nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_in("status", ("PENDING", "ACTIVE", "REVOKED", "EXPIRED")),
                           name="ck_representation_mandates_status"),
        sa.CheckConstraint(
            _in("verification_state", ("UNVERIFIED", "PENDING", "VERIFIED", "REJECTED")),
            name="ck_representation_mandates_verification"),
        sa.CheckConstraint("effective_until IS NULL OR effective_until >= effective_from",
                           name="ck_representation_mandates_effective_range"),
    )
    op.create_index("ix_representation_mandates_principal_legal_party_id",
                    "representation_mandates", ["principal_legal_party_id"])
    op.create_index("ix_representation_mandates_representative_user_id",
                    "representation_mandates", ["representative_user_id"])
    op.create_table(
        "representation_mandate_scopes",
        sa.Column("mandate_id", sa.String(36),
                  sa.ForeignKey("representation_mandates.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("scope", sa.String(32), primary_key=True),
        sa.CheckConstraint(_in("scope", MANDATE_SCOPES),
                           name="ck_representation_mandate_scopes_scope"),
    )


def downgrade() -> None:
    op.drop_table("representation_mandate_scopes")
    op.drop_index("ix_representation_mandates_representative_user_id",
                  table_name="representation_mandates")
    op.drop_index("ix_representation_mandates_principal_legal_party_id",
                  table_name="representation_mandates")
    op.drop_table("representation_mandates")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_organization_id",
                  table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_table("organization_legal_parties")
    op.drop_table("organizations")
