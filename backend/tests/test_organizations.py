"""Acting for someone else: organisations and mandates (Schema v1 §18–§22, §32, §114).

The rules a membership or mandate must never bend:

* it opens a path only to rights the legal party at the end already holds;
* the path closes the moment the membership, the mandate or the organisation
  stops being active — or the date it was limited to passes;
* a role or a mandate scope limits what may be done along it;
* asking whether a person or organisation exists gets the same answer either way.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.modules.identity.models import (
    LegalParty,
    Organization,
    OrganizationMembership,
    RepresentationMandate,
)
from app.modules.properties.models import PropertyAuthority
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership

PROPERTY = {
    "property_type": "apartment",
    "city": "Gdynia",
    "municipality": "Gdynia",
    "address": "ul. Agencyjna 1",
    "area_m2": 48,
    "rooms": 2,
    "capacity": 3,
}
OFFER = {"title": "Oferta agencji", "rent_amount": 240000, "min_term_months": 12,
         "contact_mode": "message"}


def _org(client, token, slug="agencja-morska"):
    resp = client.post(
        "/v1/organizations",
        json={"display_name": "Agencja Morska", "slug": slug,
              "legal_name": "Agencja Morska Sp. z o.o.", "registration_number": "0000123456"},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _join(client, owner_token, org_id, member_email, role):
    member = register_and_login(client, member_email, "host")
    assert client.post(
        f"/v1/organizations/{org_id}/members", json={"email": member_email, "role": role},
        headers=auth(owner_token),
    ).status_code == 202
    assert client.post(
        f"/v1/organizations/{org_id}/membership/accept", headers=auth(member)
    ).status_code == 200
    return member


def _org_property(client, token, org_id, address="ul. Agencyjna 1", verify=True):
    resp = client.post(
        "/v1/properties",
        json={**PROPERTY, "address": address, "organization_id": org_id,
              "authority_type": "PROPERTY_MANAGER"},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    if verify:
        verify_ownership(client, token, resp.json()["id"])
    return resp.json()


def _draft(client, token, property_id):
    return client.post(f"/v1/properties/{property_id}/classifieds", json=OFFER,
                       headers=auth(token))


def _publish(client, token, offer_id):
    return client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(token))


@pytest.fixture
def boss(client):
    return register_and_login(client, "boss@agencja.pl", "host")


# --- the organisation and its legal side --------------------------------------


def test_creating_an_organisation_makes_its_legal_party_and_an_owner(client, boss):
    org = _org(client, boss)
    assert org["my_role"] == "OWNER"
    with TestingSession() as db:
        party = db.get(LegalParty, org["legal_party_id"])
    assert party.party_type == "ORGANIZATION"
    assert party.display_name == "Agencja Morska Sp. z o.o."


def test_slugs_are_unique(client, boss):
    _org(client, boss)
    resp = client.post(
        "/v1/organizations",
        json={"display_name": "Inna", "slug": "agencja-morska", "legal_name": "Inna S.A."},
        headers=auth(boss),
    )
    assert resp.status_code == 409


def test_a_property_registered_for_the_organisation_is_held_by_it(client, boss):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"], verify=False)
    with TestingSession() as db:
        authority = db.scalar(select(PropertyAuthority).where(
            PropertyAuthority.property_id == prop["id"]))
    assert authority.holder_legal_party_id == org["legal_party_id"]
    assert authority.authority_type == "PROPERTY_MANAGER"


def test_an_organisation_claim_is_verified_against_its_legal_name(client, boss):
    """No person's name is needed: the company's registered name is what the
    evidence is checked against, and it was given at creation."""
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"], verify=False)
    from tests.conftest import admin_login

    admin = admin_login(client)
    resp = client.post(
        f"/v1/admin/property-authorities/{prop['authorities'][0]['id']}/verify",
        headers=auth(admin),
    )
    assert resp.status_code == 200, resp.text


# --- members act within their role -------------------------------------------


def test_an_agent_can_list_and_publish_the_organisations_flat(client, boss):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"])
    agent = _join(client, boss, org["id"], "agent@agencja.pl", "AGENT")

    offer = _draft(client, agent, prop["id"])
    assert offer.status_code == 201, offer.text
    assert _publish(client, agent, offer.json()["id"]).status_code == 200


def test_an_agent_sees_the_organisations_flats_in_their_list(client, boss):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"])
    agent = _join(client, boss, org["id"], "lister@agencja.pl", "AGENT")
    assert prop["id"] in client.get("/v1/properties", headers=auth(agent)).text


@pytest.mark.parametrize("role", ["VIEWER", "FINANCE"])
def test_roles_without_the_scope_cannot_list(client, boss, role):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"])
    member = _join(client, boss, org["id"], f"{role.lower()}@agencja.pl", role)
    assert _draft(client, member, prop["id"]).status_code == 404


def test_an_invitation_grants_nothing_until_accepted(client, boss):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"])
    invitee = register_and_login(client, "pending@agencja.pl", "host")
    client.post(f"/v1/organizations/{org['id']}/members",
                json={"email": "pending@agencja.pl", "role": "AGENT"}, headers=auth(boss))

    assert _draft(client, invitee, prop["id"]).status_code == 404


def test_revoking_a_member_closes_the_path_at_once(client, boss):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"])
    agent = _join(client, boss, org["id"], "leaver@agencja.pl", "AGENT")
    offer_id = _draft(client, agent, prop["id"]).json()["id"]
    agent_id = client.get("/v1/me", headers=auth(agent)).json()["id"]

    client.post(f"/v1/organizations/{org['id']}/members/{agent_id}/revoke", headers=auth(boss))
    assert _publish(client, agent, offer_id).status_code == 404
    assert prop["id"] not in client.get("/v1/properties", headers=auth(agent)).text


def test_a_suspended_organisation_authorises_nothing(client, boss):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"])
    with TestingSession() as db:
        db.get(Organization, org["id"]).status = "SUSPENDED"
        db.commit()
    assert _draft(client, boss, prop["id"]).status_code == 404


def test_one_agency_cannot_touch_anothers_flats(client, boss):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"])
    rival_boss = register_and_login(client, "boss@rival.pl", "host")
    _org(client, rival_boss, slug="rival")
    assert _draft(client, rival_boss, prop["id"]).status_code == 404


def test_an_organisation_cannot_publish_an_unverified_claim(client, boss):
    org = _org(client, boss)
    prop = _org_property(client, boss, org["id"], verify=False)
    offer_id = _draft(client, boss, prop["id"]).json()["id"]
    assert _publish(client, boss, offer_id).status_code == 403


def test_registering_for_an_organisation_you_are_not_in_is_refused(client, boss):
    org = _org(client, boss)
    outsider = register_and_login(client, "outsider@example.com", "host")
    resp = client.post("/v1/properties", json={**PROPERTY, "organization_id": org["id"]},
                       headers=auth(outsider))
    assert resp.status_code == 404


def test_a_viewer_cannot_register_for_the_organisation(client, boss):
    org = _org(client, boss)
    viewer = _join(client, boss, org["id"], "looker@agencja.pl", "VIEWER")
    resp = client.post("/v1/properties", json={**PROPERTY, "organization_id": org["id"]},
                       headers=auth(viewer))
    assert resp.status_code == 404


# --- managing members ---------------------------------------------------------


def test_only_owners_and_admins_invite(client, boss):
    org = _org(client, boss)
    agent = _join(client, boss, org["id"], "noinvite@agencja.pl", "AGENT")
    register_and_login(client, "friend@example.com", "host")
    resp = client.post(f"/v1/organizations/{org['id']}/members",
                       json={"email": "friend@example.com", "role": "AGENT"},
                       headers=auth(agent))
    assert resp.status_code == 403


def test_inviting_an_unknown_address_looks_the_same_as_a_known_one(client, boss):
    """Otherwise this endpoint answers "does this person use Homies?"."""
    org = _org(client, boss)
    register_and_login(client, "known@example.com", "host")
    known = client.post(f"/v1/organizations/{org['id']}/members",
                        json={"email": "known@example.com", "role": "AGENT"},
                        headers=auth(boss))
    unknown = client.post(f"/v1/organizations/{org['id']}/members",
                          json={"email": "nobody-here@example.com", "role": "AGENT"},
                          headers=auth(boss))
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())


def test_the_last_owner_cannot_be_removed(client, boss):
    org = _org(client, boss)
    boss_id = client.get("/v1/me", headers=auth(boss)).json()["id"]
    resp = client.post(f"/v1/organizations/{org['id']}/members/{boss_id}/revoke",
                       headers=auth(boss))
    assert resp.status_code == 409


def test_a_stranger_learns_nothing_about_an_organisation(client, boss):
    org = _org(client, boss)
    stranger = register_and_login(client, "nosy@example.com", "host")
    assert client.get(f"/v1/organizations/{org['id']}/members",
                      headers=auth(stranger)).status_code == 404


def test_ownership_cannot_be_handed_out_by_invitation(client, boss):
    org = _org(client, boss)
    resp = client.post(f"/v1/organizations/{org['id']}/members",
                       json={"email": "x@example.com", "role": "OWNER"}, headers=auth(boss))
    assert resp.status_code == 422


# --- mandates -----------------------------------------------------------------


@pytest.fixture
def owner_flat(client):
    owner = register_and_login(client, "principal@example.com", "host")
    prop = client.post("/v1/properties", json={**PROPERTY, "address": "ul. Właściciela 5"},
                       headers=auth(owner)).json()
    verify_ownership(client, owner, prop["id"])
    return owner, prop["id"]


def _mandate(client, principal, email, scopes, **dates):
    body = {"representative_email": email, "scopes": scopes}
    body.update({k: v.isoformat() for k, v in dates.items()})
    return client.post("/v1/me/mandates", json=body, headers=auth(principal))


def test_a_mandate_lets_the_representative_publish(client, owner_flat):
    owner, prop = owner_flat
    rep = register_and_login(client, "trusted@example.com", "host")
    assert _mandate(client, owner, "trusted@example.com",
                    ["MANAGE_PROPERTY", "PUBLISH_LISTING"]).status_code == 202

    offer = _draft(client, rep, prop)
    assert offer.status_code == 201, offer.text
    assert _publish(client, rep, offer.json()["id"]).status_code == 200


def test_a_mandate_is_limited_to_its_scopes(client, owner_flat):
    owner, prop = owner_flat
    rep = register_and_login(client, "viewings-only@example.com", "host")
    _mandate(client, owner, "viewings-only@example.com", ["MANAGE_VIEWINGS"])
    assert _draft(client, rep, prop).status_code == 404


def test_a_mandate_passes_on_nothing_the_principal_lacks(client, owner_flat):
    """The principal's own claim is unverified here, so the representative
    may prepare but not publish — exactly what the principal could do."""
    owner = register_and_login(client, "unverified-principal@example.com", "host")
    prop = client.post("/v1/properties", json={**PROPERTY, "address": "ul. Niezweryfikowana 1"},
                       headers=auth(owner)).json()["id"]
    rep = register_and_login(client, "eager@example.com", "host")
    _mandate(client, owner, "eager@example.com", ["MANAGE_PROPERTY", "PUBLISH_LISTING"])

    offer_id = _draft(client, rep, prop).json()["id"]
    assert _publish(client, rep, offer_id).status_code == 403


def test_a_revoked_mandate_closes_the_path(client, owner_flat):
    owner, prop = owner_flat
    rep = register_and_login(client, "fired@example.com", "host")
    _mandate(client, owner, "fired@example.com", ["MANAGE_PROPERTY", "PUBLISH_LISTING"])
    mandate_id = client.get("/v1/me/mandates", headers=auth(owner)).json()[0]["id"]

    client.post(f"/v1/me/mandates/{mandate_id}/revoke", headers=auth(owner))
    assert _draft(client, rep, prop).status_code == 404


def test_a_mandate_works_only_inside_its_dates(client, owner_flat):
    owner, prop = owner_flat
    register_and_login(client, "later@example.com", "host")
    rep = client.post("/v1/auth/login", json={"email": "later@example.com",
                                              "password": "password-123456"}).json()
    rep = rep["access_token"]
    _mandate(client, owner, "later@example.com", ["MANAGE_PROPERTY", "PUBLISH_LISTING"],
             effective_from=date.today() + timedelta(days=7))
    assert _draft(client, rep, prop).status_code == 404

    with TestingSession() as db:
        m = db.scalar(select(RepresentationMandate))
        m.effective_from = date.today() - timedelta(days=30)
        m.effective_until = date.today() - timedelta(days=1)
        db.commit()
    assert _draft(client, rep, prop).status_code == 404


def test_an_unverified_mandate_authorises_nothing(client, owner_flat):
    owner, prop = owner_flat
    rep = register_and_login(client, "unchecked@example.com", "host")
    _mandate(client, owner, "unchecked@example.com", ["MANAGE_PROPERTY", "PUBLISH_LISTING"])
    with TestingSession() as db:
        db.scalar(select(RepresentationMandate)).verification_state = "PENDING"
        db.commit()
    assert _draft(client, rep, prop).status_code == 404


def test_only_the_principal_can_revoke(client, owner_flat):
    owner, _ = owner_flat
    rep = register_and_login(client, "holder@example.com", "host")
    _mandate(client, owner, "holder@example.com", ["MANAGE_VIEWINGS"])
    mandate_id = client.get("/v1/me/mandates", headers=auth(rep)).json()[0]["id"]
    assert client.post(f"/v1/me/mandates/{mandate_id}/revoke",
                       headers=auth(rep)).status_code == 404


def test_a_representative_cannot_pass_the_mandate_on(client, owner_flat):
    """A mandate the representative grants is over their OWN legal person,
    which holds nothing on the principal's flat."""
    owner, prop = owner_flat
    rep = register_and_login(client, "middle@example.com", "host")
    third = register_and_login(client, "third@example.com", "host")
    _mandate(client, owner, "middle@example.com", ["MANAGE_PROPERTY", "PUBLISH_LISTING"])
    _mandate(client, rep, "third@example.com", ["MANAGE_PROPERTY", "PUBLISH_LISTING"])
    assert _draft(client, third, prop).status_code == 404


def test_granting_to_an_unknown_address_looks_the_same(client, owner_flat):
    owner, _ = owner_flat
    register_and_login(client, "real@example.com", "host")
    known = _mandate(client, owner, "real@example.com", ["MANAGE_VIEWINGS"])
    unknown = _mandate(client, owner, "ghost@example.com", ["MANAGE_VIEWINGS"])
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())


def test_a_mandate_cannot_end_before_it_starts(client, owner_flat):
    owner, _ = owner_flat
    resp = _mandate(client, owner, "x@example.com", ["MANAGE_VIEWINGS"],
                    effective_from=date.today(), effective_until=date.today() - timedelta(days=1))
    assert resp.status_code == 422


def test_membership_uniqueness_is_enforced_by_the_database(client, boss):
    org = _org(client, boss)
    boss_id = client.get("/v1/me", headers=auth(boss)).json()["id"]
    with TestingSession() as db:
        db.add(OrganizationMembership(organization_id=org["id"], user_id=boss_id,
                                      role="AGENT", status="ACTIVE"))
        with pytest.raises(Exception):  # noqa: B017 — unique violation
            db.commit()


def test_organisation_and_mandate_writes_are_throttled(client):
    from app.core import ratelimit as rl

    assert rl.resolve_policy("POST", "/v1/organizations") is rl.PROPERTY_WRITE
    assert rl.resolve_policy("POST", "/v1/organizations/x/members") is rl.PROPERTY_WRITE
    assert rl.resolve_policy("POST", "/v1/me/mandates") is rl.PROPERTY_WRITE
