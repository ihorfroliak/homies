"""The last viewing place, raced for real (Domain Schema v1 §60, real Postgres).

A race driven through TestClient proves nothing: it serialises requests, so
the "race" never overlaps (the CI-03 lesson). This test overlaps them on
purpose. One database session takes the listing's settings lock and confirms
the first tenant; while it holds the lock, the provider confirms the second
tenant through the API in another thread. That request must wait for the lock
— and, once the first commits, find the place gone.

Without the lock the second confirmation would read the slot as free, succeed,
and put two parties at one door in a slot that holds one.
"""

import threading
import time as clock
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

SUMMER = date(2027, 7, 15)
SLOT = datetime.combine(SUMMER, time(10), ZoneInfo("Europe/Warsaw")).astimezone(timezone.utc)
PROPERTY = {"property_type": "apartment", "city": "Opole", "municipality": "Opole",
            "address": "ul. Wyścigowa 1", "area_m2": 45, "rooms": 2, "capacity": 3}
OFFER = {"title": "Ostatnie miejsce", "rent_amount": 200000, "min_term_months": 12,
         "contact_mode": "message"}


def _setup(pg_client):
    owner = register_and_login(pg_client, "race-owner@example.com", "host")
    prop = pg_client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()
    verify_ownership(pg_client, owner, prop["id"])
    listing = pg_client.post(f"/v1/properties/{prop['id']}/classifieds", json=OFFER,
                             headers=auth(owner)).json()["id"]
    pg_client.post(f"/v1/classifieds/{listing}/publish", headers=auth(owner))
    pg_client.put(f"/v1/classifieds/{listing}/viewing-settings",
                  json={"minimum_notice_minutes": 0, "max_concurrent_bookings": 1},
                  headers=auth(owner))
    pg_client.post(f"/v1/classifieds/{listing}/viewing-windows",
                   json={"window_type": "ONE_OFF", "local_date": SUMMER.isoformat(),
                         "local_start_time": "10:00", "local_end_time": "10:30"},
                   headers=auth(owner))
    viewings = []
    for n in (1, 2):
        tenant = register_and_login(pg_client, f"racer-{n}@example.com", "guest")
        resp = pg_client.post(f"/v1/classifieds/{listing}/viewings",
                              json={"starts_at": SLOT.isoformat()}, headers=auth(tenant))
        assert resp.status_code == 201, resp.text
        viewings.append(resp.json()["id"])
    return owner, listing, viewings


def test_the_second_confirmation_waits_for_the_first_and_then_finds_it_full(
    pg_client, pg_migrated_engine
):
    owner, listing, (first, second) = _setup(pg_client)

    holder = sessionmaker(bind=pg_migrated_engine)()
    holder.execute(text("SELECT 1 FROM viewing_settings WHERE listing_id = :l FOR UPDATE"),
                   {"l": listing})
    holder.execute(text("UPDATE viewings SET status = 'CONFIRMED' WHERE id = :v"),
                   {"v": first})

    result: dict = {}

    def confirm_second():
        result["response"] = pg_client.post(f"/v1/viewings/{second}/confirm",
                                            headers=auth(owner))

    worker = threading.Thread(target=confirm_second)
    worker.start()
    clock.sleep(1.0)
    waited = worker.is_alive()

    holder.commit()
    holder.close()
    worker.join(timeout=30)

    assert waited, "the second confirmation did not wait for the lock"
    assert result["response"].status_code == 409, result["response"].text
