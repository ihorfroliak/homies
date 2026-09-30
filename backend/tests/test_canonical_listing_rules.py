"""Canonical listing decisions of 2026-09-24 (TASK-002 §23–§24).

* LONG_TERM has no six-month floor (see test_classifieds_board.py for the
  term matrix); the database agrees below.
* An aparthotel unit is an APARTMENT subtype whose residential-use
  eligibility has no policy yet: it may be registered and prepared, never
  published on the strength of its type (LEGAL/POLICY REVIEW REQUIRED).
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.conftest import auth, register_and_login, verify_ownership

PROPERTY = {"city": "Sopot", "municipality": "Sopot", "address": "ul. Morska 3",
            "area_m2": 35, "rooms": 1, "capacity": 2}
OFFER = {"title": "Przy plaży", "rent_amount": 280000, "min_term_months": 12,
         "contact_mode": "message"}


def _prepared(client, property_type):
    owner = register_and_login(client, f"{property_type}@example.com", "host")
    prop = client.post("/v1/properties", json={**PROPERTY, "property_type": property_type},
                       headers=auth(owner))
    assert prop.status_code == 201, prop.text
    verify_ownership(client, owner, prop.json()["id"])
    offer = client.post(f"/v1/properties/{prop.json()['id']}/classifieds", json=OFFER,
                        headers=auth(owner))
    assert offer.status_code == 201, offer.text
    return owner, offer.json()["id"]


def test_an_aparthotel_unit_can_be_prepared_but_not_published(client):
    owner, offer = _prepared(client, "aparthotel_unit")
    response = client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    assert response.status_code == 409, response.text
    assert "policy" in response.json()["detail"]
    assert client.get(f"/v1/classifieds/{offer}").status_code == 404


def test_an_apartment_with_the_same_setup_publishes(client):
    """The refusal is the subtype's, not a broken publication path."""
    owner, offer = _prepared(client, "apartment")
    response = client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    assert response.status_code == 200, response.text


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs PostgreSQL")
@pytest.mark.parametrize("months", [0, -3])
def test_the_database_refuses_a_term_below_one_month(pg_client, pg_migrated_engine, months):
    owner, offer = _prepared(pg_client, "apartment")
    with pytest.raises(IntegrityError) as caught, pg_migrated_engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET min_term_months = :m WHERE id = :o"),
                     {"m": months, "o": offer})
    assert caught.value.orig.sqlstate == "23514"
    assert caught.value.orig.diag.constraint_name == "ck_classified_offers_min_term_positive"
