"""TASK-015 Slice 1 — moderation decision chain and publication hold (SQLite).

Sequential semantics and structural guards. Races, locks, privileges and the
database-level guarantees under concurrency are proven on PostgreSQL in
test_moderation_core_pg.py.
"""

import ast
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.audit import AuditLog
from app.modules.alerts.models import NotificationPreference, UserNotification
from app.modules.events import service as events
from app.modules.events.models import DomainEvent, Notification
from app.modules.identity.models import User
from app.modules.properties import router as props
from app.modules.properties.models import ClassifiedOffer, ListingPublicGeneration
from app.modules.trust import decisions, hold
from app.modules.trust.models import ModerationDecision, Report
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership

BACKEND = Path(__file__).resolve().parents[1]
PROPERTY = {"category": "APARTMENT", "city": "Poznań", "address": "ul. Moderowana 1",
            "area_m2": 44, "rooms": 2, "capacity": 2}
OFFER = {"title": "Do moderacji", "rent_amount": 250000, "min_term_months": 12,
         "contact_mode": "phone", "contact_phone": "+48 600 700 800"}
FORBIDDEN_EVENT_KEYS = {"reporter_user_id", "description", "explanation", "decided_by_user_id",
                        "address", "latitude", "longitude", "exact_geog", "body", "email",
                        "phone", "contact_phone", "snapshot", "note"}

_n = {"i": 0}


def _listing(client, email=None):
    _n["i"] += 1
    owner = register_and_login(client, email or f"mod-owner-{_n['i']}@example.com", "host")
    prop = client.post("/v1/properties", json={**PROPERTY, "address": f"ul. M {_n['i']}"},
                       headers=auth(owner)).json()["id"]
    verify_ownership(client, owner, prop)
    offer = client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    return owner, prop, offer


def _user(email, role="admin") -> str:
    with TestingSession() as db:
        user = User(email=email, password_hash="x", role=role)
        db.add(user)
        db.commit()
        return user.id


def _decide(listing, action, reason, expected, moderator, **kwargs):
    with TestingSession() as db:
        result = decisions.apply_listing_decision(
            db, actor=db.get(User, moderator), listing_id=listing, action=action,
            reason_code=reason, expected_head_decision_id=expected, **kwargs)
        db.commit()
        return result


def _offer(listing) -> ClassifiedOffer:
    with TestingSession() as db:
        offer = db.get(ClassifiedOffer, listing)
        db.expunge(offer)
        return offer


def _count(model, *where) -> int:
    with TestingSession() as db:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def _set(listing, **values):
    with TestingSession() as db:
        db.execute(text("UPDATE classified_offers SET "
                        + ", ".join(f"{k} = :{k}" for k in values) + " WHERE id = :id"),
                   {**values, "id": listing})
        db.commit()


@pytest.fixture
def moderator():
    _n["i"] += 1
    return _user(f"moderator-{_n['i']}@example.com")


# --- the hold and publication ----------------------------------------------------


def test_a_hold_pauses_the_listing_and_publish_answers_held_by_moderation(client, moderator):
    owner, _prop, offer = _listing(client)
    generation = _offer(offer).public_generation
    applied = _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator)
    assert (applied.listing_status_before, applied.listing_status_after) == ("active", "paused")
    assert client.get(f"/v1/classifieds/{offer}").status_code == 404

    r = client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    assert r.status_code == 409 and r.json()["detail"] == props.HELD_BY_MODERATION
    after = _offer(offer)
    assert after.status == "paused" and after.public_generation == generation
    assert _count(DomainEvent, DomainEvent.event_type == "ListingBecamePublic",
                  DomainEvent.correlation_id == offer) == generation


@pytest.mark.parametrize("skew", ["active", "stale"])
def test_confirm_under_a_hold_is_refused_with_no_side_effects(client, moderator, skew):
    """The state an N-1 release (which ignores holds) can leave: held but
    `active`/`stale`. Before S1 confirm ignored make_public's refusal and
    answered 200 with an audit row and a freshness event."""
    owner, _prop, offer = _listing(client)
    _decide(offer, "CONTENT_EDIT_REQUIRED", "MISLEADING_PRICE", None, moderator)
    _set(offer, status=skew)
    before = _offer(offer)
    audits = _count(AuditLog, AuditLog.entity_id == offer)
    evts = _count(DomainEvent, DomainEvent.correlation_id == offer)

    r = client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))
    assert r.status_code == 409 and r.json()["detail"] == props.HELD_BY_MODERATION
    after = _offer(offer)
    assert after.status == skew
    assert after.last_confirmed_available_at == before.last_confirmed_available_at
    assert after.public_generation == before.public_generation
    assert _count(AuditLog, AuditLog.entity_id == offer) == audits
    assert _count(DomainEvent, DomainEvent.correlation_id == offer) == evts

    r = client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    assert r.status_code == 409 and r.json()["detail"] == props.HELD_BY_MODERATION
    assert _offer(offer).status == skew


def test_release_never_republishes_and_republish_opens_a_new_generation(client, moderator):
    owner, _prop, offer = _listing(client)
    g = _offer(offer).public_generation
    held = _decide(offer, "VISIBILITY_LIMITED", "FAKE", None, moderator)
    released = _decide(offer, "NO_ACTION", "REINSTATED_REMEDIED", held.decision_id, moderator)
    assert released.supersedes_decision_id == held.decision_id and not released.held
    after = _offer(offer)
    assert after.status == "paused" and after.public_generation == g
    assert client.get(f"/v1/classifieds/{offer}").status_code == 404
    # Confirm is no back door: a paused listing is published, not confirmed.
    r = client.post(f"/v1/classifieds/{offer}/confirm", headers=auth(owner))
    assert r.status_code == 409 and r.json()["detail"] != props.HELD_BY_MODERATION

    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    assert _offer(offer).public_generation == g + 1  # D-5: a genuine return to market
    assert _count(DomainEvent, DomainEvent.dedup_key == f"ListingBecamePublic:{offer}:{g + 1}") == 1
    assert _count(ListingPublicGeneration, ListingPublicGeneration.listing_id == offer,
                  ListingPublicGeneration.public_generation == g + 1) == 1


def test_a_hold_on_a_draft_or_paused_listing_still_blocks_publication(client, moderator):
    owner, prop, _ = _listing(client)
    draft = client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    _decide(draft, "VISIBILITY_LIMITED", "SCAM", None, moderator)
    assert client.post(f"/v1/classifieds/{draft}/publish",
                       headers=auth(owner)).json()["detail"] == props.HELD_BY_MODERATION
    assert _offer(draft).public_generation == 0


# --- the decision chain ----------------------------------------------------------


def test_a_stale_head_is_refused_and_writes_nothing(client, moderator):
    _owner, _prop, offer = _listing(client)
    first = _decide(offer, "CONTENT_EDIT_REQUIRED", "MISLEADING_PRICE", None, moderator)
    with pytest.raises(decisions.StaleHead) as caught:
        _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator)
    assert caught.value.current_head_id == first.decision_id
    assert _count(ModerationDecision, ModerationDecision.target_id == offer) == 1


def test_a_retry_after_a_committed_decision_observes_the_new_head(client, moderator):
    """PR-003 `commit_unknown`: the first attempt committed, the caller did not
    learn it and retries with the head it saw. The retry must not branch."""
    _owner, _prop, offer = _listing(client)
    first = _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator)
    with pytest.raises(decisions.StaleHead) as caught:
        _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator)
    assert caught.value.current_head_id == first.decision_id
    with TestingSession() as db:
        assert hold.head(db, "LISTING", offer).id == first.decision_id


@pytest.mark.parametrize("action, reason, held_first, refused", [
    ("VISIBILITY_LIMITED", "NOT_A_VIOLATION", False, True),      # a hold needs a policy reason
    ("VISIBILITY_LIMITED", "REINSTATED_REMEDIED", False, True),
    ("NO_ACTION", "SCAM", False, True),                         # dismissal is NOT_A_VIOLATION
    ("NO_ACTION", "REINSTATED_REMEDIED", False, True),          # nothing to release
    ("NO_ACTION", "NOT_A_VIOLATION", False, False),
    ("NO_ACTION", "NOT_A_VIOLATION", True, True),               # a release says why
    ("NO_ACTION", "REINSTATED_DECISION_ERROR", True, False),
    ("CONTENT_REMOVED", "SCAM", False, True),                   # not a listing action in S1
    ("ACCOUNT_SUSPENDED", "SCAM", False, True),                 # no account status (D-6)
])
def test_reason_and_action_rules(client, moderator, action, reason, held_first, refused):
    _owner, _prop, offer = _listing(client)
    head = (_decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator).decision_id
            if held_first else None)
    if refused:
        with pytest.raises(decisions.InvalidDecision):
            _decide(offer, action, reason, head, moderator)
    else:
        assert _decide(offer, action, reason, head, moderator).action == action


def test_only_a_moderator_decides_by_the_role_in_the_database(client):
    _owner, _prop, offer = _listing(client)
    host = _user(f"not-a-moderator-{offer}@example.com", role="host")
    with pytest.raises(decisions.NotAModerator):
        _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, host)


def test_a_moderator_who_manages_the_property_is_refused(client):
    email = f"owner-moderator-{_n['i']}@example.com"
    _owner, _prop, offer = _listing(client, email=email)
    with TestingSession() as db:
        user = db.scalar(select(User).where(User.email == email))
        user.role = "admin"
        db.commit()
        owner_id = user.id
    with pytest.raises(decisions.ConflictOfInterest):
        _decide(offer, "NO_ACTION", "NOT_A_VIOLATION", None, owner_id)


def _report(listing, reporter, category="SCAM") -> str:
    with TestingSession() as db:
        report = Report(reporter_user_id=reporter, target_type="LISTING", target_id=listing,
                        listing_id=listing, category=category, description="free text")
        db.add(report)
        db.commit()
        return report.id


def test_the_reporter_cannot_decide_their_own_report(client, moderator):
    _owner, _prop, offer = _listing(client)
    report = _report(offer, moderator)
    with pytest.raises(decisions.ConflictOfInterest):
        _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator, report_id=report)


def test_a_decision_resolves_the_live_reports_of_its_target_only(client, moderator):
    _o, _p, offer = _listing(client)
    _o2, _p2, other = _listing(client)
    a = _user(f"reporter-a-{offer}@example.com", role="guest")
    b = _user(f"reporter-b-{offer}@example.com", role="guest")
    r1, r2, r3 = _report(offer, a), _report(offer, b), _report(other, a)
    applied = _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator, report_id=r1)
    assert set(applied.resolved_report_ids) == {r1, r2}
    with TestingSession() as db:
        for rid in (r1, r2):
            report = db.get(Report, rid)
            assert report.status == "RESOLVED"
            assert report.resolution_decision_id == applied.decision_id
        assert db.get(Report, r3).status == "OPEN"
    later = _report(offer, a)  # after the decision: open for the next review
    with TestingSession() as db:
        assert db.get(Report, later).status == "OPEN"


def test_one_live_report_per_reporter_and_target(client):
    with TestingSession() as db:
        user = User(email="dup-reporter@example.com", password_hash="x", role="guest")
        db.add(user)
        db.flush()
        db.add(Report(reporter_user_id=user.id, target_type="LISTING", target_id="t-1",
                      category="SCAM"))
        db.flush()
        db.add(Report(reporter_user_id=user.id, target_type="LISTING", target_id="t-1",
                      category="FAKE"))
        with pytest.raises(IntegrityError):
            db.flush()


def test_decisions_are_immutable_in_the_orm(client, moderator):
    _owner, _prop, offer = _listing(client)
    applied = _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator)
    with TestingSession() as db:
        row = db.get(ModerationDecision, applied.decision_id)
        row.reason_code = "OTHER"
        with pytest.raises(RuntimeError, match="append-only"):
            db.flush()
    with TestingSession() as db:
        db.delete(db.get(ModerationDecision, applied.decision_id))
        with pytest.raises(RuntimeError, match="append-only"):
            db.flush()


def test_the_database_refuses_a_fork_of_the_chain(client, moderator):
    _owner, _prop, offer = _listing(client)
    first = _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator)

    def insert(**kwargs):
        with TestingSession() as db:
            db.add(ModerationDecision(target_type="LISTING", target_id=offer, listing_id=offer,
                                      action="NO_ACTION", reason_code="REINSTATED_REMEDIED",
                                      decided_by_user_id=moderator, **kwargs))
            db.commit()

    insert(supersedes_decision_id=first.decision_id)
    with pytest.raises(IntegrityError):  # the same decision superseded twice
        insert(supersedes_decision_id=first.decision_id)
    with pytest.raises(IntegrityError):  # a second first decision for the target
        insert(supersedes_decision_id=None)


# --- event, audit, metrics -------------------------------------------------------


def test_the_decision_event_carries_exactly_the_allowlisted_keys(client, moderator):
    _owner, _prop, offer = _listing(client)
    reporter = _user(f"evt-reporter-{offer}@example.com", role="guest")
    report = _report(offer, reporter)
    notifications = _count(Notification)
    applied = _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator, report_id=report,
                      explanation="internal: the phone number belongs to a known scammer")
    with TestingSession() as db:
        evt = db.scalar(select(DomainEvent).where(
            DomainEvent.dedup_key == f"ModerationDecisionRecorded:{applied.decision_id}"))
    assert evt is not None and evt.event_type == decisions.MODERATION_DECISION_RECORDED
    assert set(evt.payload) == set(decisions.EVENT_PAYLOAD_KEYS)
    assert not FORBIDDEN_EVENT_KEYS & set(evt.payload)
    flat = json.dumps(evt.payload)
    for leak in ("scammer", "free text", reporter, moderator):
        assert leak not in flat
    assert evt.payload["action"] == "VISIBILITY_LIMITED" and evt.payload["target_id"] == offer
    # not routed: the booking-era recipient resolution never sees it
    assert decisions.MODERATION_DECISION_RECORDED not in events.ROUTING
    assert _count(Notification) == notifications


def test_the_audit_row_carries_ids_and_codes_only(client, moderator):
    _owner, _prop, offer = _listing(client)
    applied = _decide(offer, "VISIBILITY_LIMITED", "SCAM", None, moderator,
                      explanation="private moderator note")
    with TestingSession() as db:
        row = db.scalar(select(AuditLog).where(AuditLog.action == "moderation.visibility_limited",
                                               AuditLog.entity_id == offer))
    assert row is not None and row.actor == moderator
    assert set(row.data) == {"decision_id", "reason_code", "supersedes_decision_id",
                             "status_before", "status_after"}
    assert row.data["decision_id"] == applied.decision_id
    assert "private" not in json.dumps(row.data)


def _decisions_metric(action):
    return decisions.DECISIONS.labels(target_type="LISTING", action=action)._value.get()


def test_the_decision_counter_counts_only_committed_decisions(client, moderator):
    _owner, _prop, offer = _listing(client)
    before = _decisions_metric("CONTENT_EDIT_REQUIRED")
    with TestingSession() as db:
        decisions.apply_listing_decision(
            db, actor=db.get(User, moderator), listing_id=offer, action="CONTENT_EDIT_REQUIRED",
            reason_code="OTHER", expected_head_decision_id=None)
        db.rollback()
    assert _decisions_metric("CONTENT_EDIT_REQUIRED") == before
    with TestingSession() as db:
        decisions.apply_listing_decision(
            db, actor=db.get(User, moderator), listing_id=offer, action="CONTENT_EDIT_REQUIRED",
            reason_code="OTHER", expected_head_decision_id=None)
        with pytest.raises(IntegrityError), db.begin_nested():  # an unrelated savepoint fails
            db.execute(text("INSERT INTO users (id, email, password_hash, role) "
                            "SELECT id, email, password_hash, role FROM users LIMIT 1"))
        db.commit()
    assert _decisions_metric("CONTENT_EDIT_REQUIRED") == before + 1


# --- schema seams ----------------------------------------------------------------


def test_the_inbox_admits_transactional_notices_but_preferences_stay_product_only(client):
    uid = _user("inbox-transactional@example.com", role="guest")
    with TestingSession() as db:
        db.add(UserNotification(user_id=uid, category="TRANSACTIONAL",
                                notification_type="MODERATION", title_key="t", body_key="b"))
        db.commit()
    with TestingSession() as db:
        db.add(NotificationPreference(user_id=uid, category="TRANSACTIONAL", channel="IN_APP",
                                      enabled=False))
        with pytest.raises(IntegrityError):
            db.commit()


def test_only_the_reports_moderation_and_review_routes_exist(client):
    """Slices 2+3, 5, 4a and 4b add exactly these: messages are reported through
    /v1/reports and decided through /decisions; a review is answered by a
    decision, not an endpoint; conversations and photos are decided through
    /decisions too — 4b adds only the moderator's view of a photo."""
    paths = {p for p in client.app.openapi()["paths"] if "report" in p or "moderation" in p}
    assert paths == {
        "/v1/reports", "/v1/me/reports", "/v1/admin/moderation/queue",
        "/v1/admin/moderation/targets/LISTING/{listing_id}", "/v1/admin/moderation/decisions",
        "/v1/classifieds/{listing_id}/moderation-review",
        "/v1/admin/moderation/targets/MESSAGE/{message_id}",
        "/v1/admin/moderation/targets/MEDIA/{media_asset_id}",
        "/v1/admin/moderation/media/{media_asset_id}/content",
    }


# --- structural sentinels --------------------------------------------------------

LEGACY_DORMANT = ("app/modules/booking/", "app/modules/payments/", "app/modules/ledger/",
                  "app/modules/listings/", "app/modules/admin/legacy.py",
                  "app/modules/identity/host_payouts.py")
# The one place a listing becomes `active`.
SOLE_ACTIVE_WRITER = ("app/modules/properties/publicity.py", "make_public")
# Constructors of OTHER aggregates whose own status is called "active".
OTHER_AGGREGATES = {"SavedSearch"}
# Read-side calls: a keyword `status="active"` there filters, it writes nothing.
READS = {"filter_by"}
_RAW_SQL_WRITE = re.compile(r"(?is)\bupdate\s+classified_offers\b.*\bset\b.*\bstatus\s*=\s*'active'")


def _enclosing_functions(tree):
    owner = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                owner.setdefault(node, fn.name)  # outermost wins: walk order is top-down
    return owner


def _is_active(node) -> bool:
    return isinstance(node, ast.Constant) and node.value == "active"


def _callee(call: ast.Call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def active_writes(rel: str, source: str) -> list[tuple[int, str]]:
    """Every place in `source` that could store status 'active'."""
    tree = ast.parse(source)
    owner = _enclosing_functions(tree)
    found = []
    for node in ast.walk(tree):
        hit = False
        if isinstance(node, ast.Dict):
            hit = any(isinstance(k, ast.Constant) and k.value == "status" and _is_active(v)
                      for k, v in zip(node.keys, node.values, strict=True))
        elif isinstance(node, ast.Call):
            hit = (_callee(node) not in OTHER_AGGREGATES | READS
                   and any(kw.arg == "status" and _is_active(kw.value) for kw in node.keywords))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            hit = _is_active(node.value) and any(
                isinstance(t, ast.Attribute) and t.attr == "status" for t in targets)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            hit = bool(_RAW_SQL_WRITE.search(node.value))
        if hit and (rel, owner.get(node, "<module>")) != SOLE_ACTIVE_WRITER:
            found.append((node.lineno, owner.get(node, "<module>")))
    return found


def test_the_sentinel_catches_every_shape_of_writing_active():
    for snippet in (
        "def f(db): db.execute(update(ClassifiedOffer).values(status='active'))",
        "def f(db): db.execute(update(ClassifiedOffer).values({'status': 'active'}))",
        "def f(offer): offer.status = 'active'",
        "def f(db): db.execute(text(\"UPDATE classified_offers SET status = 'active' WHERE id=1\"))",
        "def f(db): ClassifiedOffer(status='active')",
    ):
        assert active_writes("app/modules/x.py", snippet), snippet
    for harmless in (
        "def f(o): return o.status == 'active'",
        "def f(q): return q.filter_by(status='active')",
        "def f(): return SavedSearch(status='active')",
        "def f(db): db.execute(update(ClassifiedOffer).values(status='paused'))",
    ):
        assert not active_writes("app/modules/x.py", harmless), harmless


def test_make_public_is_the_only_code_that_moves_a_listing_into_active():
    offenders = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith(LEGACY_DORMANT):
            continue
        offenders += [(rel, line, fn) for line, fn in
                      active_writes(rel, path.read_text(encoding="utf-8"))]
    assert offenders == []
    publicity = (BACKEND / SOLE_ACTIVE_WRITER[0]).read_text(encoding="utf-8")
    assert '"status": "active"' in publicity  # the allow-listed site is still the writer


def test_every_make_public_caller_handles_a_hold():
    """Every caller keeps the result and answers a hold (`.held`): a caller
    that ignores the result would turn a refusal into a success (the
    pre-S1 confirm bug)."""
    callers = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith(LEGACY_DORMANT) or rel == SOLE_ACTIVE_WRITER[0]:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and _callee(node) == "make_public":
                    callers.append(rel + "::" + fn.name)
                    assigned = [a for a in ast.walk(fn) if isinstance(a, ast.Assign)
                                and a.value is node and isinstance(a.targets[0], ast.Name)]
                    assert assigned, f"{rel}::{fn.name} ignores make_public's result"
                    name = assigned[0].targets[0].id
                    used = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)
                            and isinstance(n.value, ast.Name) and n.value.id == name}
                    assert {"applied", "held"} <= used, f"{rel}::{fn.name} uses {used}"
    assert sorted(callers) == ["app/modules/properties/router.py::confirm_classified",
                               "app/modules/properties/router.py::publish_classified"]


def test_one_migration_head_and_it_is_the_release_head():
    from alembic.script import ScriptDirectory

    from app.core import release
    from app.core.schema import alembic_config

    heads = ScriptDirectory.from_config(alembic_config()).get_heads()
    manifest = json.loads(release.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert heads == [manifest["schema_head"]] == ["a3c5e7f9b1d4"]
