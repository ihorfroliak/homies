"""The reveal quota against real Postgres.

Two things SQLite cannot prove. First, the index the quota query depends on
exists only if a migration created it. Second, `revealed_at` is `timestamptz`
here and a naive string on SQLite — a window comparison that happens to work on
one can silently match nothing on the other, and a quota that matches nothing
is a quota that is not there.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app.core.config import settings
from app.modules.identity.models import User
from app.modules.properties.models import ContactReveal
from tests.conftest import auth, last_code, register_and_login

PROPERTY = {
    "property_type": "apartment",
    "city": "Warszawa",
    "municipality": "Warszawa",
    "address": "ul. Kwotowa 1",
    "area_m2": 50,
    "rooms": 2,
    "capacity": 4,
}

OFFER = {
    "title": "Mieszkanie długoterminowo",
    "rent_amount": 300000,
    "min_term_months": 12,
    "contact_mode": "phone",
    "contact_phone": "+48 500 333 444",
}


@pytest.fixture
def small_quota():
    original = settings.contact_reveal_daily_quota
    settings.contact_reveal_daily_quota = 2
    yield 2
    settings.contact_reveal_daily_quota = original


def _verified_seeker(pg_client, email, phone):
    token = register_and_login(pg_client, email, "guest")
    pg_client.post("/v1/me/verify/phone/start", json={"phone": phone}, headers=auth(token))
    assert pg_client.post(
        "/v1/me/verify/phone/confirm", json={"code": last_code()}, headers=auth(token)
    ).status_code == 200
    return token


def _publish(pg_client, owner, address):
    prop = pg_client.post(
        "/v1/properties", json={**PROPERTY, "address": address}, headers=auth(owner)
    )
    assert prop.status_code == 201, prop.text
    offer = pg_client.post(
        f"/v1/properties/{prop.json()['id']}/classifieds", json=OFFER, headers=auth(owner)
    )
    offer_id = offer.json()["id"]
    pg_client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(owner))
    return offer_id


def test_the_quota_index_exists_in_the_migrated_schema(pg_session):
    """Read from the live catalogue: the model is what we meant, this is what
    the database will actually use."""
    definition = pg_session.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_contact_reveals_viewer_time'")
    )
    assert definition is not None, "the quota index is missing — the migration did not run"
    assert "viewer_id" in definition and "revealed_at" in definition


def test_the_ceiling_holds_against_timestamptz(pg_client, small_quota):
    """End to end on the real column type. If the window comparison did not
    match, every reveal would look like the first one and the quota would never
    fire — which is exactly how this fails silently."""
    owner = register_and_login(pg_client, "pg-quota-owner@example.com", "host")
    seeker = _verified_seeker(pg_client, "pg-quota-seeker@example.com", "+48600000021")
    offers = [_publish(pg_client, owner, f"ul. Kwotowa {i}") for i in range(small_quota + 1)]

    for offer_id in offers[:small_quota]:
        assert pg_client.post(
            f"/v1/classifieds/{offer_id}/contact", headers=auth(seeker)
        ).status_code == 200

    blocked = pg_client.post(f"/v1/classifieds/{offers[-1]}/contact", headers=auth(seeker))
    assert blocked.status_code == 429, blocked.text
    assert "500 333 444" not in blocked.text


def test_an_aged_row_leaves_the_window_on_postgres(pg_client, pg_session, small_quota):
    owner = register_and_login(pg_client, "pg-age-owner@example.com", "host")
    seeker = _verified_seeker(pg_client, "pg-age-seeker@example.com", "+48600000022")
    offers = [_publish(pg_client, owner, f"ul. Stara {i}") for i in range(small_quota + 1)]

    for offer_id in offers[:small_quota]:
        pg_client.post(f"/v1/classifieds/{offer_id}/contact", headers=auth(seeker))
    assert pg_client.post(
        f"/v1/classifieds/{offers[-1]}/contact", headers=auth(seeker)
    ).status_code == 429

    viewer = pg_session.scalar(
        select(User).where(User.email == "pg-age-seeker@example.com")
    )
    row = pg_session.scalar(
        select(ContactReveal)
        .where(ContactReveal.viewer_id == viewer.id)
        .order_by(ContactReveal.revealed_at)
    )
    row.revealed_at = datetime.now(timezone.utc) - timedelta(hours=25)
    pg_session.commit()

    assert pg_client.post(
        f"/v1/classifieds/{offers[-1]}/contact", headers=auth(seeker)
    ).status_code == 200
