"""Alembic environment. Migrations are the source of truth for the schema
in every shared/production environment (D7 blocker B6). Local dev and tests
still use create_all for speed, but prod schema evolution goes through here.
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

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
    Property,
)

config = context.config

# Single source of the DB URL (TD-01): explicit ALEMBIC_DATABASE_URL override
# (used to migrate a throwaway DB) else the application's own settings — so the
# CLI and the app's programmatic ensure_schema() migrate the same database.
from app.core.config import settings  # noqa: E402

config.set_main_option(
    "sqlalchemy.url",
    os.environ.get("ALEMBIC_DATABASE_URL", settings.database_url),
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
