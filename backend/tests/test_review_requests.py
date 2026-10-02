"""TASK-015 Slice 5 — moderation review requests (SQLite, through HTTP).

Eligibility, authorization (including the organisation agent whose global
role is guest), the note, the one-open and per-episode caps, the answer by
the next decision (keep or release), the owner projection, queue re-entry,
moderator detail, privacy and query counts. Races and unknown COMMITs are
proven on PostgreSQL in test_review_requests_pg.py.
"""

import json

import pytest
from sqlalchemy import event, func, select

from app.core.audit import AuditLog
from app.modules.alerts.models import UserNotification
from app.modules.events.models import DomainEvent
from app.modules.trust import notices, reviews
from app.modules.trust.models import ModerationDecision, ModerationReviewRequest
from tests.conftest import TestingSession, auth, engine, register_and_login
from tests.test_organizations import _org, _org_property
from tests.test_reports_moderation import (
    OFFER,
    _decide,
    _keys,
    _listing,
    _me,
    _moderator,
    _my_listing,
    _report,
    _verified,
)

NOTE = "Zdjęcia są nasze, zrobione 3 maja — proszę o ponowną ocenę."
FORBIDDEN_REVIEW_KEYS = {"note", "requested_by_user_id", "requester", "review_request",
                         "explanation", "reporter_user_id"}


def _review(client, token, offer, note=None, **extra):
    body = {**({"note": note} if note is not None else {}), **extra}
    return client.post(f"/v1/classifieds/{offer}/moderation-review", json=body,
                       headers=auth(token))


def _head(client, moderator, offer):
    return client.get(f"/v1/admin/moderation/targets/LISTING/{offer}",
                      headers=auth(moderator)).json()["head"]


def _held(client, moderator, offer, action="VISIBILITY_LIMITED", reason="SCAM"):
    head = _head(client, moderator, offer)
    resp = _decide(client, moderator, offer, action, reason, head["id"] if head else None)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _queue(client, moderator):
    return {i["target_id"]: i for i in client.get("/v1/admin/moderation/queue",
                                                 headers=auth(moderator)).json()["items"]}


def _requests(offer):
    with TestingSession() as db:
        return db.execute(
            select(ModerationReviewRequest.status, ModerationReviewRequest.decision_id,
                   ModerationReviewRequest.answered_by_decision_id)
            .join(ModerationDecision, ModerationDecision.id == ModerationReviewRequest.decision_id)
            .where(ModerationDecision.target_id == offer)
            .order_by(ModerationReviewRequest.created_at)).all()


# --- the loop -----------------------------------------------------------------------

def test_keep_hold_loop_request_queue_detail_answer_projection(client):
    owner, offer = _listing(client)
    moderator = _moderator(client)
    _report(client, _verified(client), offer, "SCAM")
    hold1 = _held(client, moderator, offer)
    assert offer not in _queue(client, moderator)  # the report was resolved: no work

    resp = _review(client, owner, offer, NOTE)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert set(body) == {"id", "listing_id", "status", "created_at"}
    assert body["status"] == "OPEN" and body["listing_id"] == offer
    assert _my_listing(client, owner, offer)["moderation"]["review"] == "OPEN"
    with TestingSession() as db:  # nothing about the listing changed
        assert db.get(ModerationDecision, hold1["decision_id"]) is not None
    assert _my_listing(client, owner, offer)["status"] == "paused"

    item = _queue(client, moderator)[offer]
    assert item["has_open_review_request"] is True and item["review_requested_at"]
    assert (item["live_reports"], item["max_severity"], item["oldest_report_at"]) == (0, None, None)
    assert "Zdjęcia" not in json.dumps(item)

    detail = client.get(f"/v1/admin/moderation/targets/LISTING/{offer}",
                        headers=auth(moderator)).json()
    request = detail["review_request"]
    assert request["id"] == body["id"] and request["note"] == NOTE
    assert request["decision_id"] == hold1["decision_id"] and request["status"] == "OPEN"
    assert request["requested_by_user_id"] == _me(client, owner)
    assert not _keys(request) & {"email", "phone"}
    with TestingSession() as db:
        viewed = db.scalars(select(AuditLog).where(
            AuditLog.action == "moderation.target_viewed", AuditLog.entity_id == offer)).all()
        assert viewed[-1].data["review_request_id"] == body["id"]
    assert [r.status for r in _requests(offer)] == ["OPEN"]  # opening does not answer

    keep = _held(client, moderator, offer, "CONTENT_EDIT_REQUIRED", "MISLEADING_PRICE")
    assert keep["answered_review_request_id"] == body["id"]
    [row] = _requests(offer)
    assert (row.status, row.answered_by_decision_id) == ("ANSWERED", keep["decision_id"])
    state = _my_listing(client, owner, offer)["moderation"]
    assert (state["state"], state["review"], state["action"]) == (
        "HELD", "ANSWERED", "CONTENT_EDIT_REQUIRED")
    assert offer not in _queue(client, moderator)
    types = [i["notification_type"] for i in client.get(
        "/v1/me/inbox", headers=auth(owner)).json()["items"]]
    assert types.count(notices.LISTING_HELD) == 2 and len(types) == 2  # no "review" notice


def test_release_answers_the_request_and_never_republishes(client):
    owner, offer = _listing(client)
    moderator = _moderator(client)
    hold1 = _held(client, moderator, offer)
    rid = _review(client, owner, offer).json()["id"]
    release = _decide(client, moderator, offer, "NO_ACTION", "REINSTATED_DECISION_ERROR",
                      hold1["decision_id"])
    assert release.status_code == 201 and release.json()["answered_review_request_id"] == rid
    assert release.json()["listing_status"] == "paused"
    state = _my_listing(client, owner, offer)["moderation"]
    assert state == {"state": "NONE", "action": None, "reason_code": None, "since": None,
                     "review": "NONE"}
    assert _review(client, owner, offer).status_code == 409  # not held any more
    assert client.post(f"/v1/classifieds/{offer}/publish",
                       headers=auth(owner)).status_code == 200


# --- eligibility --------------------------------------------------------------------

def test_only_a_current_reviewable_hold_can_be_reviewed(client):
    owner, offer = _listing(client)
    moderator = _moderator(client)
    assert _review(client, owner, offer).status_code == 409  # never held
    _decide(client, moderator, offer, "NO_ACTION", "NOT_A_VIOLATION", None)
    assert _review(client, owner, offer).status_code == 409  # a dismissal is not a hold
    hold1 = _held(client, moderator, offer)
    assert _review(client, owner, offer).status_code == 201
    again = _review(client, owner, offer)
    assert again.status_code == 409 and "already" in again.json()["detail"]
    assert len(_requests(offer)) == 1
    assert hold1["held"] is True
    # A hold that is not appeal-eligible (no path writes one yet) is refused.
    other_owner, other = _listing(client)
    with TestingSession() as db:
        db.add(ModerationDecision(target_type="LISTING", target_id=other, listing_id=other,
                                  action="VISIBILITY_LIMITED", reason_code="SCAM",
                                  decided_by_user_id=_me(client, moderator),
                                  appeal_eligible=False))
        db.commit()
    refused = _review(client, other_owner, other)
    assert refused.status_code == 409 and "cannot be reviewed" in refused.json()["detail"]


@pytest.mark.parametrize("body,why", [
    ({"note": "x" * 501}, "longer than 500"),
    ({"decision_id": "00000000-0000-0000-0000-000000000000"}, "the hold is the server's"),
    ({"status": "ANSWERED"}, "status is the server's"),
    ({"action": "NO_ACTION"}, "no moderation state from the client"),
])
def test_invalid_review_requests_are_refused(client, body, why):
    owner, offer = _listing(client)
    moderator = _moderator(client)
    _held(client, moderator, offer)
    resp = client.post(f"/v1/classifieds/{offer}/moderation-review", json=body,
                       headers=auth(owner))
    assert resp.status_code == 422, why
    assert _requests(offer) == []


def test_the_note_is_plain_text(client):
    owner, offer = _listing(client)
    moderator = _moderator(client)
    _held(client, moderator, offer)
    raw = "  Proszę\u0000 o‮ ocenę <b>teraz</b>\r\n​ "
    assert _review(client, owner, offer, raw).status_code == 201
    with TestingSession() as db:
        note = db.scalar(select(ModerationReviewRequest.note))
    assert note == "Proszę o ocenę <b>teraz</b>"


def test_three_reviews_per_continuous_hold_episode(client):
    owner, offer = _listing(client)
    moderator = _moderator(client)
    _held(client, moderator, offer)
    for _ in range(3):
        assert _review(client, owner, offer).status_code == 201
        _held(client, moderator, offer, "CONTENT_EDIT_REQUIRED", "MISLEADING_PRICE")  # keep
    fourth = _review(client, owner, offer)
    assert fourth.status_code == 409 and "3" in fourth.json()["detail"]
    assert len(_requests(offer)) == 3
    # Release ends the episode; a later hold starts a fresh one.
    head = _head(client, moderator, offer)["id"]
    assert _decide(client, moderator, offer, "NO_ACTION", "REINSTATED_REMEDIED",
                   head).status_code == 201
    assert _review(client, owner, offer).status_code == 409
    _held(client, moderator, offer)
    assert _review(client, owner, offer).status_code == 201


# --- authorization ------------------------------------------------------------------

def test_strangers_get_the_same_404_as_a_missing_listing(client):
    owner, offer = _listing(client)
    moderator = _moderator(client)
    _held(client, moderator, offer)
    guest = register_and_login(client, "stranger-guest@example.com", "guest")
    host = register_and_login(client, "stranger-host@example.com", "host")
    missing = _review(client, guest, "00000000-0000-0000-0000-000000000000")
    for token in (guest, host, moderator):
        resp = _review(client, token, offer)
        assert resp.status_code == 404 and resp.json() == missing.json()
    assert client.post(f"/v1/classifieds/{offer}/moderation-review", json={}).status_code == 401
    assert client.get("/v1/me/classifieds", headers=auth(guest)).json() == []
    assert _requests(offer) == []


def test_an_agent_whose_account_role_is_guest_closes_the_loop(client):
    """The authority chain, not the global role, decides (S2+S3 debt): an
    organisation AGENT registered as a guest gets the notice, sees the
    listing on /me/classifieds and can request a review."""
    boss = register_and_login(client, "boss-s5@agencja.pl", "host")
    org = _org(client, boss, slug="agencja-s5")
    prop = _org_property(client, boss, org["id"], address="ul. Rewizyjna 5")
    agent = register_and_login(client, "agent-s5@agencja.pl", "guest")
    assert client.post(f"/v1/organizations/{org['id']}/members",
                       json={"email": "agent-s5@agencja.pl", "role": "AGENT"},
                       headers=auth(boss)).status_code == 202
    assert client.post(f"/v1/organizations/{org['id']}/membership/accept",
                       headers=auth(agent)).status_code == 200
    offer = client.post(f"/v1/properties/{prop['id']}/classifieds", json=OFFER,
                        headers=auth(boss)).json()["id"]
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(boss)).status_code == 200
    moderator = _moderator(client)
    _held(client, moderator, offer)

    inbox = client.get("/v1/me/inbox", headers=auth(agent)).json()["items"]
    assert [i["notification_type"] for i in inbox] == [notices.LISTING_HELD]
    mine = client.get("/v1/me/classifieds", headers=auth(agent))
    assert mine.status_code == 200
    assert [i["id"] for i in mine.json()] == [offer]
    assert mine.json()[0]["moderation"]["state"] == "HELD"
    assert _review(client, agent, offer).status_code == 201
    assert _my_listing(client, boss, offer)["moderation"]["review"] == "OPEN"


# --- privacy ------------------------------------------------------------------------

def test_the_note_stays_with_the_moderator(client):
    owner, offer = _listing(client)
    reporter = _verified(client)
    moderator = _moderator(client)
    _report(client, reporter, offer, "SCAM")
    hold1 = _held(client, moderator, offer)
    rid = _review(client, owner, offer, NOTE).json()["id"]
    _decide(client, moderator, offer, "NO_ACTION", "REINSTATED_REMEDIED", hold1["decision_id"])
    with TestingSession() as db:
        written = [
            *(e.data for e in db.scalars(select(AuditLog))),
            *(e.payload for e in db.scalars(select(DomainEvent))),
            *(n.data for n in db.scalars(select(UserNotification))),
        ]
        review_audit = db.scalar(select(AuditLog).where(
            AuditLog.action == "moderation.review_requested"))
    assert set(review_audit.data) == {"decision_id", "review_request_id"}
    assert review_audit.data["review_request_id"] == rid
    surfaces = [
        written,
        client.get("/v1/me/classifieds", headers=auth(owner)).json(),
        client.get("/v1/me/inbox", headers=auth(owner)).json(),
        client.get("/v1/me/reports", headers=auth(reporter)).json(),
        client.get(f"/v1/classifieds/{offer}").json(),
    ]
    flat = json.dumps(surfaces, ensure_ascii=False)
    assert "Zdjęcia" not in flat
    for surface in surfaces[1:]:
        assert not _keys(surface) & FORBIDDEN_REVIEW_KEYS


# --- queue and query counts ---------------------------------------------------------

def test_queue_order_high_reports_then_reviews_then_normal(client):
    _, high = _listing(client)
    owner, reviewed = _listing(client)
    _, normal = _listing(client)
    moderator = _moderator(client)
    _held(client, moderator, reviewed)
    _report(client, _verified(client), normal, "DUPLICATE")
    _review(client, owner, reviewed)
    _report(client, _verified(client), high, "SAFETY")
    order = [t for t in _queue(client, moderator) if t in (high, reviewed, normal)]
    assert order == [high, reviewed, normal]


def _statements(table: str, call) -> int:
    seen: list[str] = []

    def capture(conn, cursor, statement, *args):
        if table in statement:
            seen.append(statement)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    return len(seen)


def test_review_state_and_queue_are_read_per_page_not_per_row(client):
    owner, first = _listing(client)
    moderator = _moderator(client)
    prop = _my_listing(client, owner, first)["property_id"]
    offers = [first]
    for _ in range(2):
        offer = client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                            headers=auth(owner)).json()["id"]
        assert client.post(f"/v1/classifieds/{offer}/publish",
                           headers=auth(owner)).status_code == 200
        offers.append(offer)
    _held(client, moderator, first)

    def owner_page():
        assert client.get("/v1/me/classifieds", headers=auth(owner)).status_code == 200

    def queue_page():
        assert client.get("/v1/admin/moderation/queue", headers=auth(moderator)).status_code == 200

    one = (_statements("moderation_review_requests", owner_page),
           _statements("moderation_review_requests", queue_page))
    for offer in offers[1:]:
        _held(client, moderator, offer)
        _review(client, owner, offer)
    assert (_statements("moderation_review_requests", owner_page),
            _statements("moderation_review_requests", queue_page)) == one == (1, 2)


def test_review_requests_have_no_answer_endpoint_and_no_new_notice_type(client):
    paths = client.app.openapi()["paths"]
    assert "/v1/classifieds/{listing_id}/moderation-review" in paths
    assert not [p for p in paths if "answer" in p]
    with TestingSession() as db:
        types = set(db.scalars(select(func.distinct(UserNotification.notification_type))))
    assert types <= {notices.LISTING_HELD, notices.LISTING_RELEASED}
    assert reviews.EPISODE_CAP == 3 and reviews.NOTE_MAX == 500
