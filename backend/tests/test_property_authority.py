"""Rights over a property belong to a legal party, and publishing needs them
checked (Domain Schema v1 §16, §30–§32, §50, §105).

Before this, "who may manage this flat" meant `properties.owner_id ==
user.id`: whoever typed the address in owned it, for ever, unchecked. On a free
board that is the whole fraud model — list a flat you do not own, collect a
deposit, disappear. These tests are about the gate that closes it and the ways
such gates usually leak: a revoked right that still publishes, a live listing
that outlives the right behind it, a verification that vouches for a name
changed afterwards, and a refusal that tells a stranger which ids are real.
"""

import pytest
from sqlalchemy import select

from app.modules.identity.models import LegalParty, PersonLegalParty
from app.modules.properties.models import (
    OWNER_PHASE1_SCOPES,
    PropertyAuthority,
    PropertyAuthorityScope,
)
from tests.conftest import (
    TestingSession,
    admin_login,
    auth,
    register_and_login,
    verify_ownership,
)

PROPERTY = {
    "property_type": "apartment",
    "city": "Gdańsk",
    "municipality": "Gdańsk",
    "address": "ul. Prawna 3",
    "area_m2": 44,
    "rooms": 2,
    "capacity": 3,
}

OFFER = {
    "title": "Mieszkanie długoterminowo",
    "rent_amount": 260000,
    "min_term_months": 12,
    "contact_mode": "message",
}


@pytest.fixture
def owner(client):
    return register_and_login(client, "claimant@example.com", "host")


def _register(client, token, address="ul. Prawna 3"):
    resp = client.post(
        "/v1/properties", json={**PROPERTY, "address": address}, headers=auth(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _draft(client, token, property_id):
    resp = client.post(
        f"/v1/properties/{property_id}/classifieds", json=OFFER, headers=auth(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _publish(client, token, offer_id):
    return client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(token))


def _name(client, token, first="Anna", last="Nowak"):
    return client.put(
        "/v1/me/legal-identity",
        json={"legal_first_name": first, "legal_last_name": last},
        headers=auth(token),
    )


# --- registering a flat is a claim, not a proof -------------------------------


def test_registering_a_property_records_an_unverified_owner_claim(client, owner):
    prop = _register(client, owner)

    [claim] = prop["authorities"]
    assert claim["authority_type"] == "OWNER"
    assert claim["status"] == "ACTIVE"
    assert claim["verification_state"] == "UNVERIFIED"
    assert sorted(claim["scopes"]) == sorted(OWNER_PHASE1_SCOPES)


def test_the_claim_is_held_by_a_legal_party_not_by_the_account(client, owner):
    """Schema v1 §13/§30: a User is who is typing; the right belongs to the
    legal person behind them."""
    prop = _register(client, owner)
    user_id = client.get("/v1/me", headers=auth(owner)).json()["id"]

    with TestingSession() as db:
        authority = db.scalar(
            select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"])
        )
        party = db.get(LegalParty, authority.holder_legal_party_id)
        person = db.get(PersonLegalParty, party.id)

    assert party.party_type == "PERSON"
    assert person.linked_user_id == user_id
    assert authority.holder_legal_party_id != user_id


def test_one_account_has_one_legal_person_however_many_flats(client, owner):
    _register(client, owner, "ul. Pierwsza 1")
    _register(client, owner, "ul. Druga 2")

    with TestingSession() as db:
        parties = list(db.scalars(select(PersonLegalParty)))
    assert len(parties) == 1


def test_scopes_outside_the_known_set_are_refused_by_the_database(client, owner):
    """A typo'd scope stored silently would authorise nothing and look fine."""
    prop = _register(client, owner)
    with TestingSession() as db:
        authority = db.scalar(
            select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"])
        )
        db.add(PropertyAuthorityScope(property_authority_id=authority.id, scope="PUBLISH"))
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation, driver-specific type
            db.commit()


# --- the publication gate -----------------------------------------------------


def test_an_unverified_claim_can_prepare_a_listing(client, owner):
    """The owner must be able to do all the work while the claim is checked."""
    prop = _register(client, owner)
    assert _draft(client, owner, prop["id"])


def test_an_unverified_claim_cannot_publish(client, owner):
    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])

    resp = _publish(client, owner, offer_id)
    assert resp.status_code == 403, resp.text
    assert "verified" in resp.text.lower()
    assert offer_id not in client.get("/v1/classifieds").text


def test_a_verified_claim_publishes(client, owner):
    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])
    verify_ownership(client, owner, prop["id"])

    assert _publish(client, owner, offer_id).status_code == 200
    assert offer_id in client.get("/v1/classifieds").text


def test_an_unverified_claim_can_still_take_a_listing_down(client, owner):
    """Stopping a listing must never wait on paperwork."""
    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])
    verify_ownership(client, owner, prop["id"])
    _publish(client, owner, offer_id)

    with TestingSession() as db:
        authority = db.scalar(
            select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"])
        )
        authority.verification_state = "UNVERIFIED"
        db.commit()

    assert client.post(
        f"/v1/classifieds/{offer_id}/pause", headers=auth(owner)
    ).status_code == 200


# --- strangers learn nothing --------------------------------------------------


def test_a_stranger_gets_404_not_403(client, owner):
    """A 403 would confirm the id is real. Same answer as for an id that does
    not exist."""
    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])
    stranger = register_and_login(client, "stranger-auth@example.com", "host")

    assert client.post(
        f"/v1/properties/{prop['id']}/classifieds", json=OFFER, headers=auth(stranger)
    ).status_code == 404
    assert _publish(client, stranger, offer_id).status_code == 404
    assert client.post(
        f"/v1/classifieds/{offer_id}/pause", headers=auth(stranger)
    ).status_code == 404


def test_a_stranger_does_not_see_the_property_in_their_list(client, owner):
    prop = _register(client, owner)
    stranger = register_and_login(client, "stranger-list@example.com", "host")

    assert prop["id"] not in client.get("/v1/properties", headers=auth(stranger)).text
    assert prop["id"] in client.get("/v1/properties", headers=auth(owner)).text


def test_a_verified_stranger_cannot_publish_your_listing(client, owner):
    """Verification is per claim, not per person. Being verified on your own
    flat gives you nothing on mine (Schema v1 §30: identity ≠ authority)."""
    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])

    other = register_and_login(client, "verified-other@example.com", "host")
    theirs = _register(client, other, "ul. Obca 9")
    verify_ownership(client, other, theirs["id"])

    assert _publish(client, other, offer_id).status_code == 404


# --- verification is a checked decision ---------------------------------------


def test_verification_needs_a_legal_name(client, owner):
    """Ownership is checked against a land-register entry, which names a legal
    person. Verifying a claim with no legal name vouches for nobody."""
    prop = _register(client, owner)
    admin = admin_login(client)

    resp = client.post(
        f"/v1/admin/property-authorities/{prop['authorities'][0]['id']}/verify",
        headers=auth(admin),
    )
    assert resp.status_code == 409, resp.text
    assert "legal" in resp.text.lower()


def test_the_legal_name_locks_once_a_claim_is_verified(client, owner):
    """Otherwise a verified owner renames themselves and the verification
    silently vouches for a person nobody checked."""
    assert _name(client, owner).status_code == 200
    assert _name(client, owner, "Ewa", "Zielińska").status_code == 200  # still editable

    prop = _register(client, owner)
    verify_ownership(client, owner, prop["id"])

    resp = _name(client, owner, "Someone", "Else")
    assert resp.status_code == 409, resp.text

    with TestingSession() as db:
        person = db.scalar(select(PersonLegalParty))
    assert (person.legal_first_name, person.legal_last_name) == ("Jan", "Kowalski")


def test_only_admins_verify(client, owner):
    prop = _register(client, owner)
    _name(client, owner)
    resp = client.post(
        f"/v1/admin/property-authorities/{prop['authorities'][0]['id']}/verify",
        headers=auth(owner),
    )
    assert resp.status_code == 403


def test_verification_is_audited(client, owner):
    from app.core.audit import AuditLog

    prop = _register(client, owner)
    verify_ownership(client, owner, prop["id"])

    with TestingSession() as db:
        actions = [
            row.action
            for row in db.scalars(
                select(AuditLog).where(AuditLog.entity_id == prop["authorities"][0]["id"])
            )
        ]
    assert "property_authority.verified" in actions


# --- revocation ---------------------------------------------------------------


def test_revocation_stops_publication(client, owner):
    """Schema v1 §105: a revoked authority authorises nothing new."""
    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])
    verify_ownership(client, owner, prop["id"])
    admin = admin_login(client)
    client.post(
        f"/v1/admin/property-authorities/{prop['authorities'][0]['id']}/revoke",
        headers=auth(admin),
    )

    assert _publish(client, owner, offer_id).status_code == 404


def test_revocation_takes_down_what_the_right_was_holding_up(client, owner):
    """A fake owner caught after publishing must not keep the listing live
    until they choose to remove it."""
    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])
    verify_ownership(client, owner, prop["id"])
    _publish(client, owner, offer_id)
    assert offer_id in client.get("/v1/classifieds").text

    admin = admin_login(client)
    resp = client.post(
        f"/v1/admin/property-authorities/{prop['authorities'][0]['id']}/revoke",
        headers=auth(admin),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["paused_offers"] == [offer_id]
    assert offer_id not in client.get("/v1/classifieds").text


def test_a_listing_stays_up_if_another_verified_right_backs_it(client, owner):
    """Revoking one co-owner's authority must not pull a listing another
    verified owner is entitled to keep."""
    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])
    verify_ownership(client, owner, prop["id"])
    _publish(client, owner, offer_id)

    with TestingSession() as db:
        original = db.scalar(
            select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"])
        )
        second = PropertyAuthority(
            property_id=prop["id"],
            holder_legal_party_id=original.holder_legal_party_id,
            authority_type="CO_OWNER",
            status="ACTIVE",
            verification_state="VERIFIED",
            effective_from=original.effective_from,
            created_by_user_id=original.created_by_user_id,
        )
        db.add(second)
        db.flush()
        db.add(PropertyAuthorityScope(property_authority_id=second.id, scope="PUBLISH_LISTING"))
        db.commit()

    admin = admin_login(client)
    resp = client.post(
        f"/v1/admin/property-authorities/{prop['authorities'][0]['id']}/revoke",
        headers=auth(admin),
    )
    assert resp.json()["paused_offers"] == []
    assert offer_id in client.get("/v1/classifieds").text


def test_a_revoked_right_cannot_be_verified_back_into_force(client, owner):
    prop = _register(client, owner)
    _name(client, owner)
    admin = admin_login(client)
    authority_id = prop["authorities"][0]["id"]
    client.post(f"/v1/admin/property-authorities/{authority_id}/revoke", headers=auth(admin))

    resp = client.post(
        f"/v1/admin/property-authorities/{authority_id}/verify", headers=auth(admin)
    )
    assert resp.status_code == 409


def test_an_expired_right_authorises_nothing(client, owner):
    """Dates are part of the right: a power of attorney that ended last month
    publishes nothing this month."""
    from datetime import date, timedelta

    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])
    verify_ownership(client, owner, prop["id"])

    with TestingSession() as db:
        authority = db.scalar(
            select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"])
        )
        authority.effective_from = date.today() - timedelta(days=60)
        authority.effective_until = date.today() - timedelta(days=1)
        db.commit()

    assert _publish(client, owner, offer_id).status_code == 404


def test_the_database_refuses_an_end_before_the_start(client, owner):
    from datetime import timedelta

    prop = _register(client, owner)
    with TestingSession() as db:
        authority = db.scalar(
            select(PropertyAuthority).where(PropertyAuthority.property_id == prop["id"])
        )
        authority.effective_until = authority.effective_from - timedelta(days=1)
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation
            db.commit()


# --- rate limiting ------------------------------------------------------------


def test_the_legal_identity_write_is_throttled_as_a_write(client):
    from app.core import ratelimit as rl

    assert rl.resolve_policy("PUT", "/v1/me/legal-identity") is rl.PROPERTY_WRITE


def test_a_right_without_the_publish_scope_cannot_publish(client, owner):
    """Scopes are the point of the model: a property manager may be allowed to
    show a flat and answer messages without being allowed to put it on the
    market. With every test holding every scope, ignoring the scope entirely
    would pass everything — so one right here is narrowed."""
    from sqlalchemy import delete

    prop = _register(client, owner)
    offer_id = _draft(client, owner, prop["id"])
    verify_ownership(client, owner, prop["id"])

    with TestingSession() as db:
        db.execute(
            delete(PropertyAuthorityScope).where(
                PropertyAuthorityScope.property_authority_id == prop["authorities"][0]["id"],
                PropertyAuthorityScope.scope == "PUBLISH_LISTING",
            )
        )
        db.commit()

    assert _publish(client, owner, offer_id).status_code == 404
    # The right still covers what it still names.
    assert prop["id"] in client.get("/v1/properties", headers=auth(owner)).text
