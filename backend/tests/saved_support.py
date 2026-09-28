"""Shared set-up for the TASK-014 suites (not a test module)."""

from app.modules.geography.models import GeoArea
from tests.test_geography import _load, _ref


def load_geo(session_factory) -> dict:
    """The TASK-010 geography fixture data (Kraków, Warszawa, Balice …) and
    the Kazimierz search area; returns their ids by name."""
    with session_factory() as db:
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
