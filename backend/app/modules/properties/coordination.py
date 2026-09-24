"""Serialising changes that decide whether a listing may be public.

A listing is public only while three things hold at once: an authority in
force and VERIFIED backs its property, its space is listable, and its own
status is `active`. Publishing reads the first two and writes the third;
revoking an authority or archiving a space writes the first two and takes
listings down. Checked in one transaction and written in another, they race:
TASK-001 F-04 showed a publication that passed the authority check, waited,
and then wrote `active` after the revoke had already committed.

The coordination resource is the **Property row**. Every such operation takes
it FOR UPDATE before it reads or writes anything else, then re-reads what it
depends on. It is the narrowest row every one of them shares; unrelated
properties never wait on each other.

Lock order (acquire in this order, never the reverse):

    1. properties            (this module — the coordination row)
    2. spaces
    3. property_authorities
    4. classified_offers

`publish`, `authority.revoke` and `spaces.archive` all follow it, so none of
them can deadlock against another.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.properties.models import Property


def lock_property(db: Session, property_id: str) -> Property | None:
    """Take the property's coordination lock for the rest of the transaction.

    Everything the session loaded before this point may be stale — another
    transaction may have committed while we waited — so the identity map is
    expired and later reads go back to the database. On SQLite (unit tests)
    FOR UPDATE is a no-op; the serialisation is proved on PostgreSQL.
    """
    db.expire_all()
    return db.scalar(
        select(Property)
        .where(Property.id == property_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
