import logging
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from prometheus_client import Gauge
from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core import db_deadline
from app.core.config import Settings, settings

log = logging.getLogger("homies.db")


class Base(DeclarativeBase):
    pass


@dataclass(frozen=True)
class DatabaseDeadlines:
    """The database deadline policy (PR-003) — every budget in one place.

    See Settings (app/core/config.py) for what each one bounds. The client
    deadline is derived, not configured: statement_timeout plus a grace, so it
    only expires when the server could not answer.
    """

    connect_timeout_s: int
    pool_timeout_s: float
    lock_timeout_ms: int
    statement_timeout_ms: int
    idle_in_transaction_timeout_ms: int
    client_connection_check_interval_ms: int
    client_grace_s: float

    @classmethod
    def from_settings(cls, cfg: Settings) -> "DatabaseDeadlines":
        return cls(
            connect_timeout_s=cfg.db_connect_timeout_seconds,
            pool_timeout_s=cfg.db_pool_timeout_seconds,
            lock_timeout_ms=cfg.db_lock_timeout_ms,
            statement_timeout_ms=cfg.db_statement_timeout_ms,
            idle_in_transaction_timeout_ms=cfg.db_idle_in_transaction_timeout_ms,
            client_connection_check_interval_ms=cfg.db_client_connection_check_interval_ms,
            client_grace_s=cfg.db_client_grace_seconds,
        )

    @property
    def client_deadline_s(self) -> float:
        return self.statement_timeout_ms / 1000 + self.client_grace_s


DEADLINES = DatabaseDeadlines.from_settings(settings)


def _connect_args(url: str, deadlines: DatabaseDeadlines = DEADLINES) -> dict:
    """libpq connection parameters for Postgres.

    connect_timeout (OBS-01): without it a database host that *blackholes*
    packets — a network partition, a dropped security-group rule, a dead node —
    hangs every connection attempt for the OS TCP timeout (~130s on Linux)
    instead of failing; `statement_timeout` cannot help, because there is no
    session yet. It also bounds a server that accepts TCP but never completes
    the startup handshake (frozen).

    The server-side limits travel as session options, so they hold for every
    connection of the application role whatever the role's defaults are.
    Keepalives let an idle pooled connection to a vanished peer be noticed
    by the kernel rather than at its next use.
    """
    if url.startswith("postgresql"):
        # Sessions start in UTC (TASK-012R, defence in depth only): business
        # rules normalise instants themselves and stay correct in any zone.
        options = " ".join([
            "-c timezone=UTC",
            f"-c statement_timeout={deadlines.statement_timeout_ms}",
            f"-c lock_timeout={deadlines.lock_timeout_ms}",
            f"-c idle_in_transaction_session_timeout={deadlines.idle_in_transaction_timeout_ms}",
            f"-c client_connection_check_interval={deadlines.client_connection_check_interval_ms}",
        ])
        return {
            "connect_timeout": deadlines.connect_timeout_s,
            "options": options,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        }
    return {}


def _guard_connections(engine: Engine, deadlines: DatabaseDeadlines) -> None:
    """Make every DBAPI connection of `engine` a deadline-guarded one."""

    @event.listens_for(engine, "do_connect")
    def _connect(dialect: Any, conn_rec: Any, cargs: tuple, cparams: dict) -> Any:
        cparams.setdefault("cursor_factory", db_deadline.DeadlineCursor)
        conn = db_deadline.DeadlineConnection.connect(*cargs, **cparams)
        conn.client_deadline_s = deadlines.client_deadline_s
        return conn


def create_bounded_engine(url: str, deadlines: DatabaseDeadlines = DEADLINES,
                          **kwargs: Any) -> Engine:
    """The one way the application opens a database engine (PR-003).

    Postgres engines get the connect/server/client deadlines and a bounded pool
    wait; anything else (SQLite in tests) is created as before.

    Postgres engines never render bound parameters into an exception
    (BP-10, D-108): a statement that fails on its way out of a request is
    logged with its traceback, and its parameters are message bodies, client
    message ids and other private input.
    """
    if url.startswith("postgresql"):
        if kwargs.get("poolclass") is None:
            kwargs.setdefault("pool_timeout", deadlines.pool_timeout_s)
        kwargs["hide_parameters"] = True
        engine = create_engine(url, pool_pre_ping=True,
                               connect_args=_connect_args(url, deadlines), **kwargs)
        _guard_connections(engine, deadlines)
        return engine
    return create_engine(url, pool_pre_ping=True, **kwargs)


engine = create_bounded_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# PR-003: pool pressure was invisible — requests waiting for a connection
# showed up in no metric. Read at scrape time; no labels.
POOL_IN_USE = Gauge("homies_db_pool_connections_in_use",
                    "Application pool connections checked out right now")
POOL_CAPACITY = Gauge("homies_db_pool_connections_capacity",
                      "Most connections the application pool will open (size + overflow)")
if isinstance(engine.pool, QueuePool):
    _pool = engine.pool
    POOL_IN_USE.set_function(lambda: _pool.checkedout())
    POOL_CAPACITY.set_function(lambda: _pool.size() + max(_pool._max_overflow, 0))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        close_quietly(db)


def close_quietly(db: Session) -> None:
    """Close a session whose connection may already have failed (PR-003).

    Closing rolls back. When the request already failed because the database
    stopped answering, that rollback fails too (at once — the connection is
    shut — or at the client deadline), and raising it here would replace the
    request's own error: an "outcome unknown" COMMIT would be reported as a
    rollback failure. SQLAlchemy has already invalidated the connection, so
    nothing returns to the pool broken; the failure is logged, not raised.
    """
    try:
        db.close()
    except (sa_exc.OperationalError, sa_exc.TimeoutError) as exc:
        log.warning("session close after a database failure: %s",
                    type(getattr(exc, "orig", exc)).__name__)


def lock_row(db: Session, model: Any, row_id: str, *, shared: bool = False) -> Any | None:
    """Lock one row by primary key (FOR UPDATE, or FOR SHARE with `shared`)
    and return the entity as committed now — or None if it does not exist.

    The lock is taken on the bare id: a model with a joined eager
    relationship cannot be selected FOR UPDATE/SHARE whole, because
    PostgreSQL refuses a row lock on the nullable side of the outer join the
    eager load adds (TASK-015 S4b found it; SQLite ignores row locks, so only
    the PostgreSQL suite sees it). The entity is then re-read under the lock.
    """
    pk = model.__mapper__.primary_key[0]
    if db.scalar(select(pk).where(pk == row_id).with_for_update(read=shared)) is None:
        return None
    return db.get(model, row_id, populate_existing=True)
