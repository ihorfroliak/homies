"""Price as components with history (Domain Schema v1 §46–§47).

The five flat price columns on `classified_offers` were overwritten on every
change, so the price a tenant was shown last month could not be recovered —
and that is exactly what a dispute about an advert is argued from. They become
rows in `listing_price_components`, each valid for a period, with three
summaries on the offer (headline, monthly total, move-in total) kept in step
by the service that changes them.

Backfill maps each existing offer exactly as the application now does for a
new one: zero-valued optional components are not stored; utilities the owner
included in the rent are recorded but not mandatory; the deposit is a
refundable one-off. `valid_from` is the offer's creation time — the price has
applied since then, as far as anything recorded shows.

The flat columns are dropped. Keeping them would leave two sources of truth
for the same number, and the one nobody updates is the one that gets read.

Revision ID: d4e8b2c61a95
Revises: c9d3a5e71f28
Create Date: 2026-09-23
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "d4e8b2c61a95"
down_revision = "c9d3a5e71f28"
branch_labels = None
depends_on = None

TYPES = (
    "BASE_RENT", "ADMIN_FEE", "UTILITIES_FIXED", "UTILITIES_ESTIMATE", "SECURITY_DEPOSIT",
    "AGENCY_FEE", "CLEANING_FEE", "HOMIES_FEE", "OTHER_MANDATORY", "SALE_ASKING_PRICE",
)
CADENCES = ("ONE_TIME", "MONTHLY", "PER_STAY", "PER_NIGHT")
FLAT = ("rent_amount", "admin_fee", "utilities_amount", "parking_fee", "deposit_amount")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "listing_price_components",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("listing_id", sa.String(36),
                  sa.ForeignKey("classified_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_type", sa.String(32), nullable=False),
        sa.Column("component_key", sa.String(40), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("refundable", sa.Boolean(), nullable=False),
        sa.Column("estimated", sa.Boolean(), nullable=False),
        sa.Column("display_label", sa.String(120), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_in("component_type", TYPES),
                           name="ck_listing_price_components_type"),
        sa.CheckConstraint(_in("cadence", CADENCES), name="ck_listing_price_components_cadence"),
        sa.CheckConstraint("amount_minor >= 0", name="ck_listing_price_components_amount"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from",
                           name="ck_listing_price_components_period"),
    )
    op.create_index("ix_listing_price_components_listing_id", "listing_price_components",
                    ["listing_id"])
    op.create_index("uq_listing_price_components_current", "listing_price_components",
                    ["listing_id", "component_type", "component_key"], unique=True,
                    postgresql_where=sa.text("valid_to IS NULL"))

    op.add_column("classified_offers",
                  sa.Column("primary_price_minor", sa.BigInteger(), nullable=True))
    op.add_column("classified_offers",
                  sa.Column("estimated_monthly_total_minor", sa.BigInteger(), nullable=True))
    op.add_column("classified_offers",
                  sa.Column("move_in_total_minor", sa.BigInteger(), nullable=True))
    op.add_column("classified_offers",
                  sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"))
    op.create_index("ix_classified_offers_estimated_monthly_total_minor", "classified_offers",
                    ["estimated_monthly_total_minor"])

    _backfill()

    for column in FLAT:
        op.drop_column("classified_offers", column)


def _backfill() -> None:
    conn = op.get_bind()
    offers = conn.execute(
        sa.text(
            "SELECT id, owner_id, created_at, rent_amount, admin_fee, utilities_amount, "
            "utilities_included, parking_fee, deposit_amount FROM classified_offers"
        )
    ).fetchall()
    insert = sa.text(
        "INSERT INTO listing_price_components (id, listing_id, component_type, "
        "component_key, amount_minor, cadence, mandatory, refundable, estimated, "
        "valid_from, created_by_user_id, created_at) VALUES (:id, :listing, :type, :key, "
        ":amount, :cadence, :mandatory, :refundable, :estimated, :since, :user, now())"
    )
    for (oid, owner, created, rent, admin, utilities, included, parking, deposit) in offers:
        rows = [("BASE_RENT", "", rent, "MONTHLY", True, False, False)]
        if admin:
            rows.append(("ADMIN_FEE", "", admin, "MONTHLY", True, False, False))
        if utilities:
            rows.append(("UTILITIES_ESTIMATE", "", utilities, "MONTHLY", not included, False, True))
        if parking:
            rows.append(("OTHER_MANDATORY", "parking", parking, "MONTHLY", True, False, False))
        if deposit:
            rows.append(("SECURITY_DEPOSIT", "", deposit, "ONE_TIME", True, True, False))

        monthly = sum(a for _, _, a, cad, mand, _, _ in rows if mand and cad == "MONTHLY")
        one_off = sum(a for _, _, a, cad, mand, _, _ in rows if mand and cad == "ONE_TIME")
        for ctype, key, amount, cadence, mandatory, refundable, estimated in rows:
            conn.execute(insert, {
                "id": str(uuid4()), "listing": oid, "type": ctype, "key": key,
                "amount": amount, "cadence": cadence, "mandatory": mandatory,
                "refundable": refundable, "estimated": estimated, "since": created,
                "user": owner,
            })
        conn.execute(
            sa.text(
                "UPDATE classified_offers SET primary_price_minor = :p, "
                "estimated_monthly_total_minor = :m, move_in_total_minor = :i WHERE id = :id"
            ),
            {"p": rent, "m": monthly, "i": monthly + one_off, "id": oid},
        )


def downgrade() -> None:
    for column in FLAT:
        op.add_column("classified_offers",
                      sa.Column(column, sa.BigInteger(), nullable=False, server_default="0"))
    conn = op.get_bind()
    # The current component of each kind becomes the flat value again. History
    # is lost on the way down; that is what downgrading this revision means.
    for column, (ctype, key) in {
        "rent_amount": ("BASE_RENT", ""),
        "admin_fee": ("ADMIN_FEE", ""),
        "utilities_amount": ("UTILITIES_ESTIMATE", ""),
        "parking_fee": ("OTHER_MANDATORY", "parking"),
        "deposit_amount": ("SECURITY_DEPOSIT", ""),
    }.items():
        conn.execute(
            sa.text(
                f"UPDATE classified_offers o SET {column} = c.amount_minor "  # noqa: S608
                "FROM listing_price_components c WHERE c.listing_id = o.id "
                "AND c.component_type = :t AND c.component_key = :k AND c.valid_to IS NULL"
            ),
            {"t": ctype, "k": key},
        )
    op.drop_index("ix_classified_offers_estimated_monthly_total_minor",
                  table_name="classified_offers")
    for column in ("version", "move_in_total_minor", "estimated_monthly_total_minor",
                   "primary_price_minor"):
        op.drop_column("classified_offers", column)
    op.drop_index("uq_listing_price_components_current", table_name="listing_price_components")
    op.drop_index("ix_listing_price_components_listing_id", table_name="listing_price_components")
    op.drop_table("listing_price_components")
