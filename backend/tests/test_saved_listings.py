"""Saved Listings (TASK-014): owner isolation, idempotency, privacy-safe tombstones."""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.modules.properties.models import ClassifiedOffer
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership
from tests.saved_support import load_geo


@pytest.fixture
def geo(client):
    return load_geo(TestingSession)

PROPERTY = {"category": "APARTMENT", "area_m2": 48, "rooms": 2, "capacity": 2}
OFFER = {"title": "Zapisane", "rent_amount": 270000, "min_term_months": 12,
         "contact_mode": "phone", "contact_phone": "+48 600 700 800"}
# Values that exist only in private or owner data — none may appear in any
# saved-listing response, tombstone or not.
SENTINELS = ("ul. Sentinelowa", "77SNT", "Z13B", "31-999", "600 700 800",
             "owner-sl@example.com")


@pytest.fixture
def owner(client):
    return register_and_login(client, "owner-sl@example.com", "host")


@pytest.fixture
def renter(client):
    return register_and_login(client, "renter-sl@example.com", "guest")


def _publish(client, owner, geo, n=0):
    made = client.post("/v1/properties", json={
        **PROPERTY, "locality_id": geo["krakow"], "thoroughfare": "ul. Sentinelowa",
        "building_number": "77SNT", "unit_number": f"Z13B{n or ''}", "postcode": "31-999",
        "latitude": 50.0612, "longitude": 19.9371}, headers=auth(owner))
    assert made.status_code == 201, made.text
    pid = made.json()["id"]
    verify_ownership(client, owner, pid)
    oid = client.post(f"/v1/properties/{pid}/classifieds", json=OFFER,
                      headers=auth(owner)).json()["id"]
    assert client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner)).status_code == 200
    return oid


def _saved(client, token):
    r = client.get("/v1/me/saved-listings", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_save_is_idempotent_and_unsave_is_idempotent(client, owner, renter, geo):
    oid = _publish(client, owner, geo)
    first = client.post(f"/v1/me/saved-listings/{oid}", headers=auth(renter))
    assert first.status_code == 201, first.text
    again = client.post(f"/v1/me/saved-listings/{oid}", headers=auth(renter))
    assert again.status_code == 200
    assert again.json()["saved_id"] == first.json()["saved_id"]
    assert first.json()["availability_status"] == "AVAILABLE"
    assert first.json()["listing"]["id"] == oid
    assert _saved(client, renter)["total"] == 1
    assert client.delete(f"/v1/me/saved-listings/{oid}", headers=auth(renter)).status_code == 204
    assert client.delete(f"/v1/me/saved-listings/{oid}", headers=auth(renter)).status_code == 204
    assert _saved(client, renter)["total"] == 0


def test_saves_are_private_to_their_owner(client, owner, renter, geo):
    oid = _publish(client, owner, geo)
    client.post(f"/v1/me/saved-listings/{oid}", headers=auth(renter))
    other = register_and_login(client, "other-sl@example.com", "guest")
    assert _saved(client, other) == {"items": [], "total": 0, "limit": 50, "offset": 0}
    # Another account's DELETE cannot touch this save.
    assert client.delete(f"/v1/me/saved-listings/{oid}", headers=auth(other)).status_code == 204
    assert _saved(client, renter)["total"] == 1
    assert client.get("/v1/me/saved-listings").status_code == 401


def test_only_a_public_listing_can_be_saved(client, owner, renter, geo):
    oid = _publish(client, owner, geo)
    client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
    assert client.post(f"/v1/me/saved-listings/{oid}", headers=auth(renter)).status_code == 404
    assert client.post("/v1/me/saved-listings/no-such-listing",
                       headers=auth(renter)).status_code == 404
    for bad in ("x" * 37, "a%00b", "a b"):
        assert client.post(f"/v1/me/saved-listings/{bad}",
                           headers=auth(renter)).status_code == 422


def test_non_public_save_is_a_privacy_safe_tombstone(client, owner, renter, geo):
    oid = _publish(client, owner, geo)
    saved = client.post(f"/v1/me/saved-listings/{oid}", headers=auth(renter)).json()
    client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
    page = _saved(client, renter)
    assert page["total"] == 1  # the relationship is kept
    item = page["items"][0]
    assert item == {"saved_id": saved["saved_id"], "listing_id": oid,
                    "saved_at": saved["saved_at"],
                    "availability_status": "NO_LONGER_AVAILABLE", "listing": None}
    text = json.dumps(page)
    for secret in SENTINELS + (OFFER["title"], "270000", "Kraków"):
        assert secret not in text, secret
    # Public again → the normal public shape comes back.
    assert client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner)).status_code == 200
    back = _saved(client, renter)["items"][0]
    assert back["availability_status"] == "AVAILABLE" and back["listing"]["id"] == oid


def test_stale_by_time_alone_is_a_tombstone(client, owner, renter, geo):
    """Silent freshness expiry: still `active`, 22 days unconfirmed — not public."""
    oid = _publish(client, owner, geo)
    client.post(f"/v1/me/saved-listings/{oid}", headers=auth(renter))
    with TestingSession() as db:
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == oid).values(
            last_confirmed_available_at=datetime.now(timezone.utc) - timedelta(days=22)))
        db.commit()
    assert _saved(client, renter)["items"][0]["availability_status"] == "NO_LONGER_AVAILABLE"


def test_public_saves_never_carry_private_details(client, owner, renter, geo):
    oid = _publish(client, owner, geo)
    client.post(f"/v1/me/saved-listings/{oid}", headers=auth(renter))
    page = _saved(client, renter)
    text = json.dumps(page)
    for secret in SENTINELS:
        assert secret not in text, secret
    # The exact point, as a number or inside any non-timestamp string. A plain
    # substring check on the dump was flaky: an ISO timestamp such as
    # "…T00:12:50.061234" contains "50.0612".
    for value in _leaves(page):
        if isinstance(value, float):
            assert abs(value - 50.0612) > 1e-9 and abs(value - 19.9371) > 1e-9, value
        elif isinstance(value, str) and not _ISO_INSTANT.match(value):
            assert "50.0612" not in value and "19.9371" not in value, value


_ISO_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _leaves(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _leaves(v)
    elif isinstance(node, list):
        for v in node:
            yield from _leaves(v)
    else:
        yield node


def test_order_is_newest_first_and_pages_deterministically(client, owner, renter, geo):
    ids = [_publish(client, owner, geo, n) for n in range(1, 4)]
    for oid in ids:
        client.post(f"/v1/me/saved-listings/{oid}", headers=auth(renter))
    everything = [i["listing_id"] for i in _saved(client, renter)["items"]]
    assert everything == list(reversed(ids))
    first = client.get("/v1/me/saved-listings", params={"limit": 2},
                       headers=auth(renter)).json()["items"]
    rest = client.get("/v1/me/saved-listings", params={"limit": 2, "offset": 2},
                      headers=auth(renter)).json()["items"]
    assert [i["listing_id"] for i in first + rest] == everything


def test_the_per_user_cap_holds(client, owner, renter, geo, monkeypatch):
    monkeypatch.setattr(settings, "saved_listings_per_user", 2)
    ids = [_publish(client, owner, geo, n) for n in range(1, 4)]
    assert client.post(f"/v1/me/saved-listings/{ids[0]}", headers=auth(renter)).status_code == 201
    assert client.post(f"/v1/me/saved-listings/{ids[1]}", headers=auth(renter)).status_code == 201
    capped = client.post(f"/v1/me/saved-listings/{ids[2]}", headers=auth(renter))
    assert capped.status_code == 409
    # Re-saving an existing one is still an idempotent 200, not a cap error.
    assert client.post(f"/v1/me/saved-listings/{ids[0]}", headers=auth(renter)).status_code == 200
