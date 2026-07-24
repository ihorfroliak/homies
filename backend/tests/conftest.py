import os

os.environ["ENV"] = "test"  # must precede app imports: lifespan skips real-DB setup

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.db import Base, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.identity.models import User  # noqa: E402

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client():
    from app.core.config import settings
    from app.core.ratelimit import limiter

    # Rate limiting is process-global; leave it OFF for ordinary tests so bulk
    # flows do not trip it. The SEC-01 suite turns it on explicitly.
    limiter.reset()
    settings.rate_limit_enabled = False
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def admin_token(client):
    with TestingSession() as db:
        db.add(
            User(
                email="admin@example.com",
                password_hash=hash_password("admin-password-123"),
                role="admin",
            )
        )
        db.commit()
    resp = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin-password-123"},
    )
    return resp.json()["access_token"]


def register_and_login(client, email: str, role: str) -> str:
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "password-123456", "role": role},
    )
    assert resp.status_code == 201, resp.text
    resp = client.post("/v1/auth/login", json={"email": email, "password": "password-123456"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# --- Postgres migration-backed schema (TD-01) --------------------------------
# The fast unit suite runs on SQLite (create_all) — it exercises business logic,
# not Postgres-only DB guards. Tests that must validate the REAL schema
# (migrations, exclusion constraint, triggers, concurrency) use the fixtures
# below, which build a fresh schema via Alembic on a real Postgres. They skip
# unless TEST_DATABASE_URL is set (CI-03 provides it; locally point it at the
# dev Postgres).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(scope="session")
def pg_migrated_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set — Postgres migration tests skipped")
    from alembic import command
    from sqlalchemy import create_engine, text

    from app.core.schema import alembic_config

    os.environ["ALEMBIC_DATABASE_URL"] = TEST_DATABASE_URL  # env.py reads this first
    eng = create_engine(TEST_DATABASE_URL)
    with eng.begin() as conn:  # fresh schema every session
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture()
def pg_session(pg_migrated_engine):
    """A session on the migration-built Postgres schema, cleaned between tests
    (data only — schema is preserved)."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    tables = (
        "notifications domain_events incidents webhook_events journal_lines "
        "journal_entries ledger_accounts payments bookings host_blocks listings "
        "host_profiles refresh_tokens audit_log users"
    ).split()
    with pg_migrated_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    Session = sessionmaker(bind=pg_migrated_engine, expire_on_commit=False)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def fire_webhook(client, intent_id: str, secret: str = "dev-webhook-secret"):
    return client.post(
        "/v1/payments/webhook/simulated",
        json={"intent_id": intent_id, "event": "payment_intent.succeeded"},
        headers={"X-Webhook-Secret": secret},
    )


def drain_notifications(max_rounds: int = 20):
    """Run the notification worker against the test DB until no notification is
    due for delivery (all delivered/dead, or scheduled for the future).
    Deterministic — the background worker is disabled in tests."""
    from datetime import datetime, timezone

    from sqlalchemy import func, select

    from app.modules.events import worker
    from app.modules.events.models import Notification

    for _ in range(max_rounds):
        with TestingSession() as db:
            worker.run_once(db, batch=100)
        with TestingSession() as db:
            due = db.scalar(
                select(func.count()).select_from(Notification).where(
                    Notification.status.in_(("pending", "failed")),
                    Notification.next_attempt_at <= datetime.now(timezone.utc),
                )
            )
        if not due:
            break
