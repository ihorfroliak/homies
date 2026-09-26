"""TASK-010R — geography correctness and public-location privacy, on real
PostgreSQL/PostGIS (TASK-011 findings GEO-01, GEO-02, GEO-03 and the public
EXACT adjudication, D-57/D-58).

* GEO-01: a locality-bound search area must lie inside every place the
  address also names (its locality, or the administrative subtree).
* GEO-02: a valid reference name of any length the reference model allows
  never reaches a narrower column — no HTTP 500, no truncation.
* GEO-03: for a STRUCTURED address the reference entities are the authority
  for display and filters; the legacy free-text mirrors are only a fallback
  for what the address does not reference.
* Public EXACT is prohibited: new requests are refused and the database
  cannot hold it; the exact point stays private on the Property.

Reference data is a test fixture loaded through the real import seam.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.modules.geography import service
from app.modules.geography.models import Country, GeoArea, GeoExternalRef, GeoSource
from app.modules.properties import location
from app.modules.properties.models import ClassifiedOffer, Property
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership
from tests.test_geography import PL_AREAS, PL_LOCALITIES, SOURCE
from tests.test_geography_pg import BASELINE_002_HEAD, _migrate, scratch_url  # noqa: F401

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

PROPERTY = {"category": "APARTMENT", "area_m2": 48, "rooms": 2, "capacity": 2}
OFFER = {"title": "Mieszkanie", "rent_amount": 320000, "min_term_months": 12,
         "contact_mode": "message"}


def _ref(db, external_id, column):
    return service._by_ref(db, SOURCE, external_id, column)


@pytest.fixture
def geo(pg_client, pg_session):
    db = pg_session
    if db.get(GeoSource, SOURCE) is None:
        db.add(GeoSource(code=SOURCE, name="Test fixture (not an official register)"))
        db.flush()
    service.import_areas(db, "PL", SOURCE, PL_AREAS)
    service.import_localities(db, "PL", SOURCE, PL_LOCALITIES)
    db.commit()
    ids = {
        "krakow": _ref(db, "L-KRK", "locality_id"),
        "warszawa": _ref(db, "L-WAW", "locality_id"),
        "malopolskie": _ref(db, "12", "admin_area_id"),
        "mazowieckie": _ref(db, "14", "admin_area_id"),
        "krakow_county": _ref(db, "1261", "admin_area_id"),
        "zabierzow": _ref(db, "1206152", "admin_area_id"),
    }
    kazimierz = GeoArea(country_code="PL", locality_id=ids["krakow"],
                        kind="NEIGHBOURHOOD", name="Kazimierz", slug="kazimierz")
    # A search area bound to no locality — country-wide by its own meaning.
    coast = GeoArea(country_code="PL", locality_id=None, kind="SEARCH_AREA",
                    name="Wybrzeże", slug="wybrzeze")
    db.add_all([kazimierz, coast])
    db.commit()
    ids["kazimierz"], ids["coast"] = kazimierz.id, coast.id
    return ids


def _create(client, token, **body):
    if "address" not in body:
        body.setdefault("building_number", "1")
    return client.post("/v1/properties", json={**PROPERTY, **body}, headers=auth(token))


def _publish(client, token, property_id, **offer):
    verify_ownership(client, token, property_id)
    made = client.post(f"/v1/properties/{property_id}/classifieds",
                       json={**OFFER, **offer}, headers=auth(token))
    assert made.status_code == 201, made.text
    offer_id = made.json()["id"]
    published = client.post(f"/v1/classifieds/{offer_id}/publish", headers=auth(token))
    assert published.status_code == 200, published.text
    return offer_id


def _ids(client, **params):
    response = client.get("/v1/classifieds", params=params)
    assert response.status_code == 200, response.text
    return {o["id"] for o in response.json()["items"]}


def _count(db, model):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


# --- GEO-01: a locality-bound search area must fit the rest of the address -----------


def test_geo01_admin_area_and_a_search_area_of_another_region_are_refused(
        pg_client, pg_session, geo):
    """The TASK-011 reproduction: Mazowieckie + Kazimierz (Kraków, Małopolskie)."""
    owner = register_and_login(pg_client, "geo01-bad@example.com", "host")
    response = _create(pg_client, owner, admin_area_id=geo["mazowieckie"],
                       geo_area_id=geo["kazimierz"])
    assert response.status_code == 422, response.text
    assert "outside" in response.text
    assert _count(pg_session, Property) == 0
    assert _ids(pg_client, admin_area_id=geo["mazowieckie"], geo_area_id=geo["kazimierz"]) \
        == set()


@pytest.mark.parametrize("area", ["malopolskie", "krakow_county"])
def test_geo01_an_ancestor_area_with_its_search_area_is_valid(pg_client, pg_session, geo,
                                                               area):
    owner = register_and_login(pg_client, f"geo01-{area}@example.com", "host")
    made = _create(pg_client, owner, admin_area_id=geo[area], geo_area_id=geo["kazimierz"])
    assert made.status_code == 201, made.text
    offer = _publish(pg_client, owner, made.json()["id"])
    place = pg_client.get(f"/v1/classifieds/{offer}").json()["place"]
    assert place["geo_area"]["name"] == "Kazimierz"
    assert offer in _ids(pg_client, admin_area_id=geo["malopolskie"],
                         geo_area_id=geo["kazimierz"])


def test_geo01_the_locality_with_its_own_search_area_is_valid(pg_client, geo):
    owner = register_and_login(pg_client, "geo01-own@example.com", "host")
    made = _create(pg_client, owner, locality_id=geo["krakow"], geo_area_id=geo["kazimierz"])
    assert made.status_code == 201, made.text


def test_geo01_a_search_area_of_an_unrelated_locality_is_refused(pg_client, pg_session, geo):
    owner = register_and_login(pg_client, "geo01-other@example.com", "host")
    response = _create(pg_client, owner, locality_id=geo["warszawa"],
                       geo_area_id=geo["kazimierz"])
    assert response.status_code == 422, response.text
    assert _count(pg_session, Property) == 0


def test_geo01_cross_country_combinations_are_refused(pg_client, pg_session, geo):
    if pg_session.get(Country, "DE") is None:  # countries survive truncation
        pg_session.add(Country(code="DE", name="Germany", default_currency="EUR"))
        pg_session.commit()
    service.import_areas(pg_session, "DE", SOURCE,
                         [service.AreaRow("DE-09", None, "DE_STATE", "Bayern", "bayern")])
    pg_session.commit()
    bayern = _ref(pg_session, "DE-09", "admin_area_id")
    owner = register_and_login(pg_client, "geo01-de@example.com", "host")
    response = _create(pg_client, owner, country_code="DE", admin_area_id=bayern,
                       geo_area_id=geo["kazimierz"])
    assert response.status_code == 422, response.text
    response = _create(pg_client, owner, country_code="PL", admin_area_id=bayern)
    assert response.status_code == 422, response.text
    assert _count(pg_session, Property) == 0


@pytest.mark.parametrize("place", [{"admin_area_id": "mazowieckie"},
                                   {"locality_id": "warszawa"}])
def test_geo01_a_search_area_bound_to_no_locality_stays_usable(pg_client, geo, place):
    owner = register_and_login(pg_client, "geo01-coast@example.com", "host")
    (key, value), = place.items()
    made = _create(pg_client, owner, **{key: geo[value]}, geo_area_id=geo["coast"])
    assert made.status_code == 201, made.text


# --- GEO-02: long authoritative names ---------------------------------------------------


def _long_locality(db, length, suffix="a"):
    name = ("Długa Nazwa " + suffix * length)[:length]
    assert len(name) == length
    external_id = f"L-LONG-{length}-{suffix}"
    service.import_localities(db, "PL", SOURCE, [
        service.LocalityRow(external_id, SOURCE, "1261011", "VILLAGE", name, "01")])
    db.commit()
    return _ref(db, external_id, "locality_id"), name


@pytest.mark.parametrize("length", [80, 81, 120, 121, 200])
def test_geo02_a_valid_locality_name_of_any_allowed_length_works(pg_client, pg_session, geo,
                                                                 length):
    locality, name = _long_locality(pg_session, length)
    owner = register_and_login(pg_client, f"geo02-{length}@example.com", "host")
    made = _create(pg_client, owner, locality_id=locality)
    assert made.status_code == 201, made.text
    assert made.json()["city"] == name  # the owner view, not truncated
    offer = _publish(pg_client, owner, made.json()["id"])
    public = pg_client.get(f"/v1/classifieds/{offer}").json()
    assert public["city"] == name and public["place"]["locality"]["name"] == name
    assert offer in _ids(pg_client, city=name)
    assert offer in _ids(pg_client, locality_id=locality)
    assert _count(pg_session, Property) == 1


def test_geo02_a_long_search_area_name_works(pg_client, pg_session, geo):
    name = ("Osiedle " + "b" * 200)[:200]
    area = GeoArea(country_code="PL", locality_id=geo["krakow"], kind="NEIGHBOURHOOD",
                   name=name)
    pg_session.add(area)
    pg_session.commit()
    owner = register_and_login(pg_client, "geo02-area@example.com", "host")
    made = _create(pg_client, owner, locality_id=geo["krakow"], geo_area_id=area.id)
    assert made.status_code == 201, made.text
    offer = _publish(pg_client, owner, made.json()["id"])
    public = pg_client.get(f"/v1/classifieds/{offer}").json()
    assert public["district"] == name and public["place"]["geo_area"]["name"] == name
    assert offer in _ids(pg_client, district=name)


def test_geo02_names_beyond_the_reference_domain_are_refused_predictably(pg_session, geo):
    with pytest.raises(service.GeographyError, match="official_name"):
        service.import_localities(pg_session, "PL", SOURCE, [
            service.LocalityRow("L-TOO-LONG", SOURCE, "1261011", "VILLAGE", "x" * 201, "01")])
    pg_session.rollback()
    with pytest.raises(service.GeographyError, match="official_name"):
        service.import_areas(pg_session, "PL", SOURCE, [
            service.AreaRow("99", None, "PL_VOIVODESHIP", "y" * 201)])
    pg_session.rollback()
    assert _ref(pg_session, "L-TOO-LONG", "locality_id") is None


@pytest.mark.parametrize("field, length", [("city", 81), ("district", 81)])
def test_geo02_free_text_beyond_its_column_is_a_422_not_a_500(pg_client, pg_session, field,
                                                              length):
    owner = register_and_login(pg_client, f"geo02-{field}@example.com", "host")
    body = {"city": "Gdańsk", "address": "ul. Długa 5", field: "z" * length}
    response = _create(pg_client, owner, **body)
    assert response.status_code == 422, response.text
    assert _count(pg_session, Property) == 0


# --- GEO-03: the reference is the authority for structured records -------------------


def _published_in_krakow(pg_client, geo, email="geo03@example.com"):
    owner = register_and_login(pg_client, email, "host")
    made = _create(pg_client, owner, locality_id=geo["krakow"], geo_area_id=geo["kazimierz"])
    assert made.status_code == 201, made.text
    return owner, made.json()["id"], _publish(pg_client, owner, made.json()["id"])


def test_geo03_an_imported_rename_is_what_display_and_filters_follow(pg_client, pg_session,
                                                                     geo):
    """The TASK-011 reproduction, on an already published listing."""
    _, _, offer = _published_in_krakow(pg_client, geo)
    service.import_localities(pg_session, "PL", SOURCE, [
        service.LocalityRow("L-KRK", SOURCE, "1261011", "CITY", "Renamed locality", "96")])
    pg_session.commit()
    assert _ref(pg_session, "L-KRK", "locality_id") == geo["krakow"]  # same identity

    public = pg_client.get(f"/v1/classifieds/{offer}").json()
    assert public["place"]["locality"]["name"] == "Renamed locality"
    assert public["city"] == "Renamed locality"  # no contradictory city/locality pair
    listed = next(o for o in pg_client.get("/v1/classifieds").json()["items"]
                  if o["id"] == offer)
    assert listed["city"] == "Renamed locality"
    assert offer in _ids(pg_client, city="Renamed locality")
    assert offer not in _ids(pg_client, city="Kraków")
    assert offer in _ids(pg_client, locality_id=geo["krakow"])


def test_geo03_a_renamed_search_area_is_what_display_and_filters_follow(pg_client,
                                                                        pg_session, geo):
    _, _, offer = _published_in_krakow(pg_client, geo, "geo03-area@example.com")
    pg_session.execute(text("UPDATE geo_areas SET name = 'Stare Podgórze' WHERE id = :i"),
                       {"i": geo["kazimierz"]})
    pg_session.commit()
    assert pg_client.get(f"/v1/classifieds/{offer}").json()["district"] == "Stare Podgórze"
    assert offer in _ids(pg_client, district="Stare Podgórze")
    assert offer not in _ids(pg_client, district="Kazimierz")


def test_geo03_a_stale_mirror_never_overrides_the_reference(pg_client, pg_session, geo):
    """Rows written before TASK-010R copied the names into the mirrors. Such a
    copy — or any drifted one — must lose to the reference."""
    _, prop, offer = _published_in_krakow(pg_client, geo, "geo03-stale@example.com")
    pg_session.execute(text("UPDATE properties SET city = 'Stale City', "
                            "district = 'Stale District' WHERE id = :i"), {"i": prop})
    pg_session.commit()
    public = pg_client.get(f"/v1/classifieds/{offer}").json()
    assert (public["city"], public["district"]) == ("Kraków", "Kazimierz")
    assert offer not in _ids(pg_client, city="Stale City")
    assert offer not in _ids(pg_client, district="Stale District")
    assert offer in _ids(pg_client, city="Kraków", district="Kazimierz")


def test_geo03_unstructured_records_fall_back_to_the_typed_text(pg_client, pg_session, geo):
    owner = register_and_login(pg_client, "geo03-text@example.com", "host")
    made = _create(pg_client, owner, city="Gdańsk", district="Oliwa", address="ul. Długa 5")
    assert made.status_code == 201, made.text
    assert made.json()["location"]["resolution"] == "UNSTRUCTURED"
    offer = _publish(pg_client, owner, made.json()["id"])
    public = pg_client.get(f"/v1/classifieds/{offer}").json()
    assert (public["city"], public["district"], public["place"]["locality"]) == \
        ("Gdańsk", "Oliwa", None)
    assert offer in _ids(pg_client, city="Gdańsk", district="Oliwa")
    assert _ids(pg_client, country_code="PL") >= {offer}
    assert offer not in _ids(pg_client, locality_id=geo["krakow"])


def test_geo03_structured_filters_do_not_leak_across_places(pg_client, pg_session, geo):
    _, _, krakow = _published_in_krakow(pg_client, geo, "geo03-k@example.com")
    owner = register_and_login(pg_client, "geo03-w@example.com", "host")
    made = _create(pg_client, owner, locality_id=geo["warszawa"])
    warsaw = _publish(pg_client, owner, made.json()["id"])
    assert _ids(pg_client, country_code="PL") == {krakow, warsaw}
    assert _ids(pg_client, country_code="DE") == set()
    assert _ids(pg_client, admin_area_id=geo["malopolskie"]) == {krakow}
    assert _ids(pg_client, admin_area_id=geo["mazowieckie"]) == {warsaw}
    assert _ids(pg_client, locality_id=geo["warszawa"]) == {warsaw}
    assert _ids(pg_client, geo_area_id=geo["kazimierz"]) == {krakow}
    assert _ids(pg_client, city="Warszawa") == {warsaw}
    assert _ids(pg_client, city="Kraków", locality_id=geo["warszawa"]) == set()


# --- public location privacy ------------------------------------------------------------

SENTINEL_LAT, SENTINEL_LON = 50.061237, 19.937681
SENTINELS = ("ul. Sentinelowa", "987Z", "U-4242", "99-876", "SENTINEL-RAW-7731",
             "PRG-SENTINEL-55501", "50.061237", "19.937681")


def _sentinel_listing(pg_client, pg_session, geo, precision):
    owner = register_and_login(pg_client, f"sentinel-{precision}@example.com", "host")
    made = _create(pg_client, owner, locality_id=geo["krakow"], geo_area_id=geo["kazimierz"],
                   thoroughfare="ul. Sentinelowa", building_number="987Z",
                   unit_number="U-4242", postcode="99-876", address="SENTINEL-RAW-7731",
                   latitude=SENTINEL_LAT, longitude=SENTINEL_LON)
    assert made.status_code == 201, made.text
    prop = pg_session.get(Property, made.json()["id"])
    pg_session.add(GeoExternalRef(source_code="PL_PRG_ADDRESS", external_id="PRG-SENTINEL-55501",
                                  address_id=prop.address_id))
    pg_session.commit()
    offer = _publish(pg_client, owner, prop.id, public_location_precision=precision)
    return owner, prop, offer


@pytest.mark.parametrize("precision", ["APPROXIMATE", "DISTRICT"])
def test_no_private_sentinel_reaches_any_anonymous_surface(pg_client, pg_session, geo,
                                                           precision):
    owner, prop, offer = _sentinel_listing(pg_client, pg_session, geo, precision)
    probes = [
        pg_client.get(f"/v1/classifieds/{offer}"),
        pg_client.get("/v1/classifieds"),
        pg_client.get("/v1/classifieds", params={"city": "Kraków"}),
        pg_client.get("/v1/classifieds", params={"locality_id": geo["krakow"]}),
        pg_client.get("/v1/classifieds", params={"geo_area_id": geo["kazimierz"]}),
        pg_client.get("/v1/classifieds", params={"bbox": "19.9,50.0,20.0,50.1"}),
        pg_client.get("/v1/geo/localities", params={"country": "PL", "q": "Kra"}),
        pg_client.get(f"/v1/geo/localities/{geo['krakow']}/areas"),
    ]
    for response in probes:
        assert response.status_code == 200, (response.request.url, response.text)
        body = response.text
        for sentinel in (*SENTINELS, prop.address_id):
            assert sentinel not in body, (sentinel, response.request.url)
    # Owner surfaces are gated; the dormant legacy route is not mounted.
    assert pg_client.get("/v1/properties").status_code == 401
    assert pg_client.get(f"/v1/listings/{offer}").status_code == 404
    # The private point is kept — for its owner only.
    mine = pg_client.get("/v1/properties", headers=auth(owner)).json()
    assert float(mine[0]["latitude"]) == SENTINEL_LAT
    assert mine[0]["location"]["thoroughfare"] == "ul. Sentinelowa"


def test_public_exact_is_refused(pg_client, pg_session, geo):
    owner = register_and_login(pg_client, "exact@example.com", "host")
    made = _create(pg_client, owner, locality_id=geo["krakow"], latitude=SENTINEL_LAT,
                   longitude=SENTINEL_LON)
    verify_ownership(pg_client, owner, made.json()["id"])
    refused = pg_client.post(f"/v1/properties/{made.json()['id']}/classifieds",
                             json={**OFFER, "public_location_precision": "EXACT"},
                             headers=auth(owner))
    assert refused.status_code == 422, refused.text
    assert _count(pg_session, ClassifiedOffer) == 0
    offer = _publish(pg_client, owner, made.json()["id"])
    point = pg_client.get(f"/v1/classifieds/{offer}").json()["public_location"]
    assert point["precision"] == "APPROXIMATE"
    assert (point["latitude"], point["longitude"]) != (SENTINEL_LAT, SENTINEL_LON)


def test_the_database_cannot_hold_public_exact(pg_client, pg_session, pg_migrated_engine, geo):
    _, _, offer = _sentinel_listing(pg_client, pg_session, geo, "APPROXIMATE")
    with pytest.raises((IntegrityError, DBAPIError)) as caught, \
            pg_migrated_engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET public_location_precision = 'EXACT' "
                          "WHERE id = :i"), {"i": offer})
    assert caught.value.orig.sqlstate == "23514"
    assert caught.value.orig.diag.constraint_name == "ck_classified_offers_location_precision"


# --- migration: stored EXACT becomes APPROXIMATE, the private point stays -------------

TASK_010_HEAD = "e4f6a8b0c2d4"
TASK_010R_HEAD = "a7c9e1f3b5d7"
POINTS = [(50.061237, 19.937681), (-33.868820, 151.209290), (90.0, 180.0),
          (0.0, -0.000001), None]


def test_stored_exact_becomes_approximate_and_nothing_private_is_lost(scratch_url):  # noqa: F811
    """Foundation Baseline 002 → TASK-010 → TASK-010R, with offers written as
    EXACT while it was still allowed."""
    _migrate(scratch_url, BASELINE_002_HEAD)
    engine = create_engine(scratch_url)
    now = datetime.now(timezone.utc)
    offers = {}
    with engine.begin() as conn:
        owner = str(uuid.uuid4())
        conn.execute(text("INSERT INTO users (id, email, password_hash, full_name, role, "
                          "created_at) VALUES (:i, 'x@x.example', 'x', '', 'host', now())"),
                     {"i": owner})
        for n, point in enumerate(POINTS):
            lat, lon = point if point else (None, None)
            pid = conn.scalar(text(
                "INSERT INTO properties (id, owner_id, property_type, city, district, postcode, "
                "municipality, address, latitude, longitude, capacity, bedrooms, bathrooms, "
                "has_elevator, furnished, parking, pets_allowed, attributes, created_at) VALUES "
                "(gen_random_uuid()::text, :o, 'apartment', 'Kraków', '', '', 'x', :a, :la, "
                ":lo, 2, 1, 1, false, 'full', 'none', false, '{}', now()) RETURNING id"),
                {"o": owner, "a": f"ul. Punkt {n}", "la": lat, "lo": lon})
            space = conn.scalar(text(
                "INSERT INTO spaces (id, property_id, space_type, status, version, created_at, "
                "updated_at) VALUES (gen_random_uuid()::text, :p, 'WHOLE_PROPERTY', 'ACTIVE', "
                "1, :n, :n) RETURNING id"), {"p": pid, "n": now})
            for precision in ("EXACT", "APPROXIMATE", "DISTRICT"):
                public = location.public_point(lat, lon, precision) if point else (None, None)
                if precision == "EXACT" and point:
                    public = (Decimal(str(lat)), Decimal(str(lon)))  # the old behaviour
                oid = conn.scalar(text(
                    "INSERT INTO classified_offers (id, property_id, space_id, owner_id, title, "
                    "description, status, currency, utilities_included, other_costs, "
                    "contact_mode, contact_phone, open_ended, public_location_precision, "
                    "public_latitude, public_longitude, version, created_at) VALUES "
                    "(gen_random_uuid()::text, :p, :s, :o, 't', '', 'active', 'PLN', false, "
                    "'', 'message', '', true, :pr, :la, :lo, 1, :n) RETURNING id"),
                    {"p": pid, "s": space, "o": owner, "pr": precision, "la": public[0],
                     "lo": public[1], "n": now})
                offers[oid] = (pid, space, point, precision)

    def snapshot():
        with engine.connect() as conn:
            props = conn.execute(text(
                "SELECT id, latitude, longitude, ST_AsText(exact_geog::geometry) AS g "
                "FROM properties ORDER BY id")).all()
            rows = {r.id: r for r in conn.execute(text(
                "SELECT id, property_id, space_id, public_location_precision AS precision, "
                "public_latitude AS lat, public_longitude AS lon, "
                "ST_AsText(public_geog::geometry) AS g FROM classified_offers")).all()}
        return props, rows

    _migrate(scratch_url, TASK_010_HEAD)
    props_010, offers_010 = snapshot()
    with engine.connect() as conn:
        addresses = dict(conn.execute(text("SELECT id, address_id FROM properties")).all())
    assert sum(o.precision == "EXACT" for o in offers_010.values()) == len(POINTS)

    _migrate(scratch_url, TASK_010R_HEAD)
    props_r, offers_r = snapshot()
    assert props_r == props_010  # private exact point and identity untouched
    with engine.connect() as conn:
        assert dict(conn.execute(text("SELECT id, address_id FROM properties")).all()) \
            == addresses
        assert conn.scalar(text("SELECT count(*) FROM spaces")) == len(POINTS)
        assert conn.scalar(text("SELECT count(*) FROM classified_offers "
                                "WHERE public_location_precision = 'EXACT'")) == 0
    assert set(offers_r) == set(offers)
    for oid, (pid, space, point, precision) in offers.items():
        row = offers_r[oid]
        assert (row.property_id, row.space_id) == (pid, space)
        if precision == "EXACT":
            assert row.precision == "APPROXIMATE"
            expected = location.public_point(*point, "APPROXIMATE") if point else (None, None)
            assert (row.lat, row.lon) == expected, (point, row)
            if point:
                assert (float(row.lat), float(row.lon)) != point
        else:  # APPROXIMATE / DISTRICT rows are not rewritten
            assert row == offers_010[oid]

    # Down to the TASK-010 candidate (the CHECK admits EXACT again) and back:
    # converted rows stay APPROXIMATE.
    _migrate(scratch_url, TASK_010_HEAD, down=True)
    with engine.begin() as conn:
        conn.execute(text("SAVEPOINT s"))
        conn.execute(text("UPDATE classified_offers SET public_location_precision = 'EXACT' "
                          "WHERE id = :i"), {"i": next(iter(offers))})
        conn.execute(text("ROLLBACK TO SAVEPOINT s"))
    _migrate(scratch_url, TASK_010R_HEAD)
    assert snapshot() == (props_r, offers_r)
    engine.dispose()
