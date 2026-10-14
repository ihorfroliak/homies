"""BP-5: immutable viewing cancellation source, without inventing historical actors.

Revision ID: 23e89acb98b4
Revises: 11d778ab87a3

BARRIER/BLOCKED: the previous writer omits the source on cancellation. Merely
adding nullable columns would not enforce the new contract. DDL and backfill
are one transaction; the viewings table lock prevents a concurrent old write
from creating an unclassified row between backfill and guard installation.
Unknown historical cancellations are sealed exceptions, not HOMIES defaults.
Downgrade is only for disposable development; it preserves pre-existing data.
"""

from collections import defaultdict

import sqlalchemy as sa

from alembic import op

revision = "23e89acb98b4"
down_revision = "11d778ab87a3"
branch_labels = None
depends_on = None
schema_transition = "BARRIER"
rollback_to_previous = "BLOCKED"

SOURCE_STATE = (
    "(status = 'CANCELLED' AND ((cancelled_by IS NOT NULL AND NOT cancellation_source_legacy)"
    " OR (cancelled_by IS NULL AND cancellation_source_legacy))) OR "
    "(status <> 'CANCELLED' AND cancelled_by IS NULL AND NOT cancellation_source_legacy)"
)


def _backfill() -> None:
    conn = op.get_bind()
    viewings = sa.table("viewings", sa.column("id", sa.String),
                        sa.column("listing_id", sa.String), sa.column("status", sa.String),
                        sa.column("cancelled_by", sa.String),
                        sa.column("cancellation_source_legacy", sa.Boolean))
    events = sa.table("domain_events", sa.column("correlation_id", sa.String),
                      sa.column("event_type", sa.String), sa.column("dedup_key", sa.String),
                      sa.column("payload", sa.JSON))
    # A canonical, unique cancellation fact binds the actor to this viewing.
    # A matching moderation timestamp alone is deliberately not evidence.
    rows = conn.execute(sa.select(viewings.c.id, viewings.c.listing_id,
                                   events.c.dedup_key, events.c.payload).select_from(
        viewings.outerjoin(events, sa.and_(events.c.correlation_id == viewings.c.id,
                                           events.c.event_type == "ViewingCancelled")))
        .where(viewings.c.status == "CANCELLED")).mappings()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["id"]].append(row)
    for viewing_id, evidence in grouped.items():
        source = None
        if len(evidence) == 1:
            row = evidence[0]
            payload = row["payload"]
            if (isinstance(payload, dict)
                    and row["dedup_key"] == f"ViewingCancelled:{viewing_id}"
                    and payload.get("viewing_id") == viewing_id
                    and payload.get("listing_id") == row["listing_id"]
                    and payload.get("prior_status") in ("REQUESTED", "CONFIRMED")
                    and payload.get("cancelled_by") in ("REQUESTER", "PROVIDER", "HOMIES")):
                source = payload["cancelled_by"]
        conn.execute(viewings.update().where(viewings.c.id == viewing_id).values(
            cancelled_by=source, cancellation_source_legacy=source is None))


def upgrade() -> None:
    op.add_column("viewings", sa.Column("cancelled_by", sa.String(16), nullable=True))
    op.add_column("viewings", sa.Column("cancellation_source_legacy", sa.Boolean,
                                        nullable=False, server_default=sa.false()))
    _backfill()
    with op.batch_alter_table("viewings") as batch:
        batch.create_check_constraint("ck_viewings_cancelled_by",
                                      "cancelled_by IS NULL OR cancelled_by IN "
                                      "('REQUESTER', 'PROVIDER', 'HOMIES')")
        batch.create_check_constraint("ck_viewings_cancellation_source_state", SOURCE_STATE)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION guard_viewing_cancellation_source() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    IF NEW.cancellation_source_legacy THEN
                        RAISE EXCEPTION 'legacy cancellation exceptions are migration-only'
                            USING ERRCODE = '23514';
                    END IF;
                ELSE
                    IF NEW.cancellation_source_legacy IS DISTINCT FROM OLD.cancellation_source_legacy
                       OR (OLD.cancelled_by IS NOT NULL
                           AND NEW.cancelled_by IS DISTINCT FROM OLD.cancelled_by) THEN
                        RAISE EXCEPTION 'viewing cancellation source is immutable'
                            USING ERRCODE = '23514';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$
        """)
        op.execute("""
            CREATE TRIGGER viewing_cancellation_source_guard
            BEFORE INSERT OR UPDATE ON viewings
            FOR EACH ROW EXECUTE FUNCTION guard_viewing_cancellation_source()
        """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER viewing_cancellation_source_guard ON viewings")
        op.execute("DROP FUNCTION guard_viewing_cancellation_source()")
    with op.batch_alter_table("viewings") as batch:
        batch.drop_constraint("ck_viewings_cancellation_source_state", type_="check")
        batch.drop_constraint("ck_viewings_cancelled_by", type_="check")
        batch.drop_column("cancellation_source_legacy")
        batch.drop_column("cancelled_by")