"""BP-8: real HTTP refusal, isolation, generation and unchanged repeat accounting."""
import json

import pytest
from sqlalchemy import func, select

from app.core.audit import AuditLog
from app.core.config import settings
from app.modules.properties.models import ClassifiedOffer, ContactReveal
from tests.conftest import TestingSession, auth, register_and_login, verify_phone
from tests.test_engagement_safety import _decide
from tests.test_message_moderation import _thread
from tests.test_reports_moderation import _listing, _moderator

PHONE = "+48 600 900 111"
SECRET = "bp8-private-moderation-reason-canary"


def _reveal(client, token, listing):
    return client.post(f"/v1/classifieds/{listing}/contact", headers=auth(token))


def _counts():
    with TestingSession() as db:
        return (db.scalar(select(func.count()).select_from(ContactReveal)),
                db.scalar(select(func.count()).select_from(AuditLog).where(
                    AuditLog.action == "classified.contact_revealed")))


@pytest.mark.parametrize("repeat", [False, True])
def test_g14_blocks_new_and_repeat_without_phone_or_side_effects(client, repeat, caplog, monkeypatch):
    owner, tenant, listing, conv, _ = _thread(client)
    verify_phone(client, tenant, "+48600100101")
    monkeypatch.setattr(settings, "contact_reveal_daily_quota", 1)
    if repeat:
        assert _reveal(client, tenant, listing).status_code == 200
        # Previously revealed numbers may change; no updated phone may escape.
        with TestingSession() as db:
            db.get(ClassifiedOffer, listing).contact_phone = PHONE
            db.commit()
        assert _reveal(client, tenant, listing).json()["contact_phone"] == PHONE
        assert _counts() == (1, 1)
    moderator = _moderator(client)
    restricted = _decide(client, moderator, "CONVERSATION", conv, "FEATURE_RESTRICTED",
                         "HARASSMENT", explanation=SECRET)
    assert restricted.status_code == 201, restricted.text
    before = _counts()
    quota = client.get("/v1/me/reveal-quota", headers=auth(tenant)).json()["used"]
    for _ in range(2):
        refused = _reveal(client, tenant, listing)
        assert refused.status_code == 409, refused.text
        assert refused.json() == {"detail": "RECONTACT_BLOCKED: contact is unavailable for this publication"}
        assert "contact_phone" not in refused.text and PHONE not in refused.text
        assert SECRET not in refused.text and "HARASSMENT" not in refused.text
    assert _counts() == before
    assert client.get("/v1/me/reveal-quota", headers=auth(tenant)).json()["used"] == quota
    assert PHONE not in caplog.text and SECRET not in caplog.text
    outsider = register_and_login(client, "bp8-other@example.com", "guest")
    verify_phone(client, outsider, "+48600100102")
    assert _reveal(client, outsider, listing).status_code == 200
    # Another listing remains available (subject to the unchanged quota).
    _, other_listing = _listing(client)
    other = _reveal(client, tenant, other_listing)
    assert other.status_code == (429 if repeat else 200), other.text
    # A legitimate publication transition, not a synthetic counter edit.
    for action in ("pause", "publish"):
        response = client.post(f"/v1/classifieds/{listing}/{action}", headers=auth(owner))
        assert response.status_code == 200, response.text
    # Repeats remain free at full quota; a new reveal still observes it.
    after = _reveal(client, tenant, listing)
    assert after.status_code == (200 if repeat else 429), after.text
    if repeat:
        assert after.json()["contact_phone"] == PHONE
    else:
        monkeypatch.setattr(settings, "contact_reveal_daily_quota", 2)
        assert _reveal(client, tenant, listing).status_code == 200
    with TestingSession() as db:
        logs = list(db.scalars(select(AuditLog).where(AuditLog.action == "classified.contact_revealed")))
        assert all(SECRET not in json.dumps(row.data) for row in logs)


def test_existing_authentication_public_and_contact_mode_gates(client):
    owner, tenant, listing, _, _ = _thread(client)
    url = f"/v1/classifieds/{listing}/contact"
    assert client.post(url).status_code == 401
    denied = _reveal(client, tenant, listing)
    assert denied.status_code == 403 and "PHONE_NOT_VERIFIED" in denied.text
    verify_phone(client, tenant, "+48600100103")
    with TestingSession() as db:
        db.get(ClassifiedOffer, listing).contact_mode = "message"
        db.commit()
    denied = _reveal(client, tenant, listing)
    assert denied.status_code == 409 and "MESSAGES_ONLY" in denied.text
    assert client.post(f"/v1/classifieds/{listing}/pause", headers=auth(owner)).status_code == 200
    assert _reveal(client, tenant, listing).status_code == 404
    assert _counts() == (0, 0)

def test_rollback_conflict_fallback_rechecks_restriction(client, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from app.modules.identity.models import User
    from app.modules.properties.router import reveal_contact
    from fastapi import HTTPException

    _, tenant, listing, conv, _ = _thread(client)
    verify_phone(client, tenant, "+48600100104")
    viewer_id = client.get("/v1/me", headers=auth(tenant)).json()["id"]
    moderator = _moderator(client)
    with TestingSession() as db:
        viewer = db.get(User, viewer_id)
        original_flush, original_rollback = db.flush, db.rollback

        def conflicting_insert(*args, **kwargs):
            if any(isinstance(row, ContactReveal) for row in db.new):
                raise IntegrityError("synthetic unique conflict", None, RuntimeError("conflict"))
            return original_flush(*args, **kwargs)

        def rollback_then_restrict():
            original_rollback()
            response = _decide(client, moderator, "CONVERSATION", conv,
                               "FEATURE_RESTRICTED", "HARASSMENT", explanation=SECRET)
            assert response.status_code == 201, response.text

        monkeypatch.setattr(db, "flush", conflicting_insert)
        monkeypatch.setattr(db, "rollback", rollback_then_restrict)
        with pytest.raises(HTTPException) as refused:
            reveal_contact(listing, user=viewer, db=db)
        assert refused.value.status_code == 409
        assert refused.value.detail == "RECONTACT_BLOCKED: contact is unavailable for this publication"
    assert _counts() == (0, 0)
