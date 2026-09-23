import os
import re

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


def _seed_attribute_catalogue():
    """The fast suite builds its schema with create_all, which runs no seeds.

    The rows are read from the migration that owns them rather than copied here:
    two lists of amenity codes drift, and the one that drifts is always the one
    nobody runs.
    """
    import importlib.util
    from pathlib import Path

    from app.modules.properties.models import AttributeDefinition

    # Loaded by path: `alembic` on sys.path is the installed library, and the
    # versions directory is not a package.
    source = (
        Path(__file__).resolve().parents[1]
        / "alembic" / "versions" / "9010d2077493_attribute_catalogue.py"
    )
    spec = importlib.util.spec_from_file_location("_attr_catalogue_seed", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestingSession() as db:
        if db.query(AttributeDefinition).first() is not None:
            return
        db.add_all(AttributeDefinition(**row) for row in module._seed_rows())
        db.commit()


@pytest.fixture()
def client():
    from app.core.config import settings
    from app.core.ratelimit import limiter

    # Rate limiting is process-global; leave it OFF for ordinary tests so bulk
    # flows do not trip it. The SEC-01 suite turns it on explicitly.
    limiter.reset()
    settings.rate_limit_enabled = False
    Base.metadata.create_all(engine)
    _seed_attribute_catalogue()

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


# Verification codes never leave the process in tests: the delivery seam is
# swapped for a capture, so a test can read the code the user would have got
# without the code ever appearing in an HTTP response (where production would
# then be one careless change away from leaking it).
SENT_MESSAGES: list[dict] = []


@pytest.fixture(autouse=True)
def _capture_verification_messages(monkeypatch):
    from app.modules.events.providers import DeliveryResult

    SENT_MESSAGES.clear()

    class _Capture:
        def send(self, to, subject, body, idem_key):
            SENT_MESSAGES.append(
                {"to": to, "subject": subject, "body": body, "idem_key": idem_key}
            )
            return DeliveryResult(ok=True)

    monkeypatch.setattr(
        "app.modules.identity.verification.channel_for", lambda name: _Capture()
    )
    return SENT_MESSAGES


def last_code() -> str:
    match = re.search(r"\b(\d{6})\b", SENT_MESSAGES[-1]["body"])
    assert match, f"no code in {SENT_MESSAGES[-1]['body']!r}"
    return match.group(1)


def verify_phone(client, token: str, phone: str) -> None:
    """Drive the real endpoints — never set the column directly, or the tests
    stop proving that the flow a user walks actually works."""
    started = client.post(
        "/v1/me/verify/phone/start", json={"phone": phone}, headers=auth(token)
    )
    assert started.status_code == 200, started.text
    confirmed = client.post(
        "/v1/me/verify/phone/confirm", json={"code": last_code()}, headers=auth(token)
    )
    assert confirmed.status_code == 200, confirmed.text


def admin_login(client) -> str:
    """An admin token for whichever database this client is wired to.

    Works for the SQLite and the Postgres client alike by borrowing the
    session the app itself was given, so a test never has to know which engine
    it is running on.
    """
    from app.core.db import get_db
    from sqlalchemy import select

    email = "fixture-admin@example.com"
    source = client.app.dependency_overrides[get_db]()
    db = next(source)
    try:
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(User(email=email, password_hash=hash_password("admin-password-123"),
                        role="admin"))
            db.commit()
    finally:
        db.close()
    resp = client.post("/v1/auth/login", json={"email": email, "password": "admin-password-123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def verify_ownership(client, owner_token: str, property_id: str) -> None:
    """Take a property claim through the real verification path.

    The owner gives a legal name, an admin verifies every authority on the
    property. Driven through the endpoints rather than by setting the column,
    so every test that publishes also proves the path a real owner walks.
    """
    named = client.put(
        "/v1/me/legal-identity",
        json={"legal_first_name": "Jan", "legal_last_name": "Kowalski"},
        headers=auth(owner_token),
    )
    # 409 means a claim of theirs is already verified and the name is locked —
    # the state this helper exists to reach.
    assert named.status_code in (200, 409), named.text

    admin = admin_login(client)
    authorities = client.get(
        f"/v1/admin/properties/{property_id}/authorities", headers=auth(admin)
    )
    assert authorities.status_code == 200, authorities.text
    for entry in authorities.json():
        if entry["verification_state"] != "VERIFIED":
            done = client.post(
                f"/v1/admin/property-authorities/{entry['id']}/verify", headers=auth(admin)
            )
            assert done.status_code == 200, done.text


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
def pg_client(pg_migrated_engine):
    """A TestClient wired to the migration-built Postgres schema, so requests
    hit the real engine (row locks, exclusion constraints). Data is truncated
    between tests; the schema is preserved. Used by the CI-03 concurrency tests
    — SQLite cannot model true multi-connection concurrency."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.core.db import get_db

    tables = (
        # Every table a test can write to. A missing name leaks state into the
        # next test: `disputes` was absent since FIN-03 and nothing noticed.
        "notifications domain_events incidents webhook_events disputes "
        "contact_reveals classified_offers spaces property_authority_scopes property_authorities "
        "properties person_legal_parties legal_parties verification_codes "
        "journal_lines journal_entries ledger_accounts payments bookings "
        "host_blocks listings host_profiles refresh_tokens audit_log users"
    ).split()
    with pg_migrated_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))

    Session = sessionmaker(bind=pg_migrated_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    settings.rate_limit_enabled = False
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def pg_session(pg_migrated_engine):
    """A session on the migration-built Postgres schema, cleaned between tests
    (data only — schema is preserved)."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    tables = (
        # Every table a test can write to. A missing name leaks state into the
        # next test: `disputes` was absent since FIN-03 and nothing noticed.
        "notifications domain_events incidents webhook_events disputes "
        "contact_reveals classified_offers spaces property_authority_scopes property_authorities "
        "properties person_legal_parties legal_parties verification_codes "
        "journal_lines journal_entries ledger_accounts payments bookings "
        "host_blocks listings host_profiles refresh_tokens audit_log users"
    ).split()
    with pg_migrated_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    Session = sessionmaker(bind=pg_migrated_engine, expire_on_commit=False)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def stripe_webhook(monkeypatch):
    """Real StripeConnectProvider wired to a locally generated signing secret.

    Lives here (not in a test module) so every suite that drives the production
    webhook can request it without importing it — importing a fixture makes its
    name collide with the test parameter (ruff F811).
    """
    import secrets

    import app.modules.payments.router as payments_router
    from app.core.config import settings
    from app.modules.payments.provider import StripeConnectProvider

    secret = "whsec_" + secrets.token_hex(24)
    monkeypatch.setattr(settings, "stripe_webhook_secret", secret)
    provider = StripeConnectProvider(api_key="sk_test_" + secrets.token_hex(12))
    monkeypatch.setattr(payments_router, "provider", provider)
    return secret


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
