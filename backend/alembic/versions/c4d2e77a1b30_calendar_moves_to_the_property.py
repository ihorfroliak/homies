"""calendar moves to the property

Availability is a fact about the physical object, not about one way of offering
it. While the calendar was keyed on `listing_id`, two listings of the same flat
— a short-stay offer and a monthly one — could be booked for the same nights and
every check would pass.

The dangerous part of this migration is the exclusion constraint. It is the last
line of defence against double booking, so the new one (keyed on property_id) is
created BEFORE the old one is dropped. Both coexist for a moment; the old is
strictly narrower, so nothing is falsely rejected and there is never a window
without protection. The name `excl_booking_overlap` is kept — it is asserted by
test_td01_migrations and by the DR restore check.

Backfill creates one Property per existing Listing. The fields a listing never
recorded — property_type, municipality, area_m2, rooms — are left NULL rather
than guessed: "apartment" would be a fact nobody established, and municipality
in particular decides the tourist tax. They are nullable in the database and
required by the API, so every property created from here on has them.

Revision ID: c4d2e77a1b30
Revises: f91f4ece13f6
Create Date: 2026-09-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d2e77a1b30"
down_revision: str | Sequence[str] | None = "f91f4ece13f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. The four fields a legacy listing cannot supply become nullable.
    op.alter_column("properties", "property_type", existing_type=sa.String(24), nullable=True)
    op.alter_column("properties", "municipality", existing_type=sa.String(80), nullable=True)
    op.alter_column("properties", "area_m2", existing_type=sa.Integer(), nullable=True)
    op.alter_column("properties", "rooms", existing_type=sa.Integer(), nullable=True)

    # 2. Add the links, nullable for now.
    op.add_column("listings", sa.Column("property_id", sa.String(36), nullable=True))
    op.add_column("bookings", sa.Column("property_id", sa.String(36), nullable=True))
    op.add_column("host_blocks", sa.Column("property_id", sa.String(36), nullable=True))

    # 3. One property per existing listing, carrying only what the listing knew.
    #    gen_random_uuid() is in pgcrypto/core since PG13; ids elsewhere are
    #    application-generated uuid4 strings, and both are uuid text.
    op.execute(
        """
        INSERT INTO properties (
            id, owner_id, city, district, postcode, address,
            bedrooms, bathrooms, capacity, has_elevator, furnished, parking,
            pets_allowed, attributes, created_at
        )
        SELECT gen_random_uuid()::text, l.host_id, l.city, '', '', l.address,
               0, 1, l.capacity, false, 'full', 'none',
               false, '{}'::json, l.created_at
        FROM listings l
        """
    )
    # Match them back by the pair that identifies them: same owner, same address.
    op.execute(
        """
        UPDATE listings l
        SET property_id = p.id
        FROM properties p
        WHERE p.owner_id = l.host_id
          AND p.address = l.address
          AND p.city = l.city
          AND l.property_id IS NULL
        """
    )
    op.execute(
        "UPDATE bookings b SET property_id = l.property_id "
        "FROM listings l WHERE l.id = b.listing_id"
    )
    op.execute(
        "UPDATE host_blocks h SET property_id = l.property_id "
        "FROM listings l WHERE l.id = h.listing_id"
    )

    # 4. Now the links are mandatory.
    op.alter_column("listings", "property_id", existing_type=sa.String(36), nullable=False)
    op.alter_column("bookings", "property_id", existing_type=sa.String(36), nullable=False)
    op.alter_column("host_blocks", "property_id", existing_type=sa.String(36), nullable=False)

    op.create_foreign_key(
        "fk_listings_property", "listings", "properties", ["property_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_bookings_property", "bookings", "properties", ["property_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_host_blocks_property", "host_blocks", "properties", ["property_id"], ["id"]
    )
    op.create_index("ix_listings_property_id", "listings", ["property_id"])
    op.create_index("ix_bookings_property_id", "bookings", ["property_id"])
    op.create_index("ix_host_blocks_property_id", "host_blocks", ["property_id"])

    # 5. The load-bearing step. New constraint first, under a temporary name,
    #    so the table is never unprotected.
    op.execute(
        """
        ALTER TABLE bookings ADD CONSTRAINT excl_booking_overlap_property
        EXCLUDE USING gist (
            property_id WITH =,
            daterange(check_in, check_out) WITH &&
        ) WHERE (status IN ('pending', 'confirmed'))
        """
    )
    op.execute("ALTER TABLE bookings DROP CONSTRAINT excl_booking_overlap")
    op.execute(
        "ALTER TABLE bookings RENAME CONSTRAINT excl_booking_overlap_property "
        "TO excl_booking_overlap"
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE bookings ADD CONSTRAINT excl_booking_overlap_listing
        EXCLUDE USING gist (
            listing_id WITH =,
            daterange(check_in, check_out) WITH &&
        ) WHERE (status IN ('pending', 'confirmed'))
        """
    )
    op.execute("ALTER TABLE bookings DROP CONSTRAINT excl_booking_overlap")
    op.execute(
        "ALTER TABLE bookings RENAME CONSTRAINT excl_booking_overlap_listing "
        "TO excl_booking_overlap"
    )

    op.drop_index("ix_host_blocks_property_id", table_name="host_blocks")
    op.drop_index("ix_bookings_property_id", table_name="bookings")
    op.drop_index("ix_listings_property_id", table_name="listings")
    op.drop_constraint("fk_host_blocks_property", "host_blocks", type_="foreignkey")
    op.drop_constraint("fk_bookings_property", "bookings", type_="foreignkey")
    op.drop_constraint("fk_listings_property", "listings", type_="foreignkey")
    op.drop_column("host_blocks", "property_id")
    op.drop_column("bookings", "property_id")
    op.drop_column("listings", "property_id")

    # Properties created by the backfill are left in place: dropping rows on a
    # downgrade would destroy data an operator may since have completed.
    op.alter_column("properties", "rooms", existing_type=sa.Integer(), nullable=False)
    op.alter_column("properties", "area_m2", existing_type=sa.Integer(), nullable=False)
    op.alter_column("properties", "municipality", existing_type=sa.String(80), nullable=False)
    op.alter_column("properties", "property_type", existing_type=sa.String(24), nullable=False)
