"""INSERT … ON CONFLICT DO NOTHING on PostgreSQL and SQLite alike: the
"exactly once" of matches, deliveries and inbox entries is the database's
uniqueness, and a concurrent duplicate simply inserts nothing."""

from sqlalchemy.orm import Session


def insert_ignore(db: Session, model, rows: list[dict], conflict: list[str]) -> int:
    if not rows:
        return 0
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert  # type: ignore[assignment]
    stmt = insert(model).values(rows).on_conflict_do_nothing(index_elements=conflict)
    return int(getattr(db.execute(stmt), "rowcount", 0) or 0)
