"""Exact location stays private; listings get a public map point
(Domain Schema v1 §9, §42, §80, §106).

* `properties.exact_geog` — the flat's own position as geography, generated
  from latitude/longitude so it can never disagree with them. Private: no
  public response reads it.
* `classified_offers.public_latitude/longitude` — the point the public map
  shows, chosen by `public_location_precision` (EXACT / APPROXIMATE /
  DISTRICT, default APPROXIMATE). `public_geog` is generated from it.
* GiST indexes on both geography columns, for viewport and radius search.

The geography columns are GENERATED rather than written by the application:
the application writes plain numbers that SQLite can also hold, and Postgres
keeps the spatial column in step by construction.

Backfill: existing offers get APPROXIMATE, and their public point is the centre
of the grid cell their property lies in — the same rule the application now
applies (location.py). Duplicated here rather than imported: a migration must
keep meaning what it meant when it ran, whatever the application later becomes.

Requires the PostGIS extension, created here. On a managed database the
migration role needs the right to create it, or a DBA creates it beforehand.

Revision ID: f1a7c3d9e2b4
Revises: d4e8b2c61a95
Create Date: 2026-09-23
"""

from decimal import ROUND_FLOOR, Decimal

import sqlalchemy as sa
from alembic import op

revision = "f1a7c3d9e2b4"
down_revision = "d4e8b2c61a95"
branch_labels = None
depends_on = None

GRID_LAT = Decimal("0.005")
GRID_LON = Decimal("0.008")
_SIX = Decimal("0.000001")


def _centre(value: Decimal, step: Decimal) -> Decimal:
    index = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    return (index * step + step / 2).quantize(_SIX)


def _geog(lat: str, lon: str) -> str:
    return (
        f"GENERATED ALWAYS AS (CASE WHEN {lat} IS NULL OR {lon} IS NULL THEN NULL "
        f"ELSE ST_SetSRID(ST_MakePoint({lon}::double precision, {lat}::double precision), "
        f"4326)::geography END) STORED"
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.execute(
        "ALTER TABLE properties ADD COLUMN exact_geog geography(Point, 4326) "
        + _geog("latitude", "longitude")
    )
    op.execute("CREATE INDEX ix_properties_exact_geog ON properties USING gist (exact_geog)")

    op.add_column(
        "classified_offers",
        sa.Column("public_location_precision", sa.String(16), nullable=False,
                  server_default="APPROXIMATE"),
    )
    op.create_check_constraint(
        "ck_classified_offers_location_precision",
        "classified_offers",
        "public_location_precision IN ('EXACT', 'APPROXIMATE', 'DISTRICT')",
    )
    op.add_column("classified_offers",
                  sa.Column("public_latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("classified_offers",
                  sa.Column("public_longitude", sa.Numeric(9, 6), nullable=True))
    op.execute(
        "ALTER TABLE classified_offers ADD COLUMN public_geog geography(Point, 4326) "
        + _geog("public_latitude", "public_longitude")
    )
    op.execute(
        "CREATE INDEX ix_classified_offers_public_geog ON classified_offers "
        "USING gist (public_geog)"
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT o.id, p.latitude, p.longitude FROM classified_offers o "
            "JOIN properties p ON p.id = o.property_id "
            "WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL"
        )
    ).fetchall()
    for offer_id, lat, lon in rows:
        conn.execute(
            sa.text(
                "UPDATE classified_offers SET public_latitude = :lat, public_longitude = :lon "
                "WHERE id = :id"
            ),
            {"lat": _centre(Decimal(lat), GRID_LAT), "lon": _centre(Decimal(lon), GRID_LON),
             "id": offer_id},
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_classified_offers_public_geog")
    op.drop_column("classified_offers", "public_geog")
    op.drop_column("classified_offers", "public_longitude")
    op.drop_column("classified_offers", "public_latitude")
    op.drop_constraint("ck_classified_offers_location_precision", "classified_offers",
                       type_="check")
    op.drop_column("classified_offers", "public_location_precision")
    op.execute("DROP INDEX IF EXISTS ix_properties_exact_geog")
    op.drop_column("properties", "exact_geog")
    # The extension is left in place: other objects may depend on it by now,
    # and dropping an extension is not this migration's decision to make.
