"""disputes table (FIN-03)

A card dispute has its own lifecycle, its own money and its own identity at
the provider, so it gets its own table rather than more columns on payments.
`provider_dispute_id` is UNIQUE: that index is the idempotency guarantee that
a duplicate webhook delivery cannot post the withdrawal twice.


Revision ID: 87cebed1635f
Revises: 2d9d18df4688
Create Date: 2026-08-17 13:44:11.789808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87cebed1635f'
down_revision: Union[str, Sequence[str], None] = '2d9d18df4688'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also reported a missing ix_notifications_event_id.
    # That is pre-existing drift unrelated to FIN-03 and is deliberately left
    # out of this migration rather than smuggled in with a money change.
    op.create_table('disputes',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('provider_dispute_id', sa.String(length=80), nullable=False),
    sa.Column('payment_id', sa.String(length=36), nullable=False),
    sa.Column('booking_id', sa.String(length=36), nullable=True),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('fee', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('reason', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('absorbed_by_platform', sa.Boolean(), nullable=False),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_disputes_booking_id'), 'disputes', ['booking_id'], unique=False)
    op.create_index(op.f('ix_disputes_payment_id'), 'disputes', ['payment_id'], unique=False)
    op.create_index(op.f('ix_disputes_provider_dispute_id'), 'disputes', ['provider_dispute_id'], unique=True)
    op.create_index(op.f('ix_disputes_status'), 'disputes', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_disputes_status'), table_name='disputes')
    op.drop_index(op.f('ix_disputes_provider_dispute_id'), table_name='disputes')
    op.drop_index(op.f('ix_disputes_payment_id'), table_name='disputes')
    op.drop_index(op.f('ix_disputes_booking_id'), table_name='disputes')
    op.drop_table('disputes')
