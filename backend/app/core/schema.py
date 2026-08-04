"""Schema management (TD-01). Alembic migrations are the single source of truth
for the database schema. The application never creates or mutates schema through
ORM metadata (`create_all`) any more.

- local dev: `ensure_schema()` applies migrations for convenience (`make up`
  just works) — still the same migration path as production, so no drift.
- staging / production: the app assumes migrations were already applied by a
  separate deploy step. It only *verifies* the DB is at head and fails loudly
  otherwise — it never silently creates schema.
- test: tests own their engine (conftest); `ensure_schema()` is not called.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.core.config import settings

log = logging.getLogger("homies.schema")

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Environments where the app may apply migrations itself as a dev convenience.
SELF_MIGRATING_ENVIRONMENTS = frozenset({"local"})


class SchemaNotMigratedError(RuntimeError):
    """The database is not at the migration head. A production-like deployment
    must run `alembic upgrade head` before starting the app."""


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _head_revision() -> str:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:
        # No revisions found at all — the migration directory is missing or
        # empty (e.g. an image built without alembic/). Without this guard both
        # head and current are None, `current != head` is False, and the app
        # would report "schema verified" against a completely empty database.
        raise SchemaNotMigratedError(
            "No Alembic revisions found. The migration directory is missing or "
            "empty, so the schema cannot be verified."
        )
    return head


def _current_revision() -> str | None:
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def ensure_schema() -> None:
    """Apply (local) or verify (everything else) the schema. Never `create_all`."""
    if settings.env in SELF_MIGRATING_ENVIRONMENTS:
        log.info("applying migrations (env=%s)", settings.env)
        command.upgrade(alembic_config(), "head")
        return

    head, current = _head_revision(), _current_revision()
    if current != head:
        raise SchemaNotMigratedError(
            f"Database is at revision {current!r} but head is {head!r}. "
            "Run `alembic upgrade head` before starting the app."
        )
    log.info("schema verified at head %s", head)
