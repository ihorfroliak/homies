"""Listing freshness, availability and owner quality guidance (TASK-012).

API and service level (SQLite). The races, the database clock and the
migration are proved on PostgreSQL in test_listing_freshness_pg.py.

"Old" is simulated by moving `last_confirmed_available_at` back in time — the
same thing the passing of days does to a real listing.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.modules.events.models import DomainEvent
from app.modules.properties import freshness, quality
from app.modules.properties.models import ClassifiedOffer
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership, verify_phone
from tests.test_media import _approved, _attach

PROPERTY = {"category": "APARTMENT", "city": "Poznań", "address": "ul. Świeża 4/2",
            "area_m2": 44, "rooms": 2, "capacity": 2}
OFFER = {"title": "Aktualne mieszkanie", "rent_amount": 250000, "min_term_months": 12,
         "contact_mode": "phone", "contact_phone": "+48 600 700 800"}
DAY = timedelta(days=1)


@pytest.fixture
def owner(client):
    return register_and_login(client, "fresh-owner@example.com", "host")


def _property(client, token, **extra):
    made = client.post("/v1/properties", json={**PROPERTY, **extra}, headers=auth(token))
    assert made.status_code == 201, made.text
    verify_ownership(client, token, made.json()["id"])
    return made.json()["id"]


def _draft(client, token, prop, **extra):
    made = client.post(f"/v1/properties/{prop}/classifieds", json={**OFFER, **extra},
                       headers=auth(token))
    assert made.status_code == 201, made.text
    return made.json()["id"]


def _published(client, token, **extra):
    offer = _draft(client, token, _property(client, token), **extra)
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(token)).status_code == 200
    return offer


def _age(offer, days):
    """Set the last confirmation `days` ago."""
    with TestingSession() as db:
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == offer).values(
            last_confirmed_available_at=datetime.now(timezone.utc) - timedelta(days=days)))
        db.commit()


def _row(offer):
    with TestingSession() as db:
        return db.get(ClassifiedOffer, offer)


def _events(offer, event_type):
    with TestingSession() as db:
        return db.scalars(select(DomainEvent).where(
            DomainEvent.correlation_id == offer, DomainEvent.event_type == event_type)).all()


def _board(client, **params):
    return {o["id"]: o for o in client.get("/v1/classifieds", params=params).json()["items"]}


def _sweep(as_of=None):
    with TestingSession() as db:
        result = freshness.sweep(db, as_of=as_of)
        db.commit()
    return result


# --- the policy, pinned at its boundaries ----------------------------------------------

T0 = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
TICK = timedelta(microseconds=1)


@pytest.mark.parametrize("age, expected", [
    (timedelta(0), "FRESH"),
    (timedelta(days=14) - TICK, "FRESH"),
    (timedelta(days=14), "RECONFIRM_DUE"),
    (timedelta(days=21) - TICK, "RECONFIRM_DUE"),
    (timedelta(days=21), "STALE"),
    (timedelta(days=400), "STALE"),
])
def test_the_policy_boundaries(age, expected):
    assert freshness.state(T0 - age, T0) == expected


def test_the_policy_is_one_place_and_derives_the_dates():
    assert freshness.CONFIRMATION_VALID_FOR == timedelta(days=14)
    assert freshness.AUTO_PAUSE_AFTER == timedelta(days=21)
    assert freshness.reconfirm_at(T0) == T0 + timedelta(days=14)
    assert freshness.stale_at(T0) == T0 + timedelta(days=21)
    assert freshness.state(None, T0) is None


# --- publication and confirmation ------------------------------------------------------


def test_publication_counts_as_confirmation(client, owner):
    before = datetime.now(timezone.utc)
    offer = _published(client, owner)
    row = _row(offer)
    assert row.last_confirmed_available_at is not None, "publication did not confirm"
    stamp = freshness._aware(row.last_confirmed_available_at)
    assert before - timedelta(seconds=5) <= stamp <= datetime.now(timezone.utc) + timedelta(seconds=5)
    assert freshness._aware(row.published_at) == stamp
    public = client.get(f"/v1/classifieds/{offer}").json()
    assert public["freshness"] == "FRESH" and public["confirmed_on"] == stamp.date().isoformat()


def test_a_draft_has_no_confirmation(client, owner):
    offer = _draft(client, owner, _property(client, owner))
    assert _row(offer).last_confirmed_available_at is None


def test_confirming_renews_the_listing_and_records_evidence(client, owner):
    offer = _published(client, owner)
    _age(offer, 16)
    assert client.get(f"/v1/classifieds/{offer}").json()["freshness"] == "RECONFIRM_DUE"
    version = _row(offer).version
    confirmed = client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["freshness"] == "FRESH"
    assert _row(offer).version == version  # confirmation is not a content edit
    assert len(_events(offer, freshness.LISTING_CONFIRMED)) == 1
    # A second confirmation is a new confirmation, not a duplicate of the first.
    assert client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner)).status_code == 200
    assert _row(offer).status == "active"


def test_only_someone_with_authority_can_confirm(client, owner):
    offer = _published(client, owner)
    stranger = register_and_login(client, "stranger-fresh@example.com", "host")
    assert client.post(f"/v1/classifieds/{offer}/confirm",
                       headers=auth(stranger)).status_code == 404
    tenant = register_and_login(client, "tenant-fresh@example.com", "guest")
    assert client.post(f"/v1/classifieds/{offer}/confirm",
                       headers=auth(tenant)).status_code == 403
    assert _events(offer, freshness.LISTING_CONFIRMED) == []


@pytest.mark.parametrize("status_", ["draft", "paused", "archived"])
def test_draft_paused_and_archived_are_not_confirmable(client, owner, status_):
    offer = _published(client, owner)
    with TestingSession() as db:
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == offer).values(
            status=status_))
        db.commit()
    response = client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))
    assert response.status_code == 409, response.text
    assert _row(offer).status == status_


# --- going stale -----------------------------------------------------------------------------


def test_a_stale_listing_disappears_from_every_public_path_before_any_sweep(client, owner):
    """The rule is evaluated on read: at 21 days the listing is off the board
    whether or not the sweep has run — list, detail, contact, messages,
    viewings and photos alike."""
    offer = _published(client, owner, contact_mode="phone")
    prop = _row(offer).property_id
    asset = _approved(client, owner, prop)
    assert _attach(client, owner, offer, asset, cover=True).status_code in (200, 201)
    tenant = register_and_login(client, "tenant-stale@example.com", "guest")
    verify_phone(client, tenant, "+48511222333")
    assert client.get(f"/v1/media/{asset}").status_code == 200
    _age(offer, 21)
    assert _row(offer).status == "active"  # nothing has transitioned yet
    assert offer not in _board(client)
    assert client.get(f"/v1/classifieds/{offer}").status_code == 404
    assert client.post(f"/v1/classifieds/{offer}/contact", headers=auth(tenant)).status_code == 404
    assert client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "Czy aktualne?"},
                       headers=auth(tenant)).status_code == 404
    assert client.get(f"/v1/classifieds/{offer}/viewing-slots",
                      headers=auth(tenant)).status_code == 404
    assert client.get(f"/v1/media/{asset}").status_code == 404


def test_reconfirm_due_is_still_public(client, owner):
    offer = _published(client, owner)
    _age(offer, 20)
    assert offer in _board(client)
    assert client.get(f"/v1/classifieds/{offer}").json()["freshness"] == "RECONFIRM_DUE"


def test_the_sweep_records_stale_once_and_is_idempotent(client, owner):
    fresh = _published(client, owner)
    due = _published(client, owner, title="Do potwierdzenia")
    stale = _published(client, owner, title="Nieaktualne")
    _age(due, 15)
    _age(stale, 30)
    first = _sweep()
    assert first.staled == [stale] and first.reminded == [due]
    assert (_row(fresh).status, _row(due).status, _row(stale).status) == (
        "active", "active", "stale")
    again = _sweep()
    assert again.staled == [] and again.reminded == []
    assert len(_events(stale, freshness.LISTING_AUTO_PAUSED_STALE)) == 1
    assert len(_events(due, freshness.LISTING_RECONFIRMATION_DUE)) == 1


def test_the_sweep_never_touches_paused_draft_or_archived(client, owner):
    offers = {}
    for status_ in ("paused", "archived", "draft"):
        offer = _published(client, owner, title=f"Listing {status_}")
        _age(offer, 60)
        with TestingSession() as db:
            db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == offer).values(
                status=status_))
            db.commit()
        offers[status_] = offer
    assert _sweep().staled == []
    assert {s: _row(o).status for s, o in offers.items()} == {
        "paused": "paused", "archived": "archived", "draft": "draft"}


def test_event_payloads_carry_no_location_or_contact(client, owner):
    offer = _published(client, owner)
    _age(offer, 30)
    _sweep()
    (event,) = _events(offer, freshness.LISTING_AUTO_PAUSED_STALE)
    assert set(event.payload) == {"listing_id", "property_id", "last_confirmed_available_at",
                                  "confirmation_valid_days", "auto_pause_after_days"}


# --- reactivation ---------------------------------------------------------------------------


def test_confirming_a_stale_listing_brings_it_back(client, owner):
    offer = _published(client, owner)
    _age(offer, 30)
    _sweep()
    owned = {o["id"]: o for o in client.get("/v1/me/classifieds", headers=auth(owner)).json()}
    assert owned[offer]["status"] == "stale"
    assert owned[offer]["freshness_detail"]["state"] == "STALE"
    back = client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))
    assert back.status_code == 200, back.text
    assert back.json()["status"] == "active" and back.json()["freshness"] == "FRESH"
    assert offer in _board(client)
    assert len(_events(offer, freshness.LISTING_REACTIVATED)) == 1


def test_a_stale_listing_can_also_be_republished(client, owner):
    offer = _published(client, owner)
    _age(offer, 30)
    _sweep()
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    assert _row(offer).status == "active"
    assert freshness.state(_row(offer).last_confirmed_available_at,
                           datetime.now(timezone.utc)) == "FRESH"


def test_reactivation_runs_every_publication_check(client, owner):
    """A stale aparthotel unit (which can only exist through data drift) and a
    stale listing whose space was archived both stay down."""
    offer = _published(client, owner)
    _age(offer, 30)
    _sweep()
    space = _row(offer).space_id
    assert client.post(f"/v1/spaces/{space}/archive", headers=auth(owner)).status_code == 200
    refused = client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))
    assert refused.status_code == 409 and "archived" in refused.text
    assert _row(offer).status == "stale"


def test_an_archived_listing_is_never_paused_back_to_life(client, owner):
    offer = _published(client, owner)
    with TestingSession() as db:
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == offer).values(
            status="archived"))
        db.commit()
    assert client.post(f"/v1/classifieds/{offer}/pause", headers=auth(owner)).status_code == 409
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 409
    assert _row(offer).status == "archived"


# --- availability ---------------------------------------------------------------------------


def test_availability_is_editable_under_version_control(client, owner):
    offer = _published(client, owner)
    version = _row(offer).version
    body = {"expected_version": version, "available_from": "2027-03-01",
            "min_term_months": 6}
    changed = client.put(f"/v1/classifieds/{offer}/availability", json=body, headers=auth(owner))
    assert changed.status_code == 200, changed.text
    assert changed.json()["available_from"] == "2027-03-01"
    assert changed.json()["move_in"] == "FROM_DATE"
    assert changed.json()["version"] == version + 1
    # The same edit against the old version loses.
    assert client.put(f"/v1/classifieds/{offer}/availability", json=body,
                      headers=auth(owner)).status_code == 409


@pytest.mark.parametrize("body", [
    {"min_term_months": 0},
    {"open_ended": True, "min_term_months": 3},
    {"min_term_months": None},
    {"available_from": "not-a-date", "min_term_months": 3},
])
def test_availability_is_validated(client, owner, body):
    offer = _published(client, owner)
    response = client.put(f"/v1/classifieds/{offer}/availability",
                          json={"expected_version": _row(offer).version, **body},
                          headers=auth(owner))
    assert response.status_code == 422


def test_move_in_is_derived_now_or_later_or_unknown(client, owner):
    past = _published(client, owner, available_from=(date.today() - DAY * 3).isoformat())
    later = _published(client, owner, available_from=(date.today() + DAY * 40).isoformat())
    unknown = _published(client, owner)
    board = _board(client)
    assert (board[past]["move_in"], board[later]["move_in"], board[unknown]["move_in"]) == (
        "NOW", "FROM_DATE", "UNKNOWN")
    by = (date.today() + DAY * 10).isoformat()
    assert set(_board(client, available_by=by)) == {past}


def test_availability_edit_is_not_a_confirmation(client, owner):
    offer = _published(client, owner)
    _age(offer, 16)
    client.put(f"/v1/classifieds/{offer}/availability",
               json={"expected_version": _row(offer).version, "open_ended": True},
               headers=auth(owner))
    assert client.get(f"/v1/classifieds/{offer}").json()["freshness"] == "RECONFIRM_DUE"


# --- owner guidance -------------------------------------------------------------------------


def test_owner_view_separates_required_from_recommended(client, owner):
    offer = _published(client, owner)
    (mine,) = [o for o in client.get("/v1/me/classifieds", headers=auth(owner)).json()
               if o["id"] == offer]
    q = mine["quality"]
    assert q["missing_required"] == []
    assert set(q["recommended_improvements"]) == {
        "add_photos", "add_description", "choose_place_from_list", "set_move_in_date",
        "state_utilities", "add_amenities"}
    passed = sum(c["passed"] for c in q["checks"])
    assert q["completeness_percent"] == 100 * passed // len(q["checks"])
    assert mine["freshness_detail"]["state"] == "FRESH"
    assert mine["freshness_detail"]["confirmation_valid_days"] == 14


def test_an_unverified_draft_is_told_what_blocks_publication(client, owner):
    made = client.post("/v1/properties", json=PROPERTY, headers=auth(owner))
    offer = _draft(client, owner, made.json()["id"])
    (mine,) = [o for o in client.get("/v1/me/classifieds", headers=auth(owner)).json()
               if o["id"] == offer]
    assert mine["quality"]["missing_required"] == ["verify_property_authority"]
    assert "confirm_still_current" not in {c["code"] for c in mine["quality"]["checks"]}


def test_the_assessment_is_deterministic(client, owner):
    offer = _published(client, owner)
    with TestingSession() as db:
        row = db.get(ClassifiedOffer, offer)
        user_id = row.owner_id
        runs = {tuple((c.code, c.passed) for c in quality.assess(
            db, user_id, row, row.listed_property, T0).checks) for _ in range(5)}
    assert len(runs) == 1


def test_the_public_never_sees_quality_or_owner_detail(client, owner):
    offer = _published(client, owner)
    public = client.get(f"/v1/classifieds/{offer}").json()
    assert "quality" not in public and "freshness_detail" not in public
    assert "published_at" not in public and "last_confirmed_available_at" not in public


def test_other_users_do_not_see_my_listings(client, owner):
    _published(client, owner)
    other = register_and_login(client, "other-owner@example.com", "host")
    assert client.get("/v1/me/classifieds", headers=auth(other)).json() == []


def test_a_revoked_right_cannot_bring_a_stale_listing_back(client, owner):
    from app.modules.properties.models import PropertyAuthority
    from tests.conftest import admin_login

    offer = _published(client, owner)
    _age(offer, 30)
    _sweep()
    with TestingSession() as db:
        aid = db.scalar(select(PropertyAuthority.id).where(
            PropertyAuthority.property_id == _row(offer).property_id))
    admin = admin_login(client)
    assert client.post(f"/v1/admin/property-authorities/{aid}/revoke",
                       headers=auth(admin)).status_code == 200
    refused = client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))
    assert refused.status_code in (403, 404), refused.text
    assert _row(offer).status == "stale"
    assert _events(offer, freshness.LISTING_REACTIVATED) == []
