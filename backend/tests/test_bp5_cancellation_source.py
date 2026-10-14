"""BP-5 attribution is a persisted fact, never an inference from timestamps."""

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.modules.engagement.models import Viewing
from app.modules.events.models import DomainEvent
from tests.conftest import TestingSession, auth
from tests.test_engagement_safety import _decide, _request, _viewing_ready
from tests.test_message_moderation import _thread
from tests.test_reports_moderation import _moderator


@pytest.mark.parametrize("actor", ["REQUESTER", "PROVIDER", "HOMIES"])
def test_durable_source_and_compatibility_in_both_inboxes(client, actor):
    owner, tenant, listing, _conv, _message = _thread(client)
    day = _viewing_ready(client, owner, listing)
    requested = _request(client, tenant, listing, day, 10)
    assert requested.status_code == 201
    viewing = requested.json()["id"]
    assert requested.json()["cancelled_by"] is None
    if actor == "HOMIES":
        response = _decide(client, _moderator(client), "LISTING", listing,
                           "VISIBILITY_LIMITED", "SAFETY", close_engagement=True)
        assert response.status_code == 201, response.text
    else:
        response = client.post(f"/v1/viewings/{viewing}/cancel",
                               headers=auth(tenant if actor == "REQUESTER" else owner))
        assert response.status_code == 200, response.text
        assert response.json()["cancelled_by"] == actor
    for path, token in [("/v1/me/viewings", tenant),
                        (f"/v1/classifieds/{listing}/viewings", owner)]:
        row = next(v for v in client.get(path, headers=auth(token)).json() if v["id"] == viewing)
        assert row["cancelled_by"] == actor
        assert row["cancelled_by_homies"] is (actor == "HOMIES")
        assert "cancellation_source_legacy" not in row
    # Neither repeat actor can overwrite the winner or append another fact.
    for token in (owner, tenant):
        retry = client.post(f"/v1/viewings/{viewing}/cancel", headers=auth(token))
        assert retry.status_code == 409
        assert retry.json()["detail"].startswith("VIEWING_STATE_CONFLICT")
    with TestingSession() as db:
        row = db.get(Viewing, viewing)
        assert row.cancelled_by == actor and not row.cancellation_source_legacy
        facts = db.scalars(select(DomainEvent).where(
            DomainEvent.event_type == "ViewingCancelled",
            DomainEvent.correlation_id == viewing)).all()
        assert len(facts) == 1 and facts[0].payload["cancelled_by"] == actor
        row.cancelled_by = "PROVIDER" if actor != "PROVIDER" else "REQUESTER"
        with pytest.raises(ValueError, match="source is immutable"):
            db.flush()
        db.rollback()


@pytest.mark.parametrize("values", [
    {"cancelled_by": "HOMIES"},
    {"cancelled_by": "UNKNOWN"},
    {"status": "CANCELLED", "cancelled_at": "now"},
])
def test_source_shape_rejects_false_attribution_and_missing_new_source(client, values):
    from datetime import datetime, timezone

    owner, tenant, listing, _conv, _message = _thread(client)
    day = _viewing_ready(client, owner, listing)
    viewing = _request(client, tenant, listing, day, 10).json()["id"]
    if "cancelled_at" in values:
        values = {**values, "cancelled_at": datetime.now(timezone.utc)}
    with TestingSession() as db, pytest.raises(IntegrityError):
        db.execute(update(Viewing).where(Viewing.id == viewing).values(**values))
        db.commit()