"""Public derived availability: privacy, transport limits and real overlap rules."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.core import ratelimit as rl
from app.core.config import settings as config
from app.modules.engagement import viewings
from app.modules.engagement.models import Viewing, ViewingSettings
from app.modules.properties.models import ClassifiedOffer
from tests.conftest import TestingSession, auth, engine
from tests.test_sec01_ratelimit import FakeClock
from tests import test_viewings as shared
from tests.test_viewings import SUMMER, _one_off, _settings, _utc

listing, owner, tenant = shared.listing, shared.owner, shared.tenant


@pytest.fixture(autouse=True)
def schedule_clock(monkeypatch):
    monkeypatch.setattr(viewings, "_now", lambda: datetime(2027, 1, 1, tzinfo=timezone.utc))


def _read(client, listing, **params):
    return client.get(f"/v1/classifieds/{listing}/viewing-slots", params=params)


def test_guest_and_signed_in_see_only_derived_slots(client, owner, tenant, listing, caplog):
    _settings(client, owner, listing, max_concurrent_bookings=7, buffer_before_minutes=13)
    _one_off(client, owner, listing, SUMMER)
    guest = _read(client, listing, start=SUMMER.isoformat(), days=1)
    signed = client.get(f"/v1/classifieds/{listing}/viewing-slots",
                        params={"start": SUMMER.isoformat(), "days": 1}, headers=auth(tenant))
    assert guest.status_code == signed.status_code == 200
    assert guest.json() == signed.json()
    assert set(guest.json()) == {"slots", "timezone", "duration_minutes"}
    assert len(guest.json()["slots"]) == 4
    for secret in ("max_concurrent_bookings", "buffer_before", "Pokazowa", "requester",
                   "viewing-owner@example.com", "minimum_notice", "booking_mode"):
        assert secret not in guest.text
    assert "Pokazowa" not in caplog.text
    assert client.post(f"/v1/classifieds/{listing}/viewings",
                       json={"starts_at": guest.json()["slots"][0]}).status_code == 401
    assert client.put(f"/v1/classifieds/{listing}/viewing-settings", json={}).status_code == 401


@pytest.mark.parametrize("state", ["draft", "paused", "archived", "stale", "held", "aged"])
def test_nonpublic_is_uniform_not_found(client, listing, state):
    if state == "held":
        from tests.test_engagement_safety import _decide
        from tests.test_reports_moderation import _moderator
        result = _decide(client, _moderator(client), "LISTING", listing,
                         "VISIBILITY_LIMITED", "SCAM")
        assert result.status_code == 201, result.text
    with TestingSession() as db:
        row = db.get(ClassifiedOffer, listing)
        if state == "aged":
            row.last_confirmed_available_at = datetime.now(timezone.utc) - timedelta(days=22)
        elif state != "held":
            row.status = state
        db.commit()
    denied = _read(client, listing)
    assert denied.status_code == 404, denied.text
    assert denied.json() == _read(client, "missing").json() == {"detail": "Offer not found"}


def test_empty_and_disabled_keep_nullable_projection(client, owner, listing):
    assert _read(client, listing).json() == {
        "slots": [], "duration_minutes": None, "timezone": None}
    _settings(client, owner, listing, enabled=False)
    _one_off(client, owner, listing, SUMMER)
    assert _read(client, listing, start=SUMMER.isoformat()).json() == {
        "slots": [], "duration_minutes": 30, "timezone": "Europe/Warsaw"}


@pytest.mark.parametrize("start,days,code", [
    ("2026-12-31", 1, 422), ("2027-01-01", 1, 200),
    ("2028-01-02", 31, 200), ("2028-01-03", 1, 422),
    ("9999-12-31", 1, 422), ("2027-01-01", 0, 422), ("2027-01-01", 32, 422),
])
def test_date_bounds(client, owner, listing, start, days, code):
    _settings(client, owner, listing)
    assert _read(client, listing, start=start, days=days).status_code == code


def test_dedicated_rate_limit_cannot_rotate_listing_or_forwarded_identity(
        client, listing, monkeypatch):
    monkeypatch.setattr(config, "rate_limit_enabled", True)
    monkeypatch.setattr(config, "trust_proxy_hops", 1)
    monkeypatch.setattr(config, "trusted_proxy_cidrs", ["10.0.0.0/8"])
    monkeypatch.setattr(rl.limiter, "store", rl.InMemoryTokenBucketStore(FakeClock()))
    for n in range(rl.VIEWING_SLOTS.capacity):
        response = client.get(f"/v1/classifieds/{listing}/viewing-slots",
                              headers={"x-forwarded-for": f"198.51.100.{n + 1}"})
        assert response.status_code == 200
    refused = client.get("/v1/classifieds/another/viewing-slots",
                         headers={"x-forwarded-for": "203.0.113.100"})
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) > 0
    assert refused.json() == {"detail": "Too many requests"}


def test_proxy_requires_trusted_socket_and_validates_chain():
    def request(peer, forwarded):
        return SimpleNamespace(client=SimpleNamespace(host=peer),
                               headers={"x-forwarded-for": forwarded})
    trust = ["10.0.0.0/8"]
    assert rl.client_ip(request("198.51.100.1", "203.0.113.2"), 1, trust) == "198.51.100.1"
    assert rl.client_ip(request("10.0.0.1", "spoof, 203.0.113.2"), 1, trust) == "203.0.113.2"
    assert rl.client_ip(request("10.0.0.1", "203.0.113.2, 10.0.0.2"), 2, trust) == "203.0.113.2"
    assert rl.client_ip(request("10.0.0.1", "spoof, 203.0.113.2"), 2, trust) == "10.0.0.1"
    assert rl.client_ip(request("10.0.0.1", "invalid"), 1, trust) == "10.0.0.1"
    assert rl.client_ip(request("10.0.0.1", "203.0.113.2"), 1) == "10.0.0.1"


@pytest.mark.parametrize("day,expected", [(date(2027, 3, 28), [0, 1, 3, 4]),
                                          (date(2027, 10, 31), [0, 1, 3, 4])])
def test_dst_never_offers_nonexistent_or_ambiguous_start(client, owner, listing, day, expected):
    from zoneinfo import ZoneInfo
    _settings(client, owner, listing, duration_minutes=60)
    _one_off(client, owner, listing, day, "00:00", "05:00")
    response = _read(client, listing, start=day.isoformat(), days=1)
    assert response.status_code == 200
    assert [datetime.fromisoformat(v).astimezone(ZoneInfo("Europe/Warsaw")).hour
            for v in response.json()["slots"]] == expected


def test_work_budget_returns_retryable_refusal_not_partial_slots(client, owner, listing, monkeypatch):
    _settings(client, owner, listing)
    _one_off(client, owner, listing, SUMMER)
    monkeypatch.setattr(viewings, "MAX_SLOT_CANDIDATES", 1)
    response = _read(client, listing, start=SUMMER.isoformat(), days=1)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert response.json() == {"detail": "Viewing availability temporarily unavailable"}


def test_overlap_counts_match_original_for_capacity_buffers_and_booking_statuses(
        client, owner, listing):
    _settings(client, owner, listing, max_concurrent_bookings=2,
              buffer_before_minutes=10, buffer_after_minutes=15)
    _one_off(client, owner, listing, SUMMER, "09:00", "18:00")
    with TestingSession() as db:
        from app.modules.identity.models import User
        requester = db.query(User).first().id
        for n in range(12):
            start = _utc(SUMMER, 9) + timedelta(minutes=n * 23)
            db.add(Viewing(listing_id=listing, requester_user_id=requester, starts_at=start,
                           ends_at=start + timedelta(minutes=40 + n * 5),
                           status="REQUESTED" if n % 3 == 0 else "CONFIRMED"))
        db.commit()
        schedule = db.get(ViewingSettings, listing)
        expected = [start for n in range(18)
                    if viewings._held_overlapping(db, listing,
                        (start := _utc(SUMMER, 9) + timedelta(minutes=30*n)) - timedelta(minutes=25),
                        start + timedelta(minutes=55)) < 2]
        assert viewings.slots(db, schedule, SUMMER, 1) == expected


def test_sql_round_trips_do_not_scale_with_candidates(client, owner, listing):
    _settings(client, owner, listing, duration_minutes=10)
    for weekday in range(7):
        response = client.post(f"/v1/classifieds/{listing}/viewing-windows",
                               json={"window_type": "WEEKLY", "weekday": weekday,
                                     "local_start_time": "00:00", "local_end_time": "23:50"},
                               headers=auth(owner))
        assert response.status_code == 201
    counts = []
    for days in (1, 31):
        queries = []
        def observe(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)
        event.listen(engine, "before_cursor_execute", observe)
        try:
            response = _read(client, listing, start=SUMMER.isoformat(), days=days)
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        assert response.status_code == 200
        assert len(response.json()["slots"]) == 143 * days
        counts.append(len(queries))
    # The loaded listing also select-in loads its existing media/price relations.
    assert counts[0] == counts[1] == 7


@pytest.mark.parametrize("budget", ["MAX_SLOT_WINDOWS", "MAX_SLOT_BLACKOUTS", "MAX_SLOT_BOOKINGS"])
def test_row_budgets_never_return_truncated_availability(client, owner, listing, monkeypatch, budget):
    from app.modules.engagement.models import ViewingBlackout
    from app.modules.identity.models import User
    _settings(client, owner, listing)
    _one_off(client, owner, listing, SUMMER)
    _one_off(client, owner, listing, SUMMER)
    with TestingSession() as db:
        requester = db.query(User).first().id
        for _ in range(2):
            if budget == "MAX_SLOT_BLACKOUTS":
                db.add(ViewingBlackout(listing_id=listing, starts_at=_utc(SUMMER, 10),
                                      ends_at=_utc(SUMMER, 10, 30), reason="private canary"))
            elif budget == "MAX_SLOT_BOOKINGS":
                db.add(Viewing(listing_id=listing, requester_user_id=requester,
                               starts_at=_utc(SUMMER, 10), ends_at=_utc(SUMMER, 10, 30),
                               status="CONFIRMED"))
        db.commit()
    monkeypatch.setattr(viewings, budget, 1)
    response = _read(client, listing, start=SUMMER.isoformat(), days=1)
    assert response.status_code == 503
    assert response.json() == {"detail": "Viewing availability temporarily unavailable"}
    assert response.headers["Retry-After"] == "1"


def test_public_budget_fails_closed():
    class Broken:
        def consume(self, *args):
            raise RuntimeError("unavailable")
    limiter = rl.RateLimiter(store=Broken())
    assert limiter.check("viewing_slots:ip:1", rl.VIEWING_SLOTS)[0] is False


def test_maximum_capacity_counts_confirmed_only(client, owner, listing):
    from app.modules.identity.models import User
    _settings(client, owner, listing, max_concurrent_bookings=20)
    _one_off(client, owner, listing, SUMMER, "10:00", "10:30")
    with TestingSession() as db:
        requester = db.query(User).first().id
        for n in range(20):
            db.add(Viewing(listing_id=listing, requester_user_id=requester,
                           starts_at=_utc(SUMMER, 10), ends_at=_utc(SUMMER, 10, 30),
                           status="CONFIRMED" if n < 19 else "REQUESTED"))
        db.commit()
    assert len(_read(client, listing, start=SUMMER.isoformat(), days=1).json()["slots"]) == 1
    with TestingSession() as db:
        db.query(Viewing).filter(Viewing.status == "REQUESTED").one().status = "CONFIRMED"
        db.commit()
    assert _read(client, listing, start=SUMMER.isoformat(), days=1).json()["slots"] == []


def test_public_date_bound_does_not_redefine_authorized_booking_rules(client, owner, tenant, listing):
    # A stored legitimate schedule still governs an independently validated
    # authenticated write, even outside the public transport's browsing horizon.
    far = date(2028, 7, 1)
    _settings(client, owner, listing)
    _one_off(client, owner, listing, far, "10:00", "10:30")
    assert _read(client, listing, start=far.isoformat(), days=1).status_code == 422
    response = client.post(f"/v1/classifieds/{listing}/viewings",
                           json={"starts_at": _utc(far, 10).isoformat()}, headers=auth(tenant))
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("trusted", [False, True])
def test_shipped_uvicorn_preserves_socket_for_proxy_policy(trusted):
    import json
    import socket
    import threading
    import time
    from pathlib import Path

    import httpx
    import uvicorn
    from fastapi import FastAPI, Request

    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    command = json.loads(next(line[4:] for line in dockerfile.splitlines() if line.startswith("CMD ")))
    assert "--no-proxy-headers" in command
    probe = FastAPI()

    @probe.get("/")
    def address(request: Request):
        return {"address": rl.client_ip(request, 1, ["127.0.0.1/32"] if trusted else [])}

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(probe, proxy_headers=False, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        until = time.monotonic() + 5
        while not server.started and time.monotonic() < until:
            time.sleep(0.01)
        assert server.started
        response = httpx.get(f"http://127.0.0.1:{port}/",
                             headers={"x-forwarded-for": "198.51.100.2"})
        assert response.json() == {"address": "198.51.100.2" if trusted else "127.0.0.1"}
    finally:
        server.should_exit = True
        thread.join(5)
        sock.close()
        assert not thread.is_alive()
