from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _connect_args(url: str) -> dict:
    """Bound the TCP connect for Postgres (OBS-01).

    Without this, a database host that *blackholes* packets — a network
    partition, a dropped security-group rule, a dead node — hangs every
    connection attempt for the OS TCP timeout (~130s on Linux) instead of
    failing. That stalls request threads, and it stalled the readiness probe
    itself: `statement_timeout` cannot help, because there is no session yet.
    Found by the OBS-01 readiness test hanging against a down database.
    """
    if url.startswith("postgresql"):
        return {"connect_timeout": 3}
    return {}


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=_connect_args(settings.database_url),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
