"""TASK-001 concurrency findings F-03, F-06 and F-09, closed (TASK-002 R4).

Each test pins one transaction at an exact point with events and observes
the other one waiting on a lock in pg_stat_activity — not assumed from
timing. Against the pre-TASK-002 code, each of these tests fails.
"""

import threading
import time

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.modules.identity.models import User
from app.modules.properties import router as properties
from app.modules.properties.models import ContactReveal
from tests.conftest import auth, register_and_login
from tests.test_reveal_quota_pg import _publish, _verified_seeker

WAIT = 15


def _someone_waits_on_a_lock(engine) -> bool:
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            if conn.scalar(text(
                "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock')"
            )):
                return True
        time.sleep(0.05)
    return False


def _run(results, key, fn):
    try:
        results[key] = fn()
    except HTTPException as exc:
        results[key] = exc


# --- F-03: the persistent contact quota ------------------------------------------


def test_f03_two_new_disclosures_at_quota_one_admit_exactly_one(
    pg_client, pg_migrated_engine, monkeypatch
):
    owner = register_and_login(pg_client, "race-reveal-owner@example.com", "host")
    _verified_seeker(pg_client, "race-reveal-tenant@example.com", "+48600111222")
    offers = [_publish(pg_client, owner, f"ul. Wyścigowa {n}") for n in range(2)]
    monkeypatch.setattr(settings, "contact_reveal_daily_quota", 1)

    counted = threading.Event()
    resume = threading.Event()
    original = properties._quota_used
    first = {"taken": False}
    guard = threading.Lock()

    def gated(db, viewer_id):
        result = original(db, viewer_id)
        with guard:
            mine = not first["taken"]
            first["taken"] = True
        if mine:
            counted.set()
            assert resume.wait(WAIT)
        return result

    monkeypatch.setattr(properties, "_quota_used", gated)
    Session = sessionmaker(bind=pg_migrated_engine, expire_on_commit=False)

    def reveal(offer_id):
        with Session() as db:
            user = db.scalar(select(User).where(User.email == "race-reveal-tenant@example.com"))
            return properties.reveal_contact(offer_id, user, db)

    results: dict = {}
    one = threading.Thread(target=_run, args=(results, "one", lambda: reveal(offers[0])))
    two = threading.Thread(target=_run, args=(results, "two", lambda: reveal(offers[1])))
    one.start()
    try:
        assert counted.wait(WAIT), "the first disclosure never counted its quota"
        two.start()
        assert _someone_waits_on_a_lock(pg_migrated_engine), "the second did not wait"
    finally:
        resume.set()
        one.join(WAIT)
        if two.ident:
            two.join(WAIT)

    assert results["one"].offer_id == offers[0]
    assert isinstance(results["two"], HTTPException) and results["two"].status_code == 429
    with pg_migrated_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(ContactReveal)) == 1


def test_f03_a_repeat_disclosure_costs_nothing_and_keeps_its_time(
    pg_client, pg_migrated_engine, monkeypatch
):
    owner = register_and_login(pg_client, "repeat-owner@example.com", "host")
    tenant = _verified_seeker(pg_client, "repeat-tenant@example.com", "+48600333444")
    offer = _publish(pg_client, owner, "ul. Powtórna 1")
    monkeypatch.setattr(settings, "contact_reveal_daily_quota", 1)
    assert pg_client.post(f"/v1/classifieds/{offer}/contact",
                          headers=auth(tenant)).status_code == 200
    with pg_migrated_engine.connect() as conn:
        first = conn.scalar(select(ContactReveal.revealed_at))
    again = pg_client.post(f"/v1/classifieds/{offer}/contact", headers=auth(tenant))
    assert again.status_code == 200
    with pg_migrated_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(ContactReveal)) == 1
        assert conn.scalar(select(ContactReveal.revealed_at)) == first


# --- F-06: a cancelled viewing stays cancelled -----------------------------------


def test_f06_a_stale_confirmation_cannot_resurrect_a_cancelled_viewing(
    pg_client, pg_migrated_engine
):
    """TASK-001 reproduction: confirm reads REQUESTED and waits for the
    settings lock; cancel commits; confirm used to resume and write CONFIRMED
    over it, leaving status=CONFIRMED with cancelled_at set."""
    from tests.test_viewings_pg import _setup

    owner, listing_id, (first, _) = _setup(pg_client)
    Session = sessionmaker(bind=pg_migrated_engine)
    results: dict = {}
    with Session() as holder:
        holder.execute(text("SELECT 1 FROM viewing_settings WHERE listing_id = :l FOR UPDATE"),
                       {"l": listing_id})
        confirm = threading.Thread(target=lambda: results.update(
            confirm=pg_client.post(f"/v1/viewings/{first}/confirm", headers=auth(owner))))
        confirm.start()
        try:
            assert _someone_waits_on_a_lock(pg_migrated_engine), "confirm never waited"
            cancelled = pg_client.post(f"/v1/viewings/{first}/cancel", headers=auth(owner))
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "CANCELLED"
        finally:
            holder.commit()
            confirm.join(WAIT)

    assert results["confirm"].status_code == 409, results["confirm"].text
    with pg_migrated_engine.connect() as conn:
        row = conn.execute(text("SELECT status, cancelled_at IS NOT NULL FROM viewings "
                                "WHERE id = :v"), {"v": first}).one()
    assert tuple(row) == ("CANCELLED", True)


def test_no_viewing_is_ever_confirmed_with_a_cancellation_time(pg_client, pg_migrated_engine):
    """The database refuses the contradictory state outright, whatever writes it."""
    from sqlalchemy.exc import IntegrityError

    from tests.test_viewings_pg import _setup

    owner, _, (first, _) = _setup(pg_client)
    assert pg_client.post(f"/v1/viewings/{first}/cancel",
                          headers=auth(owner)).status_code == 200
    with pytest.raises(IntegrityError) as caught, pg_migrated_engine.begin() as conn:
        conn.execute(text("UPDATE viewings SET status = 'CONFIRMED' WHERE id = :v"),
                     {"v": first})
    assert caught.value.orig.sqlstate == "23514"
    assert caught.value.orig.diag.constraint_name == "ck_viewings_cancelled_state"


# --- F-09: one conversation per requester and listing ----------------------------


def test_f09_two_simultaneous_starts_make_one_conversation(pg_client, pg_migrated_engine,
                                                          monkeypatch):
    from sqlalchemy.orm import Session as BaseSession

    from app.modules.engagement import router as engagement
    from app.modules.engagement.models import Conversation
    from tests.test_media import OFFER, PROPERTY
    from tests.conftest import verify_ownership

    owner = register_and_login(pg_client, "chat-owner@example.com", "host")
    prop = pg_client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(pg_client, owner, prop)
    listing = pg_client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                             headers=auth(owner)).json()["id"]
    assert pg_client.post(f"/v1/classifieds/{listing}/publish",
                          headers=auth(owner)).status_code == 200
    register_and_login(pg_client, "chat-race@example.com", "guest")
    monkeypatch.setattr(settings, "conversation_daily_quota", 1)

    counted = threading.Event()
    resume = threading.Event()
    first = {"taken": False}
    guard = threading.Lock()

    class GatedSession(BaseSession):
        """Holds the first request right after it has looked for an existing
        conversation — the point where TASK-001 made both requests proceed."""

        def scalar(self, statement, *args, **kwargs):
            value = super().scalar(statement, *args, **kwargs)
            if "FROM conversations" in str(statement):
                with guard:
                    mine = not first["taken"]
                    first["taken"] = True
                if mine:
                    counted.set()
                    assert resume.wait(WAIT)
            return value

    Session = sessionmaker(bind=pg_migrated_engine, class_=GatedSession,
                           expire_on_commit=False)

    def start(n):
        with Session() as db:
            user = db.scalar(select(User).where(User.email == "chat-race@example.com"))
            return engagement.start_conversation(
                listing, engagement.MessageIn(body=f"message {n}"), user, db
            ).conversation.id

    results: dict = {}
    one = threading.Thread(target=_run, args=(results, "one", lambda: start(1)))
    two = threading.Thread(target=_run, args=(results, "two", lambda: start(2)))
    one.start()
    try:
        assert counted.wait(WAIT), "the first start never looked for a conversation"
        two.start()
        assert _someone_waits_on_a_lock(pg_migrated_engine), "the second start did not wait"
    finally:
        resume.set()
        one.join(WAIT)
        if two.ident:
            two.join(WAIT)

    assert results["one"] == results["two"], results
    with pg_migrated_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Conversation)) == 1


def test_f09_the_database_holds_one_active_thread(pg_client, pg_migrated_engine):
    """Even a write that skips the service cannot create a second active
    conversation for the same requester and listing."""
    from sqlalchemy.exc import IntegrityError

    from tests.test_media import OFFER, PROPERTY
    from tests.conftest import verify_ownership

    owner = register_and_login(pg_client, "db-chat-owner@example.com", "host")
    prop = pg_client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(pg_client, owner, prop)
    listing = pg_client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                             headers=auth(owner)).json()["id"]
    pg_client.post(f"/v1/classifieds/{listing}/publish", headers=auth(owner))
    tenant = register_and_login(pg_client, "db-chat@example.com", "guest")
    made = pg_client.post(f"/v1/classifieds/{listing}/conversations",
                          json={"body": "Dzień dobry"}, headers=auth(tenant))
    assert made.status_code in (200, 201), made.text
    with pytest.raises(IntegrityError) as caught, pg_migrated_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO conversations (id, listing_id, requester_user_id, status, "
            "provider_stage, created_at, updated_at, version) "
            "SELECT gen_random_uuid()::text, listing_id, requester_user_id, 'ACTIVE', 'NEW', "
            "now(), now(), 1 FROM conversations LIMIT 1"))
    assert caught.value.orig.sqlstate == "23505"
    assert caught.value.orig.diag.constraint_name == "uq_conversations_active_requester_listing"


def test_f09_two_new_threads_at_quota_one_admit_exactly_one(
    pg_client, pg_migrated_engine, monkeypatch
):
    """Two different listings, quota 1: the daily cap holds under concurrency."""
    from sqlalchemy.orm import Session as BaseSession

    from app.modules.engagement import router as engagement
    from app.modules.engagement.models import Conversation
    from tests.conftest import verify_ownership
    from tests.test_media import OFFER, PROPERTY

    owner = register_and_login(pg_client, "quota-chat-owner@example.com", "host")
    listings = []
    for n in range(2):
        prop = pg_client.post("/v1/properties", json={**PROPERTY, "address": f"ul. Kwota {n}"},
                              headers=auth(owner)).json()["id"]
        verify_ownership(pg_client, owner, prop)
        offer = pg_client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                               headers=auth(owner)).json()["id"]
        assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                              headers=auth(owner)).status_code == 200
        listings.append(offer)
    register_and_login(pg_client, "quota-chat@example.com", "guest")
    monkeypatch.setattr(settings, "conversation_daily_quota", 1)

    counted = threading.Event()
    resume = threading.Event()
    first = {"taken": False}
    guard = threading.Lock()

    class GatedSession(BaseSession):
        def scalar(self, statement, *args, **kwargs):
            value = super().scalar(statement, *args, **kwargs)
            if "count" in str(statement) and "FROM conversations" in str(statement):
                with guard:
                    mine = not first["taken"]
                    first["taken"] = True
                if mine:
                    counted.set()
                    assert resume.wait(WAIT)
            return value

    Session = sessionmaker(bind=pg_migrated_engine, class_=GatedSession,
                           expire_on_commit=False)

    def start(listing):
        with Session() as db:
            user = db.scalar(select(User).where(User.email == "quota-chat@example.com"))
            return engagement.start_conversation(
                listing, engagement.MessageIn(body="Dzień dobry"), user, db
            ).conversation.id

    results: dict = {}
    one = threading.Thread(target=_run, args=(results, "one", lambda: start(listings[0])))
    two = threading.Thread(target=_run, args=(results, "two", lambda: start(listings[1])))
    one.start()
    try:
        assert counted.wait(WAIT), "the first start never counted its quota"
        two.start()
        assert _someone_waits_on_a_lock(pg_migrated_engine), "the second start did not wait"
    finally:
        resume.set()
        one.join(WAIT)
        if two.ident:
            two.join(WAIT)

    assert isinstance(results["one"], str)
    assert isinstance(results["two"], HTTPException) and results["two"].status_code == 429
    with pg_migrated_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Conversation)) == 1
