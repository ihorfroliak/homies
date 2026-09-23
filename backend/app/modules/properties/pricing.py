"""Transparent price composition with history (Domain Schema v1 §46–§47, §83, §120).

The owner states the price as a handful of numbers — rent, building fee,
utilities, parking, deposit. They are stored as components, each with a period
of validity. A change closes the current row and opens a new one: the price a
tenant saw last month is never overwritten, because that is exactly what an
argument about "the advert said 2 800" is settled from.

The offer also carries three summaries — the headline price, what the tenant
pays each month, and what they need on the day they move in. They are
recomputed from the components in the same transaction as every change (§83)
so search can filter on them with an index, and a test proves they cannot
drift from the rows they summarise (§47).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.modules.properties.models import ClassifiedOffer, ListingPriceComponent


@dataclass(frozen=True)
class PriceInput:
    rent_amount: int
    admin_fee: int = 0
    utilities_amount: int = 0
    utilities_included: bool = False
    parking_fee: int = 0
    deposit_amount: int = 0


@dataclass(frozen=True)
class ComponentSpec:
    component_type: str
    component_key: str
    amount_minor: int
    cadence: str
    mandatory: bool
    refundable: bool = False
    estimated: bool = False

    def same_as(self, row: ListingPriceComponent) -> bool:
        return (
            row.amount_minor == self.amount_minor
            and row.cadence == self.cadence
            and row.mandatory == self.mandatory
            and row.refundable == self.refundable
            and row.estimated == self.estimated
        )


class VersionConflict(Exception):
    """The offer changed since the caller read it."""


def components_for(price: PriceInput) -> list[ComponentSpec]:
    """The owner's numbers as components. Zero-valued optional components are
    not stored: "no parking fee" is the absence of one, not a row saying 0.

    Utilities an owner includes in the rent are still recorded — the tenant is
    entitled to know the figure — but as non-mandatory, so they are not added
    to the monthly total a second time.
    """
    specs = [ComponentSpec("BASE_RENT", "", price.rent_amount, "MONTHLY", mandatory=True)]
    if price.admin_fee:
        specs.append(ComponentSpec("ADMIN_FEE", "", price.admin_fee, "MONTHLY", mandatory=True))
    if price.utilities_amount:
        specs.append(
            ComponentSpec(
                "UTILITIES_ESTIMATE",
                "",
                price.utilities_amount,
                "MONTHLY",
                mandatory=not price.utilities_included,
                estimated=True,
            )
        )
    if price.parking_fee:
        specs.append(
            ComponentSpec("OTHER_MANDATORY", "parking", price.parking_fee, "MONTHLY", mandatory=True)
        )
    if price.deposit_amount:
        specs.append(
            ComponentSpec(
                "SECURITY_DEPOSIT", "", price.deposit_amount, "ONE_TIME",
                mandatory=True, refundable=True,
            )
        )
    return specs


def summarize(components) -> tuple[int | None, int, int]:
    """(headline price, monthly total, move-in total), from any component-like
    rows or specs.

    Monthly: every mandatory monthly component — including estimated
    utilities, because the tenant pays them whether or not the figure is exact.
    Move-in: the first month plus every mandatory one-off, the refundable
    deposit included — it comes back, but it has to be found on day one.
    """
    headline = None
    monthly = 0
    one_off = 0
    for c in components:
        if c.component_type in ("BASE_RENT", "SALE_ASKING_PRICE"):
            headline = c.amount_minor
        if not c.mandatory:
            continue
        if c.cadence == "MONTHLY":
            monthly += c.amount_minor
        elif c.cadence == "ONE_TIME":
            one_off += c.amount_minor
    return headline, monthly, monthly + one_off


def current_components(db: Session, listing_id: str) -> list[ListingPriceComponent]:
    return list(
        db.scalars(
            select(ListingPriceComponent).where(
                ListingPriceComponent.listing_id == listing_id,
                ListingPriceComponent.valid_to.is_(None),
            )
        )
    )


def history(db: Session, listing_id: str) -> list[ListingPriceComponent]:
    return list(
        db.scalars(
            select(ListingPriceComponent)
            .where(ListingPriceComponent.listing_id == listing_id)
            .order_by(ListingPriceComponent.valid_from, ListingPriceComponent.component_type)
        )
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def set_price(
    db: Session,
    offer: ClassifiedOffer,
    price: PriceInput,
    actor_id: str,
    *,
    expected_version: int | None = None,
) -> bool:
    """Apply a price. Returns whether anything changed.

    Unchanged components keep their rows and their original `valid_from`; only
    what actually moved is closed and reopened, so history records changes,
    not saves. The version check happens in the UPDATE itself — "WHERE
    version = expected" — so two concurrent edits cannot both succeed: the
    loser updates no row and is told to reload (§120).
    """
    now = datetime.now(timezone.utc)
    desired = {(c.component_type, c.component_key): c for c in components_for(price)}
    existing = {(r.component_type, r.component_key): r for r in current_components(db, offer.id)}

    to_close = [
        row for key, row in existing.items()
        if key not in desired or not desired[key].same_as(row)
    ]
    to_open = [
        spec for key, spec in desired.items()
        if key not in existing or not spec.same_as(existing[key])
    ]
    flag_changed = offer.utilities_included != price.utilities_included
    changed = bool(to_close or to_open or flag_changed)

    headline, monthly, move_in = summarize(desired.values())
    values: dict[str, Any] = {
        "primary_price_minor": headline,
        "estimated_monthly_total_minor": monthly,
        "move_in_total_minor": move_in,
        "utilities_included": price.utilities_included,
    }
    # The first price is how the offer comes into being, not a change to it:
    # a new offer starts at version 1, and only later edits move it on.
    is_edit = changed and bool(existing)
    if is_edit:
        values["version"] = ClassifiedOffer.version + 1

    statement = update(ClassifiedOffer).where(ClassifiedOffer.id == offer.id)
    if expected_version is not None:
        statement = statement.where(ClassifiedOffer.version == expected_version)
    result = cast(
        CursorResult,
        db.execute(statement.values(**values).execution_options(synchronize_session=False)),
    )
    if result.rowcount != 1:
        raise VersionConflict(offer.id)

    closes = [now]
    for row in to_close:
        # A period must have length. If a component opened and closes within
        # the resolution of the clock, the close is nudged a microsecond on
        # rather than recording a period that ends where it began.
        closed_at = max(now, _aware(row.valid_from) + timedelta(microseconds=1))
        row.valid_to = closed_at
        closes.append(closed_at)
    # New rows open exactly where the old ones closed, so the history of each
    # component is contiguous: no instant with no price, and none with two.
    opened_at = max(closes)
    db.flush()  # close before opening: the "one current row" index must never see two
    for spec in to_open:
        db.add(
            ListingPriceComponent(
                listing_id=offer.id,
                component_type=spec.component_type,
                component_key=spec.component_key,
                amount_minor=spec.amount_minor,
                cadence=spec.cadence,
                mandatory=spec.mandatory,
                refundable=spec.refundable,
                estimated=spec.estimated,
                valid_from=opened_at,
                created_by_user_id=actor_id,
            )
        )
    db.flush()
    # The summary columns were written by a Core UPDATE and the relationship
    # still holds the old rows; both are reloaded so the response is the truth.
    db.expire(offer, ["current_components"])
    db.refresh(offer)

    if is_edit:
        audit(
            db,
            actor=actor_id,
            action="classified.price_changed",
            entity_type="classified_offer",
            entity_id=offer.id,
        )
    return changed
