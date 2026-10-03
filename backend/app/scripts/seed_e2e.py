"""Development/E2E seed: fictional Kraków and Warszawa rental listings.

Usage (local or CI only; refuses production):

    HOMIES_ALLOW_E2E_SEED=1 python -m app.scripts.seed_e2e

Everything here is FICTIONAL — owners, addresses, titles, prices and photos
(generated colour fields). Place names are real; reference identifiers are a
seed namespace, not official TERYT codes. Listings are created through the
real Phase-1 API in-process (register → legal identity → property → admin
verifies the authority → draft → photo upload → admin approves → attach →
publish), so the seed walks the same path a real owner does and can never
produce a state the product cannot. Idempotent: a second run does nothing.

Schema is owned by Alembic: run `python -m app.scripts.migrate` first. Needs the
dev extras (`pip install ".[dev]"`): the in-process client is Starlette's TestClient.
"""

from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, make_url, select

from app.composition import create_phase1_app
from app.core.config import DEV_ENVIRONMENTS, settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.modules.geography import service as geography
from app.modules.geography.models import GeoArea, GeoSource
from app.modules.identity.models import User
from app.modules.properties.models import ClassifiedOffer, Property

SOURCE = "E2E_SEED"
ADMIN_EMAIL = "e2e-admin@example.com"
ADMIN_PASSWORD = "e2e-admin-password-not-secret"
OWNER_PASSWORD = "e2e-owner-password-not-secret"
MARKER_EMAIL = "e2e-owner-1@example.com"

AREAS = [
    geography.AreaRow("E12", None, "PL_VOIVODESHIP", "Małopolskie", "malopolskie"),
    geography.AreaRow("E1261", "E12", "PL_COUNTY", "Kraków", "krakow"),
    geography.AreaRow("E1261011", "E1261", "PL_MUNICIPALITY", "Kraków", "krakow"),
    geography.AreaRow("E14", None, "PL_VOIVODESHIP", "Mazowieckie", "mazowieckie"),
    geography.AreaRow("E1465", "E14", "PL_COUNTY", "Warszawa", "warszawa"),
    geography.AreaRow("E1465011", "E1465", "PL_MUNICIPALITY", "Warszawa", "warszawa"),
]
LOCALITIES = [
    geography.LocalityRow("E-KRK", SOURCE, "E1261011", "CITY", "Kraków", "96", "krakow"),
    geography.LocalityRow("E-WAW", SOURCE, "E1465011", "CITY", "Warszawa", "96", "warszawa"),
]
NEIGHBOURHOODS = {
    "E-KRK": [("Kazimierz", "kazimierz"), ("Stare Miasto", "stare-miasto"),
              ("Podgórze", "podgorze"), ("Krowodrza", "krowodrza")],
    "E-WAW": [("Mokotów", "mokotow")],
}


@dataclass(frozen=True)
class Listing:
    locality: str
    area: str
    street: str
    lat: float
    lon: float
    title: str
    rent: int                 # whole złoty; stored ×100
    admin_fee: int = 0
    utilities: int = 0
    utilities_included: bool = False
    deposit: int = 0
    rooms: int = 2
    area_m2: int = 45
    floor: int | None = 2
    elevator: bool = False
    furnished: str = "full"
    parking: str = "none"
    pets: bool = False
    available_from: str | None = None
    min_term_months: int | None = 12
    open_ended: bool = False
    precision: str = "APPROXIMATE"
    photo: tuple[int, int, int] | None = (190, 214, 204)
    description: str = ""


LISTINGS = [
    Listing("E-KRK", "kazimierz", "ul. Fikcyjna", 50.0513, 19.9449, "Jasne 2 pokoje na Kazimierzu",
            3200, admin_fee=450, utilities=300, deposit=3200, available_from="2026-11-01",
            description="Fikcyjna oferta testowa. Mieszkanie po remoncie, blisko tramwaju."),
    Listing("E-KRK", "kazimierz", "ul. Przykładowa", 50.0498, 19.9471, "Kawalerka przy placu",
            2300, admin_fee=300, utilities_included=True, rooms=1, area_m2=28, deposit=2300,
            photo=(214, 196, 170)),
    Listing("E-KRK", "stare-miasto", "ul. Testowa", 50.0619, 19.9368, "Mieszkanie w kamienicy, Stare Miasto",
            4800, admin_fee=600, utilities=450, rooms=3, area_m2=72, floor=3, deposit=9600,
            open_ended=True, min_term_months=None, photo=(176, 196, 222)),
    Listing("E-KRK", "stare-miasto", "ul. Wzorcowa", 50.0641, 19.9402, "3 pokoje z windą",
            5200, admin_fee=700, utilities=500, rooms=3, area_m2=80, floor=5, elevator=True,
            parking="garage", deposit=5200, available_from="2026-12-01"),
    Listing("E-KRK", "podgorze", "ul. Próbna", 50.0441, 19.9540, "Przytulne 2 pokoje, Podgórze",
            2800, utilities=350, deposit=2800, pets=True, photo=(222, 206, 186)),
    Listing("E-KRK", "podgorze", "ul. Ćwiczebna", 50.0420, 19.9583, "Nowe budownictwo nad Wisłą",
            3900, admin_fee=550, utilities=400, rooms=2, area_m2=52, floor=4, elevator=True,
            parking="spot", deposit=7800, available_from="2027-01-15"),
    Listing("E-KRK", "krowodrza", "ul. Szkicowa", 50.0731, 19.9198, "Pokój w mieszkaniu studenckim",
            1400, utilities_included=True, rooms=1, area_m2=14, deposit=1400, furnished="partial",
            precision="DISTRICT", photo=None),
    Listing("E-KRK", "krowodrza", "ul. Robocza", 50.0752, 19.9233, "Duże mieszkanie dla rodziny",
            6100, admin_fee=800, utilities=600, rooms=4, area_m2=98, floor=1, deposit=12200,
            furnished="none", parking="street", pets=True),
    Listing("E-KRK", "kazimierz", "ul. Makieta", 50.0524, 19.9430, "Studio z antresolą",
            2600, admin_fee=350, rooms=1, area_m2=32, deposit=2600, photo=(200, 188, 222)),
    Listing("E-KRK", "stare-miasto", "ul. Atrapa", 50.0602, 19.9391, "2 pokoje blisko Rynku",
            3600, admin_fee=500, utilities=380, deposit=3600, available_from="2026-10-20"),
    Listing("E-WAW", "mokotow", "ul. Wymyślona", 52.1934, 21.0347, "2 pokoje na Mokotowie",
            4200, admin_fee=650, utilities=420, deposit=4200, elevator=True, floor=6),
    Listing("E-WAW", "mokotow", "ul. Zmyślona", 52.1967, 21.0291, "Kawalerka przy metrze",
            2900, admin_fee=400, utilities_included=True, rooms=1, area_m2=27, deposit=2900),
]


DISPOSABLE_DATABASE = re.compile(r"^[a-z0-9_]+_(e2e|test|ci)$")


def _guard() -> None:
    """Three independent locks (SEC-004): the explicit opt-in, an ENV that was
    actually set (never the `local` default of an operator's shell) and is a
    development environment, and a database whose name says it is disposable
    (`*_e2e`, `*_test`, `*_ci`). A production URL exported in a shell fails the
    last two even with the opt-in."""
    if os.environ.get("HOMIES_ALLOW_E2E_SEED") != "1":
        raise SystemExit("Refusing: set HOMIES_ALLOW_E2E_SEED=1 (development/E2E databases only).")
    if "env" not in settings.model_fields_set or settings.env.lower() not in DEV_ENVIRONMENTS:
        raise SystemExit("Refusing: set ENV explicitly to a development environment (local, test, ci).")
    database = make_url(settings.database_url).database or ""
    if not DISPOSABLE_DATABASE.match(database):
        raise SystemExit("Refusing: the database name must end in _e2e, _test or _ci (disposable databases only).")


def _reference_data() -> dict[str, str]:
    """Geography (seed namespace) and the admin; returns slug → GeoArea id."""
    with SessionLocal() as db:
        if db.get(GeoSource, SOURCE) is None:
            db.add(GeoSource(code=SOURCE, name="E2E seed (fictional data; not an official register)"))
            db.flush()
        geography.import_areas(db, "PL", SOURCE, AREAS)
        geography.import_localities(db, "PL", SOURCE, LOCALITIES)
        areas: dict[str, str] = {}
        for locality_ref, rows in NEIGHBOURHOODS.items():
            locality_id = geography._by_ref(db, SOURCE, locality_ref, "locality_id")
            for name, slug in rows:
                area = db.scalar(select(GeoArea).where(GeoArea.locality_id == locality_id,
                                                       GeoArea.slug == slug))
                if area is None:
                    area = GeoArea(country_code="PL", locality_id=locality_id,
                                   kind="NEIGHBOURHOOD", name=name, slug=slug)
                    db.add(area)
                    db.flush()
                areas[slug] = area.id
        if db.scalar(select(User).where(User.email == ADMIN_EMAIL)) is None:
            db.add(User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), role="admin"))
        db.commit()
        areas["E-KRK"] = geography._by_ref(db, SOURCE, "E-KRK", "locality_id")
        areas["E-WAW"] = geography._by_ref(db, SOURCE, "E-WAW", "locality_id")
        return areas


def _photo(rgb: tuple[int, int, int]) -> bytes:
    """A plain generated colour field with a lighter band — no camera, no metadata."""
    image = Image.new("RGB", (1200, 900), rgb)
    band = Image.new("RGB", (1200, 300), tuple(min(255, c + 25) for c in rgb))
    image.paste(band, (0, 600))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=82)
    return out.getvalue()


class _Api:
    def __init__(self) -> None:
        self.client = TestClient(create_phase1_app())

    def call(self, method: str, path: str, token: str | None = None, expect=(200, 201), **kw):
        headers = kw.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.request(method, path, headers=headers, **kw)
        if response.status_code not in expect:
            raise SystemExit(f"{method} {path} → {response.status_code}: {response.text[:300]}")
        return response

    def login(self, email: str, password: str) -> str:
        return self.call("POST", "/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]

    def owner(self, email: str, name: str) -> str:
        self.call("POST", "/v1/auth/register", expect=(201, 409),
                  json={"email": email, "password": OWNER_PASSWORD, "full_name": name, "role": "host"})
        token = self.login(email, OWNER_PASSWORD)
        first, last = name.split(" ", 1)
        self.call("PUT", "/v1/me/legal-identity", token, expect=(200, 409),
                  json={"legal_first_name": first, "legal_last_name": last})
        return token


def _publish(api: _Api, owner: str, admin: str, areas: dict[str, str], n: int, item: Listing) -> str:
    prop = api.call("POST", "/v1/properties", owner, json={
        "category": "APARTMENT", "locality_id": areas[item.locality], "geo_area_id": areas[item.area],
        "thoroughfare": item.street, "building_number": str(10 + n), "postcode": "00-000",
        "latitude": item.lat, "longitude": item.lon, "area_m2": item.area_m2, "rooms": item.rooms,
        "capacity": max(1, item.rooms), "floor": item.floor, "has_elevator": item.elevator,
        "furnished": item.furnished, "parking": item.parking, "pets_allowed": item.pets,
    }).json()["id"]
    for entry in api.call("GET", f"/v1/admin/properties/{prop}/authorities", admin).json():
        if entry["verification_state"] != "VERIFIED":
            api.call("POST", f"/v1/admin/property-authorities/{entry['id']}/verify", admin)
    offer = api.call("POST", f"/v1/properties/{prop}/classifieds", owner, json={
        "title": item.title, "description": item.description or "Fikcyjna oferta testowa (dane E2E).",
        "public_location_precision": item.precision, "rent_amount": item.rent * 100,
        "admin_fee": item.admin_fee * 100, "utilities_amount": item.utilities * 100,
        "utilities_included": item.utilities_included, "deposit_amount": item.deposit * 100,
        "min_term_months": item.min_term_months, "open_ended": item.open_ended,
        "available_from": item.available_from, "contact_mode": "message",
    }).json()["id"]
    if item.photo is not None:
        asset = api.call("POST", f"/v1/properties/{prop}/media", owner,
                         params={"rights_declared": "true"}, content=_photo(item.photo),
                         headers={"Content-Type": "image/jpeg"}).json()["id"]
        api.call("POST", f"/v1/admin/media/{asset}/approve", admin)
        api.call("POST", f"/v1/classifieds/{offer}/media", owner,
                 json={"media_asset_id": asset, "is_cover": True, "sort_order": 0})
    api.call("POST", f"/v1/classifieds/{offer}/publish", owner)
    return offer


def main() -> None:
    _guard()
    areas = _reference_data()
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == MARKER_EMAIL))
        if owner is not None:
            published = db.scalar(select(func.count()).select_from(ClassifiedOffer)
                                  .join(Property, Property.id == ClassifiedOffer.property_id)
                                  .join(User, User.id == Property.owner_id)
                                  .where(User.email.like("e2e-owner-%@example.com"),
                                         ClassifiedOffer.status == "active"))
            if published == len(LISTINGS):
                print("E2E seed already present; nothing to do.")
                return
            raise SystemExit(f"Partial E2E seed ({published}/{len(LISTINGS)} listings): "
                             "recreate the disposable database and run again.")
    # This process only: the seed drives the API in-process; the running
    # server's limits are untouched.
    settings.rate_limit_enabled = False
    api = _Api()
    admin = api.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    owners = [api.owner(MARKER_EMAIL, "Anna Testowa"), api.owner("e2e-owner-2@example.com", "Piotr Przykładowy")]
    ids = [_publish(api, owners[n % 2], admin, areas, n, item) for n, item in enumerate(LISTINGS)]
    print(f"E2E seed: {len(ids)} fictional listings published.")


if __name__ == "__main__":
    main()
