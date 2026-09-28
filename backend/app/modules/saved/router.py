"""Saved Listings and Saved Searches — `/v1/me/…` (TASK-014).

Every route is the caller's own: rows are always selected by `user_id =
caller`, so another account's save or search answers exactly like one that
does not exist (404) — no IDOR, no enumeration.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.modules.alerts.metrics import SAVED_LISTINGS, SAVED_SEARCHES
from app.modules.alerts.models import SavedSearchMatch
from app.modules.identity.models import User
from app.modules.properties import freshness, search
from app.modules.properties.models import ClassifiedOffer
from app.modules.properties.router import _page_options, _preload_places, _public
from app.modules.properties.schemas import ClassifiedPage
from app.modules.properties.search import InvalidSearchQuery
from app.modules.saved import service
from app.modules.saved.models import SavedListing, SavedSearch
from app.modules.saved.schemas import (
    SavedListingOut,
    SavedListingPage,
    SavedSearchCreate,
    SavedSearchList,
    SavedSearchOut,
    SavedSearchUpdate,
)

router = APIRouter(tags=["saved"])

# Ids are UUIDs; anything else (a NUL, a 10 kB string) is refused before SQL.
Id = Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9-]+$")]


def _lock_account(db: Session, user_id: str) -> None:
    """Serialise one account's own writes, so the per-user caps hold under
    parallel requests (the reveal-quota pattern, TASK-001 F-03)."""
    db.execute(select(User.id).where(User.id == user_id).with_for_update())


# --- saved listings -----------------------------------------------------------------------


def _saved_out(db: Session, saves: list[SavedListing]) -> list[SavedListingOut]:
    """One query for "which are public now", one page load for those — a
    fixed number of queries whatever the page size."""
    if not saves:
        return []
    ids = [s.listing_id for s in saves]
    public = set(db.scalars(select(ClassifiedOffer.id).where(
        ClassifiedOffer.id.in_(ids), freshness.public_clause(db))))
    offers = {}
    if public:
        rows = list(db.scalars(_page_options(
            search.from_clause(select(ClassifiedOffer))
            .where(ClassifiedOffer.id.in_(public))
            .options(contains_eager(ClassifiedOffer.space)))))
        areas = _preload_places(db, rows)  # noqa: F841 — keeps preloaded areas alive
        now = freshness.db_now(db)
        offers = {o.id: _public(o, now) for o in rows}
    return [
        SavedListingOut(
            saved_id=s.id, listing_id=s.listing_id, saved_at=freshness.to_utc(s.saved_at),
            availability_status="AVAILABLE" if s.listing_id in offers else "NO_LONGER_AVAILABLE",
            # A tombstone carries nothing of the listing: no title, price,
            # media, place, owner or contact — not even from a cache.
            listing=offers.get(s.listing_id),
        )
        for s in saves
    ]


@router.post(
    "/me/saved-listings/{listing_id}",
    response_model=SavedListingOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Already saved — the existing save (idempotent)."},
               404: {"description": "No public listing with this id."},
               409: {"description": "The account holds the maximum number of saved listings."}},
)
def save_listing(listing_id: Id, response: Response, user=Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Save a public listing. Saving again answers 200 with the same save."""
    def existing() -> SavedListing | None:
        return db.scalar(select(SavedListing).where(SavedListing.user_id == user.id,
                                                    SavedListing.listing_id == listing_id))

    found = existing()
    if found is not None:
        response.status_code = status.HTTP_200_OK
        return _saved_out(db, [found])[0]
    now = freshness.db_now(db)
    offer = db.get(ClassifiedOffer, listing_id)
    if offer is None or not freshness.is_public(offer, now):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    _lock_account(db, user.id)
    count = db.scalar(select(func.count()).select_from(SavedListing)
                      .where(SavedListing.user_id == user.id)) or 0
    if count >= settings.saved_listings_per_user:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"At most {settings.saved_listings_per_user} listings can be saved")
    save = SavedListing(user_id=user.id, listing_id=listing_id, saved_at=now)
    db.add(save)
    try:
        db.commit()
    except IntegrityError:  # a parallel save of the same listing won
        db.rollback()
        found = existing()
        if found is None:
            raise
        response.status_code = status.HTTP_200_OK
        return _saved_out(db, [found])[0]
    SAVED_LISTINGS.labels(action="saved").inc()
    return _saved_out(db, [save])[0]


@router.delete("/me/saved-listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsave_listing(listing_id: Id, user=Depends(get_current_user),
                   db: Session = Depends(get_db)) -> Response:
    """Remove a save. Idempotent: 204 whether or not it was saved."""
    removed = db.execute(delete(SavedListing).where(SavedListing.user_id == user.id,
                                                    SavedListing.listing_id == listing_id))
    db.commit()
    if getattr(removed, "rowcount", 0):
        SAVED_LISTINGS.labels(action="removed").inc()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/saved-listings", response_model=SavedListingPage)
def my_saved_listings(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Newest save first (ties by save id — deterministic paging)."""
    total = db.scalar(select(func.count()).select_from(SavedListing)
                      .where(SavedListing.user_id == user.id)) or 0
    saves = list(db.scalars(
        select(SavedListing).where(SavedListing.user_id == user.id)
        .order_by(SavedListing.saved_at.desc(), SavedListing.id.desc())
        .limit(limit).offset(offset)))
    return SavedListingPage(items=_saved_out(db, saves), total=total, limit=limit, offset=offset)


# --- saved searches -----------------------------------------------------------------------


def _own_search(db: Session, user_id: str, search_id: str) -> SavedSearch:
    found = db.scalar(select(SavedSearch).where(SavedSearch.id == search_id,
                                                SavedSearch.user_id == user_id))
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved search not found")
    return found


def _search_out(db: Session, s: SavedSearch, *, with_count: bool) -> SavedSearchOut:
    q, reason = service.query_state(db, s)
    return SavedSearchOut(
        id=s.id, name=s.name, query=s.canonical_query,
        query_schema_version=s.query_schema_version,
        query_state="VALID" if q is not None else "INVALID", invalid_reason=reason,
        market_country_code=s.market_country_code, status=s.status,  # type: ignore[arg-type]
        notifications_enabled=s.notifications_enabled,
        created_at=freshness.to_utc(s.created_at), updated_at=freshness.to_utc(s.updated_at),
        baseline_at=freshness.to_utc(s.baseline_at), version=s.version,
        match_count=search.count_matching(db, q) if (with_count and q is not None) else None,
    )


def _prepared(db: Session, raw: str) -> search.SearchQuery:
    try:
        return service.prepare_query(db, raw)
    except InvalidSearchQuery as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None


def _duplicate(db: Session, user_id: str, fingerprint: str, exclude: str | None = None) -> None:
    stmt = select(SavedSearch.id).where(SavedSearch.user_id == user_id,
                                        SavedSearch.query_fingerprint == fingerprint)
    if exclude is not None:
        stmt = stmt.where(SavedSearch.id != exclude)
    other = db.scalar(stmt)
    if other is not None:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This search is already saved",
                            headers={"Location": f"/v1/me/saved-searches/{other}"})


@router.post(
    "/me/saved-searches",
    response_model=SavedSearchOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "The same search is already saved (`Location` names it), "
                                    "or the account holds the maximum number of searches."},
               422: {"description": "The query is not a valid TASK-013 search."}},
)
def create_saved_search(body: SavedSearchCreate, user=Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """Save a search. A search with no current results is a first-class save.

    What already matches is visible (`match_count`, `/matches`) and is never
    notified: the database instant of saving is the search's baseline, and
    only listings that become public after it can alert (no initial flood)."""
    q = _prepared(db, body.query)
    canonical = q.canonical()
    fingerprint = service.fingerprint(service.QUERY_SCHEMA_VERSION, canonical)
    _lock_account(db, user.id)
    count = db.scalar(select(func.count()).select_from(SavedSearch)
                      .where(SavedSearch.user_id == user.id)) or 0
    if count >= settings.saved_searches_per_user:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"At most {settings.saved_searches_per_user} searches can be saved")
    _duplicate(db, user.id, fingerprint)
    now = freshness.db_now(db)
    saved = SavedSearch(
        user_id=user.id, name=body.name, market_country_code=service.market_country(db, q),
        canonical_query=canonical, query_schema_version=service.QUERY_SCHEMA_VERSION,
        query_fingerprint=fingerprint, notifications_enabled=body.notifications_enabled,
        status="active", created_at=now, updated_at=now, baseline_at=now, version=1,
    )
    service.set_anchors(saved, q)
    db.add(saved)
    try:
        db.flush()
    except IntegrityError:  # a parallel save of the same search won
        db.rollback()
        _duplicate(db, user.id, fingerprint)
        raise
    audit(db, actor=user.id, action="saved_search.created", entity_type="saved_search",
          entity_id=saved.id)
    db.commit()
    SAVED_SEARCHES.labels(action="created").inc()
    return _search_out(db, saved, with_count=True)


@router.get("/me/saved-searches", response_model=SavedSearchList)
def my_saved_searches(limit: int = Query(default=50, ge=1, le=100),
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(SavedSearch)
                      .where(SavedSearch.user_id == user.id)) or 0
    rows = list(db.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id)
                           .order_by(SavedSearch.created_at.desc(), SavedSearch.id.desc())
                           .limit(limit)))
    return SavedSearchList(items=[_search_out(db, s, with_count=False) for s in rows],
                           total=total, limit=limit)


@router.get("/me/saved-searches/{search_id}", response_model=SavedSearchOut)
def get_saved_search(search_id: Id, user=Depends(get_current_user),
                     db: Session = Depends(get_db)):
    return _search_out(db, _own_search(db, user.id, search_id), with_count=True)


@router.get("/me/saved-searches/{search_id}/matches", response_model=ClassifiedPage,
            responses={409: {"description": "The stored query is INVALID."}})
def saved_search_matches(
    search_id: Id,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """What the search finds right now — exactly `GET /v1/classifieds` with
    the stored query (the same SearchQuery, the same public rule)."""
    saved = _own_search(db, user.id, search_id)
    q, reason = service.query_state(db, saved)
    if q is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The saved query is invalid: {reason}")
    total = search.count_matching(db, q)
    rows = list(db.scalars(_page_options(search.select_matching(db, q))
                           .order_by(*search.order_by(q)).limit(limit).offset(offset)))
    areas = _preload_places(db, rows)  # noqa: F841
    now = freshness.db_now(db)
    return ClassifiedPage(items=[_public(o, now) for o in rows], total=total, limit=limit,
                          offset=offset, query=q.canonical(), sort=q.sort)


@router.patch(
    "/me/saved-searches/{search_id}",
    response_model=SavedSearchOut,
    responses={409: {"description": "`expected_version` is not the current version, or the "
                                    "new query duplicates another saved search."}},
)
def update_saved_search(search_id: Id, body: SavedSearchUpdate,
                        user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Rename, pause/resume, switch notifications, or change the query.
    A new query gets a new baseline: its existing matches never alert."""
    saved = _own_search(db, user.id, search_id)
    now = freshness.db_now(db)
    values: dict = {"updated_at": now, "version": SavedSearch.version + 1}
    if body.name is not None:
        values["name"] = body.name
    if body.status is not None:
        values["status"] = body.status
    if body.notifications_enabled is not None:
        values["notifications_enabled"] = body.notifications_enabled
    q = None
    if body.query is not None:
        q = _prepared(db, body.query)
        canonical = q.canonical()
        if canonical != saved.canonical_query:
            fingerprint = service.fingerprint(service.QUERY_SCHEMA_VERSION, canonical)
            _duplicate(db, user.id, fingerprint, exclude=saved.id)
            values.update(canonical_query=canonical, query_fingerprint=fingerprint,
                          query_schema_version=service.QUERY_SCHEMA_VERSION,
                          market_country_code=service.market_country(db, q), baseline_at=now)
        else:
            q = None
    changed = db.execute(update(SavedSearch)
                         .where(SavedSearch.id == saved.id, SavedSearch.user_id == user.id,
                                SavedSearch.version == body.expected_version)
                         .values(**values).execution_options(synchronize_session=False))
    if getattr(changed, "rowcount", 0) != 1:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The saved search was changed elsewhere. Reload and try again.")
    db.refresh(saved)
    if q is not None:
        service.set_anchors(saved, q)
    db.commit()
    return _search_out(db, saved, with_count=True)


@router.delete("/me/saved-searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(search_id: Id, user=Depends(get_current_user),
                        db: Session = Depends(get_db)) -> Response:
    """Delete a saved search. Deliveries already queued for it are suppressed
    at send time (its matches go with it)."""
    saved = _own_search(db, user.id, search_id)
    db.execute(delete(SavedSearchMatch).where(SavedSearchMatch.saved_search_id == saved.id))
    db.delete(saved)
    audit(db, actor=user.id, action="saved_search.deleted", entity_type="saved_search",
          entity_id=search_id)
    db.commit()
    SAVED_SEARCHES.labels(action="deleted").inc()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
