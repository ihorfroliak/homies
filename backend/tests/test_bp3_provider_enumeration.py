"""BP-3: enumeration is capability-scoped, not a grant of owner access."""
from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app.modules.identity.models import OrganizationMembership, RepresentationMandate
from app.modules.properties.models import PropertyAuthority, PropertyAuthorityScope
from tests.conftest import TestingSession, auth, authorization_date, register_and_login
from tests.test_conversations import _agency, _listing, _member
from tests.test_property_authority import _draft, _register


def listing_rows(client, token, scope=None):
    params = {} if scope is None else {"scope": scope}
    return client.get("/v1/me/classifieds", params=params, headers=auth(token))


def test_default_preserves_unverified_publication_management(client):
    owner = register_and_login(client, "bp3-owner@example.com", "host")
    prop = _register(client, owner)
    offer = _draft(client, owner, prop["id"])
    legacy = listing_rows(client, owner)
    assert legacy.status_code == 200
    assert legacy.json()[0]["id"] == offer
    assert {"freshness_detail", "quality", "moderation"} <= legacy.json()[0].keys()
    assert listing_rows(client, owner, "PUBLISH_LISTING").json() == legacy.json()
    for scope in ("MANAGE_MESSAGES", "MANAGE_VIEWINGS"):
        assert listing_rows(client, owner, scope).json() == []
    assert client.get("/v1/me/classifieds", params={"scope": "MANAGE_MESSAGES"}).status_code == 401
    assert listing_rows(client, owner, "EDIT_PROPERTY").status_code == 422


@pytest.mark.parametrize("scope", ["MANAGE_MESSAGES", "MANAGE_VIEWINGS"])
def test_personal_scope_minimal_projection_and_property_isolation(client, scope):
    owner = register_and_login(client, "bp3-owner@example.com", "host")
    stranger = register_and_login(client, "bp3-stranger@example.com", "host")
    prop, offer = _listing(client, owner)
    _, other = _listing(client, stranger, address="ul. Obca 99")
    response = listing_rows(client, owner, scope)
    assert response.status_code == 200
    assert response.json() == [{"id": offer, "title": "Tylko wiadomości", "status": "active", "scope": scope}]
    assert other not in response.text
    assert "ul. Rozmowna" not in response.text
    with TestingSession() as db:
        root = db.scalar(select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"]))
        db.execute(delete(PropertyAuthorityScope).where(
            PropertyAuthorityScope.property_authority_id == root.id,
            PropertyAuthorityScope.scope == scope))
        db.commit()
    assert listing_rows(client, owner, scope).json() == []
    assert listing_rows(client, owner).json()[0]["id"] == offer


@pytest.mark.parametrize("change", ["unverified", "revoked", "expired"])
def test_root_must_remain_verified_and_in_force(client, change):
    owner = register_and_login(client, "bp3-owner@example.com", "host")
    prop, _ = _listing(client, owner)
    with TestingSession() as db:
        root = db.scalar(select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"]))
        if change == "unverified":
            root.verification_state = "UNVERIFIED"
        elif change == "revoked":
            root.status = "REVOKED"
        else:
            root.effective_from = authorization_date() - timedelta(days=3)
            root.effective_until = authorization_date() - timedelta(days=1)
        db.commit()
    assert listing_rows(client, owner, "MANAGE_MESSAGES").json() == []
    assert listing_rows(client, owner, "MANAGE_VIEWINGS").json() == []


@pytest.mark.parametrize("scope,other", [("MANAGE_MESSAGES", "MANAGE_VIEWINGS"),
                                         ("MANAGE_VIEWINGS", "MANAGE_MESSAGES")])
def test_mandate_scope_does_not_become_publication_or_other_engagement_right(client, scope, other):
    owner = register_and_login(client, "bp3-owner@example.com", "host")
    agent = register_and_login(client, "bp3-agent@example.com", "guest")
    _, offer = _listing(client, owner)
    grant = client.post("/v1/me/mandates", json={"representative_email": "bp3-agent@example.com",
                                               "scopes": [scope]}, headers=auth(owner))
    assert grant.status_code == 202, grant.text
    assert listing_rows(client, agent).json() == []
    assert listing_rows(client, agent, other).json() == []
    assert listing_rows(client, agent, scope).json()[0]["id"] == offer
    denied = client.post(f"/v1/classifieds/{offer}/pause", headers=auth(agent))
    assert denied.status_code in (403, 404)
    with TestingSession() as db:
        mandate = db.scalar(select(RepresentationMandate))
        mandate.status = "REVOKED"
        db.commit()
    assert listing_rows(client, agent, scope).json() == []


@pytest.mark.parametrize("change", ["expired", "unverified", "missing-root-scope"])
def test_mandate_cannot_amplify_expired_unverified_or_missing_right(client, change):
    owner = register_and_login(client, "bp3-owner@example.com", "host")
    agent = register_and_login(client, "bp3-agent@example.com", "guest")
    prop, _ = _listing(client, owner)
    client.post("/v1/me/mandates", json={"representative_email": "bp3-agent@example.com",
                                       "scopes": ["MANAGE_MESSAGES"]}, headers=auth(owner))
    with TestingSession() as db:
        mandate = db.scalar(select(RepresentationMandate))
        if change == "expired":
            mandate.effective_from = authorization_date() - timedelta(days=3)
            mandate.effective_until = authorization_date() - timedelta(days=1)
        elif change == "unverified":
            mandate.verification_state = "UNVERIFIED"
        else:
            root = db.scalar(select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"]))
            db.execute(delete(PropertyAuthorityScope).where(
                PropertyAuthorityScope.property_authority_id == root.id,
                PropertyAuthorityScope.scope == "MANAGE_MESSAGES"))
        db.commit()
    assert listing_rows(client, agent, "MANAGE_MESSAGES").json() == []


def test_organization_role_and_revocation_are_current(client):
    boss = register_and_login(client, "bp3-boss@example.com", "host")
    org = _agency(client, boss)
    _, offer = _listing(client, boss, organization_id=org["id"])
    agent = _member(client, boss, org["id"], "bp3-agent@example.com", "AGENT")
    viewer = _member(client, boss, org["id"], "bp3-viewer@example.com", "VIEWER")
    assert listing_rows(client, agent, "MANAGE_VIEWINGS").json()[0]["id"] == offer
    assert listing_rows(client, viewer, "MANAGE_VIEWINGS").json() == []
    agent_id = client.get("/v1/me", headers=auth(agent)).json()["id"]
    with TestingSession() as db:
        member = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == agent_id))
        member.status = "REVOKED"
        db.commit()
    assert listing_rows(client, agent, "MANAGE_VIEWINGS").json() == []
