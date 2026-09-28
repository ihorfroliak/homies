"""Saved-search query handling (TASK-014): one search language, versioned.

* The stored form is `SearchQuery.canonical()` — the TASK-013 canonical query.
* `QUERY_SCHEMA_VERSION` names the meaning of that string. A stored query of a
  version this code does not support is INVALID, never guessed at.
* The fingerprint is SHA-256 over the version and the canonical query. Order
  of parameters in what a client sent cannot change it: the query is parsed
  and canonicalised first.
* Loading a stored query goes through `search.parse_query_string` →
  `search.build_query` — the live validation — plus `search.check_references`.
  Anything that no longer validates is INVALID: explicit, never broadened.
"""

import hashlib
from urllib.parse import parse_qsl, urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.geography.models import Address, AdministrativeArea, GeoArea, Locality
from app.modules.geography import service as geography
from app.modules.properties import search
from app.modules.properties.models import ClassifiedOffer, Property
from app.modules.properties.search import InvalidSearchQuery, SearchQuery
from app.modules.saved.models import SavedSearch, SavedSearchAnchor

QUERY_SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = frozenset({1})

# Page-state parameters a client may carry over from the search page it is
# saving. They are not criteria: removed by name, before validation. Any
# OTHER unknown parameter is refused, never dropped.
PAGE_PARAMETERS = frozenset({"limit", "offset"})


def fingerprint(version: int, canonical: str) -> str:
    return hashlib.sha256(f"{version}\n{canonical}".encode()).hexdigest()


def prepare_query(db: Session, raw: str) -> SearchQuery:
    """A client's query string → the validated SearchQuery to store.
    Raises InvalidSearchQuery."""
    if len(raw) > search.MAX_CANONICAL_LENGTH:
        raise InvalidSearchQuery(
            f"the query is longer than {search.MAX_CANONICAL_LENGTH} characters")
    try:
        pairs = parse_qsl(raw.lstrip("?"), keep_blank_values=True, strict_parsing=bool(raw),
                          max_num_fields=2_000)
    except ValueError:
        raise InvalidSearchQuery("the query is not a valid URL query string") from None
    criteria = urlencode([(k, v) for k, v in pairs if k not in PAGE_PARAMETERS])
    q = search.parse_query_string(db, criteria)
    search.check_references(db, q)
    return q


def load_query(db: Session, saved: SavedSearch) -> SearchQuery:
    """The stored query, re-validated now. Raises InvalidSearchQuery."""
    if saved.query_schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise InvalidSearchQuery(
            f"query schema version {saved.query_schema_version} is not supported")
    q = search.parse_query_string(db, saved.canonical_query)
    search.check_references(db, q)
    return q


def query_state(db: Session, saved: SavedSearch) -> tuple[SearchQuery | None, str | None]:
    """(query, None) when valid; (None, reason) when INVALID."""
    try:
        return load_query(db, saved), None
    except InvalidSearchQuery as exc:
        return None, str(exc)


def market_country(db: Session, q: SearchQuery) -> str | None:
    if q.country_code:
        return q.country_code
    for model, ids in ((Locality, q.locality_ids), (GeoArea, q.geo_area_ids),
                       (AdministrativeArea, q.admin_area_ids)):
        if ids:
            return db.scalar(select(model.country_code).where(model.id == ids[0]))
    return None


# --- candidate narrowing (never a matching language) -----------------------------------------


def anchors_for(q: SearchQuery) -> list[tuple[str, str]]:
    """The search's anchors: one dimension it constrains, as (kind, value)
    rows. Every listing the search can match carries one of them as a key
    (listing_keys), because dimensions AND together. The most selective
    structured dimension is chosen; with no place at all, '*'."""
    if q.locality_ids:
        return [("L", v) for v in q.locality_ids]
    if q.geo_area_ids:
        return [("G", v) for v in q.geo_area_ids]
    if q.admin_area_ids:
        return [("A", v) for v in q.admin_area_ids]
    if q.country_code:
        return [("C", q.country_code)]
    return [("*", "*")]


def set_anchors(saved: SavedSearch, q: SearchQuery) -> None:
    saved.anchors = [SavedSearchAnchor(kind=k, value=v) for k, v in anchors_for(q)]


def listing_keys(db: Session, offer: ClassifiedOffer) -> list[tuple[str, str]]:
    """Every anchor under which a search could match this listing: its
    locality, search area, each administrative area its address or locality
    lies in (ancestors included — a region matches everything beneath it),
    its country, and '*'."""
    keys: set[tuple[str, str]] = {("*", "*")}
    prop = db.get(Property, offer.property_id)
    address = db.get(Address, prop.address_id) if prop and prop.address_id else None
    if address is None:
        return sorted(keys)
    keys.add(("C", address.country_code))
    if address.locality_id:
        keys.add(("L", address.locality_id))
    if address.geo_area_id:
        keys.add(("G", address.geo_area_id))
    area_ids = {address.admin_area_id}
    if address.locality_id:
        area_ids.add(db.scalar(select(Locality.admin_area_id)
                               .where(Locality.id == address.locality_id)))
    for area_id in area_ids - {None}:
        keys.update(("A", a.id) for a in geography.area_path(db, area_id))
    return sorted(keys)
