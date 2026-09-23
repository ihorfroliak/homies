"""Properties and the free long-term classifieds board.

Homies is not a party to anything on this board: no booking, no payment, no
deposit, no dispute resolution. The only thing the platform does here is connect
two people and protect the owner's phone number while doing it.

That protection is the security-relevant part of this module:

* the public response shape (`ClassifiedOut`) has no phone field, so a leak
  needs someone to deliberately add one back;
* the number is disclosed only through `POST /classifieds/{id}/contact`, which
  requires an account with a *verified phone* — and `users.phone` is unique, so
  the SIM that proves one account cannot prove the next;
* every disclosure is recorded in `ContactReveal`, and those rows are now read:
  one account may uncover a bounded number of DIFFERENT owners per rolling 24
  hours. The rate limiter bounds speed; this bounds the total, which is what
  stands between a verified account and the whole board overnight.

Narrower than PRODUCT_MODEL, deliberately: the model asks for a verified email
*and* phone. Email verification exists (`/v1/me/verify/email/*`) but is not a
second gate here — it adds a round trip for the tenant and nothing an automated
collector cannot buy in bulk. Tightening it is a product call, not a gap.

Still open: the owner-facing "who asked for my number" view. The rows exist.
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prometheus_client import Counter
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.modules.properties import authority
from app.modules.properties.attributes import AttributeError_, load_catalogue
from app.modules.properties.attributes import validate as validate_attributes
from app.modules.properties.models import (
    AttributeDefinition,
    ClassifiedOffer,
    ContactReveal,
    Property,
)
from app.modules.properties.schemas import (
    AttributeOut,
    AuthorityOut,
    ClassifiedCreate,
    ClassifiedOut,
    ClassifiedPage,
    ContactRevealOut,
    PropertyCreate,
    PropertyOut,
    RevealQuotaOut,
)

router = APIRouter(tags=["properties"])


def _monthly_total(offer: ClassifiedOffer) -> int:
    """What the tenant pays each month, deposit excluded (it is returned)."""
    total = offer.rent_amount + offer.admin_fee + offer.parking_fee
    if not offer.utilities_included:
        total += offer.utilities_amount
    return total


def _public(offer: ClassifiedOffer) -> ClassifiedOut:
    return ClassifiedOut(
        **{
            k: getattr(offer, k)
            for k in ClassifiedOut.model_fields
            if k != "monthly_total_estimate"
        },
        monthly_total_estimate=_monthly_total(offer),
    )


def _authorized_offer(
    db: Session, user, offer_id: str, *, verified: bool
) -> ClassifiedOffer:
    """An offer the caller may manage, decided by authority over its property.

    Not by `offer.owner_id`: that records who typed the listing in, which stops
    being the right answer the moment an agent lists for an owner, or an owner
    sells and the new one takes over.
    """
    offer = db.get(ClassifiedOffer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    try:
        authority.require(db, user, offer.property_id, "PUBLISH_LISTING", verified=verified)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            # Same enumeration rule as the property itself.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found") from None
        raise
    return offer


def _property_out(db: Session, prop: Property) -> PropertyOut:
    """The owner-facing shape, with the authority summary Schema v1 §116 asks
    for: the owner needs to see that their claim is unverified to understand
    why Publish refuses."""
    return PropertyOut.model_validate(prop).model_copy(
        update={
            "authorities": [
                AuthorityOut(
                    id=a.id,
                    authority_type=a.authority_type,
                    status=a.status,
                    verification_state=a.verification_state,
                    scopes=authority.scopes_of(db, a.id),
                )
                for a in authority.authorities_of(db, prop.id)
            ]
        }
    )


# --- properties ---------------------------------------------------------------


@router.post("/properties", response_model=PropertyOut, status_code=201)
def create_property(
    body: PropertyCreate,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    """Register a physical object. It exists once, whatever is later done with it.

    `municipality` (gmina) is required: the Polish tourist tax is set per gmina
    and charged per night, so a short-stay price cannot be computed without it.
    """
    data = body.model_dump()
    try:
        validate_attributes(db, data.get("attributes") or {})
    except AttributeError_ as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    prop = Property(owner_id=user.id, **data)
    db.add(prop)
    db.flush()
    # Registering a flat is a claim to it, recorded as an authority held by the
    # registrant's legal person — unverified until Homies checks it.
    authority.grant_owner(db, user, prop.id)
    audit(db, actor=user.id, action="property.created", entity_type="property", entity_id=prop.id)
    db.commit()
    return _property_out(db, prop)


@router.get("/properties", response_model=list[PropertyOut])
def my_properties(user=Depends(require_role("host")), db: Session = Depends(get_db)):
    """Every property this account may edit — by authority, not by who
    created the row."""
    props = db.scalars(
        select(Property).where(
            Property.id.in_(authority.authorized_property_ids(user.id, "EDIT_PROPERTY"))
        )
    )
    return [_property_out(db, p) for p in props]


@router.get("/attributes", response_model=list[AttributeOut])
def list_attributes(db: Session = Depends(get_db)):
    """The attribute catalogue. Public because the filter panel is public.

    Every surface — web, both apps, admin — builds its amenity filters from
    this. Hand-written lists per client are how three of them end up disagreeing
    about what "has a dishwasher" means.
    """
    return list(db.scalars(select(AttributeDefinition).order_by(AttributeDefinition.code)))


# --- classifieds (free long-term board) ---------------------------------------


@router.post("/properties/{property_id}/classifieds", response_model=ClassifiedOut, status_code=201)
def create_classified(
    property_id: str,
    body: ClassifiedCreate,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    """Post a free long-term listing against one of your properties.

    The board starts at six months. Anything shorter is a Homies booking — paid
    and commissioned — and must not arrive here relabelled.
    """
    # A draft needs an authority in force, not a verified one: the owner has
    # to be able to prepare the listing while the claim is being checked.
    prop = authority.require(db, user, property_id, "PUBLISH_LISTING", verified=False)
    offer = ClassifiedOffer(property_id=prop.id, owner_id=user.id, **body.model_dump())
    db.add(offer)
    db.flush()
    audit(
        db,
        actor=user.id,
        action="classified.created",
        entity_type="classified_offer",
        entity_id=offer.id,
    )
    db.commit()
    return _public(offer)


@router.post("/classifieds/{offer_id}/publish", response_model=ClassifiedOut)
def publish_classified(
    offer_id: str,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    # Publishing is the one step that needs a VERIFIED claim. A listing for a
    # flat the poster does not own is the scam this board would otherwise
    # carry; it is refused here, before the first deposit is wired.
    offer = _authorized_offer(db, user, offer_id, verified=True)
    offer.status = "active"
    offer.published_at = datetime.now(timezone.utc)
    audit(
        db,
        actor=user.id,
        action="classified.published",
        entity_type="classified_offer",
        entity_id=offer.id,
    )
    db.commit()
    return _public(offer)


@router.post("/classifieds/{offer_id}/pause", response_model=ClassifiedOut)
def pause_classified(
    offer_id: str,
    user=Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    # Taking a listing down needs no verification: a holder whose claim is
    # still unchecked must always be able to stop showing it.
    offer = _authorized_offer(db, user, offer_id, verified=False)
    offer.status = "paused"
    db.commit()
    return _public(offer)


# Sorting is an allowlist, never a column name from the query string. Passing
# user input into order_by() exposes every column in the table and, with a
# string-built query, worse.
SORTS = {
    "newest": ClassifiedOffer.published_at.desc(),
    "price_asc": None,  # filled in below: the total, not the rent
    "price_desc": None,
    "size_desc": Property.area_m2.desc(),
}


def _monthly_total_sql():
    """The tenant's real monthly cost, as SQL, so it can be filtered and sorted.

    Deliberately not `rent_amount`. Two offers at 3 000 zł rent are not the same
    price when one adds 600 zł of building fees and the other does not, and a
    tenant who filters "up to 3 000" and is shown a 3 600 zł flat has been
    misled by the search, not by the owner. The deposit is excluded — it comes
    back.
    """
    utilities = case(
        (ClassifiedOffer.utilities_included.is_(True), 0),
        else_=ClassifiedOffer.utilities_amount,
    )
    return ClassifiedOffer.rent_amount + ClassifiedOffer.admin_fee + (
        ClassifiedOffer.parking_fee + utilities
    )


@router.get("/classifieds", response_model=ClassifiedPage)
def list_classifieds(
    city: str | None = None,
    district: str | None = None,
    # Budget is expressed against the TOTAL, which is what the tenant pays.
    max_monthly_total: int | None = Query(default=None, ge=0),
    min_monthly_total: int | None = Query(default=None, ge=0),
    min_rooms: int | None = Query(default=None, ge=0),
    min_area_m2: int | None = Query(default=None, ge=0),
    furnished: str | None = None,
    parking: str | None = None,
    pets_allowed: bool | None = None,
    has_elevator: bool | None = None,
    # "I can move by this date" — offers available then or sooner, plus those
    # with no date set, which means available now.
    available_by: date | None = None,
    max_term_months: int | None = Query(default=None, ge=0),
    # Repeatable: ?has=dishwasher&has=balcony. Only codes the catalogue marks
    # filterable are accepted, so a typo fails loudly instead of quietly
    # matching nothing.
    has: list[str] | None = Query(default=None),
    sort: str = "newest",
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Search the free board. Only active offers, and never a phone number."""
    if sort not in SORTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"sort must be one of {', '.join(sorted(SORTS))}",
        )

    total_expr = _monthly_total_sql()
    filters = [ClassifiedOffer.status == "active"]
    if has:
        catalogue = load_catalogue(db)
        for code in has:
            definition = catalogue.get(code)
            if definition is None or not definition.filterable:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"'{code}' is not a filterable attribute — see GET /v1/attributes",
                )
            # as_boolean() rather than a text comparison: SQLite's
            # JSON_EXTRACT yields 1/0 while Postgres yields a JSON boolean, and
            # SQLAlchemy is the thing that knows the difference. An earlier
            # version compared the literal 'true' and matched nothing on SQLite.
            filters.append(Property.attributes[code].as_boolean().is_(True))
    if city:
        filters.append(Property.city == city)
    if district:
        filters.append(Property.district == district)
    if max_monthly_total is not None:
        filters.append(total_expr <= max_monthly_total)
    if min_monthly_total is not None:
        filters.append(total_expr >= min_monthly_total)
    if min_rooms is not None:
        filters.append(Property.rooms >= min_rooms)
    if min_area_m2 is not None:
        filters.append(Property.area_m2 >= min_area_m2)
    if furnished:
        filters.append(Property.furnished == furnished)
    if parking:
        filters.append(Property.parking == parking)
    if pets_allowed is not None:
        filters.append(Property.pets_allowed.is_(pets_allowed))
    if has_elevator is not None:
        filters.append(Property.has_elevator.is_(has_elevator))
    if available_by is not None:
        # A missing date means "available now", so it must not be filtered out.
        filters.append(
            or_(
                ClassifiedOffer.available_from.is_(None),
                ClassifiedOffer.available_from <= available_by,
            )
        )
    if max_term_months is not None:
        # An open-ended offer commits the tenant to nothing, so it satisfies any
        # "I can stay at most N months" filter.
        filters.append(
            or_(
                ClassifiedOffer.open_ended.is_(True),
                ClassifiedOffer.min_term_months <= max_term_months,
            )
        )

    base = select(ClassifiedOffer).join(
        Property, Property.id == ClassifiedOffer.property_id
    ).where(*filters)

    order = SORTS[sort]
    if sort == "price_asc":
        order = total_expr.asc()
    elif sort == "price_desc":
        order = total_expr.desc()

    total = db.scalar(
        select(func.count())
        .select_from(ClassifiedOffer)
        .join(Property, Property.id == ClassifiedOffer.property_id)
        .where(*filters)
    )
    rows = db.scalars(base.order_by(order).limit(limit).offset(offset))
    return ClassifiedPage(
        items=[_public(o) for o in rows],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get("/classifieds/{offer_id}", response_model=ClassifiedOut)
def get_classified(offer_id: str, db: Session = Depends(get_db)):
    offer = db.get(ClassifiedOffer, offer_id)
    if offer is None or offer.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return _public(offer)


QUOTA_WINDOW = timedelta(hours=24)

REVEALS = Counter(
    "homies_contact_reveals_total",
    "Owner phone disclosures on the free board",
    # granted: a new number handed over. repeat: the viewer already had it.
    # quota_blocked: the account hit its daily ceiling — the one to watch, and
    # the only signal that distinguishes a busy tenant from a collector.
    ["outcome"],
)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _quota_used(db: Session, viewer_id: str) -> tuple[int, int]:
    """Reveals this account made in the last 24 hours, and when one frees up.

    A ROLLING window, not a calendar day: resetting at midnight hands anyone
    who waits for it a double quota in the small hours, which is exactly when
    an unattended collector runs.

    Counted from `contact_reveals` rather than a counter on the user, so the
    number is reconstructible, survives a restart, and matches the evidence a
    dispute would be argued from.
    """
    since = datetime.now(timezone.utc) - QUOTA_WINDOW
    rows = list(
        db.scalars(
            select(ContactReveal.revealed_at)
            .where(ContactReveal.viewer_id == viewer_id, ContactReveal.revealed_at >= since)
            .order_by(ContactReveal.revealed_at)
        )
    )
    if not rows:
        return 0, int(QUOTA_WINDOW.total_seconds())
    frees_at = _aware(rows[0]) + QUOTA_WINDOW
    retry_after = max(1, int((frees_at - datetime.now(timezone.utc)).total_seconds()))
    return len(rows), retry_after


@router.get("/me/reveal-quota", response_model=RevealQuotaOut)
def my_reveal_quota(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """What the app shows before someone runs into the wall.

    A limit nobody can see is indistinguishable from a broken button.
    """
    used, retry_after = _quota_used(db, user.id)
    quota = settings.contact_reveal_daily_quota
    return RevealQuotaOut(
        limit=quota,
        used=min(used, quota),
        remaining=max(0, quota - used),
        resets_in=retry_after if used else 0,
    )


@router.post("/classifieds/{offer_id}/contact", response_model=ContactRevealOut)
def reveal_contact(
    offer_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disclose the owner's phone number to a verified account, and record it.

    A *verified phone* is the gate, not merely sign-in. An address costs a
    scraper nothing; a SIM costs money, and `users.phone` is unique, so the
    cost is paid per account rather than once. Every number taken still leaves
    a row naming who took it. Anonymous and unverified visitors get the message
    channel instead.

    Email verification is deliberately NOT a second gate here: it adds a round
    trip for the tenant and nothing an automated collector cannot buy in bulk.
    Tightening that is a product call, not a technical gap.
    """
    if user.phone_verified_at is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Verify your phone number before contacting owners",
        )
    offer = db.get(ClassifiedOffer, offer_id)
    if offer is None or offer.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    if offer.contact_mode != "phone" or not offer.contact_phone:
        # The owner chose messages. Saying so is not a leak, and pretending the
        # offer does not exist would be a lie.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This owner accepts messages only, not phone calls"
        )

    already = db.scalar(
        select(ContactReveal).where(
            ContactReveal.offer_id == offer.id, ContactReveal.viewer_id == user.id
        )
    )
    if already is not None:
        # Same viewer asking twice. Not a second disclosure — they already have
        # the number — so it costs no quota, inflates no risk signal, and adds
        # no row. Checked BEFORE the quota, or a tenant who spent today's
        # budget could not re-open a number they were given this morning.
        REVEALS.labels(outcome="repeat").inc()
        return ContactRevealOut(offer_id=offer.id, contact_phone=offer.contact_phone)

    used, retry_after = _quota_used(db, user.id)
    if used >= settings.contact_reveal_daily_quota:
        REVEALS.labels(outcome="quota_blocked").inc()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Daily limit of owner contacts reached. It frees up as today's views age out.",
            headers={"Retry-After": str(retry_after)},
        )

    db.add(ContactReveal(offer_id=offer.id, viewer_id=user.id))
    try:
        db.flush()
    except IntegrityError:
        # Two requests for the same offer racing each other. The unique
        # constraint is what decides; the loser gets the same answer.
        db.rollback()
        REVEALS.labels(outcome="repeat").inc()
        return ContactRevealOut(offer_id=offer.id, contact_phone=offer.contact_phone)

    audit(
        db,
        actor=user.id,
        action="classified.contact_revealed",
        entity_type="classified_offer",
        entity_id=offer.id,
    )
    db.commit()
    REVEALS.labels(outcome="granted").inc()
    return ContactRevealOut(offer_id=offer.id, contact_phone=offer.contact_phone)
