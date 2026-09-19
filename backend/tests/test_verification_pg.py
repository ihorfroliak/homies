"""The database half of "one proven number, one account" (real Postgres).

The application checks for a collision before writing, but that check is a
SELECT: two confirmations of the same number racing each other both read an
empty result and both proceed. What actually holds the rule is the unique
index, and an index only exists if a migration created it — which SQLite's
create_all never proves.
"""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.modules.identity.models import User
from tests.conftest import auth, last_code, register_and_login

PHONE = "+48501234567"


def _user(email: str, phone: str | None = None) -> User:
    return User(email=email, password_hash=hash_password("password-123456"), phone=phone)


def test_the_unique_index_exists_in_the_migrated_schema(pg_session):
    """Read from the live catalogue, not from the model: the model is what we
    meant, the catalogue is what the database will actually enforce."""
    definition = pg_session.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_users_phone'")
    )
    assert definition is not None, "uq_users_phone is missing — the migration did not run"
    assert "UNIQUE" in definition
    assert "(phone)" in definition


def test_two_accounts_cannot_hold_the_same_number(pg_session):
    """Bypasses the API deliberately: this is the guarantee that survives a
    race the application-level check cannot see."""
    pg_session.add(_user("first@example.com", PHONE))
    pg_session.commit()

    pg_session.add(_user("second@example.com", PHONE))
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_unverified_accounts_all_share_a_null_number(pg_session):
    """NULL is not equal to NULL in Postgres, so the unique index costs nothing
    to everyone who has not verified yet. If it did, registration would break
    on the second user."""
    pg_session.add_all(_user(f"nulled{i}@example.com") for i in range(5))
    pg_session.commit()

    assert len(list(pg_session.scalars(select(User).where(User.phone.is_(None))))) == 5


def test_a_second_claim_is_refused_by_the_pre_check(pg_client):
    """The ordinary, non-racing case: the number is already taken and the
    application says so before it writes anything."""
    first = register_and_login(pg_client, "claim-one@example.com", "guest")
    second = register_and_login(pg_client, "claim-two@example.com", "guest")

    # Both codes are live at once — one per account — which is what makes the
    # collision reachable at all.
    codes = {}
    for name, token in (("first", first), ("second", second)):
        assert pg_client.post(
            "/v1/me/verify/phone/start", json={"phone": PHONE}, headers=auth(token)
        ).status_code == 200
        codes[name] = last_code()

    assert pg_client.post(
        "/v1/me/verify/phone/confirm", json={"code": codes["second"]}, headers=auth(second)
    ).status_code == 200

    pg_client.post("/v1/me/verify/phone/start", json={"phone": PHONE}, headers=auth(first))
    losing = pg_client.post(
        "/v1/me/verify/phone/confirm", json={"code": last_code()}, headers=auth(first)
    )
    assert losing.status_code == 409, losing.text


def test_losing_the_race_answers_409_rather_than_500(pg_client, monkeypatch):
    """A real race cannot be produced through TestClient, which serialises
    requests — so the fault is injected instead: the pre-check is made to come
    back empty while the row exists, which is precisely what the losing side of
    a race reads. The index then rejects the commit, and the person who did
    nothing wrong must get "that number is taken", not a 500.
    """
    from app.modules.identity import router as identity_router

    winner = register_and_login(pg_client, "race-winner@example.com", "guest")
    loser = register_and_login(pg_client, "race-loser@example.com", "guest")

    pg_client.post("/v1/me/verify/phone/start", json={"phone": PHONE}, headers=auth(winner))
    assert pg_client.post(
        "/v1/me/verify/phone/confirm", json={"code": last_code()}, headers=auth(winner)
    ).status_code == 200

    monkeypatch.setattr(identity_router, "_phone_taken", lambda db, phone, user_id: False)
    pg_client.post("/v1/me/verify/phone/start", json={"phone": PHONE}, headers=auth(loser))
    resp = pg_client.post(
        "/v1/me/verify/phone/confirm", json={"code": last_code()}, headers=auth(loser)
    )

    assert resp.status_code == 409, resp.text
    assert resp.status_code != 500


def test_the_code_table_survives_the_migration(pg_session):
    """A table the ORM knows about and the migration forgot passes every
    SQLite test and fails on the first production request."""
    columns = set(
        pg_session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'verification_codes'"
            )
        )
    )
    assert {
        "id", "user_id", "channel", "destination", "code_hash",
        "expires_at", "attempts", "consumed_at", "created_at",
    } <= columns
