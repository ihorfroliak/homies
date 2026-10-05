"""Viewings (Domain Schema v1 §57–§60, §113).

The failures a scheduler usually has, and these tests look for:

* a 10:00 viewing that turns into 11:00 half the year (time zones done by offset);
* a tenant booking a time the owner never offered;
* two people confirmed into the last place of the same slot;
* a stranger confirming, cancelling or reading someone else's viewing.
"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.modules.engagement.models import Viewing, ViewingWindow
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership

WARSAW = ZoneInfo("Europe/Warsaw")
SUMMER = date(2027, 7, 15)   # CEST, UTC+2
WINTER = date(2027, 1, 14)   # CET,  UTC+1

PROPERTY = {"property_type": "apartment", "city": "Opole", "municipality": "Opole",
            "address": "ul. Pokazowa 1", "area_m2": 45, "rooms": 2, "capacity": 3}
OFFER = {"title": "Oglądanie", "rent_amount": 200000, "min_term_months": 12,
         "contact_mode": "message"}


def _utc(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), WARSAW).astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@pytest.fixture
def owner(client):
    return register_and_login(client, "viewing-owner@example.com", "host")


@pytest.fixture
def tenant(client):
    return register_and_login(client, "viewing-tenant@example.com", "guest")


@pytest.fixture
def listing(client, owner):
    prop = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()
    verify_ownership(client, owner, prop["id"])
    offer = client.post(f"/v1/properties/{prop['id']}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    return offer


def _settings(client, token, listing, **overrides):
    body = {"booking_mode": "REQUEST_APPROVAL", "duration_minutes": 30,
            "minimum_notice_minutes": 0, **overrides}
    resp = client.put(f"/v1/classifieds/{listing}/viewing-settings", json=body,
                      headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp


def _one_off(client, token, listing, day, start="10:00", end="12:00"):
    resp = client.post(f"/v1/classifieds/{listing}/viewing-windows",
                       json={"window_type": "ONE_OFF", "local_date": day.isoformat(),
                             "local_start_time": start, "local_end_time": end},
                       headers=auth(token))
    assert resp.status_code == 201, resp.text


def _slots(client, token, listing, day, days=1):
    resp = client.get(f"/v1/classifieds/{listing}/viewing-slots",
                      params={"start": day.isoformat(), "days": days}, headers=auth(token))
    assert resp.status_code == 200, resp.text
    return [datetime.fromisoformat(s.replace("Z", "+00:00")) for s in resp.json()["slots"]]


def _request(client, token, listing, at: datetime, **extra):
    return client.post(f"/v1/classifieds/{listing}/viewings",
                       json={"starts_at": _iso(at), **extra}, headers=auth(token))


@pytest.fixture
def summer_window(client, owner, listing):
    _settings(client, owner, listing)
    _one_off(client, owner, listing, SUMMER)
    return listing


# --- slots are the provider's local time --------------------------------------


def test_a_window_becomes_slots_in_utc(client, tenant, summer_window):
    assert _slots(client, tenant, summer_window, SUMMER) == [
        _utc(SUMMER, 10), _utc(SUMMER, 10, 30), _utc(SUMMER, 11), _utc(SUMMER, 11, 30)]


def test_ten_oclock_stays_ten_oclock_across_summer_time(client, owner, tenant, listing):
    """In July 10:00 Warsaw is 08:00Z, in January 09:00Z. A zone stored as an
    offset would be an hour wrong for half the year."""
    _settings(client, owner, listing)
    _one_off(client, owner, listing, SUMMER, "10:00", "10:30")
    _one_off(client, owner, listing, WINTER, "10:00", "10:30")

    assert _slots(client, tenant, listing, SUMMER)[0].hour == 8
    assert _slots(client, tenant, listing, WINTER)[0].hour == 9


def test_weekly_windows_repeat_on_their_weekday_within_their_dates(client, owner, tenant,
                                                                   listing):
    _settings(client, owner, listing)
    monday = date(2027, 3, 1)
    assert monday.weekday() == 0
    client.post(f"/v1/classifieds/{listing}/viewing-windows",
                json={"window_type": "WEEKLY", "weekday": 0, "local_start_time": "18:00",
                      "local_end_time": "18:30", "valid_until": "2027-03-10"},
                headers=auth(owner))
    found = _slots(client, tenant, listing, monday, days=21)
    assert [s.astimezone(WARSAW).date() for s in found] == [date(2027, 3, 1), date(2027, 3, 8)]


def test_a_blackout_removes_what_it_covers(client, owner, tenant, summer_window):
    client.post(f"/v1/classifieds/{summer_window}/viewing-blackouts",
                json={"starts_at": _iso(_utc(SUMMER, 10, 15)),
                      "ends_at": _iso(_utc(SUMMER, 11)), "reason": "plumber"},
                headers=auth(owner))
    assert _slots(client, tenant, summer_window, SUMMER) == [_utc(SUMMER, 11),
                                                             _utc(SUMMER, 11, 30)]


def test_minimum_notice_hides_slots_too_soon(client, owner, tenant, listing):
    _settings(client, owner, listing, minimum_notice_minutes=60 * 24 * 14)
    near = (datetime.now(WARSAW) + timedelta(days=3)).date()
    _one_off(client, owner, listing, near)
    assert _slots(client, tenant, listing, near) == []


def test_disabled_settings_offer_nothing(client, owner, tenant, listing):
    _settings(client, owner, listing, enabled=False)
    _one_off(client, owner, listing, SUMMER)
    assert _slots(client, tenant, listing, SUMMER) == []


# --- requesting ---------------------------------------------------------------


def test_only_an_offered_slot_can_be_requested(client, tenant, summer_window):
    """The time at someone's door is theirs to set."""
    resp = _request(client, tenant, summer_window, _utc(SUMMER, 10, 10))
    assert resp.status_code == 409
    assert resp.json()["detail"].startswith("SLOT_NOT_OFFERED: ")
    resp = _request(client, tenant, summer_window, _utc(SUMMER, 22))
    assert resp.status_code == 409
    assert resp.json()["detail"].startswith("SLOT_NOT_OFFERED: ")


def test_approval_mode_waits_for_the_provider(client, owner, tenant, summer_window):
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    assert viewing["status"] == "REQUESTED"
    confirmed = client.post(f"/v1/viewings/{viewing['id']}/confirm", headers=auth(owner))
    assert confirmed.json()["status"] == "CONFIRMED"


def test_a_confirmed_slot_is_no_longer_offered(client, owner, tenant, summer_window):
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    client.post(f"/v1/viewings/{viewing['id']}/confirm", headers=auth(owner))
    assert _utc(SUMMER, 10) not in _slots(client, tenant, summer_window, SUMMER)


def test_instant_booking_confirms_at_once(client, owner, tenant, listing):
    _settings(client, owner, listing, booking_mode="INSTANT_BOOKING")
    _one_off(client, owner, listing, SUMMER)
    viewing = _request(client, tenant, listing, _utc(SUMMER, 11)).json()
    assert viewing["status"] == "CONFIRMED"


def test_the_last_place_cannot_be_confirmed_twice(client, owner, tenant, summer_window):
    other = register_and_login(client, "second-tenant@example.com", "guest")
    first = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    second = _request(client, other, summer_window, _utc(SUMMER, 10)).json()

    assert client.post(f"/v1/viewings/{first['id']}/confirm",
                       headers=auth(owner)).status_code == 200
    full = client.post(f"/v1/viewings/{second['id']}/confirm", headers=auth(owner))
    assert full.status_code == 409, full.text
    assert full.json()["detail"].startswith("SLOT_FULL: ")
    assert client.get("/v1/me/viewings", headers=auth(other)).json()[0]["status"] == "REQUESTED"


def test_capacity_above_one_admits_that_many(client, owner, tenant, listing):
    _settings(client, owner, listing, max_concurrent_bookings=2,
              booking_mode="INSTANT_BOOKING")
    _one_off(client, owner, listing, SUMMER, "10:00", "10:30")
    other = register_and_login(client, "group-tenant@example.com", "guest")
    assert _request(client, tenant, listing, _utc(SUMMER, 10)).status_code == 201
    assert _utc(SUMMER, 10) in _slots(client, tenant, listing, SUMMER)
    assert _request(client, other, listing, _utc(SUMMER, 10)).status_code == 201
    assert _slots(client, tenant, listing, SUMMER) == []


def test_buffers_keep_the_next_slot_free(client, owner, tenant, listing):
    _settings(client, owner, listing, buffer_after_minutes=30,
              booking_mode="INSTANT_BOOKING")
    _one_off(client, owner, listing, SUMMER)
    _request(client, tenant, listing, _utc(SUMMER, 10))
    assert _utc(SUMMER, 10, 30) not in _slots(client, tenant, listing, SUMMER)
    assert _utc(SUMMER, 11) in _slots(client, tenant, listing, SUMMER)


def test_one_booked_viewing_per_tenant_per_flat(client, tenant, summer_window):
    assert _request(client, tenant, summer_window, _utc(SUMMER, 10)).status_code == 201
    again = _request(client, tenant, summer_window, _utc(SUMMER, 11))
    assert again.status_code == 409
    assert again.json()["detail"].startswith("VIEWING_ALREADY_BOOKED: ")


def test_you_cannot_book_a_viewing_of_your_own_flat(client, owner, summer_window):
    own = _request(client, owner, summer_window, _utc(SUMMER, 10))
    assert own.status_code == 409
    assert own.json()["detail"].startswith("OWN_LISTING: ")


# --- who may do what ----------------------------------------------------------


def test_either_side_can_cancel(client, owner, tenant, summer_window):
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    assert client.post(f"/v1/viewings/{viewing['id']}/cancel",
                       headers=auth(tenant)).json()["status"] == "CANCELLED"
    other = _request(client, tenant, summer_window, _utc(SUMMER, 11)).json()
    assert client.post(f"/v1/viewings/{other['id']}/cancel",
                       headers=auth(owner)).json()["status"] == "CANCELLED"


def test_the_tenant_cannot_confirm_their_own_request(client, tenant, summer_window):
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    assert client.post(f"/v1/viewings/{viewing['id']}/confirm",
                       headers=auth(tenant)).status_code == 404


def test_a_stranger_can_touch_nothing(client, tenant, summer_window):
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    stranger = register_and_login(client, "viewing-stranger@example.com", "guest")
    for action in ("confirm", "decline", "cancel"):
        assert client.post(f"/v1/viewings/{viewing['id']}/{action}",
                           headers=auth(stranger)).status_code == 404
    assert client.get(f"/v1/classifieds/{summer_window}/viewings",
                      headers=auth(stranger)).status_code == 404


def test_a_mandate_with_viewings_scope_manages_them(client, owner, tenant, summer_window):
    helper = register_and_login(client, "viewing-helper@example.com", "host")
    client.post("/v1/me/mandates", json={"representative_email": "viewing-helper@example.com",
                                         "scopes": ["MANAGE_VIEWINGS"]}, headers=auth(owner))
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    assert client.post(f"/v1/viewings/{viewing['id']}/confirm",
                       headers=auth(helper)).status_code == 200


def test_the_tenant_view_hides_the_providers_side(client, tenant, summer_window):
    _request(client, tenant, summer_window, _utc(SUMMER, 10), note="Przyjdę z psem")
    mine = client.get("/v1/me/viewings", headers=auth(tenant)).json()
    assert "requester_user_id" not in mine[0]


def test_an_outcome_waits_for_the_viewing_to_happen(client, owner, tenant, summer_window):
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    client.post(f"/v1/viewings/{viewing['id']}/confirm", headers=auth(owner))
    resp = client.post(f"/v1/viewings/{viewing['id']}/outcome", json={"outcome": "COMPLETED"},
                       headers=auth(owner))
    assert resp.status_code == 409
    assert resp.json()["detail"].startswith("VIEWING_NOT_STARTED: ")


# --- validation ---------------------------------------------------------------


@pytest.mark.parametrize("zone", ["UTC+1", "Warsaw", "Mars/Olympus"])
def test_a_timezone_must_be_an_iana_zone(client, owner, listing, zone):
    resp = client.put(f"/v1/classifieds/{listing}/viewing-settings", json={"timezone": zone},
                      headers=auth(owner))
    assert resp.status_code == 422


@pytest.mark.parametrize("body", [
    {"window_type": "WEEKLY", "local_start_time": "10:00", "local_end_time": "11:00"},
    {"window_type": "ONE_OFF", "weekday": 1, "local_start_time": "10:00",
     "local_end_time": "11:00"},
    {"window_type": "WEEKLY", "weekday": 1, "local_start_time": "11:00",
     "local_end_time": "10:00"},
    {"window_type": "WEEKLY", "weekday": 7, "local_start_time": "10:00",
     "local_end_time": "11:00"},
])
def test_malformed_windows_are_refused(client, owner, listing, body):
    assert client.post(f"/v1/classifieds/{listing}/viewing-windows", json=body,
                       headers=auth(owner)).status_code == 422


def test_the_database_refuses_a_viewing_that_ends_before_it_starts(client, tenant,
                                                                   summer_window):
    tenant_id = client.get("/v1/me", headers=auth(tenant)).json()["id"]
    with TestingSession() as db:
        now = datetime.now(timezone.utc)
        db.add(Viewing(listing_id=summer_window, requester_user_id=tenant_id,
                       starts_at=now, ends_at=now - timedelta(minutes=1)))
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation
            db.commit()


def test_the_database_refuses_a_weekly_window_with_a_date(client, summer_window):
    with TestingSession() as db:
        db.add(ViewingWindow(listing_id=summer_window, window_type="WEEKLY", weekday=1,
                             local_date=SUMMER, local_start_time=time(10),
                             local_end_time=time(11)))
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation
            db.commit()


def test_viewing_writes_are_throttled(client):
    from app.core import ratelimit as rl

    assert rl.resolve_policy("POST", "/v1/viewings/x/confirm") is rl.PROPERTY_WRITE
    assert rl.resolve_policy("POST", "/v1/classifieds/x/viewings") is rl.PROPERTY_WRITE


# --- stable refusal codes (FE-003 BP-1) ------------------------------------------


def _code(resp) -> str:
    return resp.json()["detail"].split(":", 1)[0]


def _count_viewings(listing) -> int:
    with TestingSession() as db:
        return db.query(Viewing).filter(Viewing.listing_id == listing).count()


def test_a_listing_without_viewings_says_so(client, owner, tenant, listing):
    """No settings, or settings switched off: the listing takes no viewings at
    all — a different answer from "that time is not offered"."""
    at = _utc(SUMMER, 10)
    resp = _request(client, tenant, listing, at)
    assert (resp.status_code, _code(resp)) == (409, "VIEWINGS_NOT_OFFERED")

    _settings(client, owner, listing, enabled=False)
    _one_off(client, owner, listing, SUMMER)
    resp = _request(client, tenant, listing, at)
    assert (resp.status_code, _code(resp)) == (409, "VIEWINGS_NOT_OFFERED")
    assert _count_viewings(listing) == 0


def test_an_action_on_a_finished_viewing_is_a_state_conflict(client, owner, tenant,
                                                              summer_window):
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    outcome = client.post(f"/v1/viewings/{viewing['id']}/outcome",
                          json={"outcome": "COMPLETED"}, headers=auth(owner))
    assert (outcome.status_code, _code(outcome)) == (409, "VIEWING_STATE_CONFLICT")

    assert client.post(f"/v1/viewings/{viewing['id']}/cancel",
                       headers=auth(tenant)).status_code == 200
    for actor, action in ((tenant, "cancel"), (owner, "confirm"), (owner, "decline")):
        resp = client.post(f"/v1/viewings/{viewing['id']}/{action}", headers=auth(actor))
        assert (resp.status_code, _code(resp)) == (409, "VIEWING_STATE_CONFLICT"), action
    with TestingSession() as db:
        assert db.get(Viewing, viewing["id"]).status == "CANCELLED"


def test_a_request_whose_time_has_passed_cannot_be_confirmed(client, owner, tenant,
                                                             summer_window):
    viewing = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    with TestingSession() as db:
        row = db.get(Viewing, viewing["id"])
        row.starts_at, row.ends_at = past, past + timedelta(minutes=30)
        db.commit()
    resp = client.post(f"/v1/viewings/{viewing['id']}/confirm", headers=auth(owner))
    assert (resp.status_code, _code(resp)) == (409, "VIEWING_TIME_PASSED")
    with TestingSession() as db:
        assert db.get(Viewing, viewing["id"]).status == "REQUESTED"


def test_a_transition_on_a_changed_viewing_is_viewing_changed(client, tenant, summer_window):
    """The version compare-and-set behind every transition: a change committed
    after the viewing was read is never overwritten."""
    from fastapi import HTTPException

    from app.modules.engagement import viewings

    viewing_id = _request(client, tenant, summer_window, _utc(SUMMER, 10)).json()["id"]
    stale = TestingSession()
    try:
        row = stale.get(Viewing, viewing_id)
        with TestingSession() as other:
            other.get(Viewing, viewing_id).version += 1
            other.commit()
        with pytest.raises(HTTPException) as refused:
            viewings._transition(stale, row, ("REQUESTED",), status="CANCELLED")
        assert refused.value.status_code == 409
        assert str(refused.value.detail).startswith("VIEWING_CHANGED: ")
    finally:
        stale.close()
    with TestingSession() as db:
        assert db.get(Viewing, viewing_id).status == "REQUESTED"


# --- BP-2: the typed slot response ---------------------------------------------


def _slot_body(client, token, listing, day, days=1):
    resp = client.get(f"/v1/classifieds/{listing}/viewing-slots",
                      params={"start": day.isoformat(), "days": days}, headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_the_slot_response_carries_the_settings_timezone(client, owner, tenant, listing):
    """The zone the provider's windows are written in — not a default. A
    non-Warsaw zone makes a hard-coded `Europe/Warsaw` fail."""
    _settings(client, owner, listing, timezone="Europe/Lisbon", duration_minutes=45)
    _one_off(client, owner, listing, SUMMER, "10:00", "11:30")
    body = _slot_body(client, tenant, listing, SUMMER)
    assert set(body) == {"slots", "duration_minutes", "timezone"}
    assert body["timezone"] == "Europe/Lisbon"
    assert body["duration_minutes"] == 45
    lisbon = ZoneInfo("Europe/Lisbon")
    assert [datetime.fromisoformat(s.replace("Z", "+00:00")) for s in body["slots"]] == [
        datetime.combine(SUMMER, time(10), lisbon).astimezone(timezone.utc),
        datetime.combine(SUMMER, time(10, 45), lisbon).astimezone(timezone.utc)]


def test_a_returned_slot_string_is_requestable_as_is(client, tenant, summer_window):
    body = _slot_body(client, tenant, summer_window, SUMMER)
    assert body["timezone"] == "Europe/Warsaw" and body["duration_minutes"] == 30
    resp = client.post(f"/v1/classifieds/{summer_window}/viewings",
                       json={"starts_at": body["slots"][0]}, headers=auth(tenant))
    assert resp.status_code == 201, resp.text


def test_disabled_settings_still_name_their_timezone(client, owner, tenant, listing):
    _settings(client, owner, listing, enabled=False, timezone="Europe/Lisbon")
    _one_off(client, owner, listing, SUMMER)
    assert _slot_body(client, tenant, listing, SUMMER) == {
        "slots": [], "duration_minutes": 30, "timezone": "Europe/Lisbon"}


def test_no_settings_means_no_authoritative_timezone(client, tenant, listing):
    assert _slot_body(client, tenant, listing, SUMMER) == {
        "slots": [], "duration_minutes": None, "timezone": None}


def test_the_slot_response_stays_signed_in_only(client, listing):
    assert client.get(f"/v1/classifieds/{listing}/viewing-slots").status_code == 401


def test_the_slot_response_is_a_named_schema_in_openapi(client):
    from app.main import app

    spec = app.openapi()
    content = spec["paths"]["/v1/classifieds/{listing_id}/viewing-slots"]["get"][
        "responses"]["200"]["content"]["application/json"]["schema"]
    assert content == {"$ref": "#/components/schemas/ViewingSlotsOut"}
    props = spec["components"]["schemas"]["ViewingSlotsOut"]["properties"]
    assert set(props) == {"slots", "duration_minutes", "timezone"}
    assert props["slots"]["items"] == {"type": "string", "format": "date-time"}
    assert {"type": "null"} in props["timezone"]["anyOf"]
    assert {"type": "null"} in props["duration_minutes"]["anyOf"]


# --- BP-7: no cancellation from the start on ------------------------------------


def _audits(viewing_id) -> int:
    from app.core.audit import AuditLog

    with TestingSession() as db:
        return db.query(AuditLog).filter(AuditLog.entity_id == viewing_id,
                                         AuditLog.action == "viewing.cancelled").count()


def _cancel_facts(viewing_id) -> int:
    from app.modules.events.models import DomainEvent

    with TestingSession() as db:
        return db.query(DomainEvent).filter(DomainEvent.event_type == "ViewingCancelled",
                                            DomainEvent.correlation_id == viewing_id).count()


def _cancel_fact_payload(viewing_id) -> dict:
    from app.modules.events.models import DomainEvent

    with TestingSession() as db:
        return db.query(DomainEvent).filter(DomainEvent.event_type == "ViewingCancelled",
                                            DomainEvent.correlation_id == viewing_id
                                            ).one().payload


@pytest.mark.parametrize("state", ["REQUESTED", "CONFIRMED"])
@pytest.mark.parametrize("actor", ["requester", "provider"])
@pytest.mark.parametrize("moment", ["before", "exactly", "after"])
def test_either_side_cancels_only_before_the_start(client, owner, tenant, summer_window,
                                                    monkeypatch, state, actor, moment):
    from app.modules.properties import freshness

    starts = _utc(SUMMER, 10)
    viewing = _request(client, tenant, summer_window, starts).json()
    if state == "CONFIRMED":
        assert client.post(f"/v1/viewings/{viewing['id']}/confirm",
                           headers=auth(owner)).status_code == 200
    now = {"before": starts - timedelta(seconds=1), "exactly": starts,
           "after": starts + timedelta(hours=2)}[moment]
    monkeypatch.setattr(freshness, "db_now", lambda db: now)

    resp = client.post(f"/v1/viewings/{viewing['id']}/cancel",
                       headers=auth(tenant if actor == "requester" else owner))
    with TestingSession() as db:
        row = db.get(Viewing, viewing["id"])
        stored, cancelled_at = row.status, row.cancelled_at
    if moment == "before":
        assert resp.status_code == 200, resp.text
        assert stored == "CANCELLED"
        assert (_audits(viewing["id"]), _cancel_facts(viewing["id"])) == (1, 1)
        # One decision instant: the database clock's, on the row and the fact.
        assert cancelled_at.replace(tzinfo=timezone.utc) == now
        fact = _cancel_fact_payload(viewing["id"])
        assert fact["cancelled_at"] == freshness.canonical_instant(now)
    else:
        assert resp.status_code == 409
        assert resp.json()["detail"].startswith("VIEWING_STARTED: ")
        assert stored == state, "a refused cancel changes nothing"
        assert (_audits(viewing["id"]), _cancel_facts(viewing["id"])) == (0, 0)


def test_the_cancel_decision_is_the_database_clock(client, tenant, summer_window,
                                                   monkeypatch):
    """04a §20: the database clock decides, not the process clock — a far-off
    app clock neither blocks a timely cancel nor allows a late one."""
    from app.modules.engagement import viewings
    from app.modules.properties import freshness

    starts = _utc(SUMMER, 10)
    early = _request(client, tenant, summer_window, starts).json()
    monkeypatch.setattr(viewings, "_now", lambda: starts + timedelta(days=30))
    monkeypatch.setattr(freshness, "db_now", lambda db: starts - timedelta(minutes=5))
    assert client.post(f"/v1/viewings/{early['id']}/cancel",
                       headers=auth(tenant)).status_code == 200

    monkeypatch.undo()
    late = _request(client, tenant, summer_window, _utc(SUMMER, 11)).json()
    monkeypatch.setattr(viewings, "_now", lambda: starts - timedelta(days=30))
    monkeypatch.setattr(freshness, "db_now", lambda db: _utc(SUMMER, 11))
    resp = client.post(f"/v1/viewings/{late['id']}/cancel", headers=auth(tenant))
    assert (resp.status_code, resp.json()["detail"].split(":")[0]) == (409, "VIEWING_STARTED")


def test_a_finished_viewing_stays_a_state_conflict_after_its_start(client, owner, tenant,
                                                                   summer_window,
                                                                   monkeypatch):
    """BP-7 does not turn every late error into VIEWING_STARTED."""
    from app.modules.properties import freshness

    starts = _utc(SUMMER, 10)
    declined = _request(client, tenant, summer_window, starts).json()
    client.post(f"/v1/viewings/{declined['id']}/decline", headers=auth(owner))
    cancelled = _request(client, tenant, summer_window, _utc(SUMMER, 11)).json()
    client.post(f"/v1/viewings/{cancelled['id']}/cancel", headers=auth(tenant))
    monkeypatch.setattr(freshness, "db_now", lambda db: starts + timedelta(days=1))
    for vid in (declined["id"], cancelled["id"]):
        resp = client.post(f"/v1/viewings/{vid}/cancel", headers=auth(tenant))
        assert resp.status_code == 409
        assert resp.json()["detail"].startswith("VIEWING_STATE_CONFLICT: ")


def test_a_stranger_still_sees_nothing_after_the_start(client, tenant, summer_window,
                                                       monkeypatch):
    from app.modules.properties import freshness

    starts = _utc(SUMMER, 10)
    viewing = _request(client, tenant, summer_window, starts).json()
    stranger = register_and_login(client, "late-stranger@example.com", "guest")
    monkeypatch.setattr(freshness, "db_now", lambda db: starts + timedelta(hours=1))
    assert client.post(f"/v1/viewings/{viewing['id']}/cancel",
                       headers=auth(stranger)).status_code == 404


def test_a_passed_request_is_left_as_it_is(client, tenant, summer_window, monkeypatch):
    """No expiry: BP-7 refuses a late cancel and nothing else (DEBT-1)."""
    from app.modules.properties import freshness

    starts = _utc(SUMMER, 10)
    viewing = _request(client, tenant, summer_window, starts).json()
    monkeypatch.setattr(freshness, "db_now", lambda db: starts + timedelta(days=3))
    client.post(f"/v1/viewings/{viewing['id']}/cancel", headers=auth(tenant))
    mine = client.get("/v1/me/viewings", headers=auth(tenant)).json()
    assert [(v["id"], v["status"]) for v in mine] == [(viewing["id"], "REQUESTED")]
