"""Geography services: resolving places, walking hierarchies, importing reference data.

The database enforces hierarchy integrity (see models.py). The functions here
give the same rules an application-level answer (clean 4xx instead of a
constraint error) and keep country-specific behaviour out of the core: a
country contributes data (kind codes, sources), not `if country == "PL"`.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.geography.models import (
    Address,
    AdministrativeArea,
    Country,
    GeoArea,
    GeoExternalRef,
    GeoSource,
    Locality,
)


class GeographyError(ValueError):
    """A location that does not exist or does not fit together."""


# --- hierarchy -----------------------------------------------------------------


def area_path(db: Session, area_id: str | None) -> list[AdministrativeArea]:
    """The area and its ancestors, top level first."""
    path: list[AdministrativeArea] = []
    seen: set[str] = set()
    while area_id is not None:
        if area_id in seen:  # unreachable while the DB invariant holds
            raise GeographyError("administrative hierarchy contains a cycle")
        seen.add(area_id)
        area = db.get(AdministrativeArea, area_id)
        if area is None:
            break
        path.append(area)
        area_id = area.parent_id
    return list(reversed(path))


def descendant_area_ids(area_id: str):
    """A selectable of the area and every area below it (recursive CTE).
    Works on PostgreSQL and SQLite."""
    tree = (
        select(AdministrativeArea.id)
        .where(AdministrativeArea.id == area_id)
        .cte("area_tree", recursive=True)
    )
    tree = tree.union_all(
        select(AdministrativeArea.id).where(AdministrativeArea.parent_id == tree.c.id)
    )
    return select(tree.c.id)


def check_parent(db: Session, country_code: str, parent_id: str | None,
                 level: int, own_id: str | None = None) -> None:
    """The rules the migration's trigger enforces, answered in Python."""
    if parent_id is None:
        if level != 1:
            raise GeographyError("a top-level area has level 1")
        return
    if own_id is not None and parent_id == own_id:
        raise GeographyError("an area cannot be its own parent")
    parent = db.get(AdministrativeArea, parent_id)
    if parent is None:
        raise GeographyError("parent area not found")
    if parent.country_code != country_code:
        raise GeographyError("parent area is in another country")
    if level != parent.level + 1:
        raise GeographyError("level must be one below the parent's")
    if own_id is not None and own_id in {a.id for a in area_path(db, parent_id)}:
        raise GeographyError("that parent would create a cycle")


# --- resolving a location for a property ------------------------------------------


@dataclass(frozen=True)
class LocationInput:
    country_code: str
    locality_id: str | None = None
    admin_area_id: str | None = None
    geo_area_id: str | None = None
    postal_code: str = ""
    thoroughfare: str | None = None
    building_number: str | None = None
    unstructured_text: str = ""
    locality_text: str = ""
    district_text: str = ""


def build_address(db: Session, loc: LocationInput) -> Address:
    """A new Address for `loc`, validated against reference data.

    Structured when it names a locality or an administrative area; otherwise
    unstructured (the typed text only) — never a guess.
    """
    country = db.get(Country, loc.country_code)
    if country is None:
        raise GeographyError(f"unknown country {loc.country_code!r}")
    if loc.locality_id and loc.admin_area_id:
        raise GeographyError("give a locality or an administrative area, not both")
    locality = None
    geo = None
    if loc.locality_id:
        locality = db.get(Locality, loc.locality_id)
        if locality is None or locality.status != "ACTIVE":
            raise GeographyError("locality not found")
        if locality.country_code != loc.country_code:
            raise GeographyError("locality is in another country")
    if loc.admin_area_id:
        area = db.get(AdministrativeArea, loc.admin_area_id)
        if area is None or area.status != "ACTIVE":
            raise GeographyError("administrative area not found")
        if area.country_code != loc.country_code:
            raise GeographyError("administrative area is in another country")
    if loc.geo_area_id:
        geo = db.get(GeoArea, loc.geo_area_id)
        if geo is None or geo.status != "ACTIVE" or geo.country_code != loc.country_code:
            raise GeographyError("area not found")
        if geo.locality_id and locality is not None and geo.locality_id != locality.id:
            raise GeographyError("that area belongs to another locality")
    structured = bool(loc.locality_id or loc.admin_area_id)
    return Address(
        country_code=loc.country_code,
        locality_id=loc.locality_id,
        admin_area_id=loc.admin_area_id,
        geo_area_id=loc.geo_area_id,
        postal_code=loc.postal_code.strip(),
        thoroughfare=(loc.thoroughfare or "").strip() or None,
        building_number=(loc.building_number or "").strip() or None,
        unstructured_text=loc.unstructured_text.strip(),
        locality_text=(locality.official_name if locality else loc.locality_text).strip(),
        district_text=(geo.name if geo is not None else loc.district_text).strip(),
        resolution="STRUCTURED" if structured else "UNSTRUCTURED",
        source="USER_INPUT",
        verification="UNVERIFIED",
    )


def address_areas(db: Session, address: Address) -> list[AdministrativeArea]:
    """The official areas an address lies in, top level first."""
    if address.locality is not None:
        return area_path(db, address.locality.admin_area_id)
    return area_path(db, address.admin_area_id)


# --- reference data (import seam) --------------------------------------------------


@dataclass(frozen=True)
class AreaRow:
    external_id: str
    parent_external_id: str | None
    kind_code: str
    official_name: str
    slug: str | None = None


@dataclass(frozen=True)
class LocalityRow:
    external_id: str
    area_source_code: str
    area_external_id: str
    kind: str
    official_name: str
    source_kind: str | None = None
    slug: str | None = None


def _by_ref(db: Session, source: str, external_id: str, column):
    ref = db.scalar(select(GeoExternalRef).where(
        GeoExternalRef.source_code == source, GeoExternalRef.external_id == external_id))
    return getattr(ref, column) if ref else None


def import_areas(db: Session, country_code: str, source_code: str,
                 rows: Sequence[AreaRow]) -> int:
    """Upsert administrative areas from one source, parents before children.

    Matched by the source's own identifier, never by name. Existing areas are
    renamed and re-parented in place, so every Homies reference to them stays
    valid. Nothing is deleted: an area that disappears from a release is
    retired by a separate, reviewed step. Returns the number of rows applied.
    """
    if db.get(GeoSource, source_code) is None:
        raise GeographyError(f"unknown source {source_code!r}")
    pending = list(rows)
    applied = 0
    while pending:
        progressed = False
        for row in list(pending):
            parent_id = None
            if row.parent_external_id is not None:
                parent_id = _by_ref(db, source_code, row.parent_external_id, "admin_area_id")
                if parent_id is None:
                    continue  # parent not imported yet
            parent = db.get(AdministrativeArea, parent_id) if parent_id else None
            level = parent.level + 1 if parent else 1
            existing_id = _by_ref(db, source_code, row.external_id, "admin_area_id")
            check_parent(db, country_code, parent_id, level, own_id=existing_id)
            if existing_id:
                area = db.get(AdministrativeArea, existing_id)
                assert area is not None
                area.parent_id, area.level = parent_id, level
                area.kind_code, area.official_name, area.slug = (
                    row.kind_code, row.official_name, row.slug)
            else:
                area = AdministrativeArea(
                    country_code=country_code, parent_id=parent_id, level=level,
                    kind_code=row.kind_code, official_name=row.official_name, slug=row.slug,
                )
                db.add(area)
                db.flush()
                db.add(GeoExternalRef(source_code=source_code, external_id=row.external_id,
                                      admin_area_id=area.id))
            db.flush()
            pending.remove(row)
            applied += 1
            progressed = True
        if not progressed:
            missing = sorted({r.parent_external_id or "" for r in pending})
            raise GeographyError(f"rows reference unknown parents: {missing[:10]}")
    return applied


def import_localities(db: Session, country_code: str, source_code: str,
                      rows: Iterable[LocalityRow]) -> int:
    if db.get(GeoSource, source_code) is None:
        raise GeographyError(f"unknown source {source_code!r}")
    applied = 0
    for row in rows:
        area_id = _by_ref(db, row.area_source_code, row.area_external_id, "admin_area_id")
        area = db.get(AdministrativeArea, area_id) if area_id else None
        if area is None or area.country_code != country_code:
            raise GeographyError(f"locality {row.external_id}: unknown area {row.area_external_id}")
        existing_id = _by_ref(db, source_code, row.external_id, "locality_id")
        if existing_id:
            loc = db.get(Locality, existing_id)
            assert loc is not None
            loc.admin_area_id, loc.kind, loc.official_name = area.id, row.kind, row.official_name
            loc.source_kind, loc.slug = row.source_kind, row.slug
        else:
            loc = Locality(country_code=country_code, admin_area_id=area.id, kind=row.kind,
                           official_name=row.official_name, source_kind=row.source_kind,
                           slug=row.slug)
            db.add(loc)
            db.flush()
            db.add(GeoExternalRef(source_code=source_code, external_id=row.external_id,
                                  locality_id=loc.id))
        db.flush()
        applied += 1
    return applied


def locality_search(db: Session, country_code: str, prefix: str,
                    admin_area_id: str | None = None, limit: int = 20):
    """Localities whose name starts with `prefix` (case-insensitive) — the
    backend half of address autocomplete."""
    query = select(Locality).where(
        Locality.country_code == country_code,
        Locality.status == "ACTIVE",
        Locality.official_name.ilike(prefix.replace("%", "").replace("_", "") + "%"),
    )
    if admin_area_id:
        query = query.where(Locality.admin_area_id.in_(descendant_area_ids(admin_area_id)))
    return list(db.scalars(query.order_by(Locality.official_name).limit(limit)))


