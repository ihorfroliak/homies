"""Create an admin user. Admins are never created through the public API.

Usage: python -m app.scripts.create_admin admin@homies.example 'strong-password'
"""

import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.modules.identity.models import User


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)
    email, password = sys.argv[1].lower(), sys.argv[2]
    if len(password) < 12:
        raise SystemExit("Admin password must be at least 12 characters")
    # TD-01: schema is owned by Alembic; this ops tool assumes `alembic upgrade
    # head` has already run. It must not create schema.
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit(f"User {email} already exists")
        db.add(User(email=email, password_hash=hash_password(password), role="admin"))
        db.commit()
    print(f"Admin {email} created")


if __name__ == "__main__":
    main()
