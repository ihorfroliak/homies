"""Money columns are bigint, and stay that way (Schema v1 §8).

The rule is checked against the live catalogue, not a list of columns written
here. A new table with a price in it is covered the day its migration runs; a
hand-kept list would be exactly as out of date as the one in verify_restore.py
was before it was replaced.

What counts as money is decided by name: `amount`, `fee`, or anything ending in
`_amount`, `_fee` or `_minor`. That convention is the contract. It deliberately
does not catch `floors_total` (a count) or `commission_bps` (a ratio), and a
column that holds money under some other name is a naming defect to fix, not a
case to special-case here.
"""

import re

import pytest
from sqlalchemy import text

from tests.conftest import auth, register_and_login

MONEY_NAME = re.compile(r"^(amount|fee)$|_(amount|fee|minor)$")

# Above int4's 2 147 483 647. A 25 mln zł sale price, in grosze.
SALE_SIZED = 2_500_000_000


def _numeric_columns(conn) -> list[tuple[str, str, str]]:
    return list(
        conn.execute(
            text(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND data_type IN ('smallint', 'integer', 'bigint', 'numeric', "
                "'real', 'double precision')"
            )
        ).fetchall()
    )


def test_every_money_column_is_bigint(pg_session):
    money = [(t, c, d) for t, c, d in _numeric_columns(pg_session) if MONEY_NAME.search(c)]
    assert len(money) >= 10, f"the naming convention matched almost nothing: {money}"

    narrow = [(t, c, d) for t, c, d in money if d != "bigint"]
    assert not narrow, f"money narrower than bigint: {narrow}"


def test_no_floating_point_column_exists_anywhere(pg_session):
    """Not only money: a float anywhere in this schema is either money that
    escaped the naming rule or a measurement that will be compared for
    equality one day. Coordinates are numeric(9,6), which is exact."""
    floats = [
        (t, c) for t, c, d in _numeric_columns(pg_session) if d in ("real", "double precision")
    ]
    assert not floats, f"floating-point columns: {floats}"


def test_a_sale_sized_amount_goes_in_and_comes_back(pg_client, pg_session):
    """Behaviour, not catalogue: through the real endpoint, a value int4 cannot
    hold. On the old schema this was a 500 raised from inside the insert."""
    owner = register_and_login(pg_client, "big-money@example.com", "host")
    prop = pg_client.post(
        "/v1/properties",
        json={
            "property_type": "apartment",
            "city": "Warszawa",
            "municipality": "Warszawa",
            "address": "ul. Droga 1",
            "area_m2": 300,
            "rooms": 6,
            "capacity": 8,
        },
        headers=auth(owner),
    )
    assert prop.status_code == 201, prop.text

    offer = pg_client.post(
        f"/v1/properties/{prop.json()['id']}/classifieds",
        json={
            "title": "Penthouse",
            "rent_amount": SALE_SIZED,
            "deposit_amount": SALE_SIZED,
            "min_term_months": 12,
            "contact_mode": "message",
        },
        headers=auth(owner),
    )
    assert offer.status_code == 201, offer.text
    assert offer.json()["rent_amount"] == SALE_SIZED

    stored = dict(
        pg_session.execute(
            text("SELECT component_type, amount_minor FROM listing_price_components "
                 "WHERE listing_id = :id AND valid_to IS NULL"),
            {"id": offer.json()["id"]},
        ).fetchall()
    )
    assert stored["BASE_RENT"] == SALE_SIZED
    assert stored["SECURITY_DEPOSIT"] == SALE_SIZED
    # And the summary that search filters on did not overflow either.
    move_in = pg_session.execute(
        text("SELECT move_in_total_minor FROM classified_offers WHERE id = :id"),
        {"id": offer.json()["id"]},
    ).scalar_one()
    assert move_in == SALE_SIZED * 2


@pytest.mark.parametrize("name", ["floors_total", "commission_bps", "min_term_months"])
def test_the_convention_leaves_counts_and_ratios_alone(name):
    """Guards the guard: if the pattern started matching these, the first test
    would demand a bigint floor count and someone would 'fix' it by loosening
    the rule until it matched nothing."""
    assert not MONEY_NAME.search(name)


@pytest.mark.parametrize(
    "name", ["amount", "fee", "total_amount", "admin_fee", "primary_price_minor"]
)
def test_the_convention_catches_money(name):
    assert MONEY_NAME.search(name)
