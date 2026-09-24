"""Conversations about a listing (Domain Schema v1 §53–§55, §113–§114).

What must hold:

* the tenant and whoever answers for the listing *right now* can read and
  write; nobody else learns the conversation exists;
* access follows the right: an agent who leaves loses the thread, a newcomer
  with the right gains it, an owner whose authority is revoked is out;
* the provider's lead handling (stage, assignee) is invisible to the tenant;
* one tenant cannot blast every owner on the board.
"""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.engagement.models import Conversation, ConversationParticipant, Message
from tests.conftest import (
    TestingSession,
    admin_login,
    auth,
    register_and_login,
    verify_ownership,
)

PROPERTY = {
    "property_type": "apartment",
    "city": "Toruń",
    "municipality": "Toruń",
    "address": "ul. Rozmowna 1",
    "area_m2": 40,
    "rooms": 2,
    "capacity": 2,
}
OFFER = {"title": "Tylko wiadomości", "rent_amount": 190000, "min_term_months": 12,
         "contact_mode": "message"}


def _listing(client, token, address="ul. Rozmowna 1", organization_id=None):
    body = {**PROPERTY, "address": address}
    if organization_id:
        body["organization_id"] = organization_id
    prop = client.post("/v1/properties", json=body, headers=auth(token)).json()
    verify_ownership(client, token, prop["id"])
    offer = client.post(f"/v1/properties/{prop['id']}/classifieds", json=OFFER,
                        headers=auth(token)).json()["id"]
    assert client.post(f"/v1/classifieds/{offer}/publish",
                       headers=auth(token)).status_code == 200
    return prop, offer


def _start(client, token, offer, body="Dzień dobry, czy mieszkanie jest dostępne?"):
    return client.post(f"/v1/classifieds/{offer}/conversations", json={"body": body},
                       headers=auth(token))


def _read(client, token, conv_id):
    return client.get(f"/v1/conversations/{conv_id}", headers=auth(token))


def _send(client, token, conv_id, body="Tak, zapraszam."):
    return client.post(f"/v1/conversations/{conv_id}/messages", json={"body": body},
                       headers=auth(token))


@pytest.fixture
def owner(client):
    return register_and_login(client, "conv-owner@example.com", "host")


@pytest.fixture
def tenant(client):
    return register_and_login(client, "conv-tenant@example.com", "guest")


@pytest.fixture
def thread(client, owner, tenant):
    prop, offer = _listing(client, owner)
    resp = _start(client, tenant, offer)
    assert resp.status_code == 201, resp.text
    return {"property": prop, "offer": offer, "id": resp.json()["conversation"]["id"]}


# --- the basic exchange -------------------------------------------------------


def test_a_tenant_can_write_to_a_messages_only_owner(client, owner, tenant, thread):
    """The channel "messages only" always promised and never had."""
    detail = _read(client, owner, thread["id"]).json()
    assert detail["conversation"]["my_side"] == "provider"
    assert detail["messages"][0]["body"].startswith("Dzień dobry")


def test_the_owner_replies_and_the_tenant_reads_it(client, owner, tenant, thread):
    assert _send(client, owner, thread["id"]).status_code == 201
    bodies = [m["body"] for m in _read(client, tenant, thread["id"]).json()["messages"]]
    assert bodies[-1] == "Tak, zapraszam."


def test_writing_again_continues_the_same_conversation(client, tenant, thread):
    again = _start(client, tenant, thread["offer"], "Jeszcze jedno pytanie")
    assert again.json()["conversation"]["id"] == thread["id"]


def test_the_inbox_shows_each_side_its_conversations(client, owner, tenant, thread):
    assert thread["id"] in client.get("/v1/conversations", headers=auth(owner)).text
    assert thread["id"] in client.get("/v1/conversations", headers=auth(tenant)).text


def test_you_cannot_message_your_own_listing(client, owner, thread):
    assert _start(client, owner, thread["offer"]).status_code == 409


def test_an_unpublished_listing_takes_no_new_conversation(client, owner, tenant):
    prop = client.post("/v1/properties", json={**PROPERTY, "address": "ul. Szkic 2"},
                       headers=auth(owner)).json()
    draft = client.post(f"/v1/properties/{prop['id']}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    assert _start(client, tenant, draft).status_code == 404


@pytest.mark.parametrize("body", ["", "   ", "x" * 4001])
def test_empty_and_oversized_messages_are_refused(client, tenant, thread, body):
    assert _send(client, tenant, thread["id"], body).status_code == 422


def test_a_closed_conversation_takes_no_messages(client, tenant, thread):
    with TestingSession() as db:
        db.get(Conversation, thread["id"]).status = "CLOSED"
        db.commit()
    assert _send(client, tenant, thread["id"]).status_code == 409


# --- nobody else --------------------------------------------------------------


def test_a_stranger_cannot_read_or_write(client, thread):
    stranger = register_and_login(client, "eavesdropper@example.com", "guest")
    assert _read(client, stranger, thread["id"]).status_code == 404
    assert _send(client, stranger, thread["id"]).status_code == 404
    assert thread["id"] not in client.get("/v1/conversations", headers=auth(stranger)).text


def test_the_tenant_does_not_see_the_providers_lead_handling(client, owner, tenant, thread):
    tenant_view = _read(client, tenant, thread["id"]).json()["conversation"]
    owner_view = _read(client, owner, thread["id"]).json()["conversation"]
    for internal in ("provider_stage", "assigned_to_user_id", "requester_user_id"):
        assert internal not in tenant_view
        assert internal in owner_view


def test_a_reply_moves_a_new_lead_to_replied(client, owner, thread):
    _send(client, owner, thread["id"])
    assert _read(client, owner, thread["id"]).json()["conversation"]["provider_stage"] == \
        "REPLIED"


# --- access follows the right --------------------------------------------------


def test_an_owner_whose_right_is_revoked_is_out(client, owner, tenant, thread):
    admin = admin_login(client)
    authority_id = client.get(f"/v1/admin/properties/{thread['property']['id']}/authorities",
                              headers=auth(admin)).json()[0]["id"]
    client.post(f"/v1/admin/property-authorities/{authority_id}/revoke", headers=auth(admin))

    assert _read(client, owner, thread["id"]).status_code == 404
    assert _read(client, tenant, thread["id"]).status_code == 200, \
        "the tenant keeps their own conversation"


def _agency(client, boss):
    org = client.post("/v1/organizations",
                      json={"display_name": "Biuro", "slug": "biuro-torun",
                            "legal_name": "Biuro Sp. z o.o."}, headers=auth(boss)).json()
    return org


def _member(client, boss, org_id, email, role):
    token = register_and_login(client, email, "host")
    client.post(f"/v1/organizations/{org_id}/members", json={"email": email, "role": role},
                headers=auth(boss))
    client.post(f"/v1/organizations/{org_id}/membership/accept", headers=auth(token))
    return token


def test_an_agencys_agents_answer_for_its_listings(client, tenant):
    boss = register_and_login(client, "boss@biuro.pl", "host")
    org = _agency(client, boss)
    _, offer = _listing(client, boss, "ul. Biurowa 3", organization_id=org["id"])
    agent = _member(client, boss, org["id"], "agent@biuro.pl", "AGENT")
    viewer = _member(client, boss, org["id"], "viewer@biuro.pl", "VIEWER")

    conv = _start(client, tenant, offer).json()["conversation"]["id"]
    reply = _send(client, agent, conv)
    assert reply.status_code == 201
    # Names the person AND the organisation they answered for (§55).
    assert reply.json()["sender_organization_id"] == org["id"]
    assert reply.json()["sender_user_id"] == client.get("/v1/me",
                                                        headers=auth(agent)).json()["id"]
    assert _read(client, viewer, conv).status_code == 404

    with TestingSession() as db:
        kinds = {p.participant_type for p in db.scalars(select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conv))}
    assert kinds == {"USER", "ORGANIZATION"}


def test_an_agent_who_leaves_loses_the_thread(client, tenant):
    boss = register_and_login(client, "boss2@biuro.pl", "host")
    org = _agency(client, boss)
    _, offer = _listing(client, boss, "ul. Biurowa 4", organization_id=org["id"])
    agent = _member(client, boss, org["id"], "leaving@biuro.pl", "AGENT")
    conv = _start(client, tenant, offer).json()["conversation"]["id"]
    assert _read(client, agent, conv).status_code == 200

    agent_id = client.get("/v1/me", headers=auth(agent)).json()["id"]
    client.post(f"/v1/organizations/{org['id']}/members/{agent_id}/revoke", headers=auth(boss))
    assert _read(client, agent, conv).status_code == 404


def test_a_mandate_with_messages_scope_answers(client, owner, tenant, thread):
    helper = register_and_login(client, "helper@example.com", "host")
    client.post("/v1/me/mandates", json={"representative_email": "helper@example.com",
                                         "scopes": ["MANAGE_MESSAGES"]}, headers=auth(owner))
    assert _send(client, helper, thread["id"]).status_code == 201


def test_a_mandate_without_messages_scope_does_not(client, owner, tenant, thread):
    shower = register_and_login(client, "shower@example.com", "host")
    client.post("/v1/me/mandates", json={"representative_email": "shower@example.com",
                                         "scopes": ["MANAGE_VIEWINGS"]}, headers=auth(owner))
    assert _read(client, shower, thread["id"]).status_code == 404


# --- lead handling ------------------------------------------------------------


def test_a_lead_can_be_assigned_to_a_colleague_who_can_answer(client, tenant):
    boss = register_and_login(client, "boss3@biuro.pl", "host")
    org = _agency(client, boss)
    _, offer = _listing(client, boss, "ul. Biurowa 5", organization_id=org["id"])
    agent = _member(client, boss, org["id"], "assignee@biuro.pl", "AGENT")
    conv = _start(client, tenant, offer).json()["conversation"]["id"]
    agent_id = client.get("/v1/me", headers=auth(agent)).json()["id"]

    resp = client.post(f"/v1/conversations/{conv}/assign", json={"user_id": agent_id},
                       headers=auth(boss))
    assert resp.status_code == 200
    assert resp.json()["assigned_to_user_id"] == agent_id


def test_a_lead_cannot_be_assigned_to_someone_who_cannot_read_it(client, owner, thread):
    outsider = register_and_login(client, "notcolleague@example.com", "host")
    outsider_id = client.get("/v1/me", headers=auth(outsider)).json()["id"]
    resp = client.post(f"/v1/conversations/{thread['id']}/assign",
                       json={"user_id": outsider_id}, headers=auth(owner))
    assert resp.status_code == 422


def test_the_tenant_cannot_touch_lead_handling(client, tenant, thread):
    assert client.post(f"/v1/conversations/{thread['id']}/stage",
                       json={"provider_stage": "SHORTLISTED"},
                       headers=auth(tenant)).status_code == 404


def test_an_unknown_stage_is_refused(client, owner, thread):
    assert client.post(f"/v1/conversations/{thread['id']}/stage",
                       json={"provider_stage": "MAYBE"},
                       headers=auth(owner)).status_code == 422


# --- the cap ------------------------------------------------------------------


def test_new_conversations_are_capped_but_open_ones_continue(client, owner, tenant):
    original = settings.conversation_daily_quota
    settings.conversation_daily_quota = 2
    try:
        offers = [_listing(client, owner, f"ul. Limit {i}")[1] for i in range(3)]
        first = _start(client, tenant, offers[0])
        assert first.status_code == 201
        assert _start(client, tenant, offers[1]).status_code == 201
        blocked = _start(client, tenant, offers[2])
        assert blocked.status_code == 429, blocked.text

        # An open conversation is not a new stranger reached.
        assert _start(client, tenant, offers[0], "Dalej").status_code == 201
        assert _send(client, tenant, first.json()["conversation"]["id"]).status_code == 201
    finally:
        settings.conversation_daily_quota = original


# --- database invariants ------------------------------------------------------


def test_a_participant_is_exactly_one_identity(client, thread):
    with TestingSession() as db:
        db.add(ConversationParticipant(conversation_id=thread["id"], participant_type="USER",
                                       user_id=None, organization_id=None))
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation
            db.commit()


def test_a_persons_message_must_name_the_person(client, thread):
    with TestingSession() as db:
        db.add(Message(conversation_id=thread["id"], message_type="USER", body="anonymous"))
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation
            db.commit()


def test_messaging_is_throttled(client):
    from app.core import ratelimit as rl

    assert rl.resolve_policy("POST", "/v1/classifieds/x/conversations") is rl.CONVERSATION_START
    assert rl.resolve_policy("POST", "/v1/conversations/x/messages") is rl.MESSAGE_WRITE
    assert rl.CONVERSATION_START.capacity < rl.MESSAGE_WRITE.capacity
