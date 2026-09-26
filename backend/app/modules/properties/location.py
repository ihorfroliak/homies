"""Where a listing appears on the map, as opposed to where the flat is
(Domain Schema v1 §9, §42, §80, §106).

The exact position of a flat is private. It is what lets a stranger stand
outside the door before the owner has decided to meet them, and on a free
board it is also what lets someone pose as the owner of a flat they have only
seen from the street. So the map shows a *public* point, chosen by the owner's
precision setting:

* APPROXIMATE  — the centre of the ~550 m grid cell the flat lies in (default);
* DISTRICT     — no point at all; the listing is placed by district name only.

There is no EXACT. Public exact residential coordinates are prohibited, with
no owner opt-in (D-58, TASK-011/TASK-010R): an owner who "chooses" to publish
their door also publishes it for everyone who will ever copy the listing. The
exact point stays private on the Property. Anything that is not DISTRICT gets
the grid point — an unknown or stale precision value fails safe.

APPROXIMATE is a grid, not a random offset. A random offset drawn afresh each
time a listing is published lets anyone republish-and-average their way back to
the flat; a grid cell is the same answer every time, so there is nothing to
average. The price is that neighbouring flats in one cell share a point, which
is the point.
"""

from decimal import ROUND_FLOOR, Decimal

PRECISIONS = ("APPROXIMATE", "DISTRICT")
DEFAULT_PRECISION = "APPROXIMATE"

# Cell size. At Polish latitudes (49–55°N) 0.005° of latitude is ~555 m and
# 0.008° of longitude ~510–580 m, so the cell is close to square everywhere
# the product operates.
GRID_LAT = Decimal("0.005")
GRID_LON = Decimal("0.008")
_SIX = Decimal("0.000001")


def _cell_centre(value: Decimal, step: Decimal, upper: Decimal | None = None) -> Decimal:
    index = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    # A value exactly on the upper edge (90° N, 180° E) would open a cell that
    # lies beyond the globe; it belongs to the last cell inside it.
    if upper is not None and index * step >= upper:
        index -= 1
    return (index * step + step / 2).quantize(_SIX)


def public_point(
    latitude: Decimal | float | None,
    longitude: Decimal | float | None,
    precision: str,
) -> tuple[Decimal | None, Decimal | None]:
    """The point the public may see, or (None, None) when there is none."""
    if latitude is None or longitude is None or precision == "DISTRICT":
        return None, None
    lat = Decimal(str(latitude))
    lon = Decimal(str(longitude))
    return _cell_centre(lat, GRID_LAT, Decimal(90)), _cell_centre(lon, GRID_LON, Decimal(180))


def refresh(offer, prop) -> None:
    """Recompute the offer's public point from its property's position."""
    offer.public_latitude, offer.public_longitude = public_point(
        prop.latitude, prop.longitude, offer.public_location_precision
    )
