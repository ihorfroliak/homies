"""Public eligibility episodes — `public_generation` (TASK-014, D-77).

Every authoritative way to become public is covered; generation follows the
TASK-012 public rule (not the status label); the generation, its event and its
work item are written atomically."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.modules.events.models import DomainEvent
from app.modules.properties import freshness, publicity
from app.modules.properties.models import ClassifiedOffer, ListingPublicGeneration
from tests.conftest import (
    TestingSession,
    assert_unhandled_500,
    auth,
    register_and_login,
    verify_ownership,
)

PROPERTY = {"category": "APARTMENT", "area_m2": 44, "rooms": 2, "capacity": 2, "city": "Gdańsk",
            "address": "ul. Prywatna 9 m. 4"}
OFFER = {"title": "Epizody", "rent_amount": 240000, "min_term_months": 12,
         "contact_mode": "phone", "contact_phone": "+48 511 222 333"}


@pytest.fixture
def owner(client):
    return register_and_login(client, "gen-owner@example.com", "host")


def _draft(client, owner):
    pid = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(client, owner, pid)
    return client.post(f"/v1/properties/{pid}/classifieds", json=OFFER,
                       headers=auth(owner)).json()["id"]


def _state(oid):
    with TestingSession() as db:
        offer = db.get(ClassifiedOffer, oid)
        work = list(db.scalars(select(ListingPublicGeneration.public_generation)
                               .where(ListingPublicGeneration.listing_id == oid)
                               .order_by(ListingPublicGeneration.public_generation)))
        events = list(db.scalars(select(DomainEvent.dedup_key).where(
            DomainEvent.event_type == publicity.LISTING_BECAME_PUBLIC,
            DomainEvent.correlation_id == oid).order_by(DomainEvent.dedup_key)))
        return offer.public_generation, work, events


def _age(oid, days):
    with TestingSession() as db:
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == oid).values(
            last_confirmed_available_at=datetime.now(timezone.utc) - timedelta(days=days)))
        db.commit()


def _post(client, owner, oid, action):
    r = client.post(f"/v1/classifieds/{oid}/{action}", headers=auth(owner))
    assert r.status_code == 200, r.text
    return r


def test_never_public_is_zero_and_first_publication_is_one(client, owner):
    oid = _draft(client, owner)
    assert _state(oid) == (0, [], [])
    _post(client, owner, oid, "publish")
    assert _state(oid) == (1, [1], [f"ListingBecamePublic:{oid}:1"])


def test_already_public_republish_and_reconfirm_open_no_episode(client, owner):
    oid = _draft(client, owner)
    _post(client, owner, oid, "publish")
    _post(client, owner, oid, "publish")   # PUBLISHABLE_FROM includes active
    _post(client, owner, oid, "confirm")   # ordinary reconfirmation
    _age(oid, 15)                          # RECONFIRM_DUE is still public
    _post(client, owner, oid, "confirm")
    assert _state(oid) == (1, [1], [f"ListingBecamePublic:{oid}:1"])


def test_content_edits_while_public_open_no_episode(client, owner):
    oid = _draft(client, owner)
    _post(client, owner, oid, "publish")
    version = client.get(f"/v1/classifieds/{oid}").json()["version"]
    assert client.put(f"/v1/classifieds/{oid}/price", json={
        "rent_amount": 199000, "expected_version": version}, headers=auth(owner)).status_code == 200
    assert client.put(f"/v1/classifieds/{oid}/availability", json={
        "available_from": "2027-03-01", "min_term_months": 6, "open_ended": False,
        "expected_version": version + 1}, headers=auth(owner)).status_code == 200
    assert _state(oid)[0] == 1


def test_pause_then_publish_opens_a_new_episode(client, owner):
    oid = _draft(client, owner)
    _post(client, owner, oid, "publish")
    _post(client, owner, oid, "pause")
    _post(client, owner, oid, "publish")
    assert _state(oid) == (2, [1, 2], [f"ListingBecamePublic:{oid}:1",
                                       f"ListingBecamePublic:{oid}:2"])


def test_silent_freshness_expiry_then_confirm_opens_a_new_episode(client, owner):
    """Stored `active`, 22 days unconfirmed, the sweep never ran: NOT public.
    Confirming it is a not-public → public transition."""
    oid = _draft(client, owner)
    _post(client, owner, oid, "publish")
    _age(oid, 22)
    with TestingSession() as db:
        assert db.get(ClassifiedOffer, oid).status == "active"
    assert client.get(f"/v1/classifieds/{oid}").status_code == 404
    _post(client, owner, oid, "confirm")
    assert _state(oid)[0] == 2
    # …and the silently expired listing republished (not confirmed) as well.
    _age(oid, 30)
    _post(client, owner, oid, "publish")
    assert _state(oid)[0] == 3


def test_sweep_stale_then_confirm_opens_a_new_episode(client, owner):
    oid = _draft(client, owner)
    _post(client, owner, oid, "publish")
    _age(oid, 25)
    with TestingSession() as db:
        freshness.sweep(db)
        db.commit()
        assert db.get(ClassifiedOffer, oid).status == "stale"
    _post(client, owner, oid, "confirm")
    assert _state(oid)[0] == 2


def test_space_archive_pauses_and_a_refused_publication_opens_nothing(client, owner):
    pid = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(client, owner, pid)
    room = client.post(f"/v1/properties/{pid}/spaces", json={"label": "A", "area_m2": 10},
                       headers=auth(owner)).json()["id"]
    oid = client.post(f"/v1/properties/{pid}/classifieds", json={**OFFER, "space_id": room},
                      headers=auth(owner)).json()["id"]
    _post(client, owner, oid, "publish")
    assert client.post(f"/v1/spaces/{room}/archive", headers=auth(owner)).status_code == 200
    with TestingSession() as db:
        assert db.get(ClassifiedOffer, oid).status == "paused"
    assert client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner)).status_code == 409
    assert _state(oid)[0] == 1  # a refused publication opens nothing


def test_the_event_payload_is_identifiers_and_time_only(client, owner):
    oid = _draft(client, owner)
    _post(client, owner, oid, "publish")
    with TestingSession() as db:
        ev = db.scalar(select(DomainEvent).where(
            DomainEvent.event_type == publicity.LISTING_BECAME_PUBLIC))
        work = db.get(ListingPublicGeneration, (oid, 1))
        assert work.event_id == ev.id and work.alert_status == "pending"
    assert set(ev.payload) == {"listing_id", "property_id", "public_generation", "became_public_at"}
    text = json.dumps(ev.payload)
    for secret in ("Prywatna", "511 222 333", "gen-owner@example.com", "Epizody", "240000"):
        assert secret not in text


def test_generation_event_and_work_item_are_atomic(client, owner, monkeypatch, caplog):
    """If the work item cannot be written, the publication, the generation and
    the event all roll back — an episode never half-exists."""
    oid = _draft(client, owner)
    original = publicity._open_episode

    def exploding(db, *args, **kwargs):
        original(db, *args, **kwargs)
        raise RuntimeError("work item write failed")

    monkeypatch.setattr(publicity, "_open_episode", exploding)
    # PR-001R F1: the request-id middleware turns the unhandled exception into
    # a generic 500 (CONV-001: the product test adopts the infra contract).
    assert_unhandled_500(client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner)),
                         caplog, RuntimeError)
    with TestingSession() as db:
        offer = db.get(ClassifiedOffer, oid)
        assert (offer.status, offer.public_generation, offer.public_since) == ("draft", 0, None)
    assert _state(oid) == (0, [], [])


def test_was_public_is_the_task012_rule():
    now = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
    fresh = now - timedelta(days=20, hours=23)
    expired = now - timedelta(days=21)
    assert publicity.was_public("active", fresh, now) is True
    assert publicity.was_public("active", expired, now) is False
    assert publicity.was_public("active", None, now) is False
    for status in ("draft", "paused", "stale", "archived"):
        assert publicity.was_public(status, now, now) is False
