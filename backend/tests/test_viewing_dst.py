"""Viewing slots across daylight-saving changes (TASK-001 F-08, TASK-002 §44–§45).

Canonical decision: a Phase-1 slot's local start time names exactly one
instant. Nonexistent (spring-forward) and ambiguous (fall-back) wall times are
not offered, and every offered slot lies inside the provider's local window.

Europe/Warsaw, 2027: summer time starts Sunday 28 March at 02:00 → 03:00 and
ends Sunday 31 October at 03:00 → 02:00.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.modules.engagement import viewings
from tests.conftest import auth, register_and_login, verify_ownership

WARSAW = ZoneInfo("Europe/Warsaw")
PROPERTY = {"property_type": "apartment", "city": "Warszawa", "municipality": "Warszawa",
            "address": "ul. Zegarowa 2", "area_m2": 44, "rooms": 2, "capacity": 2}
OFFER = {"title": "Zmiana czasu", "rent_amount": 250000, "min_term_months": 12,
         "contact_mode": "message"}


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


# --- the rule itself --------------------------------------------------------------


@pytest.mark.parametrize(
    ("wall", "expected"),
    [
        (datetime(2027, 1, 15, 10, 0), _utc(2027, 1, 15, 9, 0)),     # winter, UTC+1
        (datetime(2027, 7, 15, 10, 0), _utc(2027, 7, 15, 8, 0)),     # summer, UTC+2
        (datetime(2027, 3, 28, 1, 59), _utc(2027, 3, 28, 0, 59)),    # just before the gap
        (datetime(2027, 3, 28, 3, 0), _utc(2027, 3, 28, 1, 0)),      # just after it
        (datetime(2027, 10, 31, 1, 59), _utc(2027, 10, 30, 23, 59)), # before the overlap
        (datetime(2027, 10, 31, 3, 0), _utc(2027, 10, 31, 2, 0)),    # after it
    ],
)
def test_ordinary_wall_times_name_one_instant(wall, expected):
    assert viewings.unique_instant(wall, WARSAW) == expected


@pytest.mark.parametrize("minute", [0, 1, 30, 59])
def test_spring_forward_times_do_not_exist(minute):
    assert viewings.unique_instant(datetime(2027, 3, 28, 2, minute), WARSAW) is None


@pytest.mark.parametrize("minute", [0, 1, 30, 59])
def test_fall_back_times_are_ambiguous(minute):
    assert viewings.unique_instant(datetime(2027, 10, 31, 2, minute), WARSAW) is None


# --- slots through the API ----------------------------------------------------------


@pytest.fixture
def listing(client, monkeypatch):
    monkeypatch.setattr(viewings, "_now", lambda: _utc(2027, 1, 1))
    owner = register_and_login(client, "dst-owner@example.com", "host")
    prop = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(client, owner, prop)
    offer = client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    assert client.put(f"/v1/classifieds/{offer}/viewing-settings",
                      json={"minimum_notice_minutes": 0, "duration_minutes": 30},
                      headers=auth(owner)).status_code == 200
    return owner, offer


def _slots(client, owner, offer, day: date, start: str, end: str) -> list[datetime]:
    made = client.post(f"/v1/classifieds/{offer}/viewing-windows", json={
        "window_type": "ONE_OFF", "local_date": day.isoformat(),
        "local_start_time": start, "local_end_time": end}, headers=auth(owner))
    assert made.status_code == 201, made.text
    response = client.get(f"/v1/classifieds/{offer}/viewing-slots",
                          params={"start": day.isoformat(), "days": 1}, headers=auth(owner))
    assert response.status_code == 200, response.text
    return [datetime.fromisoformat(s.replace("Z", "+00:00")) for s in response.json()["slots"]]


def _inside(slots, day, start, end, minutes=30):
    lo = datetime.combine(day, datetime.strptime(start, "%H:%M").time())
    hi = datetime.combine(day, datetime.strptime(end, "%H:%M").time())
    for slot in slots:
        local_start = slot.astimezone(WARSAW).replace(tzinfo=None)
        local_end = (slot + timedelta(minutes=minutes)).astimezone(WARSAW).replace(tzinfo=None)
        assert lo <= local_start and local_end <= hi, (slot, local_start, local_end)


def test_winter_slots(client, listing):
    day = date(2027, 1, 15)
    slots = _slots(client, *listing, day, "10:00", "11:00")
    assert slots == [_utc(2027, 1, 15, 9, 0), _utc(2027, 1, 15, 9, 30)]
    _inside(slots, day, "10:00", "11:00")


def test_summer_slots(client, listing):
    day = date(2027, 7, 15)
    slots = _slots(client, *listing, day, "10:00", "11:00")
    assert slots == [_utc(2027, 7, 15, 8, 0), _utc(2027, 7, 15, 8, 30)]
    _inside(slots, day, "10:00", "11:00")


def test_a_window_entirely_in_the_spring_gap_offers_nothing(client, listing):
    """TASK-001 reproduction: 02:00–02:30 does not exist on 28 March 2027; the
    old code offered 01:00 UTC, which is 03:00 on the provider's clock."""
    assert _slots(client, *listing, date(2027, 3, 28), "02:00", "02:30") == []


def test_a_window_across_the_spring_gap_skips_the_missing_hour(client, listing):
    day = date(2027, 3, 28)
    slots = _slots(client, *listing, day, "01:00", "04:00")
    assert slots == [_utc(2027, 3, 28, 0, 0), _utc(2027, 3, 28, 0, 30),
                     _utc(2027, 3, 28, 1, 0), _utc(2027, 3, 28, 1, 30)]
    _inside(slots, day, "01:00", "04:00")


def test_a_window_across_the_fall_back_skips_the_repeated_hour(client, listing):
    day = date(2027, 10, 31)
    slots = _slots(client, *listing, day, "01:00", "04:00")
    assert slots == [_utc(2027, 10, 30, 23, 0), _utc(2027, 10, 30, 23, 30),
                     _utc(2027, 10, 31, 2, 0), _utc(2027, 10, 31, 2, 30)]
    _inside(slots, day, "01:00", "04:00")


def test_a_slot_whose_real_end_leaves_the_window_is_not_offered(client, listing):
    """01:30 + 60 minutes on the spring-forward night ends at 03:30 on the
    wall — outside a 01:00–03:00 window, though 01:30 + 60 looks like 02:30."""
    owner, offer = listing
    assert client.put(f"/v1/classifieds/{offer}/viewing-settings",
                      json={"minimum_notice_minutes": 0, "duration_minutes": 60},
                      headers=auth(owner)).status_code == 200
    day = date(2027, 3, 28)
    # 01:30 CET + 60 min = 03:30 CEST on the wall: past the 03:00 end.
    assert _slots(client, owner, offer, day, "01:30", "03:00") == []
    # 01:00 CET + 60 min = 03:00 CEST: exactly at the window's end — offered.
    other = date(2027, 3, 28)
    slots = _slots(client, owner, offer, other, "01:00", "03:00")
    assert slots == [_utc(2027, 3, 28, 0, 0)]
    _inside(slots, other, "01:00", "03:00", minutes=60)


def test_a_request_for_the_nonexistent_time_is_refused(client, listing):
    owner, offer = listing
    _slots(client, owner, offer, date(2027, 3, 28), "02:00", "02:30")
    tenant = register_and_login(client, "dst-tenant@example.com", "guest")
    response = client.post(f"/v1/classifieds/{offer}/viewings",
                           json={"starts_at": "2027-03-28T01:00:00+00:00"}, headers=auth(tenant))
    assert response.status_code == 409, response.text
