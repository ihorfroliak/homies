"""TASK-015 Slice 4b — engagement safety (SQLite, through HTTP).

close_engagement (only VISIBILITY_LIMITED with SCAM, FAKE or SAFETY): the
listing's ACTIVE conversations close with a neutral SYSTEM line and its future
REQUESTED/CONFIRMED viewings are cancelled — history untouched. A hold refuses
viewing confirmation. CONVERSATION FEATURE_RESTRICTED closes one thread and
bars its requester from a new one for the same public generation (G-14).
MEDIA CONTENT_REMOVED restricts a photo without destroying anything. Privacy
canaries over every surface. Races: test_engagement_safety_pg.py.
"""

import json
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, update

from app.core.audit import AuditLog
from app.modules.alerts.models import UserNotification
from app.modules.engagement.models import Conversation, Message, Viewing
from app.modules.events.models import DomainEvent
from app.modules.identity.models import User
from app.modules.media import storage
from app.modules.media.models import FileObject, ListingMedia, MediaAsset
from app.modules.trust import decisions, effects, notices
from app.modules.trust.models import ModerationDecision
from tests.conftest import TestingSession, auth
from tests.test_media import _approved, _attach
from tests.test_message_moderation import _thread
from tests.test_reports_moderation import _me, _moderator, _verified

WARSAW = ZoneInfo("Europe/Warsaw")
CANARY = "zx-canary-moderator-explanation-4b"


def _decide(client, token, target_type, target_id, action, reason, head=None, **extra):
    return client.post("/v1/admin/moderation/decisions", json={
        "target_type": target_type, "target_id": target_id, "action": action,
        "reason_code": reason, "expected_head_decision_id": head, **extra},
        headers=auth(token))


def _day(offset=5) -> date:
    return datetime.now(WARSAW).date() + timedelta(days=offset)


def _viewing_ready(client, owner, offer, day=None):
    day = day or _day()
    assert client.put(f"/v1/classifieds/{offer}/viewing-settings", json={
        "booking_mode": "REQUEST_APPROVAL", "duration_minutes": 30,
        "minimum_notice_minutes": 0, "max_concurrent_bookings": 5},
        headers=auth(owner)).status_code == 200
    assert client.post(f"/v1/classifieds/{offer}/viewing-windows", json={
        "window_type": "ONE_OFF", "local_date": day.isoformat(), "local_start_time": "10:00",
        "local_end_time": "14:00"}, headers=auth(owner)).status_code == 201
    return day


def _slot(day, hour, minute=0) -> str:
    when = datetime.combine(day, time(hour, minute), WARSAW).astimezone(timezone.utc)
    return when.isoformat().replace("+00:00", "Z")


def _request(client, token, offer, day, hour, minute=0):
    return client.post(f"/v1/classifieds/{offer}/viewings",
                       json={"starts_at": _slot(day, hour, minute)}, headers=auth(token))


def _past_viewing(offer, user_id, status, days_ago=2):
    start = datetime.now(timezone.utc) - timedelta(days=days_ago)
    with TestingSession() as db:
        v = Viewing(listing_id=offer, requester_user_id=user_id, starts_at=start,
                    ends_at=start + timedelta(minutes=30), status=status)
        db.add(v)
        db.commit()
        return v.id


def _status(model, row_id):
    with TestingSession() as db:
        return db.get(model, row_id).status


def _messages(client, token, conv):
    resp = client.get(f"/v1/conversations/{conv}", headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["messages"]


def _head(target_type, target_id):
    with TestingSession() as db:
        from app.modules.trust import hold
        current = hold.head(db, target_type, target_id)
        return current.id if current else None


# --- close_engagement: who may ask for it ----------------------------------------

@pytest.mark.parametrize("action,reason", [
    ("CONTENT_EDIT_REQUIRED", "SCAM"),        # correctable holds keep engagement
    ("VISIBILITY_LIMITED", "MISLEADING_PRICE"),
    ("VISIBILITY_LIMITED", "DISCRIMINATION"),
    ("NO_ACTION", "NOT_A_VIOLATION"),
])
def test_close_engagement_is_refused_outside_its_three_reasons(client, action, reason):
    _o, _t, offer, conv, _m = _thread(client)
    moderator = _moderator(client)
    resp = _decide(client, moderator, "LISTING", offer, action, reason, close_engagement=True)
    assert resp.status_code == 422 and "close_engagement" in resp.json()["detail"]
    assert _status(Conversation, conv) == "ACTIVE"
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(ModerationDecision)) == 0


@pytest.mark.parametrize("target_type", ["MESSAGE", "CONVERSATION", "MEDIA"])
def test_close_engagement_is_for_listings_and_listing_id_for_photos(client, target_type):
    moderator = _moderator(client)
    resp = _decide(client, moderator, target_type, "x", "CONTENT_REMOVED", "SCAM",
                   close_engagement=True)
    assert resp.status_code == 422
    resp = _decide(client, moderator, "LISTING", "x", "VISIBILITY_LIMITED", "SCAM",
                   listing_id="x")
    assert resp.status_code == 422


@pytest.mark.parametrize("reason", sorted(effects.CLOSE_ENGAGEMENT_REASONS))
def test_close_engagement_closes_threads_and_cancels_only_future_viewings(client, reason):
    owner, tenant, offer, conv, _m = _thread(client)
    day = _viewing_ready(client, owner, offer)
    requested = _request(client, tenant, offer, day, 10)
    assert requested.status_code == 201, requested.text
    second = _verified(client, "second")
    confirmed = _request(client, second, offer, day, 11)
    assert client.post(f"/v1/viewings/{confirmed.json()['id']}/confirm",
                       headers=auth(owner)).status_code == 200
    third = _verified(client, "third")
    gone = _request(client, third, offer, day, 12)
    assert client.post(f"/v1/viewings/{gone.json()['id']}/cancel",
                       headers=auth(third)).status_code == 200
    tenant_id = _me(client, tenant)
    completed = _past_viewing(offer, tenant_id, "COMPLETED")
    past_confirmed = _past_viewing(offer, _me(client, second), "CONFIRMED", days_ago=1)
    no_show = _past_viewing(offer, _me(client, third), "NO_SHOW", days_ago=3)

    moderator = _moderator(client)
    resp = _decide(client, moderator, "LISTING", offer, "VISIBILITY_LIMITED", reason,
                   close_engagement=True, explanation=CANARY)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["closed_conversations"], body["cancelled_viewings"]) == (1, 2)

    assert _status(Conversation, conv) == "CLOSED"
    last = _messages(client, tenant, conv)[-1]
    assert (last["message_type"], last["body"]) == ("SYSTEM", effects.CLOSED_BY_HOMIES)
    assert last["sender_user_id"] is None
    refused = client.post(f"/v1/conversations/{conv}/messages", json={"body": "hello?"},
                          headers=auth(tenant))
    assert refused.status_code == 409 and refused.json()["detail"].startswith(
        "CONVERSATION_CLOSED")
    assert client.post(f"/v1/conversations/{conv}/messages", json={"body": "x"},
                       headers=auth(owner)).status_code == 409

    assert _status(Viewing, requested.json()["id"]) == "CANCELLED"
    assert _status(Viewing, confirmed.json()["id"]) == "CANCELLED"
    for vid, expected in ((completed, "COMPLETED"), (past_confirmed, "CONFIRMED"),
                          (no_show, "NO_SHOW"), (gone.json()["id"], "CANCELLED")):
        assert _status(Viewing, vid) == expected

    mine = {v["id"]: v for v in client.get("/v1/me/viewings", headers=auth(tenant)).json()}
    assert mine[requested.json()["id"]]["cancelled_by_homies"] is True
    assert mine[completed]["cancelled_by_homies"] is False
    theirs = {v["id"]: v for v in client.get("/v1/me/viewings", headers=auth(third)).json()}
    assert theirs[gone.json()["id"]]["cancelled_by_homies"] is False  # their own cancel
    provider = {v["id"]: v for v in client.get(f"/v1/classifieds/{offer}/viewings",
                                               headers=auth(owner)).json()}
    assert provider[confirmed.json()["id"]]["cancelled_by_homies"] is True

    with TestingSession() as db:
        sent = db.scalars(select(UserNotification).where(
            UserNotification.notification_type == notices.VIEWING_CANCELLED)).all()
        assert sorted(n.data["viewing_id"] for n in sent) == sorted(
            [requested.json()["id"], confirmed.json()["id"]])
        assert all(set(n.data) == set(notices.VIEWING_NOTICE_DATA_KEYS) for n in sent)
        assert all(n.category == "TRANSACTIONAL" for n in sent)


def test_a_new_thread_after_close_engagement_needs_a_republish(client):
    owner, tenant, offer, conv, _m = _thread(client)
    moderator = _moderator(client)
    held = _decide(client, moderator, "LISTING", offer, "VISIBILITY_LIMITED", "FAKE",
                   close_engagement=True)
    assert held.status_code == 201
    assert client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "again"},
                       headers=auth(tenant)).status_code == 404  # held → not public
    released = _decide(client, moderator, "LISTING", offer, "NO_ACTION",
                       "REINSTATED_DECISION_ERROR", head=held.json()["decision_id"])
    assert released.status_code == 201
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    again = client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "again"},
                        headers=auth(tenant))
    assert again.status_code == 201 and again.json()["conversation"]["id"] != conv
    assert _status(Conversation, conv) == "CLOSED"  # never reopened


# --- a hold without close_engagement --------------------------------------------

def test_a_hold_keeps_engagement_but_refuses_viewing_confirmation(client):
    owner, tenant, offer, conv, _m = _thread(client)
    day = _viewing_ready(client, owner, offer)
    viewing = _request(client, tenant, offer, day, 10).json()["id"]
    second = _verified(client, "decliner")
    other = _request(client, second, offer, day, 11).json()["id"]
    moderator = _moderator(client)
    held = _decide(client, moderator, "LISTING", offer, "CONTENT_EDIT_REQUIRED", "SCAM")
    assert held.status_code == 201

    assert _status(Conversation, conv) == "ACTIVE"
    assert client.post(f"/v1/conversations/{conv}/messages", json={"body": "still here"},
                       headers=auth(tenant)).status_code == 201
    refused = client.post(f"/v1/viewings/{viewing}/confirm", headers=auth(owner))
    assert refused.status_code == 409 and refused.json()["detail"].startswith("LISTING_HELD")
    assert _status(Viewing, viewing) == "REQUESTED"
    assert client.post(f"/v1/viewings/{other}/decline", headers=auth(owner)).status_code == 200
    assert client.post(f"/v1/viewings/{viewing}/cancel", headers=auth(tenant)).status_code == 200
    third = _verified(client, "late")
    assert _request(client, third, offer, day, 12).status_code == 404  # paused: not public

    # Released: confirmation works again (the listing itself still waits for
    # its owner to republish; confirmation only needed it not to be held).
    fourth = _verified(client, "after")
    released = _decide(client, moderator, "LISTING", offer, "NO_ACTION", "REINSTATED_REMEDIED",
                       head=held.json()["decision_id"])
    assert released.status_code == 201
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    pending = _request(client, fourth, offer, day, 13).json()["id"]
    assert client.post(f"/v1/viewings/{pending}/confirm", headers=auth(owner)).status_code == 200


# --- CONVERSATION FEATURE_RESTRICTED ---------------------------------------------

def test_feature_restricted_closes_one_thread_and_bars_recontact_for_the_generation(client):
    owner, tenant, offer, conv, _m = _thread(client)
    bystander = _verified(client, "bystander")
    other = client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "Hi"},
                        headers=auth(bystander)).json()["conversation"]["id"]
    moderator = _moderator(client)
    resp = _decide(client, moderator, "CONVERSATION", conv, "FEATURE_RESTRICTED", "HARASSMENT",
                   explanation=CANARY)
    assert resp.status_code == 201, resp.text
    assert resp.json()["closed_conversations"] == 1
    assert _status(Conversation, conv) == "CLOSED"
    assert _status(Conversation, other) == "ACTIVE"  # one thread, not the listing
    for token in (tenant, owner):
        last = _messages(client, token, conv)[-1]
        assert (last["message_type"], last["body"]) == ("SYSTEM", effects.CLOSED_BY_HOMIES)
        assert client.post(f"/v1/conversations/{conv}/messages", json={"body": "?"},
                           headers=auth(token)).status_code == 409

    blocked = client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "new"},
                          headers=auth(tenant))
    assert blocked.status_code == 409 and blocked.json()["detail"].startswith(
        "RECONTACT_BLOCKED")
    assert client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "more"},
                       headers=auth(bystander)).status_code == 201  # continues their thread

    # A new public generation lifts it (G-14): pause, republish.
    assert client.post(f"/v1/classifieds/{offer}/pause", headers=auth(owner)).status_code == 200
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    fresh = client.post(f"/v1/classifieds/{offer}/conversations", json={"body": "new"},
                        headers=auth(tenant))
    assert fresh.status_code == 201 and fresh.json()["conversation"]["id"] != conv


def test_a_conversation_restriction_is_terminal_and_dismissals_come_first(client):
    _o, _t, _offer, conv, _m = _thread(client)
    moderator = _moderator(client)
    wrong = _decide(client, moderator, "CONVERSATION", conv, "NO_ACTION", "SCAM")
    assert wrong.status_code == 422
    dismissed = _decide(client, moderator, "CONVERSATION", conv, "NO_ACTION", "NOT_A_VIOLATION")
    assert dismissed.status_code == 201 and _status(Conversation, conv) == "ACTIVE"
    head = dismissed.json()["decision_id"]
    restricted = _decide(client, moderator, "CONVERSATION", conv, "FEATURE_RESTRICTED", "SPAM",
                         head=head)
    assert restricted.status_code == 201
    head = restricted.json()["decision_id"]
    for action, reason in (("NO_ACTION", "NOT_A_VIOLATION"), ("FEATURE_RESTRICTED", "SCAM"),
                           ("NO_ACTION", "REINSTATED_DECISION_ERROR")):
        again = _decide(client, moderator, "CONVERSATION", conv, action, reason, head=head)
        assert again.status_code == 422, (action, reason)
    stale = _decide(client, moderator, "CONVERSATION", conv, "FEATURE_RESTRICTED", "SPAM")
    assert stale.status_code == 409 and stale.json()["detail"].startswith("STALE_HEAD")
    for action in ("CONTENT_REMOVED", "VISIBILITY_LIMITED"):
        assert _decide(client, moderator, "CONVERSATION", conv, action, "SCAM",
                       head=head).status_code == 422
    assert _decide(client, moderator, "CONVERSATION", "missing-conv", "FEATURE_RESTRICTED",
                   "SCAM").status_code == 404


def test_participants_and_managers_cannot_restrict_their_own_conversation(client):
    owner, tenant, _offer, conv, _m = _thread(client)
    with TestingSession() as db:
        db.execute(update(User).where(User.id.in_([_me(client, tenant), _me(client, owner)]))
                   .values(role="admin"))
        db.commit()
    for token in (tenant, owner):
        resp = _decide(client, token, "CONVERSATION", conv, "FEATURE_RESTRICTED", "SCAM")
        assert resp.status_code == 403 and "CONFLICT_OF_INTEREST" in resp.json()["detail"]
    assert _status(Conversation, conv) == "ACTIVE"
    plain = _verified(client, "not-a-moderator")
    assert _decide(client, plain, "CONVERSATION", conv, "FEATURE_RESTRICTED",
                   "SCAM").status_code == 403


# --- MEDIA CONTENT_REMOVED → RESTRICTED -----------------------------------------

def _photo_listing(client):
    owner, tenant, offer, conv, _m = _thread(client)
    with TestingSession() as db:
        from app.modules.properties.models import ClassifiedOffer
        prop = db.get(ClassifiedOffer, offer).property_id
    first = _approved(client, owner, prop)
    second = _approved(client, owner, prop)
    assert _attach(client, owner, offer, first, cover=True).status_code == 201
    assert _attach(client, owner, offer, second, order=1).status_code == 201
    return owner, tenant, offer, prop, first, second


def test_a_restricted_photo_disappears_publicly_and_nothing_is_destroyed(client):
    owner, _tenant, offer, prop, cover, other = _photo_listing(client)
    with TestingSession() as db:
        file_id = db.get(MediaAsset, cover).file_id
        key = db.get(FileObject, file_id).storage_key
    assert client.get(f"/v1/media/{cover}").status_code == 200
    moderator = _moderator(client)
    target = client.get(f"/v1/admin/moderation/targets/LISTING/{offer}",
                        headers=auth(moderator)).json()
    assert [m["media_asset_id"] for m in target["listing"]["media"]] == [cover, other]

    resp = _decide(client, moderator, "MEDIA", cover, "CONTENT_REMOVED", "STOLEN_MEDIA",
                   listing_id=offer, explanation=CANARY)
    assert resp.status_code == 201, resp.text

    assert client.get(f"/v1/media/{cover}").status_code == 404
    public = client.get(f"/v1/classifieds/{offer}").json()
    assert [m["id"] for m in public["media"]] == [other]
    with TestingSession() as db:
        assert db.get(MediaAsset, cover).moderation_state == "RESTRICTED"
        assert db.get(ListingMedia, (offer, cover)) is not None  # still linked
        assert db.get(FileObject, file_id) is not None
    assert storage.storage().get(key)  # the bytes are kept
    owned = {m["id"]: m for m in client.get(f"/v1/properties/{prop}/media",
                                            headers=auth(owner)).json()}
    assert owned[cover]["moderation_state"] == "RESTRICTED"
    again = _attach(client, owner, offer, cover, cover=True)
    assert again.status_code == 409

    with TestingSession() as db:
        sent = db.scalars(select(UserNotification).where(
            UserNotification.notification_type == notices.MEDIA_RESTRICTED)).all()
        assert sent and all(set(n.data) == set(notices.MEDIA_NOTICE_DATA_KEYS) for n in sent)
        assert {n.data["media_asset_id"] for n in sent} == {cover}

    detail = client.get(f"/v1/admin/moderation/targets/MEDIA/{cover}", headers=auth(moderator))
    assert detail.status_code == 200
    assert (detail.json()["moderation_state"], detail.json()["listing_ids"],
            detail.json()["head"]["id"]) == ("RESTRICTED", [offer], resp.json()["decision_id"])
    content = client.get(f"/v1/admin/moderation/media/{cover}/content", headers=auth(moderator))
    assert content.status_code == 200 and content.content
    assert content.headers["cache-control"] == "private, no-store"
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "moderation.media_viewed", AuditLog.entity_id == cover)) == 1
    assert client.get(f"/v1/admin/moderation/media/{cover}/content",
                      headers=auth(owner)).status_code == 403


def test_a_photo_restriction_is_terminal_and_checks_its_listing(client):
    owner, _t, offer, _prop, cover, other = _photo_listing(client)
    moderator = _moderator(client)
    other_offer = _photo_listing(client)[2]  # another listing, with its own photos
    wrong = _decide(client, moderator, "MEDIA", cover, "CONTENT_REMOVED", "SCAM",
                    listing_id=other_offer)
    assert wrong.status_code == 422 and "not on that listing" in wrong.json()["detail"]
    done = _decide(client, moderator, "MEDIA", cover, "CONTENT_REMOVED", "SCAM")
    assert done.status_code == 201
    again = _decide(client, moderator, "MEDIA", cover, "NO_ACTION", "NOT_A_VIOLATION",
                    head=done.json()["decision_id"])
    assert again.status_code == 422
    assert _decide(client, moderator, "MEDIA", other, "FEATURE_RESTRICTED",
                   "SCAM").status_code == 422
    with TestingSession() as db:
        db.execute(update(User).where(User.id == _me(client, owner)).values(role="admin"))
        db.commit()
    conflicted = _decide(client, owner, "MEDIA", other, "CONTENT_REMOVED", "SCAM")
    assert conflicted.status_code == 403
    assert _decide(client, moderator, "MEDIA", "missing", "CONTENT_REMOVED",
                   "SCAM").status_code == 404


# --- privacy ---------------------------------------------------------------------

def test_no_explanation_reason_or_reporter_reaches_participants_events_or_audit(client):
    owner, tenant, offer, conv, _m = _thread(client)
    moderator = _moderator(client)
    assert _decide(client, moderator, "CONVERSATION", conv, "FEATURE_RESTRICTED", "SAFETY",
                   explanation=CANARY).status_code == 201
    _o2, tenant2, offer2, conv2, _m2 = _thread(client)
    assert _decide(client, moderator, "LISTING", offer2, "VISIBILITY_LIMITED", "SAFETY",
                   close_engagement=True, explanation=CANARY).status_code == 201
    with TestingSession() as db:
        surfaces = {
            "messages": [m.body for m in db.scalars(select(Message).where(
                Message.message_type == "SYSTEM"))],
            "notices": [n.data for n in db.scalars(select(UserNotification))],
            "events": [e.payload for e in db.scalars(select(DomainEvent))],
            "audit": [a.data for a in db.scalars(select(AuditLog))],
        }
        events = db.scalars(select(DomainEvent).where(
            DomainEvent.event_type == decisions.MODERATION_DECISION_RECORDED)).all()
        assert events and all(tuple(e.payload) == decisions.EVENT_PAYLOAD_KEYS for e in events)
    flat = json.dumps(surfaces, default=str)
    assert CANARY not in flat
    assert all(body == effects.CLOSED_BY_HOMIES for body in surfaces["messages"])
    for token, c in ((tenant, conv), (tenant2, conv2)):
        shown = json.dumps(_messages(client, token, c))
        assert "SAFETY" not in shown and CANARY not in shown


def test_the_effects_happen_in_the_decisions_transaction_or_not_at_all(client, monkeypatch):
    """A refused decision (raised after the effects ran) leaves no trace."""
    _o, _t, offer, conv, _m = _thread(client)
    moderator = _moderator(client)

    def boom(*args, **kwargs):
        raise decisions.InvalidDecision("refused late")
    monkeypatch.setattr(decisions, "_resolve_reports", boom)
    resp = _decide(client, moderator, "LISTING", offer, "VISIBILITY_LIMITED", "SCAM",
                   close_engagement=True)
    assert resp.status_code == 422
    assert _status(Conversation, conv) == "ACTIVE"
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(ModerationDecision)) == 0
        assert db.scalar(select(func.count()).select_from(Message).where(
            Message.message_type == "SYSTEM")) == 0
    resp = _decide(client, moderator, "CONVERSATION", conv, "FEATURE_RESTRICTED", "SCAM")
    assert resp.status_code == 422 and _status(Conversation, conv) == "ACTIVE"
    assert _head("CONVERSATION", conv) is None
