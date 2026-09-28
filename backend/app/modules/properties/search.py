"""Marketplace discovery: one query model for the list and the map (TASK-013, D-68…D-73).

A search is a `SearchQuery` — parsed once from stable, bookmarkable URL
parameters — and every surface that answers it (the list page, the map)
builds its SQL from `select_matching()`. The map therefore can never show a
different marketplace than the list: it only projects the same rows lighter.

Pipeline (each stage ANDs onto the previous; values inside one dimension OR):

    public eligibility (freshness.public_clause — the one visibility rule)
    → geography (country, admin areas incl. descendants, localities,
      search areas, viewport / radius on the PUBLIC point)
    → property / space (category, subtype, space type, rooms, area,
      structured attributes)
    → price (base rent, stated monthly total, move-in total — integer minor units)
    → availability (available_by: a stated date on or before; UNKNOWN never matches)
    → sort (deterministic, id tie-breaker) → page or map projection

Spatial privacy (D-70): anonymous spatial inclusion uses only the public,
privacy-reduced point (`public_geog`), never the exact residential point — so
a viewport or radius can reveal no more than the grid cell already shown.

Invalid or contradictory queries (unknown values, a subtype outside the
chosen categories, min > max, places in another country than `country_code`)
answer 422. Merely unlikely combinations answer an empty page.

Every value is validated before any SQL is built (TASK-013R, F13A-01/F13A-03,
D-76): numbers are finite and inside explicit bounds the database can hold,
text and ids carry no NUL and have bounded length, controlled vocabularies are
checked against their catalogue, repeated values and the canonical query are
budgeted. A structurally invalid query is 422; a valid one that matches nothing
is 200 with no results. Database errors are never translated into 422 — known
invalid input simply never reaches the database.
"""

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, NoReturn
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Query, status
from prometheus_client import Counter
from sqlalchemy import Select, and_, case, func, literal_column, or_, select
from sqlalchemy.orm import Session, contains_eager
from sqlalchemy.sql import ColumnElement

from app.core.db import get_db
from app.modules.geography import service as geography
from app.modules.geography.models import AdministrativeArea, Address, GeoArea, Locality
from app.modules.properties import freshness
from app.modules.properties.attributes import load_catalogue
from app.modules.properties.classification import CATEGORIES, SUBTYPES
from app.modules.properties.models import SPACE_TYPES, ClassifiedOffer, Property, Space
from app.modules.properties.schemas import FURNISHED, PARKING

ALL_SUBTYPES = {s: c for c, group in SUBTYPES.items() for s in group}

# Sorts are an allowlist (never a column name from the query string); every
# one ends on the listing id so equal keys page deterministically (D-71).
SORTS = ("newest", "price_asc", "price_desc", "size_desc", "available_soonest")
DEFAULT_SORT = "newest"
MAP_CAP = 500

# --- bounds and input budgets (TASK-013R, D-76) --------------------------------------------
# Numbers: finite, and far above any real listing, far below what the columns
# hold (money bigint, the rest int4) — "unusual" still passes, "impossible" is 422.
MAX_MONEY_MINOR = 10**12          # 10 000 000 000.00 PLN; a sale price fits easily
MAX_ROOMS = 100
MAX_AREA_M2 = 100_000
MAX_TERM_MONTHS = 1_200           # 100 years
# Text and ids: a place name as long as a reference place name may be
# (localities.official_name, geo_areas.name: 200 — GEO-02, TASK-010R); ids are
# UUIDs (36); attribute codes as long as the catalogue key (48).
MAX_TEXT_LENGTH = 200
MAX_ID_LENGTH = 36
MAX_ATTRIBUTE_CODE_LENGTH = 48
# Repetition: values given for one dimension (before de-duplication), and the
# canonical query that TASK-014 will persist as a saved-search key.
MAX_VALUES_PER_DIMENSION = 25
MAX_ATTRIBUTE_CODES = 20
MAX_CANONICAL_LENGTH = 16_384

_PUBLIC_GEOG: ColumnElement[Any] = literal_column("classified_offers.public_geog")

# Privacy-safe discovery measurement (D-73): which filters are used and how
# many results a search finds — never the values searched for.
SEARCHES = Counter("homies_search_requests_total", "Discovery searches answered",
                   ["surface", "results"])
FILTER_USE = Counter("homies_search_filter_used_total", "Discovery searches using a filter",
                     ["filter"])


@dataclass(frozen=True)
class SearchQuery:
    country_code: str | None = None
    admin_area_ids: tuple[str, ...] = ()
    locality_ids: tuple[str, ...] = ()
    geo_area_ids: tuple[str, ...] = ()
    city: str | None = None          # legacy name filters (D-57 rules apply)
    district: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    near: tuple[float, float, int] | None = None   # lat, lon, radius_m
    categories: tuple[str, ...] = ()
    subtypes: tuple[str, ...] = ()
    space_types: tuple[str, ...] = ()
    min_rooms: int | None = None
    min_area_m2: int | None = None
    furnished: str | None = None
    parking: str | None = None
    pets_allowed: bool | None = None
    has_elevator: bool | None = None
    has: tuple[str, ...] = ()
    min_rent: int | None = None
    max_rent: int | None = None
    min_monthly_total: int | None = None
    max_monthly_total: int | None = None
    max_move_in_total: int | None = None
    available_by: date | None = None
    max_term_months: int | None = None
    sort: str = DEFAULT_SORT

    # --- URL state (D-72) --------------------------------------------------------

    def params(self) -> list[tuple[str, str]]:
        """The query as canonical URL parameters: stable names, defaults
        omitted, values of a multi-value dimension sorted, pairs sorted."""
        pairs: list[tuple[str, str]] = []

        def add(name: str, value: Any) -> None:
            if value is None or value == () or (name == "sort" and value == DEFAULT_SORT):
                return
            if isinstance(value, tuple) and name not in ("bbox",):
                for v in sorted(str(x) for x in value):
                    pairs.append((name, v))
                return
            if isinstance(value, bool):
                value = "true" if value else "false"
            pairs.append((name, str(value)))

        add("country_code", self.country_code)
        add("admin_area_id", self.admin_area_ids)
        add("locality_id", self.locality_ids)
        add("geo_area_id", self.geo_area_ids)
        add("city", self.city)
        add("district", self.district)
        if self.bbox is not None:
            add("bbox", ",".join(repr(float(v)) for v in self.bbox))
        if self.near is not None:
            add("near_lat", repr(float(self.near[0])))
            add("near_lon", repr(float(self.near[1])))
            add("radius_m", self.near[2])
        add("category", self.categories)
        add("subtype", self.subtypes)
        add("space_type", self.space_types)
        add("min_rooms", self.min_rooms)
        add("min_area_m2", self.min_area_m2)
        add("furnished", self.furnished)
        add("parking", self.parking)
        add("pets_allowed", self.pets_allowed)
        add("has_elevator", self.has_elevator)
        add("has", self.has)
        add("min_rent", self.min_rent)
        add("max_rent", self.max_rent)
        add("min_monthly_total", self.min_monthly_total)
        add("max_monthly_total", self.max_monthly_total)
        add("max_move_in_total", self.max_move_in_total)
        add("available_by", self.available_by.isoformat() if self.available_by else None)
        add("max_term_months", self.max_term_months)
        add("sort", self.sort)
        return sorted(pairs)

    def canonical(self) -> str:
        return urlencode(self.params())

    def used_filters(self) -> list[str]:
        return sorted({name for name, _ in self.params() if name != "sort"})


def _refuse(detail: str) -> NoReturn:
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)


def _budget(name: str, values: list[str] | None, limit: int = MAX_VALUES_PER_DIMENSION) -> list[str]:
    values = values or []
    if len(values) > limit:
        _refuse(f"at most {limit} {name} values may be given")
    return values


def _no_nul(name: str, value: str) -> None:
    # PostgreSQL text cannot hold NUL; such a value is malformed, not a miss.
    if "\x00" in value:
        _refuse(f"{name} contains a NUL character")


def _text(name: str, value: str | None) -> str | None:
    """Optional free text: empty means absent; otherwise bounded, no NUL.
    The value is otherwise kept exactly as given (no Unicode rewriting)."""
    if value is None or value == "":
        return None
    _no_nul(name, value)
    if len(value) > MAX_TEXT_LENGTH:
        _refuse(f"{name} is longer than {MAX_TEXT_LENGTH} characters")
    return value


def _ids(name: str, values: list[str] | None, max_length: int = MAX_ID_LENGTH,
         limit: int = MAX_VALUES_PER_DIMENSION) -> tuple[str, ...]:
    """A repeatable reference dimension: budgeted, each value bounded and
    NUL-free, empty values dropped, duplicates collapsed, sorted."""
    kept = set()
    for value in _budget(name, values, limit):
        if value == "":
            continue
        _no_nul(name, value)
        if len(value) > max_length:
            _refuse(f"a {name} value is longer than {max_length} characters")
        kept.add(value)
    return tuple(sorted(kept))


def _choice(name: str, value: str | None, allowed) -> str | None:
    if value is None or value == "":
        return None
    if value not in allowed:
        _refuse(f"{name} must be one of {', '.join(allowed)}")
    return value


def _finite(value: float) -> float:
    # -0.0 and 0.0 are the same place; one canonical spelling (D-72).
    return value + 0.0


def _one_of(name: str, values: list[str] | None, allowed) -> tuple[str, ...]:
    values = _budget(name, values)
    bad = sorted(set(values) - set(allowed))
    if bad:
        _refuse(f"{name} must be one of {', '.join(sorted(allowed))}; got {', '.join(bad)}")
    return tuple(sorted(set(values)))


def _range(name: str, low: int | None, high: int | None) -> None:
    if low is not None and high is not None and low > high:
        _refuse(f"min_{name} is above max_{name}")


def search_query(
    # Structured place (ids from /v1/geo). Repeatable: values of one
    # dimension are alternatives (OR); dimensions combine with AND.
    country_code: str | None = None,
    admin_area_id: list[str] | None = Query(default=None),
    locality_id: list[str] | None = Query(default=None),
    geo_area_id: list[str] | None = Query(default=None),
    # Legacy place names; the structured ids above are the canonical way.
    city: str | None = None,
    district: str | None = None,
    # The viewport "minLon,minLat,maxLon,maxLat", or a radius — both against
    # the PUBLIC point only. Listings placed by district only have no point.
    bbox: str | None = None,
    near_lat: float | None = Query(default=None, ge=-90, le=90),
    near_lon: float | None = Query(default=None, ge=-180, le=180),
    radius_m: int | None = Query(default=None, ge=1, le=50_000),
    category: list[str] | None = Query(default=None),
    subtype: list[str] | None = Query(default=None),
    space_type: list[str] | None = Query(default=None),
    min_rooms: int | None = Query(default=None, ge=0, le=MAX_ROOMS),
    min_area_m2: int | None = Query(default=None, ge=0, le=MAX_AREA_M2),
    furnished: str | None = None,
    parking: str | None = None,
    pets_allowed: bool | None = None,
    has_elevator: bool | None = None,
    # Repeatable: ?has=dishwasher&has=balcony — ALL must hold. Only codes the
    # catalogue marks filterable are accepted.
    has: list[str] | None = Query(default=None),
    # Money, integer minor units. Rent = the base rent alone. Monthly total =
    # every mandatory monthly charge the owner stated (utilities may be an
    # estimate or not stated — see `utilities_basis`). Move-in total = first
    # month + mandatory one-offs, refundable deposit included.
    min_rent: int | None = Query(default=None, ge=0, le=MAX_MONEY_MINOR),
    max_rent: int | None = Query(default=None, ge=0, le=MAX_MONEY_MINOR),
    min_monthly_total: int | None = Query(default=None, ge=0, le=MAX_MONEY_MINOR),
    max_monthly_total: int | None = Query(default=None, ge=0, le=MAX_MONEY_MINOR),
    max_move_in_total: int | None = Query(default=None, ge=0, le=MAX_MONEY_MINOR),
    # "I can move in by this date": listings stating a date on or before it.
    # A listing that gave no date never matches (D-64).
    available_by: date | None = None,
    max_term_months: int | None = Query(default=None, ge=0, le=MAX_TERM_MONTHS),
    sort: str = DEFAULT_SORT,
    db: Session = Depends(get_db),
) -> SearchQuery:
    """Parse and validate the canonical discovery query (shared by list and map)."""
    if country_code == "":
        country_code = None
    if country_code is not None and not re.fullmatch(r"[A-Z]{2}", country_code):
        _refuse("country_code must be two capital letters (ISO 3166-1 alpha-2)")
    city = _text("city", city)
    district = _text("district", district)
    furnished = _choice("furnished", furnished, FURNISHED)
    parking = _choice("parking", parking, PARKING)
    if sort not in SORTS:
        _refuse(f"sort must be one of {', '.join(SORTS)}")
    categories = _one_of("category", category, CATEGORIES)
    subtypes = _one_of("subtype", subtype, ALL_SUBTYPES)
    if categories:
        outside = [s for s in subtypes if ALL_SUBTYPES[s] not in categories]
        if outside:
            _refuse(f"subtype {', '.join(outside)} is not a kind of {', '.join(categories)}")
    space_types = _one_of("space_type", space_type, SPACE_TYPES)
    _range("rent", min_rent, max_rent)
    _range("monthly_total", min_monthly_total, max_monthly_total)

    box = None
    if bbox is not None:
        if len(bbox) > 200:
            _refuse("bbox must be four numbers: minLon,minLat,maxLon,maxLat")
        try:
            min_lon, min_lat, max_lon, max_lat = (float(p) for p in bbox.split(","))
        except ValueError:
            _refuse("bbox must be four numbers: minLon,minLat,maxLon,maxLat")
        if not all(math.isfinite(v) for v in (min_lon, min_lat, max_lon, max_lat)):
            _refuse("bbox must be four finite numbers")
        if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
            _refuse("bbox is not a valid box")
        box = (_finite(min_lon), _finite(min_lat), _finite(max_lon), _finite(max_lat))
    given = [v is not None for v in (near_lat, near_lon, radius_m)]
    if any(given) and not all(given):
        _refuse("radius search needs near_lat, near_lon and radius_m together")
    near = None
    if all(given):
        assert near_lat is not None and near_lon is not None
        if not (math.isfinite(near_lat) and math.isfinite(near_lon)):
            _refuse("near_lat and near_lon must be finite numbers")
        near = (_finite(near_lat), _finite(near_lon), radius_m)

    codes = _ids("has", has, max_length=MAX_ATTRIBUTE_CODE_LENGTH, limit=MAX_ATTRIBUTE_CODES)
    if codes:
        catalogue = load_catalogue(db)
        for code in codes:
            definition = catalogue.get(code)
            if definition is None or not definition.filterable:
                _refuse(f"'{code}' is not a filterable attribute — see GET /v1/attributes")

    admin_ids = _ids("admin_area_id", admin_area_id)
    locality_ids = _ids("locality_id", locality_id)
    geo_ids = _ids("geo_area_id", geo_area_id)
    if country_code:
        # A place in another country than the one asked for is a
        # contradiction, not an unlucky search.
        for model, ids in ((AdministrativeArea, admin_ids), (Locality, locality_ids),
                           (GeoArea, geo_ids)):
            if ids and db.scalar(select(func.count()).select_from(model).where(
                    model.id.in_(ids), model.country_code != country_code)):
                _refuse(f"a {model.__tablename__} id given is not in {country_code}")

    query = SearchQuery(
        country_code=country_code, admin_area_ids=admin_ids, locality_ids=locality_ids,
        geo_area_ids=geo_ids, city=city, district=district, bbox=box,
        near=near,  # type: ignore[arg-type]
        categories=categories, subtypes=subtypes, space_types=space_types,
        min_rooms=min_rooms, min_area_m2=min_area_m2, furnished=furnished, parking=parking,
        pets_allowed=pets_allowed, has_elevator=has_elevator, has=codes,
        min_rent=min_rent, max_rent=max_rent, min_monthly_total=min_monthly_total,
        max_monthly_total=max_monthly_total, max_move_in_total=max_move_in_total,
        available_by=available_by, max_term_months=max_term_months, sort=sort,
    )
    # A backstop the budgets above already keep far away; it bounds the
    # saved-search key TASK-014 will persist (F13A-03).
    if len(query.canonical()) > MAX_CANONICAL_LENGTH:
        _refuse(f"the query is longer than {MAX_CANONICAL_LENGTH} characters")
    return query


# --- SQL ---------------------------------------------------------------------------------


def listed_area_sql():
    """The area of what is actually on offer: the room's for a room, the
    flat's otherwise. A room whose area was not given matches no minimum."""
    return case((Space.space_type == "ROOM", Space.area_m2), else_=Property.area_m2)


def _addresses_where(*conditions) -> ColumnElement[bool]:
    return Property.address_id.in_(select(Address.id).where(*conditions))


def filters(db: Session, q: SearchQuery) -> list[ColumnElement[bool]]:
    # 1. Public eligibility: the one rule every public path uses (D-59).
    out: list[ColumnElement[bool]] = [freshness.public_clause(db)]

    # 2. Geography. Unstructured addresses match no structured filter.
    if q.country_code:
        out.append(_addresses_where(Address.country_code == q.country_code))
    if q.admin_area_ids:
        within = geography.descendant_area_ids(q.admin_area_ids)
        out.append(Property.address_id.in_(
            select(Address.id)
            .outerjoin(Locality, Locality.id == Address.locality_id)
            .where(or_(Address.admin_area_id.in_(within), Locality.admin_area_id.in_(within)))))
    if q.locality_ids:
        out.append(_addresses_where(Address.locality_id.in_(q.locality_ids)))
    if q.geo_area_ids:
        out.append(_addresses_where(Address.geo_area_id.in_(q.geo_area_ids)))
    if q.city:
        # D-57: the referenced locality's current name wins; the typed mirror
        # only for records that reference none.
        out.append(or_(
            Property.address_id.in_(
                select(Address.id).join(Locality, Locality.id == Address.locality_id)
                .where(Locality.official_name == q.city)),
            and_(Property.city == q.city,
                 _addresses_where(Address.locality_id.is_(None))),
        ))
    if q.district:
        out.append(or_(
            Property.address_id.in_(
                select(Address.id).join(GeoArea, GeoArea.id == Address.geo_area_id)
                .where(GeoArea.name == q.district)),
            and_(Property.district == q.district,
                 _addresses_where(Address.geo_area_id.is_(None))),
        ))
    if q.bbox is not None:
        envelope = func.ST_MakeEnvelope(*q.bbox, 4326)
        # PUBLIC point only (D-70) — never properties.exact_geog.
        out.append(func.ST_Intersects(_PUBLIC_GEOG, func.geography(envelope)))
    if q.near is not None:
        lat, lon, radius = q.near
        centre = func.geography(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326))
        out.append(func.ST_DWithin(_PUBLIC_GEOG, centre, radius))

    # 3. Property / space.
    if q.categories:
        out.append(Property.category.in_(q.categories))
    if q.subtypes:
        out.append(Property.subtype.in_(q.subtypes))
    if q.space_types:
        out.append(Space.space_type.in_(q.space_types))
    if q.min_rooms is not None:
        out.append(Property.rooms >= q.min_rooms)
    if q.min_area_m2 is not None:
        out.append(listed_area_sql() >= q.min_area_m2)
    if q.furnished:
        out.append(Property.furnished == q.furnished)
    if q.parking:
        out.append(Property.parking == q.parking)
    if q.pets_allowed is not None:
        out.append(Property.pets_allowed.is_(q.pets_allowed))
    if q.has_elevator is not None:
        out.append(Property.has_elevator.is_(q.has_elevator))
    for code in q.has:
        out.append(Property.attributes[code].as_boolean().is_(True))

    # 4. Price (integer minor units; the stored summaries of the components).
    if q.min_rent is not None:
        out.append(ClassifiedOffer.primary_price_minor >= q.min_rent)
    if q.max_rent is not None:
        out.append(ClassifiedOffer.primary_price_minor <= q.max_rent)
    if q.min_monthly_total is not None:
        out.append(ClassifiedOffer.estimated_monthly_total_minor >= q.min_monthly_total)
    if q.max_monthly_total is not None:
        out.append(ClassifiedOffer.estimated_monthly_total_minor <= q.max_monthly_total)
    if q.max_move_in_total is not None:
        out.append(ClassifiedOffer.move_in_total_minor <= q.max_move_in_total)

    # 5. Availability and term.
    if q.available_by is not None:
        out.append(ClassifiedOffer.available_from <= q.available_by)  # NULL never matches
    if q.max_term_months is not None:
        out.append(or_(ClassifiedOffer.open_ended.is_(True),
                       ClassifiedOffer.min_term_months <= q.max_term_months))
    return out


def from_clause(stmt: Select) -> Select:
    return (stmt.join(Property, Property.id == ClassifiedOffer.property_id)
                .join(Space, Space.id == ClassifiedOffer.space_id))


def select_matching(db: Session, q: SearchQuery, *columns) -> Select:
    """The matching universe — the only way list and map select rows."""
    if columns:
        return from_clause(select(*columns)).where(*filters(db, q))
    # The offer's property and space come from the search's own joins, not
    # from a second eager join of the same tables (EXPLAIN, TASK-013).
    return (from_clause(select(ClassifiedOffer)).where(*filters(db, q))
            .options(contains_eager(ClassifiedOffer.listed_property),
                     contains_eager(ClassifiedOffer.space)))


def order_by(q: SearchQuery) -> list:
    """Deterministic order: the chosen key, NULLs last, then the id (D-71)."""
    key = {
        "newest": ClassifiedOffer.published_at.desc().nulls_last(),
        "price_asc": ClassifiedOffer.estimated_monthly_total_minor.asc().nulls_last(),
        "price_desc": ClassifiedOffer.estimated_monthly_total_minor.desc().nulls_last(),
        "size_desc": listed_area_sql().desc().nulls_last(),
        "available_soonest": ClassifiedOffer.available_from.asc().nulls_last(),
    }[q.sort]
    return [key, ClassifiedOffer.id.asc()]


def count_matching(db: Session, q: SearchQuery, *extra) -> int:
    stmt = from_clause(select(func.count()).select_from(ClassifiedOffer)).where(
        *filters(db, q), *extra)
    return int(db.scalar(stmt) or 0)


def has_public_point() -> ColumnElement[bool]:
    """The one predicate for "this listing has a map marker"."""
    return ClassifiedOffer.public_latitude.is_not(None)


def count_map_partition(db: Session, q: SearchQuery) -> tuple[int, int]:
    """(total, with_point) of the matching universe from ONE aggregate
    statement (TASK-013R, F13A-02): one snapshot, one decision instant, so
    with_point can never exceed total and without_point = total - with_point
    is non-negative by construction — two separate counts could straddle a
    concurrent publication."""
    stmt = from_clause(
        select(func.count(), func.count().filter(has_public_point()))
        .select_from(ClassifiedOffer)
    ).where(*filters(db, q))
    total, with_point = db.execute(stmt).one()
    return int(total), int(with_point)


def bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n < 10:
        return "1-9"
    if n < 50:
        return "10-49"
    return "50+"


def record(surface: str, q: SearchQuery, total: int) -> None:
    SEARCHES.labels(surface=surface, results=bucket(total)).inc()
    for name in q.used_filters():
        FILTER_USE.labels(filter=name).inc()
