"""INSERT … ON CONFLICT DO NOTHING on PostgreSQL and SQLite alike: the
"exactly once" of matches, deliveries and inbox entries is the database's
uniqueness, and a concurrent duplicate simply inserts nothing."""

from sqlalchemy.orm import Session


def insert_ignore(db: Session, model, rows: list[dict], conflict: list[str]) -> int:
    """Insert what is not there yet; returns how many rows were inserted
    (counted from RETURNING — a multi-row statement's rowcount is not
    reliable on every driver)."""
    if not rows:
        return 0
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert  # type: ignore[assignment]
    table = model.__table__
    stmt = (insert(model).values(rows).on_conflict_do_nothing(index_elements=conflict)
            .returning(table.c[conflict[0]]))
    return len(db.execute(stmt).all())
