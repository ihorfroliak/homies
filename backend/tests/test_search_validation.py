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


# --- the canonical bound is an independent guard (TASK-013RA F13RA-N01) ----------------------
#
# Per-field budgets (ids <= 36 characters, <= 25 values per dimension) do NOT keep
# the canonical query below MAX_CANONICAL_LENGTH: a 4-byte UTF-8 character
# percent-encodes to 12 characters, so valid ids can carry the canonical form past
# 16 384. The canonical bound is therefore load-bearing on its own, and it is
# tested at the API boundary itself: exactly 16 384 answers, 16 385 is refused.

ID_DIMENSIONS = (("admin_area_id", "admin_area_ids"), ("locality_id", "locality_ids"),
                 ("geo_area_id", "geo_area_ids"))
_FULL_ID = search.MAX_ID_LENGTH  # characters; each of them a 4-byte UTF-8 character


def _canonical_length(values: dict[str, list[str]]) -> int:
    return len(search.SearchQuery(**{field: tuple(sorted(values[field]))
                                     for _, field in ID_DIMENSIONS}).canonical())


def _ids_with_canonical_length(target: int) -> list[tuple[str, str]]:
    """Unique, individually valid ids (each <= 36 characters, <= 25 per dimension)
    whose canonical query is exactly `target` characters long."""
    values: dict[str, list[str]] = {field: [] for _, field in ID_DIMENSIONS}
    codepoint = iter(range(0x1D400, 0x1D800))  # 4-byte characters: 12 when encoded
    full_fields = ["admin_area_ids", "locality_ids"]
    while True:
        field = min(full_fields, key=lambda f: len(values[f]))
        trial = {**values, field: values[field] + [chr(next(codepoint)) * _FULL_ID]}
        if target - _canonical_length(trial) < 60:
            break
        values = trial
    # Two last geo_area ids close the gap exactly: u 4-byte characters (12 each)
    # plus a ASCII letters (1 each), u + a <= 36, both values distinct.
    gap = target - _canonical_length(values) - 2 * (len("&geo_area_id="))
    shapes = {12 * u + a: (u, a) for u in range(_FULL_ID + 1)
              for a in range(_FULL_ID + 1 - u) if u + a}
    first = next(e for e in shapes if gap - e in shapes)
    for (u, a), letter in ((shapes[first], "a"), (shapes[gap - first], "b")):
        values["geo_area_ids"].append(chr(next(codepoint)) * u + letter * a)
    assert all(len(v) <= search.MAX_ID_LENGTH for vs in values.values() for v in vs)
    assert all(len(vs) <= search.MAX_VALUES_PER_DIMENSION for vs in values.values())
    assert _canonical_length(values) == target
    return [(name, v) for name, field in ID_DIMENSIONS for v in values[field]]


def test_per_field_budgets_alone_do_not_bound_the_canonical_query():
    full = {field: [chr(base + i) * _FULL_ID for i in range(search.MAX_VALUES_PER_DIMENSION)]
            for base, (_, field) in zip((0x1D400, 0x1D500, 0x1D600), ID_DIMENSIONS)}
    assert all(len(v) == search.MAX_ID_LENGTH for vs in full.values() for v in vs)
    assert _canonical_length(full) > search.MAX_CANONICAL_LENGTH


@pytest.mark.parametrize("surface", SURFACES)
def test_the_canonical_bound_is_exact_at_the_api(client, surface):
    at_bound = client.get(surface, params=_ids_with_canonical_length(search.MAX_CANONICAL_LENGTH))
    assert at_bound.status_code == 200, at_bound.text
    if surface == "/v1/classifieds":
        assert len(at_bound.json()["query"]) == search.MAX_CANONICAL_LENGTH
    over = client.get(surface, params=_ids_with_canonical_length(search.MAX_CANONICAL_LENGTH + 1))
    assert over.status_code == 422
    assert f"longer than {search.MAX_CANONICAL_LENGTH} characters" in over.text


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
