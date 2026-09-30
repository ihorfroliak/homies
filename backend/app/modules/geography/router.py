"""Public, read-only geographic reference data (TASK-010).

The backend half of location UX: countries, the administrative tree one level
at a time, and locality autocomplete. Reference data only — no address,
coordinate or anything private is reachable here. Ids returned are Homies ids;
official identifiers (TERYT …) are not exposed by this API.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.geography import service
from app.modules.geography.models import AdministrativeArea, Country, GeoArea, Locality

router = APIRouter(prefix="/geo", tags=["geography"])


class CountryOut(BaseModel):
    code: str
    name: str
    default_currency: str
    is_active_market: bool


class AreaOut(BaseModel):
    id: str
    country_code: str
    parent_id: str | None
    level: int
    kind_code: str
    name: str
    slug: str | None


class LocalityOut(BaseModel):
    id: str
    country_code: str
    kind: str
    name: str
    slug: str | None
    # The official areas it lies in, top level first — what a person needs to
    # tell two places of the same name apart ("Nowa Wieś, małopolskie").
    areas: list[AreaOut]


class GeoAreaOut(BaseModel):
    id: str
    country_code: str
    locality_id: str | None
    kind: str
    name: str
    slug: str | None


def _area(a: AdministrativeArea) -> AreaOut:
    return AreaOut(id=a.id, country_code=a.country_code, parent_id=a.parent_id, level=a.level,
                   kind_code=a.kind_code, name=a.official_name, slug=a.slug)


@router.get("/countries", response_model=list[CountryOut])
def countries(db: Session = Depends(get_db)):
    return [CountryOut(code=c.code, name=c.name, default_currency=c.default_currency,
                       is_active_market=c.is_active_market)
            for c in db.scalars(select(Country).order_by(Country.code))]


@router.get("/areas", response_model=list[AreaOut])
def areas(
    country: str = Query(pattern="^[A-Z]{2}$"),
    parent_id: str | None = None,
    db: Session = Depends(get_db),
):
    """One level of the administrative tree: the top level of `country`, or
    the children of `parent_id`."""
    query = select(AdministrativeArea).where(
        AdministrativeArea.country_code == country, AdministrativeArea.status == "ACTIVE")
    if parent_id is None:
        query = query.where(AdministrativeArea.parent_id.is_(None))
    else:
        query = query.where(AdministrativeArea.parent_id == parent_id)
    return [_area(a) for a in db.scalars(query.order_by(AdministrativeArea.official_name))]


@router.get("/localities", response_model=list[LocalityOut])
def localities(
    country: str = Query(pattern="^[A-Z]{2}$"),
    q: str = Query(min_length=1, max_length=80),
    admin_area_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Autocomplete: localities whose name starts with `q`, optionally within
    an administrative area (and everything below it)."""
    found = service.locality_search(db, country, q, admin_area_id, limit)
    return [LocalityOut(id=loc.id, country_code=loc.country_code, kind=loc.kind,
                        name=loc.official_name, slug=loc.slug,
                        areas=[_area(a) for a in service.area_path(db, loc.admin_area_id)])
            for loc in found]


@router.get("/localities/{locality_id}/areas", response_model=list[GeoAreaOut])
def locality_search_areas(locality_id: str, db: Session = Depends(get_db)):
    """Search areas (districts, neighbourhoods) of a locality."""
    if db.get(Locality, locality_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Locality not found")
    rows = db.scalars(select(GeoArea).where(
        GeoArea.locality_id == locality_id, GeoArea.status == "ACTIVE").order_by(GeoArea.name))
    return [GeoAreaOut(id=g.id, country_code=g.country_code, locality_id=g.locality_id,
                       kind=g.kind, name=g.name, slug=g.slug) for g in rows]
