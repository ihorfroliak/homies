"""Alembic environment. Migrations are the source of truth for the schema
in every shared/production environment (D7 blocker B6). Local dev and tests
still use create_all for speed, but prod schema evolution goes through here.
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, inspect, pool, text

from alembic import context

# Import Base and every model module so metadata is complete for autogenerate.
from app.core.audit import AuditLog  # noqa: F401
from app.core.db import Base
from app.modules.booking.models import Booking  # noqa: F401
from app.modules.engagement.models import Conversation  # noqa: F401
from app.modules.events.models import DomainEvent, Incident, Notification  # noqa: F401
from app.modules.geography.models import Address, AdministrativeArea, Country  # noqa: F401
from app.modules.identity.models import (  # noqa: F401
    HostProfile,
    RefreshToken,
    User,
    VerificationCode,
)
from app.modules.ledger.models import JournalEntry, JournalLine, LedgerAccount  # noqa: F401
from app.modules.listings.models import HostBlock, Listing  # noqa: F401
from app.modules.payments.models import Payment, WebhookEvent  # noqa: F401
from app.modules.properties.models import (  # noqa: F401
    ClassifiedOffer,
    ContactReveal,
    ListingPublicGeneration,
    Property,
)
from app.modules.saved.models import SavedListing, SavedSearch  # noqa: F401
from app.modules.alerts.models import AlertDelivery, SavedSearchMatch  # noqa: F401

config = context.config

# Single source of the DB URL (TD-01): explicit ALEMBIC_DATABASE_URL override
# (used to migrate a throwaway DB) else the application's own settings — so the
# CLI and the app's programmatic ensure_schema() migrate the same database.
from app.core.config import settings  # noqa: E402

config.set_main_option(
    "sqlalchemy.url",
    # '%' escaped for configparser: a percent-encoded password would otherwise
    # raise a ValueError that prints the whole URL (PR-001R).
    os.environ.get("ALEMBIC_DATABASE_URL", settings.database_url).replace("%", "%%"),
)

# The CLI configures logging from alembic.ini. A caller that already has logging
# (the application's local self-migration) passes configure_logger=False; and
# existing loggers are never disabled either way (PR-001R F5).
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _record_lineage(ctx, step, heads, run_args) -> None:
    """Keep `schema_lineage` in step with `alembic_version` (PR-002).

    Runs inside the migration transaction after each applied step, so the
    lineage row commits or rolls back with the schema change it describes.
    Before the PR-002 lineage migration the table does not exist and nothing
    is recorded (that migration backfills history). A migration without valid
    declarations fails the upgrade: never a default. Stamps are not recorded.
    """
    from app.core.lineage_registry import HISTORICAL
    from app.core.release import step_declarations

    conn = ctx.connection
    if conn is None or step.is_stamp or not inspect(conn).has_table("schema_lineage"):
        return
    if step.is_upgrade:
        script = step.up_revision
        transition, rollback = step_declarations(script.module, HISTORICAL)
        down = script.down_revision
        if isinstance(down, (tuple, list)):
            raise RuntimeError(f"merge revision {script.revision} is not supported by the lineage")
        conn.execute(
            text("INSERT INTO schema_lineage (revision, down_revision, schema_transition, "
                 "rollback_to_previous, recorded_by) VALUES (:r, :d, :t, :rb, 'MIGRATION')"),
            {"r": script.revision, "d": down, "t": transition, "rb": rollback},
        )
    else:
        conn.execute(text("DELETE FROM schema_lineage WHERE revision = :r"),
                     {"r": step.up_revision_id})


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      on_version_apply=_record_lineage)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # The migration runner (app/scripts/migrate.py) passes the connection that
    # holds the migration advisory lock and its session lock_timeout (PR-002).
    given = config.attributes.get("connection")
    if given is not None:
        _run(given)
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
