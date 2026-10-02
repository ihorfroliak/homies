"""TASK-015 Slices 2+3 — listing reports, moderator API, owner moderation state
and notices (SQLite, through HTTP).

Sequential semantics, authorization, privacy (forbidden-key) and structure.
Races, locks, quota exactness and unknown COMMITs are proven on PostgreSQL in
test_reports_moderation_pg.py.
"""

import json

import pytest
from sqlalchemy import event, func, select, update

from app.core.audit import AuditLog
from app.core.ratelimit import ADMIN, PUBLIC_READ, REPORT_CREATE, resolve_policy
from app.core.security import hash_password
from app.modules.alerts.models import UserNotification
from app.modules.events.models import DomainEvent
from app.modules.identity.models import User
from app.modules.properties import authority
from app.modules.properties.models import ClassifiedOffer
from app.modules.trust import notices, reports
from app.modules.trust.models import ModerationDecision, Report
from tests.conftest import (
    TestingSession,
    auth,
    engine,
    last_code,
    register_and_login,
    verify_ownership,
    verify_phone,
)

PROPERTY = {"category": "APARTMENT", "city": "Gdańsk", "address": "ul. Zgłoszona 7",
            "area_m2": 51, "rooms": 2, "capacity": 2}
OFFER = {"title": "Mieszkanie do zgłoszenia", "description": "Jasne, ciche",
         "rent_amount": 310000, "min_term_months": 12, "contact_mode": "phone",
         "contact_phone": "+48 600 111 222"}
# Never on an owner surface, a notice, an event or an audit entry.
FORBIDDEN_OWNER_KEYS = {"reporter_user_id", "reporter", "reports", "report_count",
                        "live_reports", "description_text", "explanation", "decided_by_user_id",
                        "category", "severity", "snapshot"}
FORBIDDEN_SNAPSHOT_KEYS = {"address", "street", "building_number", "unit", "postcode",
                           "postal_code", "latitude", "longitude", "exact_geog", "contact_phone",
                           "phone", "email", "owner_id", "owner", "property_id",
                           "address_record", "authority"}

_n = {"i": 0}


def _next() -> int:
    _n["i"] += 1
    return _n["i"]


def _listing(client, publish=True):
    i = _next()
    owner = register_and_login(client, f"rep-owner-{i}@example.com", "host")
    prop = client.post("/v1/properties", json={**PROPERTY, "address": f"ul. Zgłoszona {i}"},
                       headers=auth(owner)).json()["id"]
    verify_ownership(client, owner, prop)
    offer = client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    if publish:
        assert client.post(f"/v1/classifieds/{offer}/publish",
                           headers=auth(owner)).status_code == 200
    return owner, offer


def _verified(client, prefix="reporter"):
    token = register_and_login(client, f"{prefix}-{_next()}@example.com", "guest")
    assert client.post("/v1/me/verify/email/start", headers=auth(token)).status_code == 200
    assert client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                       headers=auth(token)).status_code == 200
    return token


def _me(client, token) -> str:
    return client.get("/v1/me", headers=auth(token)).json()["id"]


def _moderator(client) -> str:
    email = f"moderator-{_next()}@example.com"
    with TestingSession() as db:
        db.add(User(email=email, password_hash=hash_password("moderator-pass-123"), role="admin"))
        db.commit()
    resp = client.post("/v1/auth/login", json={"email": email, "password": "moderator-pass-123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _report(client, token, offer, reason="SCAM", text=None):
    body = {"target_type": "LISTING", "target_id": offer, "reason": reason}
    if text is not None:
        body["text"] = text
    return client.post("/v1/reports", json=body, headers=auth(token))


def _decide(client, token, offer, action, reason, head):
    return client.post("/v1/admin/moderation/decisions", json={
        "target_type": "LISTING", "target_id": offer, "action": action, "reason_code": reason,
        "expected_head_decision_id": head}, headers=auth(token))


def _keys(value) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            out.add(k)
            out |= _keys(v)
    elif isinstance(value, list):
        for v in value:
            out |= _keys(v)
    return out


def _count(model, *where) -> int:
    with TestingSession() as db:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def _my_listing(client, owner, offer) -> dict:
    return next(i for i in client.get("/v1/me/classifieds", headers=auth(owner)).json()
                if i["id"] == offer)


# --- reporting ------------------------------------------------------------------

def test_a_report_is_created_once_and_asking_again_returns_it(client):
    _, offer = _listing(client)
    reporter = _verified(client)
    first = _report(client, reporter, offer, "SCAM")
    assert first.status_code == 201, first.text
    assert first.json()["created"] is True and first.json()["status"] == "received"
    again = _report(client, reporter, offer, "FAKE", "different words this time")
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"] and again.json()["created"] is False
    assert again.json()["reason"] == "SCAM"
    assert _count(Report, Report.target_id == offer) == 1
    assert set(first.json()) == {"id", "target_type", "target_id", "reason", "status",
                                 "created_at", "created"}


def test_reporting_needs_a_verified_email_or_phone(client):
    _, offer = _listing(client)
    plain = register_and_login(client, f"plain-{_next()}@example.com", "guest")
    resp = _report(client, plain, offer)
    assert resp.status_code == 403
    missing = _report(client, plain, "00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 403  # before the target is even looked at: no oracle
    assert _count(Report) == 0
    assert client.post("/v1/reports", json={"target_type": "LISTING", "target_id": offer,
                                            "reason": "SCAM"}).status_code == 401
    phone_only = register_and_login(client, f"phone-{_next()}@example.com", "guest")
    verify_phone(client, phone_only, "+4850060%04d" % _next())
    assert _report(client, phone_only, offer).status_code == 201


def test_hidden_and_missing_listings_are_indistinguishable(client):
    owner, offer = _listing(client)
    assert client.post(f"/v1/classifieds/{offer}/pause", headers=auth(owner)).status_code == 200
    reporter = _verified(client)
    hidden = _report(client, reporter, offer)
    missing = _report(client, reporter, "00000000-0000-0000-0000-000000000000")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    _, draft = _listing(client, publish=False)
    assert _report(client, reporter, draft).json() == missing.json()


def test_a_hidden_listing_stays_reportable_by_someone_who_dealt_with_it(client):
    owner, offer = _listing(client)
    reporter = _verified(client)
    verify_phone(client, reporter, "+4850160%04d" % _next())
    assert client.post(f"/v1/classifieds/{offer}/contact",
                       headers=auth(reporter)).status_code == 200
    assert client.post(f"/v1/classifieds/{offer}/pause", headers=auth(owner)).status_code == 200
    assert _report(client, reporter, offer, "SCAM").status_code == 201
    stranger = _verified(client)
    assert _report(client, stranger, offer).status_code == 404


def test_nobody_reports_a_listing_they_manage(client):
    owner, offer = _listing(client)
    assert client.post("/v1/me/verify/email/start", headers=auth(owner)).status_code == 200
    assert client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                       headers=auth(owner)).status_code == 200
    assert _report(client, owner, offer).status_code == 409
    assert client.post(f"/v1/classifieds/{offer}/pause", headers=auth(owner)).status_code == 200
    assert _report(client, owner, offer).status_code == 409  # they know it exists
    assert _count(Report) == 0


@pytest.mark.parametrize("body,why", [
    ({"reason": "SPAM"}, "moderator-only on listings"),
    ({"reason": "ILLEGAL_CONTENT"}, "moderator-only"),
    ({"reason": "HARASSMENT"}, "a message reason"),
    ({"reason": "OTHER"}, "OTHER needs text"),
    ({"reason": "OTHER", "text": "too short \u0000​"}, "OTHER needs 20 characters"),
    ({"reason": "SCAM", "text": "x" * 1001}, "longer than 1000"),
    ({"reason": "SCAM", "severity": "URGENT"}, "severity is the server's"),
    ({"reason": "SCAM", "reporter_user_id": "someone"}, "the reporter is the caller"),
    ({"reason": "SCAM", "status": "RESOLVED"}, "status is the server's"),
    ({"reason": "SCAM", "snapshot": {}}, "the snapshot is the server's"),
    ({"reason": "FAKE", "target_type": "MESSAGE"}, "a listing reason on a message"),
])
def test_invalid_reports_are_refused(client, body, why):
    _, offer = _listing(client)
    reporter = _verified(client)
    resp = client.post("/v1/reports", json={"target_type": "LISTING", "target_id": offer, **body},
                       headers=auth(reporter))
    assert resp.status_code == 422, why
    assert _count(Report) == 0


def test_text_is_plain_and_severity_is_derived(client):
    _, offer = _listing(client)
    _, other = _listing(client)
    reporter = _verified(client)
    raw = "  Zadatek\u0000 przed‮ obejrzeniem!\r\nLink <b>x</b>\t ​ "
    assert _report(client, reporter, offer, "SCAM", raw).status_code == 201
    assert _report(client, reporter, other, "DUPLICATE").status_code == 201
    with TestingSession() as db:
        scam = db.scalar(select(Report).where(Report.target_id == offer))
        dup = db.scalar(select(Report).where(Report.target_id == other))
        assert scam.description == "Zadatek przed obejrzeniem!\nLink <b>x</b>"
        assert (scam.severity, dup.severity) == ("HIGH", "NORMAL")
        assert dup.description is None
    assert [reports.severity(c) for c in reports.LISTING_REASONS] == [
        "HIGH", "HIGH", "NORMAL", "HIGH", "HIGH", "NORMAL", "NORMAL", "NORMAL"]


def test_the_snapshot_is_the_allowlisted_public_face(client):
    owner, offer = _listing(client)
    reporter = _verified(client)
    assert _report(client, reporter, offer).status_code == 201
    with TestingSession() as db:
        report = db.scalar(select(Report).where(Report.target_id == offer))
        snap = report.snapshot
        generation = db.get(ClassifiedOffer, offer).public_generation
    assert set(snap) == {*reports.SNAPSHOT_KEYS, "cover_media_id", "public_generation"}
    assert not _keys(snap) & FORBIDDEN_SNAPSHOT_KEYS
    flat = json.dumps(snap, ensure_ascii=False)
    assert OFFER["contact_phone"] not in flat and "Zgłoszona" not in flat
    assert snap["title"] == OFFER["title"] and snap["rent_amount"] == OFFER["rent_amount"]
    assert snap["public_generation"] == generation == report.listing_public_generation_at_report


def test_the_account_quota_and_duplicates_are_free(client, monkeypatch):
    monkeypatch.setattr(reports, "DAILY_LIMIT", 3)
    reporter = _verified(client)
    offers = [_listing(client)[1] for _ in range(4)]
    for offer in offers[:3]:
        assert _report(client, reporter, offer).status_code == 201
    over = _report(client, reporter, offers[3])
    assert over.status_code == 429 and int(over.headers["Retry-After"]) > 0
    assert _report(client, reporter, offers[0]).status_code == 200  # duplicate: free
    assert _count(Report) == 3


def test_the_live_cap(client, monkeypatch):
    monkeypatch.setattr(reports, "LIVE_LIMIT", 2)
    reporter = _verified(client)
    moderator = _moderator(client)
    offers = [_listing(client)[1] for _ in range(3)]
    for offer in offers[:2]:
        assert _report(client, reporter, offer).status_code == 201
    assert _report(client, reporter, offers[2]).status_code == 429
    assert _decide(client, moderator, offers[0], "NO_ACTION", "NOT_A_VIOLATION",
                   None).status_code == 201
    assert _report(client, reporter, offers[2]).status_code == 201


def test_my_reports_shows_my_own_with_a_coarse_status(client):
    _, offer = _listing(client)
    a, b = _verified(client), _verified(client)
    moderator = _moderator(client)
    rid = _report(client, a, offer).json()["id"]
    _report(client, b, offer)
    page = client.get("/v1/me/reports", headers=auth(a)).json()
    assert page["total"] == 1 and [i["id"] for i in page["items"]] == [rid]
    assert page["items"][0]["status"] == "received"
    client.get(f"/v1/admin/moderation/targets/LISTING/{offer}", headers=auth(moderator))
    assert client.get("/v1/me/reports", headers=auth(a)).json()["items"][0]["status"] == "reviewed"
    _decide(client, moderator, offer, "VISIBILITY_LIMITED", "SCAM", None)
    item = client.get("/v1/me/reports", headers=auth(a)).json()["items"][0]
    assert item["status"] == "reviewed"
    assert set(item) == {"id", "target_type", "target_id", "reason", "status", "created_at",
                         "created"}
    assert client.get("/v1/me/reports").status_code == 401


def test_the_report_metric_counts_new_committed_reports_only(client):
    counter = reports.REPORTS_CREATED.labels(target_type="LISTING", category="FAKE")
    before = counter._value.get()
    _, offer = _listing(client)
    reporter = _verified(client)
    assert _report(client, reporter, offer, "FAKE").status_code == 201
    assert _report(client, reporter, offer, "FAKE").status_code == 200
    _report(client, register_and_login(client, f"u-{_next()}@example.com", "guest"), offer, "FAKE")
    assert counter._value.get() == before + 1


# --- moderator ------------------------------------------------------------------

def test_moderation_routes_are_for_moderators_only(client):
    _, offer = _listing(client)
    guest = _verified(client)
    host = register_and_login(client, f"h-{_next()}@example.com", "host")
    for token in (guest, host):
        assert client.get("/v1/admin/moderation/queue", headers=auth(token)).status_code == 403
        assert client.get(f"/v1/admin/moderation/targets/LISTING/{offer}",
                          headers=auth(token)).status_code == 403
        assert _decide(client, token, offer, "VISIBILITY_LIMITED", "SCAM",
                       None).status_code == 403
    assert client.get("/v1/admin/moderation/queue").status_code == 401
    assert _count(ModerationDecision) == 0


def test_the_queue_groups_by_target_orders_by_severity_then_age_and_carries_no_allegations(
        client):
    _, normal = _listing(client)
    _, high = _listing(client)
    _, older_high = _listing(client)
    a, b, c = _verified(client), _verified(client), _verified(client)
    moderator = _moderator(client)
    _report(client, a, normal, "DUPLICATE")
    _report(client, a, older_high, "SCAM", "secret allegation text here")
    _report(client, a, high, "DUPLICATE")
    _report(client, b, high, "SAFETY")
    _report(client, c, high, "MISLEADING_PRICE")
    with TestingSession() as db:  # distinct ages (SQLite timestamps are per second)
        for target, age in ((older_high, 3), (high, 2), (normal, 1)):
            db.execute(update(Report).where(Report.target_id == target).values(
                created_at=func.datetime("now", f"-{age} hours")))
        db.commit()
    page = client.get("/v1/admin/moderation/queue", headers=auth(moderator)).json()
    assert [i["target_id"] for i in page["items"]] == [older_high, high, normal]
    assert page["total"] == 3
    item = page["items"][1]
    assert (item["live_reports"], item["distinct_reporters"], item["max_severity"]) == (3, 3, "HIGH")
    assert item["head_decision_id"] is None and item["held"] is False
    flat = json.dumps(page)
    assert "secret allegation" not in flat and "@example.com" not in flat
    assert not _keys(page) & {"description", "snapshot", "email", "phone", "address",
                              "reporter_user_id"}
    second = client.get("/v1/admin/moderation/queue?limit=1&offset=1",
                        headers=auth(moderator)).json()
    assert [i["target_id"] for i in second["items"]] == [high] and second["total"] == 3


def test_opening_a_target_starts_its_review_once_and_is_audited(client):
    _, offer = _listing(client)
    a, b = _verified(client), _verified(client)
    moderator, other = _moderator(client), _moderator(client)
    _report(client, a, offer, "SCAM", "the deposit was requested before any viewing")
    first = client.get(f"/v1/admin/moderation/targets/LISTING/{offer}", headers=auth(moderator))
    assert first.status_code == 200, first.text
    body = first.json()
    [report] = body["reports"]
    assert report["status"] == "IN_REVIEW" and report["first_reviewed_at"] is not None
    assert report["reporter_user_id"] == _me(client, a)
    assert report["reporter_email_verified"] is True and report["reporter_phone_verified"] is False
    assert report["description"] == "the deposit was requested before any viewing"
    assert not _keys(body) & {"email", "phone", "contact_phone", "address"}
    assert set(body["listing"]["current"]) == {*reports.SNAPSHOT_KEYS, "cover_media_id",
                                               "public_generation"}
    _report(client, b, offer, "FAKE")
    again = client.get(f"/v1/admin/moderation/targets/LISTING/{offer}", headers=auth(other)).json()
    by_id = {r["id"]: r for r in again["reports"]}
    assert by_id[report["id"]]["first_reviewed_at"] == report["first_reviewed_at"]
    assert all(r["status"] == "IN_REVIEW" for r in again["reports"])
    with TestingSession() as db:
        entries = db.scalars(select(AuditLog).where(
            AuditLog.action == "moderation.target_viewed", AuditLog.entity_id == offer)).all()
        assert len(entries) == 2
        for entry in entries:
            assert set(entry.data) == {"target_type", "report_ids", "review_request_id"}
            assert "deposit" not in json.dumps(entry.data)
    assert client.get("/v1/admin/moderation/targets/LISTING/00000000-0000-0000-0000-000000000000",
                      headers=auth(moderator)).status_code == 404


def test_the_full_loop_hold_notice_owner_state_release(client):
    owner, offer = _listing(client)
    reporter = _verified(client)
    moderator = _moderator(client)
    reporter_id = _me(client, reporter)
    _report(client, reporter, offer, "SCAM", "they asked for a deposit by wire transfer")
    assert _my_listing(client, owner, offer)["moderation"] == {
        "state": "NONE", "action": None, "reason_code": None, "since": None, "review": "NONE"}
    assert client.get("/v1/me/inbox", headers=auth(owner)).json()["total"] == 0  # nothing pending

    held = _decide(client, moderator, offer, "VISIBILITY_LIMITED", "SCAM", None)
    assert held.status_code == 201, held.text
    decision = held.json()
    assert decision["held"] is True and decision["listing_status"] == "paused"
    assert decision["resolved_reports"] == 1 and decision["notified_managers"] == 1

    state = _my_listing(client, owner, offer)
    assert state["status"] == "paused"
    assert state["moderation"]["state"] == "HELD"
    assert (state["moderation"]["action"], state["moderation"]["reason_code"]) == (
        "VISIBILITY_LIMITED", "SCAM")
    inbox = client.get("/v1/me/inbox", headers=auth(owner)).json()
    [notice] = inbox["items"]
    assert notice["category"] == "TRANSACTIONAL"
    assert notice["notification_type"] == notices.LISTING_HELD
    assert set(notice["data"]) == set(notices.NOTICE_DATA_KEYS)
    assert notice["data"]["decision_id"] == decision["decision_id"]
    owner_view = json.dumps([state, inbox])
    assert reporter_id not in owner_view and "deposit by wire" not in owner_view
    assert not _keys(state["moderation"]) & FORBIDDEN_OWNER_KEYS
    assert not _keys(notice["data"]) & FORBIDDEN_OWNER_KEYS
    assert client.get("/v1/me/inbox", headers=auth(reporter)).json()["total"] == 0

    pub = client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    assert pub.status_code == 409 and pub.json()["detail"].startswith("HELD_BY_MODERATION")

    released = _decide(client, moderator, offer, "NO_ACTION", "REINSTATED_REMEDIED",
                       decision["decision_id"])
    assert released.status_code == 201 and released.json()["held"] is False
    assert released.json()["listing_status"] == "paused"  # never republished for the owner
    assert _my_listing(client, owner, offer)["moderation"]["state"] == "NONE"
    items = client.get("/v1/me/inbox", headers=auth(owner)).json()["items"]
    # (SQLite stamps both in the same second; the order is proven on PostgreSQL)
    assert sorted(i["notification_type"] for i in items) == [notices.LISTING_HELD,
                                                             notices.LISTING_RELEASED]
    assert {i["data"]["decision_id"] for i in items} == {
        decision["decision_id"], released.json()["decision_id"]}
    assert client.post(f"/v1/classifieds/{offer}/publish",
                       headers=auth(owner)).status_code == 200


def test_a_dismissal_tells_the_owner_nothing(client):
    owner, offer = _listing(client)
    reporter = _verified(client)
    moderator = _moderator(client)
    _report(client, reporter, offer, "MISLEADING_PRICE")
    resp = _decide(client, moderator, offer, "NO_ACTION", "NOT_A_VIOLATION", None)
    assert resp.status_code == 201 and resp.json()["notified_managers"] == 0
    assert client.get("/v1/me/inbox", headers=auth(owner)).json()["total"] == 0
    assert _my_listing(client, owner, offer)["moderation"]["state"] == "NONE"
    assert _my_listing(client, owner, offer)["moderation"]["action"] is None
    assert client.get("/v1/me/reports", headers=auth(reporter)).json()["items"][0][
        "status"] == "reviewed"


def test_a_stale_head_is_409_and_never_retried_for_the_moderator(client):
    _, offer = _listing(client)
    m1, m2 = _moderator(client), _moderator(client)
    first = _decide(client, m1, offer, "CONTENT_EDIT_REQUIRED", "MISLEADING_PRICE", None)
    assert first.status_code == 201
    late = _decide(client, m2, offer, "VISIBILITY_LIMITED", "SCAM", None)
    assert late.status_code == 409
    assert late.json()["detail"].startswith("STALE_HEAD")
    assert first.json()["decision_id"] in late.json()["detail"]
    assert _count(ModerationDecision, ModerationDecision.target_id == offer) == 1


def test_a_moderator_with_any_live_report_on_the_target_cannot_decide(client):
    _, offer = _listing(client)
    reporter = _verified(client)
    moderator = _moderator(client)
    # The moderator files one of several reports; nobody names a report.
    _report(client, reporter, offer, "SCAM")
    mod_user = _me(client, moderator)
    with TestingSession() as db:
        db.get(User, mod_user).email_verified_at = db.get(User, _me(client, reporter)
                                                          ).email_verified_at
        db.commit()
    assert _report(client, moderator, offer, "FAKE").status_code == 201
    resp = _decide(client, moderator, offer, "VISIBILITY_LIMITED", "SCAM", None)
    assert resp.status_code == 403 and resp.json()["detail"].startswith("CONFLICT_OF_INTEREST")
    assert _count(ModerationDecision) == 0
    assert _count(Report, Report.status == "RESOLVED") == 0
    other = _moderator(client)
    assert _decide(client, other, offer, "VISIBILITY_LIMITED", "SCAM", None).status_code == 201


@pytest.mark.parametrize("change,why", [
    ({"action": "CONTENT_REMOVED"}, "a Slice 4 action"),
    ({"action": "ACCOUNT_SUSPENDED"}, "no account status"),
    ({"close_engagement": True}, "close_engagement: Slice 4"),
    ({"report_id": "x"}, "no caller-selected report"),
    ({"target_type": "MESSAGE"}, "message moderation: Slice 4"),
    ({"reason_code": "REINSTATED_REMEDIED"}, "no hold to release"),
    ({"action": "NO_ACTION", "reason_code": "SCAM"}, "a dismissal is NOT_A_VIOLATION"),
])
def test_invalid_decisions_are_refused(client, change, why):
    _, offer = _listing(client)
    moderator = _moderator(client)
    body = {"target_type": "LISTING", "target_id": offer, "action": "VISIBILITY_LIMITED",
            "reason_code": "SCAM", "expected_head_decision_id": None, **change}
    resp = client.post("/v1/admin/moderation/decisions", json=body, headers=auth(moderator))
    assert resp.status_code == 422, why
    assert _count(ModerationDecision) == 0


def test_expected_head_is_required_and_unknown_listings_are_404(client):
    _, offer = _listing(client)
    moderator = _moderator(client)
    resp = client.post("/v1/admin/moderation/decisions", json={
        "target_type": "LISTING", "target_id": offer, "action": "VISIBILITY_LIMITED",
        "reason_code": "SCAM"}, headers=auth(moderator))
    assert resp.status_code == 422
    assert _decide(client, moderator, "00000000-0000-0000-0000-000000000000",
                   "VISIBILITY_LIMITED", "SCAM", None).status_code == 404


def test_reports_never_act_on_their_own(client):
    owner, offer = _listing(client)
    for _ in range(6):
        assert _report(client, _verified(client), offer, "SAFETY").status_code == 201
    with TestingSession() as db:
        assert db.get(ClassifiedOffer, offer).status == "active"
    assert client.get(f"/v1/classifieds/{offer}").status_code == 200
    assert _count(ModerationDecision) == 0
    assert _my_listing(client, owner, offer)["moderation"]["state"] == "NONE"
    assert client.get("/v1/me/inbox", headers=auth(owner)).json()["total"] == 0


def test_decision_audit_event_and_notice_carry_no_report_text_or_reporter(client):
    _, offer = _listing(client)
    reporter = _verified(client)
    moderator = _moderator(client)
    reporter_id = _me(client, reporter)
    _report(client, reporter, offer, "SCAM", "a private allegation with details")
    resp = client.post("/v1/admin/moderation/decisions", json={
        "target_type": "LISTING", "target_id": offer, "action": "VISIBILITY_LIMITED",
        "reason_code": "SCAM", "expected_head_decision_id": None,
        "explanation": "internal moderator note"}, headers=auth(moderator))
    decision_id = resp.json()["decision_id"]
    with TestingSession() as db:
        written = [
            *(e.data for e in db.scalars(select(AuditLog).where(AuditLog.entity_id == offer))),
            *(e.payload for e in db.scalars(select(DomainEvent).where(
                DomainEvent.correlation_id == decision_id))),
            *(n.data for n in db.scalars(select(UserNotification))),
        ]
    flat = json.dumps(written)
    for secret in ("private allegation", "internal moderator note", reporter_id):
        assert secret not in flat


def test_owner_projection_reads_moderation_heads_once_per_page(client):
    owner, first = _listing(client)
    moderator = _moderator(client)

    def statements_on_decisions(n_more: int) -> int:
        seen: list[str] = []

        def capture(conn, cursor, statement, *args):
            if "moderation_decisions" in statement:
                seen.append(statement)

        event.listen(engine, "before_cursor_execute", capture)
        try:
            assert client.get("/v1/me/classifieds", headers=auth(owner)).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        return len(seen)

    assert statements_on_decisions(0) == 1
    prop = client.get("/v1/me/classifieds", headers=auth(owner)).json()[0]["property_id"]
    for _ in range(3):
        offer = client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                            headers=auth(owner))
        assert offer.status_code in (200, 201), offer.text
    _decide(client, moderator, first, "CONTENT_EDIT_REQUIRED", "MISLEADING_PRICE", None)
    assert len(client.get("/v1/me/classifieds", headers=auth(owner)).json()) >= 2
    assert statements_on_decisions(3) == 1


def test_notice_recipients_are_the_listing_managers(client):
    owner, offer = _listing(client)
    outsider = _verified(client)
    with TestingSession() as db:
        prop = db.get(ClassifiedOffer, offer).property_id
        managers = authority.holders(db, prop, "PUBLISH_LISTING")
        owner_id = _me(client, owner)
        assert managers == [owner_id]
        assert _me(client, outsider) not in managers
        # The same audience as the owner's listing page.
        for user_id in managers:
            assert authority.can_act(db, user_id, prop, "PUBLISH_LISTING", verified=False)


def test_report_routes_have_their_rate_limit_policy():
    assert resolve_policy("POST", "/v1/reports") is REPORT_CREATE
    assert (REPORT_CREATE.capacity, REPORT_CREATE.refill_per_second) == (5, 0.05)
    assert resolve_policy("GET", "/v1/me/reports") is PUBLIC_READ
    assert resolve_policy("GET", "/v1/admin/moderation/queue") is ADMIN
    assert resolve_policy("POST", "/v1/admin/moderation/decisions") is ADMIN


def test_normalisation_is_deterministic():
    assert reports.normalize_text(None) is None
    assert reports.normalize_text(" ​\u0007 ") is None
    assert reports.normalize_text("a\r\nb\rc\td") == "a\nb\nc d"
    assert reports.normalize_text("é") == "é"  # NFC
    assert reports.normalize_text("x‮y⁦z") == "xyz"  # bidi controls removed
    assert reports.meaningful_length("a   b\n\n c") == 5
