"""Price as components with history (Domain Schema v1 §46–§47, §105, §120).

What these tests hold the implementation to:

* a price change keeps the old price — closed, not overwritten;
* saving without changing anything is not a change;
* the summaries on the offer (monthly total, move-in total) always equal what
  the current components add up to — the §47 invariant, checked by
  recomputing from the rows rather than trusting the stored numbers;
* two people editing at once cannot both win.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.modules.properties import pricing
from app.modules.properties.models import ClassifiedOffer, ListingPriceComponent
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership

PROPERTY = {
    "property_type": "apartment",
    "city": "Łódź",
    "municipality": "Łódź",
    "address": "ul. Cenowa 1",
    "area_m2": 50,
    "rooms": 2,
    "capacity": 3,
}

PRICE = {
    "rent_amount": 250000,
    "admin_fee": 50000,
    "utilities_amount": 30000,
    "utilities_included": False,
    "parking_fee": 20000,
    "deposit_amount": 250000,
}


@pytest.fixture
def owner(client):
    return register_and_login(client, "pricing-owner@example.com", "host")


@pytest.fixture
def offer(client, owner):
    prop = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(client, owner, prop)
    resp = client.post(
        f"/v1/properties/{prop}/classifieds",
        json={"title": "Oferta z ceną", "min_term_months": 12, "contact_mode": "message",
              **PRICE},
        headers=auth(owner),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _change(client, token, offer_id, version, **changes):
    return client.put(
        f"/v1/classifieds/{offer_id}/price",
        json={**PRICE, **changes, "expected_version": version},
        headers=auth(token),
    )


def _history(client, token, offer_id):
    resp = client.get(f"/v1/classifieds/{offer_id}/price-history", headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _assert_summaries_match_rows(offer_id):
    """§47: the stored summaries are recomputed from the current rows here,
    independently of the service that wrote them."""
    with TestingSession() as db:
        stored = db.get(ClassifiedOffer, offer_id)
        rows = list(
            db.scalars(
                select(ListingPriceComponent).where(
                    ListingPriceComponent.listing_id == offer_id,
                    ListingPriceComponent.valid_to.is_(None),
                )
            )
        )
    headline, monthly, move_in = pricing.summarize(rows)
    assert stored.primary_price_minor == headline
    assert stored.estimated_monthly_total_minor == monthly
    assert stored.move_in_total_minor == move_in


# --- composition --------------------------------------------------------------


def test_a_new_offer_is_priced_as_components(client, owner, offer):
    current = [c for c in _history(client, owner, offer["id"]) if c["valid_to"] is None]
    kinds = {(c["component_type"], c["component_key"]): c for c in current}

    assert kinds[("BASE_RENT", "")]["amount_minor"] == 250000
    assert kinds[("ADMIN_FEE", "")]["cadence"] == "MONTHLY"
    assert kinds[("UTILITIES_ESTIMATE", "")]["estimated"] is True
    assert kinds[("OTHER_MANDATORY", "parking")]["amount_minor"] == 20000
    deposit = kinds[("SECURITY_DEPOSIT", "")]
    assert (deposit["cadence"], deposit["refundable"]) == ("ONE_TIME", True)
    _assert_summaries_match_rows(offer["id"])


def test_monthly_excludes_the_deposit_and_move_in_includes_it(client, owner, offer):
    """The deposit comes back, so it is not a monthly cost. It still has to be
    found on the day the keys change hands."""
    monthly = 250000 + 50000 + 30000 + 20000
    assert offer["monthly_total_estimate"] == monthly
    assert offer["move_in_total"] == monthly + 250000


def test_utilities_included_in_the_rent_are_shown_but_not_added_twice(client, owner):
    prop = client.post(
        "/v1/properties", json={**PROPERTY, "address": "ul. Wliczona 2"}, headers=auth(owner)
    ).json()["id"]
    body = client.post(
        f"/v1/properties/{prop}/classifieds",
        json={"title": "Media w cenie", "min_term_months": 12, "contact_mode": "message",
              **PRICE, "utilities_included": True},
        headers=auth(owner),
    ).json()
    assert body["utilities_amount"] == 30000, "the figure is still shown to the tenant"
    assert body["monthly_total_estimate"] == 250000 + 50000 + 20000


def test_an_absent_fee_is_absent_not_zero(client, owner):
    prop = client.post(
        "/v1/properties", json={**PROPERTY, "address": "ul. Bez 3"}, headers=auth(owner)
    ).json()["id"]
    body = client.post(
        f"/v1/properties/{prop}/classifieds",
        json={"title": "Sam czynsz", "min_term_months": 12, "contact_mode": "message",
              "rent_amount": 200000},
        headers=auth(owner),
    ).json()
    types = [c["component_type"] for c in _history(client, owner, body["id"])]
    assert types == ["BASE_RENT"]
    assert body["admin_fee"] == 0


def test_a_new_offer_starts_at_version_one(client, owner, offer):
    assert offer["version"] == 1


# --- history ------------------------------------------------------------------


def test_a_price_change_keeps_the_old_price(client, owner, offer):
    """The whole point. The advert said 2 500 last month; that must still be
    provable after it says 2 700."""
    resp = _change(client, owner, offer["id"], offer["version"], rent_amount=270000)
    assert resp.status_code == 200, resp.text
    assert resp.json()["rent_amount"] == 270000

    rents = [c for c in _history(client, owner, offer["id"]) if c["component_type"] == "BASE_RENT"]
    assert [(r["amount_minor"], r["valid_to"] is None) for r in rents] == [
        (250000, False),
        (270000, True),
    ]
    old, new = rents
    # Contiguous: the new price starts the instant the old one ends — no
    # moment without a price, and none with two.
    assert datetime.fromisoformat(old["valid_to"]) == datetime.fromisoformat(new["valid_from"])
    _assert_summaries_match_rows(offer["id"])


def test_only_what_moved_is_reopened(client, owner, offer):
    """History records changes, not saves: the admin fee did not move, so its
    row — and its original start date — stays."""
    before = {c["component_type"]: c for c in _history(client, owner, offer["id"])}
    _change(client, owner, offer["id"], offer["version"], rent_amount=260000)
    after = [c for c in _history(client, owner, offer["id"]) if c["component_type"] == "ADMIN_FEE"]

    assert len(after) == 1
    assert after[0]["valid_from"] == before["ADMIN_FEE"]["valid_from"]


def test_saving_an_unchanged_price_is_not_a_change(client, owner, offer):
    resp = _change(client, owner, offer["id"], offer["version"])
    assert resp.status_code == 200
    assert resp.json()["version"] == offer["version"]
    assert len(_history(client, owner, offer["id"])) == 5


def test_removing_a_fee_closes_it(client, owner, offer):
    resp = _change(client, owner, offer["id"], offer["version"], parking_fee=0)
    assert resp.json()["parking_fee"] == 0
    parking = [c for c in _history(client, owner, offer["id"])
               if c["component_key"] == "parking"]
    assert len(parking) == 1 and parking[0]["valid_to"] is not None
    _assert_summaries_match_rows(offer["id"])


def test_including_utilities_later_changes_the_total(client, owner, offer):
    resp = _change(client, owner, offer["id"], offer["version"], utilities_included=True)
    assert resp.json()["monthly_total_estimate"] == 250000 + 50000 + 20000
    _assert_summaries_match_rows(offer["id"])


def test_search_sees_the_new_price(client, owner, offer):
    client.post(f"/v1/classifieds/{offer['id']}/publish", headers=auth(owner))
    budget = 350000  # the original monthly total

    def found():
        page = client.get("/v1/classifieds", params={"max_monthly_total": budget}).json()
        return [o["id"] for o in page["items"]]

    assert offer["id"] in found()
    _change(client, owner, offer["id"], offer["version"], rent_amount=400000)
    assert offer["id"] not in found()


def test_every_change_is_audited(client, owner, offer):
    from app.core.audit import AuditLog

    _change(client, owner, offer["id"], offer["version"], rent_amount=255000)
    with TestingSession() as db:
        actions = [r.action for r in db.scalars(
            select(AuditLog).where(AuditLog.entity_id == offer["id"]))]
    assert "classified.price_changed" in actions


# --- concurrency (§120) --------------------------------------------------------


def test_a_stale_edit_is_refused_and_changes_nothing(client, owner, offer):
    first = _change(client, owner, offer["id"], offer["version"], rent_amount=260000)
    assert first.status_code == 200
    assert first.json()["version"] == offer["version"] + 1

    stale = _change(client, owner, offer["id"], offer["version"], rent_amount=999000)
    assert stale.status_code == 409, stale.text

    rents = [c["amount_minor"] for c in _history(client, owner, offer["id"])
             if c["component_type"] == "BASE_RENT" and c["valid_to"] is None]
    assert rents == [260000], "the losing edit must not have written anything"
    _assert_summaries_match_rows(offer["id"])


def test_the_new_version_is_accepted(client, owner, offer):
    first = _change(client, owner, offer["id"], offer["version"], rent_amount=260000)
    second = _change(client, owner, offer["id"], first.json()["version"], rent_amount=265000)
    assert second.status_code == 200
    assert second.json()["rent_amount"] == 265000


# --- who may ------------------------------------------------------------------


def test_a_stranger_can_neither_change_nor_read_the_history(client, owner, offer):
    stranger = register_and_login(client, "price-stranger@example.com", "host")
    assert _change(client, stranger, offer["id"], offer["version"]).status_code == 404
    assert client.get(
        f"/v1/classifieds/{offer['id']}/price-history", headers=auth(stranger)
    ).status_code == 404


# --- the database refuses what the service must never write --------------------


def test_two_current_rows_for_one_component_are_refused(client, owner, offer):
    with TestingSession() as db:
        db.add(ListingPriceComponent(
            listing_id=offer["id"], component_type="BASE_RENT", component_key="",
            amount_minor=1, cadence="MONTHLY", created_by_user_id=db.get(
                ClassifiedOffer, offer["id"]).owner_id,
        ))
        with pytest.raises(Exception):  # noqa: B017 — unique violation
            db.commit()


def test_a_negative_amount_is_refused(client, owner, offer):
    with TestingSession() as db:
        db.add(ListingPriceComponent(
            listing_id=offer["id"], component_type="AGENCY_FEE", component_key="",
            amount_minor=-1, cadence="ONE_TIME", created_by_user_id=db.get(
                ClassifiedOffer, offer["id"]).owner_id,
        ))
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation
            db.commit()


def test_a_period_that_ends_before_it_starts_is_refused(client, owner, offer):
    now = datetime.now(timezone.utc)
    with TestingSession() as db:
        db.add(ListingPriceComponent(
            listing_id=offer["id"], component_type="AGENCY_FEE", component_key="",
            amount_minor=1, cadence="ONE_TIME", valid_from=now, valid_to=now - timedelta(days=1),
            created_by_user_id=db.get(ClassifiedOffer, offer["id"]).owner_id,
        ))
        with pytest.raises(Exception):  # noqa: B017 — CHECK violation
            db.commit()


def test_price_writes_are_throttled(client):
    from app.core import ratelimit as rl

    assert rl.resolve_policy("PUT", "/v1/classifieds/abc/price") is rl.PROPERTY_WRITE
