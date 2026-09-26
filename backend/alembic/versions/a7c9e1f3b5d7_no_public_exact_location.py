"""No public EXACT location (TASK-010R, D-58).

Revision ID: a7c9e1f3b5d7
Revises: e4f6a8b0c2d4
Create Date: 2026-09-26

Public exact residential coordinates are prohibited, with no owner opt-in.
Any offer still stored as EXACT becomes APPROXIMATE, and its public point is
recomputed from the property's private point with the same grid as
app/modules/properties/location.py (cell 0.005° × 0.008°, centre of the cell
the point lies in; a point exactly on 90° N / 180° E belongs to the last cell
inside the globe). The formula is frozen here, as migrations must be; the
test suite checks it against location.public_point.

Nothing private is touched: the property's exact latitude/longitude (and the
generated `exact_geog`) stay as they are. `public_geog` is generated from the
public point and follows it. Afterwards the CHECK admits only APPROXIMATE and
DISTRICT, so the database cannot hold EXACT again.

Downgrade widens the CHECK back; converted rows stay APPROXIMATE (which of
them were EXACT is deliberately not remembered).
"""

from alembic import op

revision = "a7c9e1f3b5d7"
down_revision = "e4f6a8b0c2d4"
branch_labels = None
depends_on = None

CHECK = "ck_classified_offers_location_precision"


def _cell(column: str, step: str, upper: str) -> str:
    index = f"floor({column} / {step})"
    return (f"round(({index} - CASE WHEN {index} * {step} >= {upper} THEN 1 ELSE 0 END)"
            f" * {step} + {step} / 2, 6)")


def upgrade() -> None:
    op.execute(f"""
        UPDATE classified_offers AS o
           SET public_location_precision = 'APPROXIMATE',
               public_latitude = CASE WHEN p.latitude IS NULL OR p.longitude IS NULL
                                      THEN NULL ELSE {_cell('p.latitude', '0.005', '90')} END,
               public_longitude = CASE WHEN p.latitude IS NULL OR p.longitude IS NULL
                                       THEN NULL ELSE {_cell('p.longitude', '0.008', '180')} END
          FROM properties AS p
         WHERE p.id = o.property_id
           AND o.public_location_precision = 'EXACT'
    """)
    op.drop_constraint(CHECK, "classified_offers", type_="check")
    op.create_check_constraint(
        CHECK, "classified_offers", "public_location_precision IN ('APPROXIMATE', 'DISTRICT')"
    )


def downgrade() -> None:
    op.drop_constraint(CHECK, "classified_offers", type_="check")
    op.create_check_constraint(
        CHECK, "classified_offers",
        "public_location_precision IN ('EXACT', 'APPROXIMATE', 'DISTRICT')",
    )
