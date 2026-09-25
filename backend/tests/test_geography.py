"""Poland-wide, Europe-ready geography, structured addresses and property
classification (TASK-010) — API and service level.

Reference data here is a **test fixture**, loaded through the real import seam
under a test-only source namespace. Names are real places; identifiers are
not claimed to be official TERYT codes. Database-level guarantees (triggers,
composite FKs, PostGIS) are proved in test_geography_pg.py.
"""

import json

import pytest

from app.modules.geography import service
from app.modules.geography.models import AdministrativeArea, Country, GeoArea, GeoSource
from tests.conftest import TestingSession, auth, register_and_login, verify_ownership

SOURCE = "TEST_FIXTURE"

# Poland: voivodeship → county → municipality, and a rural municipality whose
# village is a locality that is not itself a municipality.
PL_AREAS = [
    service.AreaRow("12", None, "PL_VOIVODESHIP", "Małopolskie", "malopolskie"),
    service.AreaRow("1261", "12", "PL_COUNTY", "Kraków", "krakow"),
    service.AreaRow("1261011", "1261", "PL_MUNICIPALITY", "Kraków", "krakow"),
    service.AreaRow("1206", "12", "PL_COUNTY", "krakowski", "krakowski"),
    service.AreaRow("1206152", "1206", "PL_MUNICIPALITY", "Zabierzów", "zabierzow"),
    service.AreaRow("14", None, "PL_VOIVODESHIP", "Mazowieckie", "mazowieckie"),
    service.AreaRow("1465", "14", "PL_COUNTY", "Warszawa", "warszawa"),
    service.AreaRow("1465011", "1465", "PL_MUNICIPALITY", "Warszawa", "warszawa"),
]
PL_LOCALITIES = [
    service.LocalityRow("L-KRK", SOURCE, "1261011", "CITY", "Kraków", "96", "krakow"),
    service.LocalityRow("L-WAW", SOURCE, "1465011", "CITY", "Warszawa", "96", "warszawa"),
    service.LocalityRow("L-BAL", SOURCE, "1206152", "VILLAGE", "Balice", "01", "balice"),
]


def _load(db):
    if db.get(GeoSource, SOURCE) is None:
        db.add(GeoSource(code=SOURCE, name="Test fixture (not an official register)"))
        db.flush()
    service.import_areas(db, "PL", SOURCE, PL_AREAS)
    service.import_localities(db, "PL", SOURCE, PL_LOCALITIES)
    db.commit()


def _ref(db, external_id, column):
    return service._by_ref(db, SOURCE, external_id, column)


@pytest.fixture
def geo(client):
    with TestingSession() as db:
        _load(db)
        ids = {
            "krakow": _ref(db, "L-KRK", "locality_id"),
            "warszawa": _ref(db, "L-WAW", "locality_id"),
            "balice": _ref(db, "L-BAL", "locality_id"),
            "malopolskie": _ref(db, "12", "admin_area_id"),
            "mazowieckie": _ref(db, "14", "admin_area_id"),
            "zabierzow": _ref(db, "1206152", "admin_area_id"),
        }
        kazimierz = GeoArea(country_code="PL", locality_id=ids["krakow"],
                            kind="NEIGHBOURHOOD", name="Kazimierz", slug="kazimierz")
        db.add(kazimierz)
        db.commit()
        ids["kazimierz"] = kazimierz.id
    return ids


PROPERTY = {"category": "APARTMENT", "area_m2": 48, "rooms": 2, "capacity": 2}
OFFER = {"title": "Na Kazimierzu", "rent_amount": 320000, "min_term_months": 12,
         "contact_mode": "message"}


def _structured(client, token, geo, **extra):
    body = {**PROPERTY, "locality_id": geo["krakow"], "geo_area_id": geo["kazimierz"],
            "thoroughfare": "ul. Józefa", "building_number": "17", "unit_number": "12A",
            "postcode": "31-056", **extra}
    return client.post("/v1/properties", json=body, headers=auth(token))


# --- reference data -----------------------------------------------------------------


def test_the_current_market_is_seeded(client):
    countries = client.get("/v1/geo/countries").json()
    assert {"code": "PL", "name": "Poland", "default_currency": "PLN",
            "is_active_market": True} in countries


def test_the_polish_hierarchy_is_three_levels_with_country_kind_codes(client, geo):
    tops = client.get("/v1/geo/areas", params={"country": "PL"}).json()
    assert {a["name"] for a in tops} == {"Małopolskie", "Mazowieckie"}
    counties = client.get("/v1/geo/areas", params={
        "country": "PL", "parent_id": geo["malopolskie"]}).json()
    assert {(a["name"], a["level"], a["kind_code"]) for a in counties} == {
        ("Kraków", 2, "PL_COUNTY"), ("krakowski", 2, "PL_COUNTY")}


def test_a_village_is_a_locality_not_a_municipality(client, geo):
    found = client.get("/v1/geo/localities", params={"country": "PL", "q": "Bal"}).json()
    assert [f["name"] for f in found] == ["Balice"]
    assert found[0]["kind"] == "VILLAGE"
    assert [a["name"] for a in found[0]["areas"]] == ["Małopolskie", "krakowski", "Zabierzów"]


def test_locality_autocomplete_can_be_limited_to_a_region(client, geo):
    everywhere = client.get("/v1/geo/localities", params={"country": "PL", "q": "W"}).json()
    assert [f["name"] for f in everywhere] == ["Warszawa"]
    in_malopolskie = client.get("/v1/geo/localities", params={
        "country": "PL", "q": "W", "admin_area_id": geo["malopolskie"]}).json()
    assert in_malopolskie == []


@pytest.mark.parametrize("country, rows", [
    ("DE", [("DE-BY", None, "DE_LAND", "Bayern"),
            ("DE-BY-OB", "DE-BY", "DE_REGIERUNGSBEZIRK", "Oberbayern"),
            ("DE-BY-OB-M", "DE-BY-OB", "DE_KREISFREIE_STADT", "München"),
            ("DE-BY-OB-M-G", "DE-BY-OB-M", "DE_GEMEINDE", "München")]),
    ("ES", [("ES-MD", None, "ES_COMUNIDAD_AUTONOMA", "Comunidad de Madrid"),
            ("ES-M", "ES-MD", "ES_PROVINCIA", "Madrid"),
            ("ES-M-079", "ES-M", "ES_MUNICIPIO", "Madrid")]),
])
def test_other_european_hierarchies_need_no_schema_change(client, country, rows):
    """Germany four levels deep, Spain three: rows, not tables."""
    with TestingSession() as db:
        db.add(Country(code=country, name=country, default_currency="EUR"))
        db.add(GeoSource(code=f"TEST_{country}", country_code=country, name="test"))
        db.flush()
        service.import_areas(db, country, f"TEST_{country}",
                             [service.AreaRow(*r) for r in rows])
        db.commit()
        deepest = service._by_ref(db, f"TEST_{country}", rows[-1][0], "admin_area_id")
        path = service.area_path(db, deepest)
    assert [a.level for a in path] == list(range(1, len(rows) + 1))
    assert [a.kind_code for a in path] == [r[2] for r in rows]


def test_reimporting_renames_and_moves_in_place(client, geo):
    """Names and parents change; Homies ids do not (temporal readiness)."""
    with TestingSession() as db:
        before = _ref(db, "1206152", "admin_area_id")
        service.import_areas(db, "PL", SOURCE, [
            service.AreaRow("1206152", "1261", "PL_MUNICIPALITY", "Zabierzów (renamed)")])
        db.commit()
        after = _ref(db, "1206152", "admin_area_id")
        area = db.get(AdministrativeArea, after)
    assert before == after
    assert area.official_name == "Zabierzów (renamed)" and area.level == 3


def test_import_refuses_unknown_parents(client):
    with TestingSession() as db:
        db.add(GeoSource(code=SOURCE, name="test"))
        db.flush()
        with pytest.raises(service.GeographyError, match="unknown parents"):
            service.import_areas(db, "PL", SOURCE, [
                service.AreaRow("X1", "NOPE", "PL_COUNTY", "Orphan")])


def test_the_service_refuses_self_parent_cross_country_and_cycles(client, geo):
    with TestingSession() as db:
        top = geo["malopolskie"]
        county = _ref(db, "1206", "admin_area_id")
        with pytest.raises(service.GeographyError, match="own parent"):
            service.check_parent(db, "PL", top, 2, own_id=top)
        with pytest.raises(service.GeographyError, match="another country"):
            service.check_parent(db, "DE", top, 2)
        with pytest.raises(service.GeographyError, match="level"):
            service.check_parent(db, "PL", top, 3)
        # Make the voivodeship a child of its own county: a cycle.
        with pytest.raises(service.GeographyError, match="cycle"):
            service.check_parent(db, "PL", county, 3, own_id=top)


# --- the property's address ------------------------------------------------------------


def test_a_structured_address_is_resolved_and_private_parts_stay_owner_side(client, geo):
    owner = register_and_login(client, "geo-owner@example.com", "host")
    made = _structured(client, owner, geo)
    assert made.status_code == 201, made.text
    loc = made.json()["location"]
    assert loc["resolution"] == "STRUCTURED" and loc["source"] == "USER_INPUT"
    assert loc["locality"]["name"] == "Kraków"
    assert loc["geo_area"]["name"] == "Kazimierz"
    assert [a["name"] for a in loc["areas"]] == ["Małopolskie", "Kraków", "Kraków"]
    assert (loc["thoroughfare"], loc["building_number"], loc["unit_number"],
            loc["postal_code"]) == ("ul. Józefa", "17", "12A", "31-056")
    # Legacy mirrors for existing clients and the city filter.
    assert made.json()["city"] == "Kraków" and made.json()["district"] == "Kazimierz"
    assert made.json()["municipality"] is None


def test_free_text_only_is_kept_and_marked_unstructured(client):
    owner = register_and_login(client, "text-owner@example.com", "host")
    made = client.post("/v1/properties", json={
        **PROPERTY, "city": "Gdańsk", "address": "ul. Długa 5/3"}, headers=auth(owner))
    assert made.status_code == 201, made.text
    loc = made.json()["location"]
    assert loc["resolution"] == "UNSTRUCTURED" and loc["locality"] is None
    assert loc["unstructured_text"] == "ul. Długa 5/3"


@pytest.mark.parametrize("change, message", [
    ({"country_code": "DE"}, "unknown country"),
    ({"locality_id": "missing"}, "locality not found"),
    ({"admin_area_id": "x"}, "not both"),
    ({"geo_area_id": "missing"}, "area not found"),
])
def test_an_inconsistent_location_is_refused(client, geo, change, message):
    owner = register_and_login(client, "bad-geo@example.com", "host")
    response = _structured(client, owner, geo, **change)
    assert response.status_code == 422
    assert message in response.text


def test_a_locality_in_another_country_is_refused(client, geo):
    with TestingSession() as db:
        db.add(Country(code="DE", name="Germany", default_currency="EUR"))
        db.commit()
    owner = register_and_login(client, "de-geo@example.com", "host")
    response = _structured(client, owner, geo, country_code="DE", geo_area_id=None)
    assert response.status_code == 422 and "another country" in response.text


def test_a_search_area_of_another_locality_is_refused(client, geo):
    owner = register_and_login(client, "area-geo@example.com", "host")
    response = _structured(client, owner, geo, locality_id=geo["warszawa"])
    assert response.status_code == 422 and "another locality" in response.text


# --- classification ---------------------------------------------------------------------


@pytest.mark.parametrize("given, expected", [
    ({"category": "APARTMENT"}, ("apartment", "APARTMENT", None)),
    ({"category": "APARTMENT", "subtype": "STUDIO"}, ("studio", "APARTMENT", "STUDIO")),
    ({"category": "HOUSE", "subtype": "DETACHED_HOUSE"}, ("house", "HOUSE", "DETACHED_HOUSE")),
    ({"property_type": "townhouse"}, ("townhouse", "HOUSE", "TERRACED_HOUSE")),
    ({"property_type": "loft", "category": "APARTMENT", "subtype": "LOFT"},
     ("loft", "APARTMENT", "LOFT")),
    ({"property_type": "house", "category": "HOUSE", "subtype": "SEMI_DETACHED_HOUSE"},
     ("house", "HOUSE", "SEMI_DETACHED_HOUSE")),
])
def test_classification_accepts_canonical_legacy_or_both(client, given, expected):
    owner = register_and_login(client, "cls@example.com", "host")
    body = {**{k: v for k, v in PROPERTY.items() if k != "category"}, **given,
            "city": "Łódź", "address": "ul. Piotrkowska 1"}
    made = client.post("/v1/properties", json=body, headers=auth(owner))
    assert made.status_code == 201, made.text
    out = made.json()
    assert (out["property_type"], out["category"], out["subtype"]) == expected


@pytest.mark.parametrize("given", [
    {"property_type": "room"},
    {"category": "ROOM"},
    {"category": "APARTMENT", "subtype": "ROOM"},
    {"category": "APARTMENT", "subtype": "DETACHED_HOUSE"},
    {"subtype": "STUDIO"},
    {"property_type": "studio", "category": "HOUSE"},
    {"category": "VILLA"},
    {},
])
def test_room_and_incoherent_classifications_are_refused(client, given):
    owner = register_and_login(client, "cls-bad@example.com", "host")
    body = {**{k: v for k, v in PROPERTY.items() if k != "category"}, **given,
            "city": "Łódź", "address": "ul. Piotrkowska 1"}
    assert client.post("/v1/properties", json=body, headers=auth(owner)).status_code == 422


def test_an_aparthotel_unit_classified_canonically_still_fails_closed(client):
    owner = register_and_login(client, "apart@example.com", "host")
    prop = client.post("/v1/properties", json={
        **PROPERTY, "subtype": "APARTHOTEL_UNIT", "city": "Sopot", "address": "ul. Morska 1",
    }, headers=auth(owner))
    assert prop.status_code == 201, prop.text
    assert prop.json()["property_type"] == "aparthotel_unit"
    verify_ownership(client, owner, prop.json()["id"])
    offer = client.post(f"/v1/properties/{prop.json()['id']}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    response = client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    assert response.status_code == 409 and "policy" in response.text


# --- public view -------------------------------------------------------------------------


PRIVATE_MARKERS = ("ul. Józefa", "Józefa", "12A", "31-056", '"17"', "unit_number",
                   "thoroughfare", "building_number", "postal_code", "unstructured_text")


def _published(client, geo, owner_email="pub@example.com", **extra):
    owner = register_and_login(client, owner_email, "host")
    prop = _structured(client, owner, geo, **extra)
    assert prop.status_code == 201, prop.text
    verify_ownership(client, owner, prop.json()["id"])
    offer = client.post(f"/v1/properties/{prop.json()['id']}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    return offer


def test_the_public_listing_shows_the_place_and_nothing_private(client, geo):
    offer = _published(client, geo)
    detail = client.get(f"/v1/classifieds/{offer}")
    assert detail.status_code == 200
    place = detail.json()["place"]
    assert place["country_code"] == "PL"
    assert place["locality"]["name"] == "Kraków"
    assert place["geo_area"]["name"] == "Kazimierz"
    assert [a["kind_code"] for a in place["areas"]] == [
        "PL_VOIVODESHIP", "PL_COUNTY", "PL_MUNICIPALITY"]
    listing = client.get("/v1/classifieds").json()
    for text in (detail.text, json.dumps(listing)):
        for marker in PRIVATE_MARKERS:
            assert marker not in text, marker


def test_public_schemas_cannot_carry_private_address_fields(client):
    """Schema-level guard: a leak would need a field to be added here."""
    spec = client.get("/openapi.json").json()["components"]["schemas"]
    assert set(spec["PublicPlace"]["properties"]) == {"country_code", "areas", "locality",
                                                        "geo_area"}
    public_fields = set(spec["ClassifiedOut"]["properties"])
    for private in ("address", "unit_number", "thoroughfare", "building_number",
                    "postal_code", "postcode", "latitude", "longitude", "location",
                    "owner_id", "contact_phone"):
        assert private not in public_fields, private


def test_search_by_country_region_locality_and_area(client, geo):
    krakow = _published(client, geo, "k@example.com")
    warsaw = _published(client, geo, "w@example.com", locality_id=geo["warszawa"],
                        geo_area_id=None)

    def ids(**params):
        return {o["id"] for o in client.get("/v1/classifieds", params=params).json()["items"]}

    assert ids(country_code="PL") == {krakow, warsaw}
    assert ids(admin_area_id=geo["malopolskie"]) == {krakow}
    assert ids(admin_area_id=geo["mazowieckie"]) == {warsaw}
    assert ids(locality_id=geo["warszawa"]) == {warsaw}
    assert ids(geo_area_id=geo["kazimierz"]) == {krakow}
    assert ids(admin_area_id=geo["zabierzow"]) == set()
