"""Legal parties and property authority (Domain Schema v1 §16–§17, §30–§31).

Rights over a property move from `properties.owner_id` — an account — to an
authority held by a legal party. An account is who is typing; a legal party is
who owns the building; they are different things and the board's fraud risk
lives in the gap between them.

Backfill: every existing property gets its creator's PERSON party and an
ACTIVE, UNVERIFIED owner authority dated from the property's creation. Nothing
is marked VERIFIED, because nothing was checked. Listings already on the board
are left as they are; the gate applies to the next publication.

Revision ID: b7e4f19a2c60
Revises: a1c6d2e8b407
Create Date: 2026-09-23
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "b7e4f19a2c60"
down_revision = "a1c6d2e8b407"
branch_labels = None
depends_on = None

AUTHORITY_TYPES = (
    "OWNER", "CO_OWNER", "AUTHORIZED_REPRESENTATIVE", "PROPERTY_MANAGER",
    "TENANT_WITH_SUBLET_RIGHT", "OTHER_VERIFIED_RIGHT",
)
AUTHORITY_STATUSES = ("PENDING", "ACTIVE", "REVOKED", "EXPIRED")
VERIFICATION_STATES = ("UNVERIFIED", "PENDING", "VERIFIED", "REJECTED")
AUTHORITY_SCOPES = (
    "EDIT_PROPERTY", "PUBLISH_LISTING", "MANAGE_MEDIA", "MANAGE_VIEWINGS",
    "MANAGE_MESSAGES", "MANAGE_APPLICATIONS", "SIGN_CONTRACT", "VIEW_FINANCIALS",
    "MANAGE_SERVICES",
)
OWNER_PHASE1_SCOPES = (
    "EDIT_PROPERTY", "PUBLISH_LISTING", "MANAGE_MEDIA", "MANAGE_VIEWINGS", "MANAGE_MESSAGES",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "legal_parties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("party_type", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("archived_at", nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_in("party_type", ("PERSON", "ORGANIZATION")),
                           name="ck_legal_parties_party_type"),
        sa.CheckConstraint(_in("status", ("ACTIVE", "ARCHIVED")), name="ck_legal_parties_status"),
    )
    op.create_table(
        "person_legal_parties",
        sa.Column("legal_party_id", sa.String(36),
                  sa.ForeignKey("legal_parties.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("linked_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("legal_first_name", sa.String(255), nullable=True),
        sa.Column("legal_last_name", sa.String(255), nullable=True),
        sa.Column("country_of_residence", sa.String(2), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        # One legal person per account: two would let one human hold rights
        # twice over and split an audit trail that should be one.
        sa.UniqueConstraint("linked_user_id"),
    )
    op.create_table(
        "property_authorities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("property_id", sa.String(36),
                  sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("holder_legal_party_id", sa.String(36),
                  sa.ForeignKey("legal_parties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("authority_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("verification_state", sa.String(16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("created_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("revoked_at", nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_in("authority_type", AUTHORITY_TYPES),
                           name="ck_property_authorities_type"),
        sa.CheckConstraint(_in("status", AUTHORITY_STATUSES),
                           name="ck_property_authorities_status"),
        sa.CheckConstraint(_in("verification_state", VERIFICATION_STATES),
                           name="ck_property_authorities_verification"),
        sa.CheckConstraint("effective_until IS NULL OR effective_until >= effective_from",
                           name="ck_property_authorities_effective_range"),
    )
    op.create_index("ix_property_authorities_property_id", "property_authorities",
                    ["property_id"])
    op.create_index("ix_property_authorities_holder_legal_party_id", "property_authorities",
                    ["holder_legal_party_id"])
    op.create_table(
        "property_authority_scopes",
        sa.Column("property_authority_id", sa.String(36),
                  sa.ForeignKey("property_authorities.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("scope", sa.String(32), primary_key=True),
        sa.CheckConstraint(_in("scope", AUTHORITY_SCOPES),
                           name="ck_property_authority_scopes_scope"),
    )

    _backfill()


def _backfill() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT p.id, p.owner_id, p.created_at, u.full_name, u.email "
            "FROM properties p JOIN users u ON u.id = p.owner_id"
        )
    ).fetchall()

    party_of: dict[str, str] = {}
    for property_id, owner_id, created_at, full_name, email in rows:
        if owner_id not in party_of:
            party_id = str(uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO legal_parties (id, party_type, display_name, status, "
                    "created_at, updated_at, version) "
                    "VALUES (:id, 'PERSON', :name, 'ACTIVE', now(), now(), 1)"
                ),
                {"id": party_id, "name": full_name or email},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO person_legal_parties (legal_party_id, linked_user_id, "
                    "created_at, updated_at) VALUES (:id, :user, now(), now())"
                ),
                {"id": party_id, "user": owner_id},
            )
            party_of[owner_id] = party_id

        authority_id = str(uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO property_authorities (id, property_id, holder_legal_party_id, "
                "authority_type, status, verification_state, effective_from, "
                "created_by_user_id, created_at, updated_at, version) "
                "VALUES (:id, :prop, :party, 'OWNER', 'ACTIVE', 'UNVERIFIED', "
                ":since, :user, now(), now(), 1)"
            ),
            {
                "id": authority_id,
                "prop": property_id,
                "party": party_of[owner_id],
                "since": created_at.date(),
                "user": owner_id,
            },
        )
        for scope in OWNER_PHASE1_SCOPES:
            conn.execute(
                sa.text(
                    "INSERT INTO property_authority_scopes (property_authority_id, scope) "
                    "VALUES (:id, :scope)"
                ),
                {"id": authority_id, "scope": scope},
            )


def downgrade() -> None:
    op.drop_table("property_authority_scopes")
    op.drop_index("ix_property_authorities_holder_legal_party_id",
                  table_name="property_authorities")
    op.drop_index("ix_property_authorities_property_id", table_name="property_authorities")
    op.drop_table("property_authorities")
    op.drop_table("person_legal_parties")
    op.drop_table("legal_parties")
