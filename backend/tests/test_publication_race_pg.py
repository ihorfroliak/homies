"""Publication cannot outlive a revoke (TASK-001 F-04) — real PostgreSQL.

Publication, authority revocation and space archiving all take the property's
coordination lock (app/modules/properties/coordination.py). Each test pins one
transaction at an exact point with events, then checks the other side either
waited (observed in pg_stat_activity, not assumed from timing) or found the
state the first one committed.

Against the pre-TASK-002 code, which checked the authority and wrote `active`
with nothing held in between, every test here fails.
"""

import threading
import time

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.properties import authority
from app.modules.properties.models import PropertyAuthority, PropertyAuthorityScope, Space
from tests.conftest import admin_login, auth, register_and_login, verify_ownership

PROPERTY = {"property_type": "apartment", "city": "Łódź", "municipality": "Łódź",
            "address": "ul. Wyścigowa 4", "area_m2": 48, "rooms": 2, "capacity": 2}
OFFER = {"title": "Wyścig", "rent_amount": 240000, "min_term_months": 12,
         "contact_mode": "message"}

WAIT = 15


def _draft_listing(pg_client):
    owner = register_and_login(pg_client, "race-publisher@example.com", "host")
    prop = pg_client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(pg_client, owner, prop)
    offer = pg_client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                           headers=auth(owner)).json()["id"]
    return owner, prop, offer


def _authority_id(engine, prop):
    with engine.connect() as conn:
        return conn.scalar(select(PropertyAuthority.id).where(PropertyAuthority.property_id == prop))


def _status(engine, offer):
    with engine.connect() as conn:
        return conn.scalar(text("SELECT status FROM classified_offers WHERE id = :o"), {"o": offer})


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


class _Reached(threading.Event):
    """Set when the publisher is held; `pid` is its PostgreSQL backend, so a
    waiter can be shown to wait on THAT transaction (TASK-006 N-03)."""

    pid: int | None = None


def _pause_publication_at(monkeypatch, point: str):
    """Hold the publishing thread at a named point.

    "precheck" — right after the lock-free authority check, before the
    property lock. "protected" — right after authorize_for_mutation has
    decided under the property lock and the chain's FOR SHARE locks (TASK-004;
    in TASK-002 this was the second `require` call)."""
    reached = _Reached()
    resume = threading.Event()

    if point == "precheck":
        original = authority.require
        calls = {"n": 0}

        def gated(*args, **kwargs):
            result = original(*args, **kwargs)
            if kwargs.get("verified"):
                calls["n"] += 1
                if calls["n"] == 1:
                    reached.pid = args[0].scalar(text("SELECT pg_backend_pid()"))
                    reached.set()
                    assert resume.wait(WAIT)
            return result

        monkeypatch.setattr(authority, "require", gated)
    else:
        decided = authority.authorize_for_mutation

        def gated_decision(*args, **kwargs):
            decided(*args, **kwargs)
            reached.pid = args[0].scalar(text("SELECT pg_backend_pid()"))
            reached.set()
            assert resume.wait(WAIT)

        monkeypatch.setattr(authority, "authorize_for_mutation", gated_decision)
    return reached, resume


def test_a_revoke_committed_during_publication_wins(pg_client, pg_migrated_engine, monkeypatch):
    """Revoke commits after publication's first check: publication, re-checking
    under the lock, must refuse — the listing never goes public."""
    owner, prop, offer = _draft_listing(pg_client)
    admin = admin_login(pg_client)
    aid = _authority_id(pg_migrated_engine, prop)
    reached, resume = _pause_publication_at(monkeypatch, "precheck")

    result = {}
    worker = threading.Thread(target=lambda: result.update(
        publish=pg_client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))))
    worker.start()
    try:
        assert reached.wait(WAIT), "publication never reached its first check"
        revoked = pg_client.post(f"/v1/admin/property-authorities/{aid}/revoke",
                                 headers=auth(admin))
        assert revoked.status_code == 200, revoked.text
    finally:
        resume.set()
        worker.join(WAIT)

    assert result["publish"].status_code in (403, 404), result["publish"].text
    assert _status(pg_migrated_engine, offer) == "draft"
    assert pg_client.get(f"/v1/classifieds/{offer}").status_code == 404


def test_a_revoke_arriving_during_publication_waits_and_takes_it_down(
    pg_client, pg_migrated_engine, monkeypatch
):
    """Publication holds the lock: revoke must wait for it, then pause the
    listing it just published — not leave it live on a revoked right."""
    owner, prop, offer = _draft_listing(pg_client)
    admin = admin_login(pg_client)
    aid = _authority_id(pg_migrated_engine, prop)
    reached, resume = _pause_publication_at(monkeypatch, "protected")

    result = {}
    publisher = threading.Thread(target=lambda: result.update(
        publish=pg_client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))))
    revoker = threading.Thread(target=lambda: result.update(
        revoke=pg_client.post(f"/v1/admin/property-authorities/{aid}/revoke",
                              headers=auth(admin))))
    publisher.start()
    try:
        assert reached.wait(WAIT), "publication never re-checked under the lock"
        revoker.start()
        assert _someone_waits_on_a_lock(pg_migrated_engine), "revoke did not wait"
        assert "revoke" not in result, "revoke finished while publication held the lock"
    finally:
        resume.set()
        publisher.join(WAIT)
        if revoker.is_alive() or revoker.ident:
            revoker.join(WAIT)

    assert result["publish"].status_code == 200, result["publish"].text
    assert result["revoke"].status_code == 200, result["revoke"].text
    assert result["revoke"].json()["paused_offers"] == [offer]
    assert _status(pg_migrated_engine, offer) == "paused"
    assert pg_client.get(f"/v1/classifieds/{offer}").status_code == 404


def test_archiving_the_space_during_publication_waits_and_takes_it_down(
    pg_client, pg_migrated_engine, monkeypatch
):
    owner, prop, offer = _draft_listing(pg_client)
    with pg_migrated_engine.connect() as conn:
        space = conn.scalar(select(Space.id).where(Space.property_id == prop))
    reached, resume = _pause_publication_at(monkeypatch, "protected")

    result = {}
    publisher = threading.Thread(target=lambda: result.update(
        publish=pg_client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))))
    archiver = threading.Thread(target=lambda: result.update(
        archive=pg_client.post(f"/v1/spaces/{space}/archive", headers=auth(owner))))
    publisher.start()
    try:
        assert reached.wait(WAIT), "publication never re-checked under the lock"
        archiver.start()
        assert _someone_waits_on_a_lock(pg_migrated_engine), "archive did not wait"
    finally:
        resume.set()
        publisher.join(WAIT)
        if archiver.ident:
            archiver.join(WAIT)

    assert result["publish"].status_code == 200, result["publish"].text
    assert result["archive"].status_code == 200, result["archive"].text
    assert _status(pg_migrated_engine, offer) == "paused"


def test_an_archived_listing_is_not_republished(pg_client, pg_migrated_engine):
    """The conditional UPDATE refuses any status outside PUBLISHABLE_FROM."""
    owner, prop, offer = _draft_listing(pg_client)
    with pg_migrated_engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET status = 'archived' WHERE id = :o"),
                     {"o": offer})
    response = pg_client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    assert response.status_code == 409, response.text
    assert _status(pg_migrated_engine, offer) == "archived"


@pytest.mark.parametrize("second_verified", [True, False])
def test_revoke_keeps_listings_backed_by_another_valid_right(
    pg_client, pg_migrated_engine, second_verified
):
    """Unchanged behaviour under the new lock: a second in-force VERIFIED
    PUBLISH_LISTING authority keeps the listing up; an unverified one does not."""
    owner, prop, offer = _draft_listing(pg_client)
    assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                          headers=auth(owner)).status_code == 200
    first = _authority_id(pg_migrated_engine, prop)
    with Session(pg_migrated_engine) as db:
        existing = db.get(PropertyAuthority, first)
        second = PropertyAuthority(
            property_id=prop,
            holder_legal_party_id=existing.holder_legal_party_id,
            authority_type="OWNER",
            status="ACTIVE",
            verification_state="VERIFIED" if second_verified else "UNVERIFIED",
            effective_from=existing.effective_from,
            created_by_user_id=existing.created_by_user_id,
        )
        db.add(second)
        db.flush()
        db.add(PropertyAuthorityScope(property_authority_id=second.id, scope="PUBLISH_LISTING"))
        db.commit()
    admin = admin_login(pg_client)
    revoked = pg_client.post(f"/v1/admin/property-authorities/{first}/revoke",
                             headers=auth(admin))
    assert revoked.status_code == 200, revoked.text
    expected = "active" if second_verified else "paused"
    assert _status(pg_migrated_engine, offer) == expected
