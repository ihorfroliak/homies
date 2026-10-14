"""BP-6 HTTP privacy and atomic rollback, complementing the real PG schedules."""

import json

import pytest
from sqlalchemy import select, func

from app.modules.alerts.models import UserNotification
from app.modules.engagement.models import Viewing, Conversation
from app.modules.events.models import DomainEvent
from app.modules.trust import decisions, notices
from app.modules.trust.models import ModerationDecision
from tests.conftest import TestingSession, auth
from tests.test_engagement_safety import _decide, _request, _viewing_ready
from tests.test_message_moderation import _thread
from tests.test_reports_moderation import _moderator, _me


@pytest.mark.parametrize("fail_late", [False, True])
def test_restriction_cleans_viewing_with_neutral_both_party_notices(client, monkeypatch, fail_late):
    owner, tenant, listing, conversation, _ = _thread(client)
    day = _viewing_ready(client, owner, listing)
    requested = _request(client, tenant, listing, day, 10)
    assert requested.status_code == 201
    viewing = requested.json()["id"]
    moderator = _moderator(client)
    if fail_late:
        def reject(*args, **kwargs):
            raise decisions.InvalidDecision("late refusal after cancellations and notices")
        monkeypatch.setattr(decisions, "_resolve_reports", reject)
    result = _decide(client, moderator, "CONVERSATION", conversation,
                     "FEATURE_RESTRICTED", "HARASSMENT", explanation="private-bp6-allegation")
    assert result.status_code == (422 if fail_late else 201), result.text
    if not fail_late:
        assert result.json()["cancelled_viewings"] == 1
    with TestingSession() as db:
        row = db.get(Viewing, viewing)
        assert (row.status, row.cancelled_by) == (("REQUESTED", None) if fail_late else
                                                 ("CANCELLED", "HOMIES"))
        assert db.get(Conversation, conversation).status == ("ACTIVE" if fail_late else "CLOSED")
        ns = list(db.scalars(select(UserNotification).where(
            UserNotification.notification_type == notices.VIEWING_CANCELLED)))
        facts = list(db.scalars(select(DomainEvent).where(
            DomainEvent.event_type == "ViewingCancelled")))
        if fail_late:
            assert ns == [] and facts == []
            assert db.scalar(select(func.count()).select_from(ModerationDecision)) == 0
        else:
            assert len(facts) == 1
            assert facts[0].payload["moderation_decision_id"] == result.json()["decision_id"]
            assert len(ns) == 2
            assert {n.user_id for n in ns} == {_me(client, owner), _me(client, tenant)}
            for n in ns:
                assert set(n.data) == {"viewing_id", "listing_id", "effective_from"}
                assert n.data["viewing_id"] == viewing and n.data["listing_id"] == listing
                assert n.category == "TRANSACTIONAL"
                assert (n.title_key, n.body_key) == ("moderation.viewing_cancelled.title",
                                                    "moderation.viewing_cancelled.body")
                assert "HARASSMENT" not in json.dumps(n.data)
                assert "private-bp6-allegation" not in json.dumps(n.data)
    if not fail_late:
        for path, token in [("/v1/me/viewings", tenant),
                            (f"/v1/classifieds/{listing}/viewings", owner)]:
            response = client.get(path, headers=auth(token))
            assert response.status_code == 200
            rows = [v for v in response.json() if v["id"] == viewing]
            assert len(rows) == 1 and rows[0]["cancelled_by"] == "HOMIES"
            assert rows[0]["cancelled_by_homies"] is True
            assert "private-bp6-allegation" not in response.text
            assert "HARASSMENT" not in response.text
        repeat = _decide(client, moderator, "CONVERSATION", conversation,
                         "FEATURE_RESTRICTED", "HARASSMENT")
        assert repeat.status_code == 409
        with TestingSession() as db:
            assert db.scalar(select(func.count()).select_from(UserNotification).where(
                UserNotification.notification_type == notices.VIEWING_CANCELLED)) == 2
            assert db.scalar(select(func.count()).select_from(DomainEvent).where(
                DomainEvent.event_type == "ViewingCancelled")) == 1
