"""BP-9: private data requires verified, current, scoped provider authority."""
from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app.modules.alerts.models import UserNotification
from app.modules.engagement import access
from app.modules.engagement.models import Conversation, ConversationParticipant
from app.modules.identity.models import RepresentationMandate, RepresentationMandateScope
from app.modules.properties.models import PropertyAuthority, PropertyAuthorityScope
from app.modules.trust import notices
from tests.conftest import TestingSession, auth, authorization_date, register_and_login
from tests.test_conversations import _listing, _start, send_json
from tests.test_engagement_safety import _decide, _request, _viewing_ready
from tests.test_reports_moderation import _me, _moderator


@pytest.fixture
def setup(client):
    owner = register_and_login(client, "bp9-owner@example.com", "host")
    tenant = register_and_login(client, "bp9-tenant@example.com", "guest")
    prop, listing = _listing(client, owner)
    conv = _start(client, tenant, listing, "private-bp9-body").json()["conversation"]["id"]
    day = _viewing_ready(client, owner, listing)
    viewing = _request(client, tenant, listing, day, 10).json()["id"]
    return owner, tenant, prop["id"], listing, conv, viewing, day


def _invalidate(prop, kind):
    with TestingSession() as db:
        root = db.scalar(select(PropertyAuthority).where(PropertyAuthority.property_id == prop))
        if kind == "unverified":
            root.verification_state = "UNVERIFIED"
        elif kind == "revoked":
            root.status = "REVOKED"
        elif kind == "expired":
            root.effective_from = authorization_date() - timedelta(days=3)
            root.effective_until = authorization_date() - timedelta(days=1)
        elif kind == "scope":
            db.execute(delete(PropertyAuthorityScope).where(
                PropertyAuthorityScope.property_authority_id == root.id,
                PropertyAuthorityScope.scope.in_(["MANAGE_MESSAGES", "MANAGE_VIEWINGS"])))
        db.commit()


@pytest.mark.parametrize("kind", ["unverified", "revoked", "expired", "scope", "stranger"])
def test_all_private_provider_paths_refuse_and_requester_keeps_access(client, setup, kind):
    owner, tenant, prop, listing, conv, viewing, day = setup
    key = send_json("provider-existing-reply")
    path = f"/v1/conversations/{conv}"
    assert client.post(path + "/messages", json=key, headers=auth(owner)).status_code == 201
    owner_id = _me(client, owner)
    _invalidate(prop, kind)
    actor = register_and_login(client, "bp9-stranger@example.com", "host") if kind == "stranger" else owner
    responses = [client.get(path, headers=auth(actor)),
                 client.get(f"/v1/classifieds/{listing}/viewings", headers=auth(actor))]
    for suffix, body in [("messages", key), ("messages", send_json("new-private")),
                         ("assign", {"user_id": owner_id}),
                         ("stage", {"provider_stage": "SHORTLISTED"})]:
        responses.append(client.post(path + "/" + suffix, json=body, headers=auth(actor)))
    for suffix in ("confirm", "decline", "cancel", "outcome"):
        responses.append(client.post(f"/v1/viewings/{viewing}/{suffix}",
                                    json={"outcome": "COMPLETED"}, headers=auth(actor)))
    responses.append(client.put(f"/v1/classifieds/{listing}/viewing-settings",
                               json={"duration_minutes": 30}, headers=auth(actor)))
    for response in responses:
        assert response.status_code == 404, response.text
        assert "private-bp9-body" not in response.text
        assert "requester_user_id" not in response.text
    assert client.get("/v1/conversations", headers=auth(actor)).json() == []
    assert client.get(path, headers=auth(tenant)).status_code == 200
    assert client.post(path + "/messages", json=send_json("still mine"),
                       headers=auth(tenant)).status_code == 201
    assert client.post(f"/v1/viewings/{viewing}/cancel", headers=auth(tenant)).status_code == 200


@pytest.mark.parametrize("kind", ["valid", "unverified", "expired", "revoked", "scope"])
def test_representative_requires_verified_root_and_valid_scoped_mandate(client, setup, kind):
    owner, tenant, prop, listing, conv, viewing, day = setup
    representative = register_and_login(client, "bp9-rep@example.com", "guest")
    response = client.post("/v1/me/mandates", json={"representative_email": "bp9-rep@example.com",
        "scopes": ["MANAGE_MESSAGES", "MANAGE_VIEWINGS"]}, headers=auth(owner))
    assert response.status_code == 202, response.text
    if kind == "unverified":
        _invalidate(prop, kind)
    with TestingSession() as db:
        mandate = db.scalar(select(RepresentationMandate))
        if kind == "expired":
            mandate.effective_from = authorization_date() - timedelta(days=3)
            mandate.effective_until = authorization_date() - timedelta(days=1)
        elif kind == "revoked":
            mandate.status = "REVOKED"
        elif kind == "scope":
            db.execute(delete(RepresentationMandateScope).where(
                RepresentationMandateScope.mandate_id == mandate.id))
        db.commit()
    expected = 200 if kind == "valid" else 404
    assert client.get(f"/v1/conversations/{conv}", headers=auth(representative)).status_code == expected
    assert client.get(f"/v1/classifieds/{listing}/viewings",
                      headers=auth(representative)).status_code == expected


def test_unverified_root_cannot_be_recorded_as_provider_or_bypass_own_listing(client, setup):
    owner, tenant, prop, listing, conv, viewing, day = setup
    _invalidate(prop, "unverified")
    other = register_and_login(client, "bp9-other@example.com", "guest")
    created = _start(client, other, listing)
    assert created.status_code == 201, created.text
    with TestingSession() as db:
        participants = list(db.scalars(select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == created.json()["conversation"]["id"])))
        assert len(participants) == 1
        old = db.get(Conversation, conv)
        assert access.side(db, _me(client, owner), old) is None
        assert access.side(db, _me(client, owner), old, verified=False) == "provider"
    assert _start(client, owner, listing).status_code == 409
    assert _request(client, owner, listing, day, 11).status_code == 409


@pytest.mark.parametrize("kind", ["valid", "unverified", "revoked", "expired", "scope"])
def test_bp6_notification_recipients_use_verified_current_viewing_authority(client, setup, kind):
    owner, tenant, prop, listing, conv, viewing, day = setup
    _invalidate(prop, kind)
    response = _decide(client, _moderator(client), "CONVERSATION", conv,
                       "FEATURE_RESTRICTED", "HARASSMENT")
    assert response.status_code == 201, response.text
    expected = {_me(client, tenant)}
    if kind == "valid":
        expected.add(_me(client, owner))
    with TestingSession() as db:
        recipients = set(db.scalars(select(UserNotification.user_id).where(
            UserNotification.notification_type == notices.VIEWING_CANCELLED)))
        assert recipients == expected


def test_assignment_candidate_and_ownership_transfer_are_current(client, setup):
    from app.modules.identity.models import User
    from app.modules.identity.parties import personal_party

    owner, tenant, prop, listing, conv, viewing, day = setup
    candidate = register_and_login(client, "bp9-assignee@example.com", "guest")
    candidate_id = _me(client, candidate)
    with TestingSession() as db:
        party = personal_party(db, db.get(User, candidate_id))
        root = PropertyAuthority(property_id=prop, holder_legal_party_id=party.id,
            authority_type="OWNER", status="ACTIVE", verification_state="UNVERIFIED",
            effective_from=authorization_date(), created_by_user_id=candidate_id)
        db.add(root)
        db.flush()
        root_id = root.id
        db.add(PropertyAuthorityScope(property_authority_id=root_id, scope="MANAGE_MESSAGES"))
        db.commit()
    path = f"/v1/conversations/{conv}"
    assert client.post(path + "/assign", json={"user_id": candidate_id},
                       headers=auth(owner)).status_code == 422
    with TestingSession() as db:
        db.get(PropertyAuthority, root_id).verification_state = "VERIFIED"
        former = db.scalar(select(PropertyAuthority).where(PropertyAuthority.property_id == prop,
                                                          PropertyAuthority.id != root_id))
        former.status = "REVOKED"
        db.commit()
    assert client.get(path, headers=auth(owner)).status_code == 404
    assert client.get(path, headers=auth(candidate)).status_code == 200
    assert client.post(path + "/assign", json={"user_id": candidate_id},
                       headers=auth(candidate)).status_code == 200
    assert client.get(path, headers=auth(tenant)).status_code == 200


@pytest.mark.parametrize("invalid", ["root", "membership", "organization"])
def test_organization_chain_still_needs_verified_root_and_active_links(client, invalid):
    from app.modules.identity.models import Organization, OrganizationMembership
    from tests.test_conversations import _agency, _member

    boss = register_and_login(client, "bp9-boss@example.com", "host")
    tenant = register_and_login(client, "bp9-org-tenant@example.com", "guest")
    org = _agency(client, boss)
    prop, listing = _listing(client, boss, organization_id=org["id"])
    agent = _member(client, boss, org["id"], "bp9-agent@example.com", "AGENT")
    agent_id = _me(client, agent)
    conv = _start(client, tenant, listing).json()["conversation"]["id"]
    assert client.get(f"/v1/conversations/{conv}", headers=auth(agent)).status_code == 200
    if invalid == "root":
        _invalidate(prop["id"], "unverified")
    else:
        with TestingSession() as db:
            if invalid == "membership":
                member = db.scalar(select(OrganizationMembership).where(
                    OrganizationMembership.user_id == agent_id))
                member.status = "REVOKED"
            else:
                db.get(Organization, org["id"]).status = "SUSPENDED"
            db.commit()
    assert client.get(f"/v1/conversations/{conv}", headers=auth(agent)).status_code == 404
    assert client.get("/v1/conversations", headers=auth(agent)).json() == []


@pytest.mark.parametrize("invalid", ["valid", "revoked", "scope", "expired"])
def test_notification_mandate_is_independently_filtered(client, setup, invalid):
    owner, tenant, prop, listing, conv, viewing, day = setup
    rep = register_and_login(client, "bp9-notice-rep@example.com", "guest")
    response = client.post("/v1/me/mandates", json={
        "representative_email": "bp9-notice-rep@example.com", "scopes": ["MANAGE_VIEWINGS"]},
        headers=auth(owner))
    assert response.status_code == 202
    with TestingSession() as db:
        mandate = db.scalar(select(RepresentationMandate))
        if invalid == "revoked":
            mandate.status = "REVOKED"
        elif invalid == "expired":
            mandate.effective_from = authorization_date() - timedelta(days=2)
            mandate.effective_until = authorization_date() - timedelta(days=1)
        elif invalid == "scope":
            db.execute(delete(RepresentationMandateScope))
        db.commit()
    response = _decide(client, _moderator(client), "CONVERSATION", conv,
                       "FEATURE_RESTRICTED", "HARASSMENT")
    assert response.status_code == 201, response.text
    expected = {_me(client, owner), _me(client, tenant)}
    if invalid == "valid":
        expected.add(_me(client, rep))
    with TestingSession() as db:
        assert set(db.scalars(select(UserNotification.user_id).where(
            UserNotification.notification_type == notices.VIEWING_CANCELLED))) == expected


@pytest.mark.parametrize("target", ["CONVERSATION", "MESSAGE"])
def test_unverified_manager_remains_conflicted_as_moderator(client, setup, target):
    from app.modules.engagement.models import Message
    from app.modules.identity.models import User

    owner, tenant, prop, listing, conv, viewing, day = setup
    owner_id = _me(client, owner)
    _invalidate(prop, "unverified")
    with TestingSession() as db:
        db.get(User, owner_id).role = "admin"
        message = db.scalar(select(Message.id).where(Message.conversation_id == conv))
        db.commit()
    result = _decide(client, owner, target, conv if target == "CONVERSATION" else message,
                     "FEATURE_RESTRICTED" if target == "CONVERSATION" else "CONTENT_REMOVED",
                     "HARASSMENT")
    assert result.status_code == 403, result.text
