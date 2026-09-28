"""TASK-013R: discovery input is validated before any SQL (F13A-01/F13A-03, D-76).

Runs on the SQLite suite; the same inputs against real PostgreSQL — where they
used to become 500s — are in test_search_validation_pg.py.
"""

from urllib.parse import parse_qsl

import pytest

from app.modules.properties import search

SURFACES = ("/v1/classifieds", "/v1/classifieds/map")
HUGE = str(10**100)


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("name, value", [
    ("max_rent", HUGE), ("min_rent", str(search.MAX_MONEY_MINOR + 1)),
    ("min_monthly_total", HUGE), ("max_monthly_total", str(2**63)),
    ("max_move_in_total", HUGE),
    ("min_rooms", HUGE), ("min_rooms", str(search.MAX_ROOMS + 1)),
    ("min_area_m2", HUGE), ("min_area_m2", str(2**31)),
    ("max_term_months", HUGE), ("max_term_months", str(search.MAX_TERM_MONTHS + 1)),
    ("radius_m", HUGE), ("near_lat", "nan"), ("near_lon", "inf"),
    ("bbox", "nan,nan,nan,nan"), ("bbox", "-inf,0,inf,1"), ("bbox", "1," * 200 + "1"),
    ("city", "Kra\x00ków"), ("district", "Kazi\x00mierz"),
    ("city", "x" * (search.MAX_TEXT_LENGTH + 1)),
    ("locality_id", "abc\x00def"), ("admin_area_id", "abc\x00def"),
    ("geo_area_id", "abc\x00def"), ("has", "bal\x00cony"),
    ("locality_id", "x" * (search.MAX_ID_LENGTH + 1)),
    ("has", "x" * (search.MAX_ATTRIBUTE_CODE_LENGTH + 1)),
    ("furnished", "INVALID"), ("parking", "INVALID"), ("furnished", "FULL"),
    ("country_code", "P\x00"), ("country_code", "pl"), ("country_code", "POL"),
])
def test_structurally_invalid_input_is_422(client, surface, name, value):
    response = client.get(surface, params={name: value})
    assert response.status_code == 422, (name, value, response.status_code, response.text)


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("name, value", [
    ("max_rent", str(search.MAX_MONEY_MINOR)), ("min_rooms", str(search.MAX_ROOMS)),
    ("min_area_m2", str(search.MAX_AREA_M2)), ("max_term_months", str(search.MAX_TERM_MONTHS)),
    ("furnished", "partial"), ("parking", "garage"), ("city", "x" * search.MAX_TEXT_LENGTH),
    ("locality_id", "no-such-locality"), ("city", "Zażółć gęślą jaźń"),
])
def test_valid_but_unmatched_input_is_an_empty_200(client, surface, name, value):
    response = client.get(surface, params={name: value})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("name", ["admin_area_id", "locality_id", "geo_area_id", "category",
                                  "subtype", "space_type"])
def test_repeated_values_are_budgeted_per_dimension(client, surface, name):
    allowed = {"category": "APARTMENT", "subtype": "STUDIO", "space_type": "ROOM"}
    value = allowed.get(name, "some-id")
    at_limit = [(name, value)] * search.MAX_VALUES_PER_DIMENSION
    assert client.get(surface, params=at_limit).status_code == 200
    over = at_limit + [(name, value)]
    response = client.get(surface, params=over)
    assert response.status_code == 422
    assert f"at most {search.MAX_VALUES_PER_DIMENSION}" in response.text


def test_attribute_codes_are_budgeted(client):
    over = [("has", f"code{i}") for i in range(search.MAX_ATTRIBUTE_CODES + 1)]
    response = client.get("/v1/classifieds", params=over)
    assert response.status_code == 422 and f"at most {search.MAX_ATTRIBUTE_CODES}" in response.text


def test_the_largest_query_the_budgets_allow_fits_the_canonical_bound():
    """Every budget at its maximum, text in 4-byte UTF-8 (percent-encoding
    makes each character 12): the canonical key still fits, so the backstop
    is never the first refusal a legitimate query meets."""
    ids = tuple(f"{i:036d}" for i in range(search.MAX_VALUES_PER_DIMENSION))
    worst = search.SearchQuery(
        country_code="PL", admin_area_ids=ids, locality_ids=ids, geo_area_ids=ids,
        city="𝔸" * search.MAX_TEXT_LENGTH, district="𝔸" * search.MAX_TEXT_LENGTH,
        bbox=(-179.123456789, -89.123456789, 179.123456789, 89.123456789),
        near=(-89.123456789, -179.123456789, 50_000),
        categories=("APARTMENT", "HOUSE"), subtypes=("SEMI_DETACHED_HOUSE",),
        space_types=("ROOM", "WHOLE_PROPERTY"), min_rooms=100, min_area_m2=100_000,
        furnished="partial", parking="garage", pets_allowed=True, has_elevator=False,
        has=tuple("x" * 48 + str(i) for i in range(search.MAX_ATTRIBUTE_CODES)),
        min_rent=10**12, max_rent=10**12, min_monthly_total=10**12,
        max_monthly_total=10**12, max_move_in_total=10**12, max_term_months=1200,
        sort="available_soonest")
    assert len(worst.canonical()) <= search.MAX_CANONICAL_LENGTH


# --- normalization (D-72, F13A-03) -------------------------------------------------------


@pytest.mark.parametrize("surface", SURFACES)
def test_equivalent_queries_have_one_canonical_form(client, surface):
    def canonical(params):
        response = client.get(surface, params=params)
        assert response.status_code == 200, response.text
        return response.json()["query"]

    # empty optional text/choices = absent
    assert canonical([("city", ""), ("district", ""), ("furnished", ""), ("parking", ""),
                      ("country_code", "")]) == ""
    assert canonical([("locality_id", ""), ("admin_area_id", "")]) == ""
    # duplicates and order of repeated values do not matter
    a = canonical([("locality_id", "b"), ("locality_id", "a"), ("locality_id", "b"),
                   ("category", "HOUSE"), ("category", "APARTMENT")])
    b = canonical([("category", "APARTMENT"), ("locality_id", "a"), ("category", "HOUSE"),
                   ("locality_id", "b")])
    assert a == b
    # (negative zero in coordinates: spatial, so in test_search_validation_pg.py)


@pytest.mark.parametrize("surface", SURFACES)
def test_the_canonical_query_round_trips_to_itself(client, surface):
    params = [("city", "Kraków"), ("locality_id", "b"), ("locality_id", "a"),
              ("furnished", "partial"), ("max_rent", str(search.MAX_MONEY_MINOR)),
              ("sort", "price_asc")]
    first = client.get(surface, params=params).json()["query"]
    second = client.get(surface, params=parse_qsl(first)).json()["query"]
    assert first == second


def test_text_is_kept_as_given_not_rewritten(client):
    # No Unicode or whitespace rewriting beyond "empty means absent".
    query = client.get("/v1/classifieds", params={"city": " Kraków "}).json()["query"]
    assert dict(parse_qsl(query))["city"] == " Kraków "
