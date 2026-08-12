"""HTTP request metrics (OBS-02).

Prometheus had counters for notifications, rate limiting and the expiry sweep,
but nothing for the API itself: latency, status codes and throughput were
invisible, so "the site is slow" had no answer and no alert could exist.

Cardinality is the design constraint here. A Prometheus label set must be
bounded, and the obvious implementation -- labelling by `request.url.path` --
is unbounded: every booking id in `/v1/bookings/<uuid>` mints a new time series
and a crawler hitting random 404s can grow them without limit until the scrape
falls over. These metrics therefore label by the matched **route template**
(`/v1/bookings/{booking_id}`), and collapse everything unmatched into a single
`unmatched` series.
"""

import time
from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "homies_http_requests_total",
    "HTTP requests by route template, method and status class",
    ["method", "route", "status"],
)

DURATION = Histogram(
    "homies_http_request_duration_seconds",
    "HTTP request latency by route template",
    ["method", "route"],
    # Tuned for an API, not a page load: the default buckets top out at 10s and
    # spend most of their resolution above 1s, where nothing here should live.
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# Scraping itself must not appear in the metrics it produces.
_EXCLUDED = ("/metrics",)


@lru_cache(maxsize=1)
def _known_templates(app: FastAPI) -> tuple[tuple[str, ...], ...]:
    """Every declared path template, as segment tuples.

    Taken from the generated OpenAPI document because that is the one place
    that spells out *full* templates (`/v1/bookings/{booking_id}`). The route
    objects do not: `include_router(prefix=...)` wraps children so that
    `scope["route"].path` is the router-relative path (`/bookings/{id}`), which
    would silently merge two different prefixes into one series. FastAPI caches
    the document, and this caches the parse.
    """
    return tuple(tuple(p.split("/")) for p in app.openapi().get("paths", {}))


def _matches(actual: tuple[str, ...], template: tuple[str, ...]) -> bool:
    if len(actual) != len(template):
        return False
    return all(t.startswith("{") or t == a for a, t in zip(actual, template, strict=True))


def route_template(request: Request) -> str:
    """The request's declared path template, or `unmatched`.

    Every return value is checked against the declared set, so cardinality is
    bounded *by construction* rather than by convention — a raw id can never
    reach a label even if routing behaves unexpectedly.

    The lookup has to work in two situations. After normal routing, the path
    parameters are known and the template is recovered by substituting them
    back into the request path. When something short-circuits *before* routing
    — notably the rate limiter, which returns 429 directly — there are no path
    parameters, and the raw path is matched against the declared templates.
    Collapsing that second case to `unmatched` would file every throttled
    request under one label and hide *which* endpoint is being throttled.
    """
    actual = tuple(request.url.path.split("/"))
    templates = _known_templates(request.app)

    params = request.scope.get("path_params") or {}
    if params:
        by_value = {str(v): k for k, v in params.items()}
        candidate = tuple(
            "{" + by_value[seg] + "}" if seg in by_value else seg for seg in actual
        )
        if candidate in templates:
            return "/".join(candidate)

    for template in templates:
        if _matches(actual, template):
            return "/".join(template)
    return "unmatched"


async def http_metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path in _EXCLUDED:
        return await call_next(request)

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # An unhandled exception still becomes a 500 for the client, so it must
        # still be counted -- otherwise the error rate looks perfect precisely
        # when the app is broken.
        REQUESTS.labels(request.method, route_template(request), "5xx").inc()
        DURATION.labels(request.method, route_template(request)).observe(
            time.perf_counter() - started
        )
        raise

    route = route_template(request)
    DURATION.labels(request.method, route).observe(time.perf_counter() - started)
    # Status *class*, not the exact code: 5 series per route instead of dozens,
    # and every alert worth writing is expressed in classes anyway.
    REQUESTS.labels(request.method, route, f"{response.status_code // 100}xx").inc()
    return response
