"""properties and free classifieds board

The Property/Offer split (docs/PRODUCT_MODEL.md §1) lands here, starting with
the offer type that touches no money: the free long-term board. Homies does not
book, charge, hold a deposit or resolve disputes for these, so the tables can
arrive without going near the ledger or the booking calendar.

`contact_reveals` carries a unique (offer_id, viewer_id): a viewer asking twice
has not been told twice, and counting repeats would overstate both a future
quota and the scraping signal.

Purely additive — no existing table is touched and no backfill is needed.


Revision ID: f91f4ece13f6
Revises: b910997aa651
Create Date: 2026-09-19 16:55:32.463728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f91f4ece13f6'
down_revision: Union[str, Sequence[str], None] = 'b910997aa651'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also reports a missing ix_notifications_event_id.
    # That is pre-existing drift unrelated to this change and is deliberately
    # left out rather than smuggled in.
    op.create_table('properties',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('owner_id', sa.String(length=36), nullable=False),
    sa.Column('property_type', sa.String(length=24), nullable=False),
    sa.Column('city', sa.String(length=80), nullable=False),
    sa.Column('district', sa.String(length=80), nullable=False),
    sa.Column('postcode', sa.String(length=12), nullable=False),
    sa.Column('municipality', sa.String(length=80), nullable=False),
    sa.Column('address', sa.String(length=255), nullable=False),
    sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('area_m2', sa.Integer(), nullable=False),
    sa.Column('rooms', sa.Integer(), nullable=False),
    sa.Column('bedrooms', sa.Integer(), nullable=False),
    sa.Column('bathrooms', sa.Integer(), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('floor', sa.Integer(), nullable=True),
    sa.Column('floors_total', sa.Integer(), nullable=True),
    sa.Column('has_elevator', sa.Boolean(), nullable=False),
    sa.Column('furnished', sa.String(length=12), nullable=False),
    sa.Column('parking', sa.String(length=12), nullable=False),
    sa.Column('pets_allowed', sa.Boolean(), nullable=False),
    sa.Column('attributes', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_properties_city'), 'properties', ['city'], unique=False)
    op.create_index(op.f('ix_properties_district'), 'properties', ['district'], unique=False)
    op.create_index(op.f('ix_properties_owner_id'), 'properties', ['owner_id'], unique=False)
    op.create_index(op.f('ix_properties_property_type'), 'properties', ['property_type'], unique=False)
    op.create_index(op.f('ix_properties_rooms'), 'properties', ['rooms'], unique=False)
    op.create_table('classified_offers',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('property_id', sa.String(length=36), nullable=False),
    sa.Column('owner_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=140), nullable=False),
    sa.Column('description', sa.String(length=4000), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('rent_amount', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('admin_fee', sa.Integer(), nullable=False),
    sa.Column('utilities_amount', sa.Integer(), nullable=False),
    sa.Column('utilities_included', sa.Boolean(), nullable=False),
    sa.Column('parking_fee', sa.Integer(), nullable=False),
    sa.Column('deposit_amount', sa.Integer(), nullable=False),
    sa.Column('other_costs', sa.String(length=500), nullable=False),
    sa.Column('min_term_months', sa.Integer(), nullable=True),
    sa.Column('open_ended', sa.Boolean(), nullable=False),
    sa.Column('available_from', sa.Date(), nullable=True),
    sa.Column('contact_phone', sa.String(length=32), nullable=False),
    sa.Column('contact_mode', sa.String(length=12), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_classified_offers_owner_id'), 'classified_offers', ['owner_id'], unique=False)
    op.create_index(op.f('ix_classified_offers_property_id'), 'classified_offers', ['property_id'], unique=False)
    op.create_index(op.f('ix_classified_offers_status'), 'classified_offers', ['status'], unique=False)
    op.create_table('contact_reveals',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('offer_id', sa.String(length=36), nullable=False),
    sa.Column('viewer_id', sa.String(length=36), nullable=False),
    sa.Column('revealed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['offer_id'], ['classified_offers.id'], ),
    sa.ForeignKeyConstraint(['viewer_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('offer_id', 'viewer_id', name='uq_contact_reveal_viewer')
    )
    op.create_index(op.f('ix_contact_reveals_offer_id'), 'contact_reveals', ['offer_id'], unique=False)
    op.create_index(op.f('ix_contact_reveals_viewer_id'), 'contact_reveals', ['viewer_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_contact_reveals_viewer_id'), table_name='contact_reveals')
    op.drop_index(op.f('ix_contact_reveals_offer_id'), table_name='contact_reveals')
    op.drop_table('contact_reveals')
    op.drop_index(op.f('ix_classified_offers_status'), table_name='classified_offers')
    op.drop_index(op.f('ix_classified_offers_property_id'), table_name='classified_offers')
    op.drop_index(op.f('ix_classified_offers_owner_id'), table_name='classified_offers')
    op.drop_table('classified_offers')
    op.drop_index(op.f('ix_properties_rooms'), table_name='properties')
    op.drop_index(op.f('ix_properties_property_type'), table_name='properties')
    op.drop_index(op.f('ix_properties_owner_id'), table_name='properties')
    op.drop_index(op.f('ix_properties_district'), table_name='properties')
    op.drop_index(op.f('ix_properties_city'), table_name='properties')
    op.drop_table('properties')
