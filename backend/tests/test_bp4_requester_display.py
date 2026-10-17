"""OD-3/D-113: minimal unverified display text behind BP-9 authorization."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.engagement.display import requester_display_name
from app.modules.identity.models import User
from app.modules.properties.models import PropertyAuthority
from tests.conftest import TestingSession, auth, register_and_login
from tests.test_conversations import _listing, _start
from tests.test_engagement_safety import _request, _viewing_ready


@pytest.mark.parametrize("raw,expected", [
    (None, "Użytkownik Homies"), ("", "Użytkownik Homies"),
    (" \t\n\u2003", "Użytkownik Homies"), ("  Cher  ", "Cher"),
    ("Anna Nowak", "Anna N."), (" Anna\tMaria\nNowak ", "Anna N."),
    ("Łukasz Żółć", "Łukasz Ż."), ("Марія Коваль", "Марія К."),
    ("李 雷", "李 雷."), ("单名", "单名"),
    ("Jean-Luc de Gaulle", "Jean-Luc G."),
    ("Ana N\u0303unez", "Ana N\u0303."),
    ("<b>Ana</b> Nowak", "<b>Ana</b> N."),
])
def test_founder_projection_rule(raw, expected):
    assert requester_display_name(raw) == expected


@pytest.fixture
def engagement(client):
    owner = register_and_login(client, "bp4-owner@example.com", "host")
    tenant = register_and_login(client, "private-bp4-email@example.com", "guest")
    tenant_id = client.get("/v1/me", headers=auth(tenant)).json()["id"]
    with TestingSession() as db:
        user = db.get(User, tenant_id)
        user.full_name = "  Мária  Joanna  Żółć  "
        user.phone = "+48600123456"
        user.phone_verified_at = datetime.now(timezone.utc)
        db.commit()
    prop, listing = _listing(client, owner)
    conv = _start(client, tenant, listing).json()["conversation"]["id"]
    day = _viewing_ready(client, owner, listing)
    viewing = _request(client, tenant, listing, day, 10).json()["id"]
    return owner, tenant, prop["id"], listing, conv, viewing


def assert_minimal(response):
    assert response.status_code == 200, response.text
    for private in ("Joanna", "Żółć", "private-bp4-email", "+48600123456",
                    '"full_name"', '"phone"', '"email"', '"phone_verified_at"',
                    '"legal_first_name"', '"legal_last_name"'):
        assert private not in response.text


def test_provider_conversation_and_viewing_dtos_project_on_server(client, engagement):
    owner, tenant, prop, listing, conv, viewing = engagement
    owner_id = client.get("/v1/me", headers=auth(owner)).json()["id"]
    inbox = client.get("/v1/conversations", headers=auth(owner))
    detail = client.get(f"/v1/conversations/{conv}", headers=auth(owner))
    viewings = client.get(f"/v1/classifieds/{listing}/viewings", headers=auth(owner))
    stage = client.post(f"/v1/conversations/{conv}/stage", json={"provider_stage": "SHORTLISTED"},
                        headers=auth(owner))
    assignment = client.post(f"/v1/conversations/{conv}/assign", json={"user_id": owner_id},
                             headers=auth(owner))
    for response in (inbox, detail, viewings, stage, assignment):
        assert_minimal(response)
    for row in (inbox.json()[0], detail.json()["conversation"], viewings.json()[0],
                stage.json(), assignment.json()):
        assert row["requester_display_name"] == "Мária Ż."
    for path in ("/v1/conversations", f"/v1/conversations/{conv}", "/v1/me/viewings"):
        response = client.get(path, headers=auth(tenant))
        assert response.status_code == 200
        assert "requester_display_name" not in response.text
        assert "Мária" not in response.text


@pytest.mark.parametrize("mode", ["unverified", "revoked", "stranger"])
def test_name_never_crosses_provider_access_gate(client, engagement, mode):
    owner, tenant, prop, listing, conv, viewing = engagement
    actor = owner
    if mode == "stranger":
        actor = register_and_login(client, "bp4-stranger@example.com", "host")
    else:
        with TestingSession() as db:
            root = db.scalar(select(PropertyAuthority).where(PropertyAuthority.property_id == prop))
            if mode == "unverified":
                root.verification_state = "UNVERIFIED"
            else:
                root.status = "REVOKED"
            db.commit()
    assert client.get("/v1/conversations", headers=auth(actor)).json() == []
    for path in (f"/v1/conversations/{conv}", f"/v1/classifieds/{listing}/viewings"):
        response = client.get(path, headers=auth(actor))
        assert response.status_code == 404
        assert "Мária" not in response.text
        assert "requester_display_name" not in response.text


def test_current_empty_name_uses_fallback_without_stored_legal_identity(client, engagement):
    owner, tenant, prop, listing, conv, viewing = engagement
    tenant_id = client.get("/v1/me", headers=auth(tenant)).json()["id"]
    with TestingSession() as db:
        db.get(User, tenant_id).full_name = "  "
        db.commit()
    response = client.get(f"/v1/classifieds/{listing}/viewings", headers=auth(owner))
    assert_minimal(response)
    assert response.json()[0]["requester_display_name"] == "Użytkownik Homies"
