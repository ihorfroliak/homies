"""Saved Searches (TASK-014): one canonical query, versioned fingerprint,
explicit INVALID, owner isolation, caps, CAS updates."""

from datetime import date

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.modules.geography.models import Locality
from app.modules.properties import search
from app.modules.properties.models import AttributeDefinition
from app.modules.saved import service
from app.modules.saved.models import SavedSearch
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership
from tests.saved_support import load_geo


@pytest.fixture
def geo(client):
    return load_geo(TestingSession)


@pytest.fixture
def renter(client):
    return register_and_login(client, "renter-ss@example.com", "guest")


def _create(client, token, query="", name="Kraków 2 pokoje", **extra):
    return client.post("/v1/me/saved-searches", json={"name": name, "query": query, **extra},
                       headers=auth(token))


# --- one search language -----------------------------------------------------------------


@pytest.mark.parametrize("raw", [
    "",
    "category=APARTMENT",
    "max_rent=300000&min_rent=100000&category=HOUSE&category=APARTMENT",
    "has=dishwasher&has=wifi&pets_allowed=true&furnished=full",
    "bbox=19.9%2C50.0%2C20.1%2C50.1&sort=price_asc",
    "near_lat=50.06&near_lon=19.94&radius_m=1500&available_by=2027-01-31",
    "city=Krak%C3%B3w&district=Stare+Miasto&min_rooms=2&min_area_m2=40",
    "max_term_months=12&space_type=ROOM&max_move_in_total=900000",
])
def test_stored_queries_round_trip_through_the_one_builder(client, raw):
    with TestingSession() as db:
        try:
            q = search.parse_query_string(db, raw)
        except search.InvalidSearchQuery as exc:  # an attribute code not in the catalogue
            pytest.skip(str(exc))
        again = search.parse_query_string(db, q.canonical())
    assert again == q
    assert again.canonical() == q.canonical()


def test_parameter_order_does_not_change_the_fingerprint(client, renter):
    a = _create(client, renter, "max_rent=300000&category=APARTMENT&category=HOUSE")
    assert a.status_code == 201, a.text
    assert a.json()["query"] == "category=APARTMENT&category=HOUSE&max_rent=300000"
    duplicate = _create(client, renter, "category=HOUSE&max_rent=300000&category=APARTMENT",
                        name="Same search, other order")
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"].startswith("SAVED_SEARCH_DUPLICATE: ")
    assert duplicate.headers["location"] == f"/v1/me/saved-searches/{a.json()['id']}"
    with TestingSession() as db:
        stored = db.get(SavedSearch, a.json()["id"])
        assert stored.query_fingerprint == service.fingerprint(1, a.json()["query"])
    assert service.fingerprint(1, "x=1") != service.fingerprint(2, "x=1")
    assert len(service.fingerprint(1, "")) == 64


def test_another_account_may_save_the_same_search(client, renter):
    assert _create(client, renter, "category=APARTMENT").status_code == 201
    other = register_and_login(client, "other-ss@example.com", "guest")
    assert _create(client, other, "category=APARTMENT").status_code == 201


@pytest.mark.parametrize("query, message", [
    ("category=CASTLE", "category must be one of"),
    ("colour=blue", "'colour' is not a search parameter"),
    ("min_rent=abc", "whole number"),
    ("min_rent=1&min_rent=2", "given more than once"),
    ("min_rent=5&max_rent=4", "above max_rent"),
    ("has=not_an_attribute", "not a filterable attribute"),
    ("near_lat=50", "radius search needs"),
    ("near_lat=nan&near_lon=1&radius_m=5", "finite"),
    ("radius_m=0&near_lat=1&near_lon=1", "radius_m must be between"),
    ("min_rent=" + "9" * 13, "min_rent must be between"),
    ("available_by=2027-02-30", "available_by must be a date"),
    ("city=a%00b", "NUL"),
    ("locality_id=does-not-exist", "no longer exists"),
])
def test_an_invalid_query_is_refused_at_save_time(client, renter, query, message):
    r = _create(client, renter, query)
    assert r.status_code == 422, r.text
    assert message in r.text


def test_page_state_is_not_a_criterion(client, renter):
    r = _create(client, renter, "?category=APARTMENT&limit=20&offset=40")
    assert r.status_code == 201, r.text
    assert r.json()["query"] == "category=APARTMENT"


def test_a_zero_result_search_is_a_first_class_save(client, renter):
    r = _create(client, renter, "min_rent=999999999")
    assert r.status_code == 201
    body = r.json()
    assert body["match_count"] == 0 and body["query_state"] == "VALID"
    assert body["notifications_enabled"] is True and body["status"] == "active"
    assert body["baseline_at"] == body["created_at"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 81, "bad\u0007bell", "tab\there"])
def test_names_are_bounded_and_clean(client, renter, name):
    assert _create(client, renter, name=name).status_code == 422


def test_the_per_user_cap_holds(client, renter, monkeypatch):
    monkeypatch.setattr(settings, "saved_searches_per_user", 2)
    assert _create(client, renter, "min_rooms=1").status_code == 201
    assert _create(client, renter, "min_rooms=2").status_code == 201
    capped = _create(client, renter, "min_rooms=3")
    assert capped.status_code == 409
    assert capped.json()["detail"].startswith("SAVED_SEARCH_LIMIT: ")
    assert client.get("/v1/me/saved-searches", headers=auth(renter)).json()["total"] == 2


def test_saved_searches_are_private_to_their_owner(client, renter):
    sid = _create(client, renter, "category=APARTMENT").json()["id"]
    other = register_and_login(client, "intruder-ss@example.com", "guest")
    for method, path, body in (
        ("get", f"/v1/me/saved-searches/{sid}", None),
        ("get", f"/v1/me/saved-searches/{sid}/matches", None),
        ("patch", f"/v1/me/saved-searches/{sid}", {"expected_version": 1, "name": "mine now"}),
        ("delete", f"/v1/me/saved-searches/{sid}", None),
    ):
        kwargs = {"headers": auth(other)} | ({"json": body} if body else {})
        assert getattr(client, method)(path, **kwargs).status_code == 404, (method, path)
    assert client.get("/v1/me/saved-searches", headers=auth(other)).json()["total"] == 0
    assert client.get(f"/v1/me/saved-searches/{sid}", headers=auth(renter)).status_code == 200


def test_updates_are_compare_and_set(client, renter):
    created = _create(client, renter, "category=APARTMENT").json()
    sid = created["id"]
    paused = client.patch(f"/v1/me/saved-searches/{sid}",
                          json={"expected_version": 1, "status": "paused",
                                "notifications_enabled": False, "name": "Pauza"},
                          headers=auth(renter))
    assert paused.status_code == 200, paused.text
    assert paused.json()["version"] == 2 and paused.json()["status"] == "paused"
    assert paused.json()["baseline_at"] == created["baseline_at"]  # no query change
    stale = client.patch(f"/v1/me/saved-searches/{sid}",
                         json={"expected_version": 1, "status": "active"}, headers=auth(renter))
    assert stale.status_code == 409


def test_a_new_query_gets_a_new_baseline(client, renter):
    created = _create(client, renter, "category=APARTMENT").json()
    changed = client.patch(f"/v1/me/saved-searches/{created['id']}",
                           json={"expected_version": 1, "query": "category=HOUSE"},
                           headers=auth(renter)).json()
    assert changed["query"] == "category=HOUSE"
    assert changed["baseline_at"] > created["baseline_at"]
    other = _create(client, renter, "min_rooms=2").json()
    clash = client.patch(f"/v1/me/saved-searches/{other['id']}",
                         json={"expected_version": 1, "query": "category=HOUSE"},
                         headers=auth(renter))
    assert clash.status_code == 409
    assert clash.json()["detail"].startswith("SAVED_SEARCH_DUPLICATE: ")
    assert clash.headers["location"] == f"/v1/me/saved-searches/{changed['id']}"


def test_delete_removes_the_search(client, renter):
    sid = _create(client, renter).json()["id"]
    assert client.delete(f"/v1/me/saved-searches/{sid}", headers=auth(renter)).status_code == 204
    assert client.get(f"/v1/me/saved-searches/{sid}", headers=auth(renter)).status_code == 404


# --- INVALID, never broadened ----------------------------------------------------------------


def test_a_retired_place_makes_the_stored_query_invalid(client, renter, geo):
    sid = _create(client, renter, f"locality_id={geo['krakow']}").json()["id"]
    with TestingSession() as db:
        db.execute(update(Locality).where(Locality.id == geo["krakow"]).values(status="RETIRED"))
        db.commit()
    body = client.get(f"/v1/me/saved-searches/{sid}", headers=auth(renter)).json()
    assert body["query_state"] == "INVALID" and "retired" in body["invalid_reason"]
    assert body["match_count"] is None
    assert client.get(f"/v1/me/saved-searches/{sid}/matches",
                      headers=auth(renter)).status_code == 409


def test_a_withdrawn_filter_value_makes_the_stored_query_invalid(client, renter):
    with TestingSession() as db:
        code = db.query(AttributeDefinition.code).filter(
            AttributeDefinition.filterable.is_(True)).first()[0]
    sid = _create(client, renter, f"has={code}").json()["id"]
    with TestingSession() as db:
        db.execute(update(AttributeDefinition).where(AttributeDefinition.code == code)
                   .values(filterable=False))
        db.commit()
    body = client.get(f"/v1/me/saved-searches/{sid}", headers=auth(renter)).json()
    assert body["query_state"] == "INVALID"


def test_an_unsupported_schema_version_is_invalid(client, renter):
    sid = _create(client, renter, "category=APARTMENT").json()["id"]
    with TestingSession() as db:
        db.execute(update(SavedSearch).where(SavedSearch.id == sid)
                   .values(query_schema_version=99))
        db.commit()
    body = client.get(f"/v1/me/saved-searches/{sid}", headers=auth(renter)).json()
    assert body["query_state"] == "INVALID" and "99" in body["invalid_reason"]


def test_a_corrupted_stored_query_is_invalid_not_broadened(client, renter):
    sid = _create(client, renter, "category=APARTMENT&max_rent=100").json()["id"]
    with TestingSession() as db:
        # An unknown criterion must not be dropped (which would broaden the search).
        db.execute(update(SavedSearch).where(SavedSearch.id == sid)
                   .values(canonical_query="category=APARTMENT&max_rent=100&future_filter=x"))
        db.commit()
    assert client.get(f"/v1/me/saved-searches/{sid}",
                      headers=auth(renter)).json()["query_state"] == "INVALID"


# --- current matches -------------------------------------------------------------------------


def test_matches_are_the_live_search(client, renter):
    owner = register_and_login(client, "owner-ss@example.com", "host")
    made = client.post("/v1/properties", json={
        "category": "APARTMENT", "area_m2": 50, "rooms": 3, "capacity": 2, "city": "Lublin",
        "address": "ul. Dopasowana 1"}, headers=auth(owner)).json()
    verify_ownership(client, owner, made["id"])
    oid = client.post(f"/v1/properties/{made['id']}/classifieds", json={
        "title": "Trzy pokoje", "rent_amount": 250000, "min_term_months": 12,
        "contact_mode": "message", "available_from": str(date(2026, 1, 1))},
        headers=auth(owner)).json()["id"]
    client.post(f"/v1/classifieds/{oid}/publish", headers=auth(owner))
    sid = _create(client, renter, "min_rooms=3").json()["id"]
    mine = client.get(f"/v1/me/saved-searches/{sid}/matches", headers=auth(renter)).json()
    live = client.get("/v1/classifieds", params={"min_rooms": 3}).json()
    assert [i["id"] for i in mine["items"]] == [i["id"] for i in live["items"]] == [oid]
    assert mine["query"] == live["query"] == "min_rooms=3"
    assert client.get(f"/v1/me/saved-searches/{sid}",
                      headers=auth(renter)).json()["match_count"] == 1
