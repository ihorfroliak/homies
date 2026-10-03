"""GROWTH-001 — measurement facts in the outbox.

Each fact the operational tables overwrite is written once, in the changing
transaction, with exactly its allowlisted keys (ids, closed codes, database
instants) and nothing private; nothing is routed to anyone.
"""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.modules.engagement.models import Viewing
from app.modules.events import facts
from app.modules.events import service as events
from app.modules.events.models import DomainEvent, Notification
from app.modules.properties import freshness
from app.modules.properties.models import ClassifiedOffer
from app.modules.trust import decisions
from tests.conftest import TestingSession, auth
from tests.test_engagement_safety import _decide, _request, _viewing_ready
from tests.test_message_moderation import CANARY, _thread
from tests.test_reports_moderation import _listing, _me, _moderator, _verified

FORBIDDEN = ("address", "body", "note", "email", "phone", "latitude", "longitude",
             "rent_amount", "explanation", "reason_text", "requester_note")


def _facts(event_type, correlation_id=None):
    with TestingSession() as db:
        query = select(DomainEvent).where(DomainEvent.event_type == event_type)
        if correlation_id:
            query = query.where(DomainEvent.correlation_id == correlation_id)
        return [e.payload for e in db.scalars(query.order_by(DomainEvent.occurred_at))]


def test_every_fact_is_unrouted_and_has_a_pinned_shape():
    assert set(facts.FACTS).isdisjoint(events.ROUTING)
    assert set(facts.PAYLOAD_KEYS) == set(facts.FACTS)
    for keys in facts.PAYLOAD_KEYS.values():
        assert not any(k in FORBIDDEN for k in keys)


def test_listing_status_changes_are_recorded_with_their_reason(client):
    owner, offer = _listing(client)  # published: draft → active
    assert client.post(f"/v1/classifieds/{offer}/pause", headers=auth(owner)).status_code == 200
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    moderator = _moderator(client)
    assert _decide(client, moderator, "LISTING", offer, "CONTENT_EDIT_REQUIRED",
                   "SCAM").status_code == 201
    changes = _facts(facts.LISTING_STATUS_CHANGED, offer)
    assert [(c["from_status"], c["to_status"], c["reason_code"]) for c in changes] == [
        ("draft", "active", "PUBLISHED"), ("active", "paused", "OWNER_PAUSE"),
        ("paused", "active", "PUBLISHED"), ("active", "paused", "MODERATION_HOLD")]
    assert [c["public_generation"] for c in changes] == [1, 1, 2, 2]
    assert all(tuple(c) == facts.PAYLOAD_KEYS[facts.LISTING_STATUS_CHANGED] for c in changes)


def test_the_stale_sweep_and_its_reconfirmation_are_recorded(client):
    owner, offer = _listing(client)
    with TestingSession() as db:
        db.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == offer).values(
            last_confirmed_available_at=datetime.now(timezone.utc) - timedelta(days=30)))
        db.commit()
    with TestingSession() as db:
        assert freshness.sweep(db).staled == [offer]
        db.commit()
    assert client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner)).status_code == 200
    changes = _facts(facts.LISTING_STATUS_CHANGED, offer)
    assert [(c["from_status"], c["to_status"], c["reason_code"]) for c in changes][-2:] == [
        ("active", "stale", "STALE_SWEEP"), ("stale", "active", "RECONFIRMED")]


def test_viewing_transitions_are_recorded_with_who_cancelled(client):
    owner, tenant, offer, conv, _m = _thread(client)
    day = _viewing_ready(client, owner, offer)
    confirmed = _request(client, tenant, offer, day, 10).json()["id"]
    assert client.post(f"/v1/viewings/{confirmed}/confirm", headers=auth(owner)).status_code == 200
    second = _verified(client, "second")
    declined = _request(client, second, offer, day, 11).json()["id"]
    assert client.post(f"/v1/viewings/{declined}/decline", headers=auth(owner)).status_code == 200
    third = _verified(client, "third")
    by_provider = _request(client, third, offer, day, 12).json()["id"]
    assert client.post(f"/v1/viewings/{by_provider}/cancel",
                       headers=auth(owner)).status_code == 200
    fourth = _verified(client, "fourth")
    by_homies = _request(client, fourth, offer, day, 13).json()["id"]

    requested = {p["viewing_id"]: p for p in _facts(facts.VIEWING_REQUESTED)}
    assert set(requested) == {confirmed, declined, by_provider, by_homies}
    assert {p["booking_mode"] for p in requested.values()} == {"REQUEST_APPROVAL"}
    responded = {p["viewing_id"]: p["to_status"] for p in _facts(facts.VIEWING_RESPONDED)}
    assert responded == {confirmed: "CONFIRMED", declined: "DECLINED"}

    moderator = _moderator(client)
    held = _decide(client, moderator, "LISTING", offer, "VISIBILITY_LIMITED", "SAFETY",
                   close_engagement=True)
    assert held.status_code == 201
    cancelled = {p["viewing_id"]: p for p in _facts(facts.VIEWING_CANCELLED)}
    assert cancelled[by_provider]["cancelled_by"] == "PROVIDER"
    assert cancelled[by_homies]["cancelled_by"] == "HOMIES"
    assert cancelled[by_homies]["moderation_decision_id"] == held.json()["decision_id"]
    assert cancelled[confirmed]["prior_status"] == "CONFIRMED"
    assert cancelled[by_provider]["moderation_decision_id"] is None

    # the requester's own cancel
    _o2, tenant2, offer2, _c2, _m2 = _thread(client)
    day2 = _viewing_ready(client, _o2, offer2)
    mine = _request(client, tenant2, offer2, day2, 10).json()["id"]
    assert client.post(f"/v1/viewings/{mine}/cancel", headers=auth(tenant2)).status_code == 200
    assert {p["viewing_id"]: p["cancelled_by"] for p in _facts(
        facts.VIEWING_CANCELLED)}[mine] == "REQUESTER"


def test_the_outcome_and_the_lead_stage_are_recorded(client):
    owner, tenant, offer, conv, _m = _thread(client)
    with TestingSession() as db:
        start = datetime.now(timezone.utc) - timedelta(days=1)
        v = Viewing(listing_id=offer, requester_user_id=_me(client, tenant), starts_at=start,
                    ends_at=start + timedelta(minutes=30), status="CONFIRMED")
        db.add(v)
        db.commit()
        viewing_id = v.id
    resp = client.post(f"/v1/viewings/{viewing_id}/outcome", json={"outcome": "COMPLETED"},
                       headers=auth(owner))
    assert resp.status_code == 200
    [outcome] = _facts(facts.VIEWING_OUTCOME_RECORDED)
    assert (outcome["viewing_id"], outcome["outcome"]) == (viewing_id, "COMPLETED")

    assert client.post(f"/v1/conversations/{conv}/stage", json={"provider_stage": "VIEWING"},
                       headers=auth(owner)).status_code == 200
    assert client.post(f"/v1/conversations/{conv}/stage", json={"provider_stage": "VIEWING"},
                       headers=auth(owner)).status_code == 200  # unchanged: no fact
    stages = _facts(facts.CONVERSATION_STAGE_CHANGED, conv)
    assert [(s["from_stage"], s["to_stage"]) for s in stages] == [("REPLIED", "VIEWING")]


def test_facts_carry_nothing_private_and_notify_nobody(client):
    owner, tenant, offer, conv, _m = _thread(client)
    day = _viewing_ready(client, owner, offer)
    _request(client, tenant, offer, day, 10)
    moderator = _moderator(client)
    _decide(client, moderator, "LISTING", offer, "VISIBILITY_LIMITED", "SCAM",
            close_engagement=True, explanation="zx-explanation-canary")
    with TestingSession() as db:
        rows = db.scalars(select(DomainEvent).where(DomainEvent.event_type.in_(facts.FACTS)))
        payloads = [r.payload for r in rows]
        assert payloads
        assert not db.scalars(select(Notification).where(
            Notification.event_type.in_(facts.FACTS))).all()
    flat = json.dumps(payloads)
    assert CANARY not in flat and "zx-explanation-canary" not in flat
    assert "ul." not in flat  # no address fragment


def test_a_rolled_back_change_leaves_no_fact(client, monkeypatch):
    owner, offer = _listing(client)
    before = len(_facts(facts.LISTING_STATUS_CHANGED, offer))

    def boom(*a, **k):
        raise decisions.InvalidDecision("refused late")
    monkeypatch.setattr(decisions, "_resolve_reports", boom)
    moderator = _moderator(client)
    assert _decide(client, moderator, "LISTING", offer, "VISIBILITY_LIMITED",
                   "SCAM").status_code == 422
    assert len(_facts(facts.LISTING_STATUS_CHANGED, offer)) == before
