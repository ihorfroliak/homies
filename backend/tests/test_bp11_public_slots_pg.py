"""A public read is advisory; the booking write still serializes capacity."""
import pytest
from sqlalchemy import text

from app.modules.engagement import viewings
from tests.conftest import TEST_DATABASE_URL
from tests.test_engagement_safety_pg import _blocked_count
from tests.test_reports_moderation_pg import _account, _deadlocks, _pid, _run, _session, _user
from tests.test_viewings_pg import SLOT, SUMMER, _setup

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


def test_public_read_during_confirmation_does_not_reserve_and_write_rechecks(
        pg_client, pg_migrated_engine):
    engine = pg_migrated_engine
    _, listing, (first, _) = _setup(pg_client)
    requester = _account(engine)
    deadlocks = _deadlocks(engine)
    holder = _session(engine)
    holder.execute(text("SELECT 1 FROM viewing_settings WHERE listing_id=:l FOR UPDATE"),
                   {"l": listing})
    holder.execute(text("UPDATE viewings SET status='CONFIRMED' WHERE id=:v"), {"v": first})
    blocker = _pid(holder)
    results = {}
    threads = []
    try:
        # No availability locks on a public read: it sees the last committed
        # occupancy while the provider confirmation is in flight.
        response = pg_client.get(f"/v1/classifieds/{listing}/viewing-slots",
                                 params={"start": SUMMER.isoformat(), "days": 1})
        assert response.status_code == 200, response.text
        assert len(response.json()["slots"]) == 1

        def booking():
            with _session(engine) as db:
                return viewings.request_viewing(listing, viewings.ViewingRequest(starts_at=SLOT),
                                                user=_user(db, requester), db=db)
        threads.append(_run(results, "booking", booking))
        assert _blocked_count(engine, blocker, 1), "booking failed to wait on settings capacity lock"
        holder.commit()
    finally:
        holder.close()
        for thread in threads:
            thread.join(15)
        assert all(not thread.is_alive() for thread in threads)
    assert getattr(results["booking"], "status_code", None) == 409, results
    assert results["booking"].detail.startswith("SLOT_NOT_OFFERED:")
    response = pg_client.get(f"/v1/classifieds/{listing}/viewing-slots",
                             params={"start": SUMMER.isoformat(), "days": 1})
    assert response.status_code == 200 and response.json()["slots"] == []
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM viewings WHERE status='CONFIRMED'")) == 1
    assert _deadlocks(engine) == deadlocks
