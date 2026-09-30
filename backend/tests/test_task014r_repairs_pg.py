"""TASK-014R on real PostgreSQL/PostGIS: the repairs whose truth is
transactional — F-1 (links committed before SMTP survive a crash, and a retry
reuses them), F-4 (a concurrent PATCH to the same query answers 409, never
500), F-3 (downgrade → re-upgrade resumes the public-generation counter from
surviving history instead of colliding with it).
"""

import re
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.modules.alerts import delivery, worker
from app.modules.alerts.models import AlertDelivery, UnsubscribeToken
from app.modules.saved import service as saved_service
from app.modules.saved.models import SavedSearch
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login
from tests.saved_support import load_geo
from tests.test_geography_pg import _migrate, scratch_url  # noqa: F401 — fixture
from tests.test_listing_freshness_pg import _blocked_by, _pid
from tests.test_saved_search_alerts import Mailbox
from tests.test_saved_search_alerts_pg import HEAD, TASK013_HEAD, _listing, _renter, _search

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

TOKEN = re.compile(r"/unsubscribe\?token=([A-Za-z0-9_-]+)")


@pytest.fixture
def sessions(pg_migrated_engine):
    return sessionmaker(bind=pg_migrated_engine, expire_on_commit=False)


@pytest.fixture
def geo(pg_client, sessions):
    return load_geo(sessions)


@pytest.fixture
def owner(pg_client):
    return register_and_login(pg_client, "owner-014r@example.com", "host")


# --- F-1 ---------------------------------------------------------------------------------------


class AcceptThenCrash(Mailbox):
    def send(self, to, subject, body, idem_key):
        super().send(to, subject, body, idem_key)
        raise RuntimeError("worker crashed after SMTP accepted the message")


def test_links_committed_before_smtp_survive_a_crash_and_a_retry_reuses_them(
        pg_client, pg_migrated_engine, sessions, geo, owner, monkeypatch):
    renter = _renter(pg_client, "renter-014r@example.com")
    sid = _search(pg_client, renter, f"locality_id={geo['krakow']}")
    crashing = AcceptThenCrash()
    monkeypatch.setattr(delivery, "channel_for", lambda name: crashing)
    _listing(pg_client, owner, {"locality_id": geo["krakow"]})
    worker.process_work(sessions)
    worker.process_deliveries(sessions)
    assert len(crashing.sent) == 1
    first = TOKEN.findall(crashing.sent[0]["body"])
    # A fresh connection sees the committed capabilities, though the delivery
    # itself rolled back to `processing`.
    with pg_migrated_engine.connect() as conn:
        stored = set(conn.scalars(text("SELECT token_hash FROM unsubscribe_tokens")))
        status = conn.scalar(text("SELECT status FROM alert_deliveries WHERE channel = 'EMAIL'"))
    assert stored == {delivery.token_hash(t) for t in first} and status == "processing"
    # Retry after reconcile: a duplicate email (at-least-once) with the same links.
    with sessions.begin() as db:
        db.execute(update(AlertDelivery).where(AlertDelivery.status == "processing")
                   .values(claimed_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    with sessions.begin() as db:
        worker.reconcile(db)
    box = Mailbox()
    monkeypatch.setattr(delivery, "channel_for", lambda name: box)
    worker.process_deliveries(sessions)
    assert TOKEN.findall(box.sent[0]["body"]) == first
    with sessions() as db:
        assert db.scalar(select(AlertDelivery.status).where(
            AlertDelivery.channel == "EMAIL")) == "delivered"
        assert len(db.scalars(select(UnsubscribeToken.token_hash)).all()) == 2
    # The first email's per-search link still works, once.
    assert pg_client.post("/v1/notifications/unsubscribe",
                          json={"token": first[0]}).json() == {"status": "ok"}
    with sessions() as db:
        assert db.get(SavedSearch, sid).notifications_enabled is False


# --- F-4 ---------------------------------------------------------------------------------------


def test_a_patch_blocked_on_the_unique_fingerprint_answers_409(
        pg_client, pg_migrated_engine, sessions, geo):
    """Deterministic: a raw transaction holds the target fingerprint; the
    PATCH passes its duplicate pre-check, blocks on the unique index
    (pg_blocking_pids evidence), and meets the violation when the holder
    commits."""
    renter = _renter(pg_client, "patch-014r@example.com")
    s1 = _search(pg_client, renter, f"locality_id={geo['krakow']}", name="one")
    s2 = _search(pg_client, renter, f"locality_id={geo['warszawa']}", name="two")
    target = f"locality_id={geo['balice']}"
    fingerprint = saved_service.fingerprint(1, target)
    holder = pg_migrated_engine.connect()
    tx = holder.begin()
    holder.execute(text("UPDATE saved_searches SET canonical_query = :c, query_fingerprint = :f "
                        "WHERE id = :id"), {"c": target, "f": fingerprint, "id": s1})
    result: dict = {}

    def patch():
        try:
            result["r"] = pg_client.patch(f"/v1/me/saved-searches/{s2}", headers=auth(renter),
                                          json={"expected_version": 1, "query": target})
        except Exception as exc:  # the test client re-raises an unhandled server error
            result["unhandled"] = type(exc).__name__

    t = threading.Thread(target=patch)
    t.start()
    try:
        assert _blocked_by(pg_migrated_engine, _pid(holder)), "PATCH never reached the index"
    finally:
        tx.commit()
        holder.close()
    t.join(30)
    assert "unhandled" not in result, f"PATCH escaped as a server error: {result['unhandled']}"
    assert result["r"].status_code == 409, result["r"].text
    with sessions() as db:
        assert db.get(SavedSearch, s2).canonical_query == f"locality_id={geo['warszawa']}"


def test_two_concurrent_patches_to_one_query_are_200_and_409(pg_client, geo):
    renter = _renter(pg_client, "race-014r@example.com")
    for trial in range(3):
        a = _search(pg_client, renter, f"locality_id={geo['krakow']}&min_rooms={trial + 1}",
                    name=f"a{trial}")
        b = _search(pg_client, renter, f"locality_id={geo['warszawa']}&min_rooms={trial + 1}",
                    name=f"b{trial}")
        target = f"locality_id={geo['balice']}&min_rooms={trial + 1}"
        barrier = threading.Barrier(2)
        codes: list[int] = []

        def patch(sid):
            barrier.wait()
            codes.append(pg_client.patch(f"/v1/me/saved-searches/{sid}", headers=auth(renter),
                                         json={"expected_version": 1, "query": target})
                         .status_code)

        threads = [threading.Thread(target=patch, args=(sid,)) for sid in (a, b)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        assert sorted(codes) == [200, 409], codes


# --- F-3 ---------------------------------------------------------------------------------------


def test_re_upgrade_resumes_generations_from_surviving_history(scratch_url, monkeypatch):  # noqa: F811
    from app.core.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    _migrate(scratch_url, HEAD)
    engine = create_engine(scratch_url)
    local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        db = local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            owner = register_and_login(client, "mig014r@example.com", "host")

            def listing(tag, publishes, end_paused):
                oid = _listing(client, owner, {"city": "Opole", "address": f"ul. {tag}"},
                               publish=False)
                for i in range(publishes):
                    if i:
                        client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
                    assert client.post(f"/v1/classifieds/{oid}/publish",
                                       headers=auth(owner)).status_code == 200
                if end_paused:
                    client.post(f"/v1/classifieds/{oid}/pause", headers=auth(owner))
                return oid

            shapes = {
                "never": (listing("never", 0, False), 0),
                "one": (listing("one", 1, False), 1),
                "two_public": (listing("two", 2, False), 2),
                "four_public": (listing("four", 4, False), 4),
                "three_paused": (listing("three", 3, True), 3),
            }
            before = {name: _row(engine, oid) for name, (oid, _) in shapes.items()}

            _migrate(scratch_url, TASK013_HEAD, down=True)
            _migrate(scratch_url, HEAD)

            with engine.connect() as conn:
                for name, (oid, generations) in shapes.items():
                    gen, since = _row(engine, oid)
                    assert gen == generations, (name, gen)
                    if generations >= 2:
                        # The current cycle's own instant, from the surviving event.
                        assert since == before[name][1], name
                done = conn.execute(text(
                    "SELECT alert_status, count(*) FROM listing_public_generations "
                    "GROUP BY alert_status")).all()
                assert dict(done) == {"done": 1 + 2 + 4 + 3}  # history, handled, not work
            # No flood and no duplicate work from history …
            renter = _renter(client, "mig014r-renter@example.com")
            _search(client, renter, "city=Opole")
            with local.begin() as db:
                assert worker.reconcile(db)["restored_work"] == 0
            with engine.connect() as conn:
                assert conn.scalar(text("SELECT count(*) FROM alert_deliveries")) == 0
            # … and the counter continues: the paused three-generation listing
            # republishes as generation 4, the public four-generation one is untouched.
            paused, _ = shapes["three_paused"]
            assert client.post(f"/v1/classifieds/{paused}/publish",
                               headers=auth(owner)).status_code == 200
            assert _row(engine, paused)[0] == 4
            four, _ = shapes["four_public"]
            client.post(f"/v1/classifieds/{four}/pause", headers=auth(owner))
            assert client.post(f"/v1/classifieds/{four}/publish",
                               headers=auth(owner)).status_code == 200
            assert _row(engine, four)[0] == 5
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _row(engine, oid):
    with engine.connect() as conn:
        return conn.execute(text("SELECT public_generation, public_since FROM classified_offers "
                                 "WHERE id = :id"), {"id": oid}).one()
