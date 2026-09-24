"""Coordinate integrity: finite, on the globe, both or neither (TASK-001 F-07).

Revision ID: a7c9e1f3b5d2
Revises: d5e7f9a1b3c4
Create Date: 2026-09-24

Preflight first, constraints second. An exact position outside the globe is
not corrected: (100, 200) is not "probably" anywhere, and PostGIS silently
wrapping it into another real place is the defect being closed. If such a row
exists the migration stops and names it; an operator decides what the
property's position really is.

The only rows this migration rewrites are derived public points that lie off
the globe because their exact position sits exactly on 90° N or 180° E (the
old grid opened a cell beyond the edge). They are recomputed from the exact
position with the corrected grid rule — deterministic, not a guess.

Operational note: each ADD CONSTRAINT scans its table under ACCESS EXCLUSIVE.
On a large production table plan it with the rest of TASK-002's rollout notes
(docs/database/MIGRATION-ROLLOUT.md).
"""

from decimal import ROUND_FLOOR, Decimal

import sqlalchemy as sa
from alembic import op

revision = "a7c9e1f3b5d2"
down_revision = "d5e7f9a1b3c4"
branch_labels = None
depends_on = None

# Copied, not imported: a migration must keep meaning what it meant when it
# was written, whatever app code later becomes.
GRID_LAT = Decimal("0.005")
GRID_LON = Decimal("0.008")
_SIX = Decimal("0.000001")


def _centre(value: Decimal, step: Decimal, upper: Decimal) -> Decimal:
    index = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    if index * step >= upper:
        index -= 1
    return (index * step + step / 2).quantize(_SIX)


def _checks(lat: str, lon: str, name: str) -> list[tuple[str, str]]:
    return [
        (f"ck_{name}_pair", f"({lat} IS NULL) = ({lon} IS NULL)"),
        (f"ck_{name}_latitude_range", f"{lat} IS NULL OR {lat} BETWEEN -90 AND 90"),
        (f"ck_{name}_longitude_range", f"{lon} IS NULL OR {lon} BETWEEN -180 AND 180"),
    ]


PROPERTY_CHECKS = _checks("latitude", "longitude", "properties_coordinates")
OFFER_CHECKS = _checks(
    "public_latitude", "public_longitude", "classified_offers_public_coordinates"
)


def _invalid(lat: str, lon: str) -> str:
    # NaN compares greater than every number in PostgreSQL numeric, and
    # ±Infinity lie outside the ranges, so NOT BETWEEN catches all three.
    return (
        f"(({lat} IS NULL) <> ({lon} IS NULL)) OR {lat} NOT BETWEEN -90 AND 90 "
        f"OR {lon} NOT BETWEEN -180 AND 180"
    )


def upgrade() -> None:
    bind = op.get_bind()

    bad = bind.execute(
        sa.text(f"SELECT id FROM properties WHERE {_invalid('latitude', 'longitude')} ORDER BY id")
    ).scalars().all()
    if bad:
        raise RuntimeError(
            f"{len(bad)} propert{'y has' if len(bad) == 1 else 'ies have'} an exact position "
            "that is not a valid (latitude, longitude) pair. Correct them by hand — this "
            f"migration will not guess a location. First ids: {', '.join(bad[:20])}"
        )

    offers = bind.execute(
        sa.text(
            "SELECT o.id, o.public_location_precision, p.latitude, p.longitude "
            "FROM classified_offers o JOIN properties p ON p.id = o.property_id "
            f"WHERE {_invalid('o.public_latitude', 'o.public_longitude')}"
        )
    ).all()
    for offer_id, precision, lat, lon in offers:
        if lat is None or lon is None or precision == "DISTRICT":
            public = (None, None)
        elif precision == "EXACT":
            public = (Decimal(lat).quantize(_SIX), Decimal(lon).quantize(_SIX))
        else:
            public = (
                _centre(Decimal(lat), GRID_LAT, Decimal(90)),
                _centre(Decimal(lon), GRID_LON, Decimal(180)),
            )
        bind.execute(
            sa.text(
                "UPDATE classified_offers SET public_latitude = :lat, public_longitude = :lon "
                "WHERE id = :id"
            ),
            {"lat": public[0], "lon": public[1], "id": offer_id},
        )

    for name, condition in PROPERTY_CHECKS:
        op.create_check_constraint(name, "properties", condition)
    for name, condition in OFFER_CHECKS:
        op.create_check_constraint(name, "classified_offers", condition)


def downgrade() -> None:
    for name, _ in OFFER_CHECKS:
        op.drop_constraint(name, "classified_offers", type_="check")
    for name, _ in PROPERTY_CHECKS:
        op.drop_constraint(name, "properties", type_="check")
