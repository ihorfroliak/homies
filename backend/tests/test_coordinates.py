"""Exact coordinates are finite, on the globe, and a pair (TASK-001 F-07) — API half.

The database enforces the same rules with CHECK constraints; that half, and
the agreement between the numeric columns and PostGIS, is in
test_coordinates_pg.py.
"""

from decimal import Decimal

import pytest

from app.modules.properties import location
from tests.conftest import auth, register_and_login

PROPERTY = {"property_type": "apartment", "city": "Gdańsk", "municipality": "Gdańsk",
            "address": "ul. Południkowa 1", "area_m2": 40, "rooms": 2, "capacity": 2}


@pytest.fixture
def owner(client):
    return register_and_login(client, "coords@example.com", "host")


def _create(client, owner, **coords):
    return client.post("/v1/properties", json={**PROPERTY, **coords}, headers=auth(owner))


@pytest.mark.parametrize(
    ("lat", "lon"),
    [(-90, 0), (90, 0), (0, -180), (0, 180), (90, 180), (-90, -180), (54.35, 18.65)],
)
def test_boundary_and_ordinary_coordinates_are_accepted(client, owner, lat, lon):
    response = _create(client, owner, latitude=lat, longitude=lon)
    assert response.status_code == 201, response.text
    assert (response.json()["latitude"], response.json()["longitude"]) == (lat, lon)


def test_no_coordinates_at_all_is_accepted(client, owner):
    response = _create(client, owner)
    assert response.status_code == 201, response.text
    assert response.json()["latitude"] is None and response.json()["longitude"] is None


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (-90.000001, 0), (90.000001, 0), (0, -180.000001), (0, 180.000001),
        (100, 200), (-1000, 0),
    ],
)
def test_out_of_range_coordinates_are_refused(client, owner, lat, lon):
    assert _create(client, owner, latitude=lat, longitude=lon).status_code == 422


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("field", ["latitude", "longitude"])
def test_non_finite_coordinates_are_refused(client, owner, field, bad):
    # Sent as raw JSON: Python's json module writes NaN/Infinity literals,
    # which is exactly what a hostile client can send.
    other = "longitude" if field == "latitude" else "latitude"
    body = (
        '{"property_type": "apartment", "city": "Gdańsk", "municipality": "Gdańsk", '
        '"address": "ul. X 1", "area_m2": 40, "rooms": 2, "capacity": 2, '
        f'"{field}": {bad}, "{other}": 10}}'
    )
    response = client.post(
        "/v1/properties", content=body,
        headers={**auth(owner), "Content-Type": "application/json"},
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(("lat", "lon"), [(52.2, None), (None, 21.0)])
def test_half_a_coordinate_pair_is_refused(client, owner, lat, lon):
    coords = {k: v for k, v in (("latitude", lat), ("longitude", lon)) if v is not None}
    assert _create(client, owner, **coords).status_code == 422


@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90, 180), (-90, -180), (90, -180), (-90, 180), (89.9999, 179.9999), (0, 0)],
)
def test_the_approximate_public_point_never_leaves_the_globe(lat, lon):
    """The grid used to open a cell beyond 90° N / 180° E for points exactly on
    the edge; its centre was then off the globe."""
    plat, plon = location.public_point(lat, lon, "APPROXIMATE")
    assert Decimal(-90) <= plat <= Decimal(90)
    assert Decimal(-180) <= plon <= Decimal(180)
    # And it is still the cell the point lies in.
    assert abs(plat - Decimal(str(lat))) <= location.GRID_LAT
    assert abs(plon - Decimal(str(lon))) <= location.GRID_LON


def test_interior_grid_cells_are_unchanged():
    """The edge fix must not move any ordinary cell (Kraków, Rynek)."""
    assert location.public_point(50.0617, 19.9374, "APPROXIMATE") == (
        Decimal("50.062500"), Decimal("19.940000")
    )


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf"])
def test_map_search_refuses_non_finite_centres(client, bad):
    response = client.get(
        "/v1/classifieds", params={"near_lat": bad, "near_lon": 19.9, "radius_m": 500}
    )
    assert response.status_code == 422, response.text
