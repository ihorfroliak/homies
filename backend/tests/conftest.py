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


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def fire_webhook(client, intent_id: str, secret: str = "dev-webhook-secret"):
    return client.post(
        "/v1/payments/webhook/simulated",
        json={"intent_id": intent_id, "event": "payment_intent.succeeded"},
        headers={"X-Webhook-Secret": secret},
    )
