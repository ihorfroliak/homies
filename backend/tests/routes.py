"""Enumerate the routes an application actually serves.

FastAPI ≥0.13x wraps included routers (`_IncludedRouter`), so `app.routes`
lists wrappers, not the routes behind them — a test that reads
`r.path for r in app.routes` silently sees only the top-level routes. This
walker follows the wrappers. It leans on FastAPI internals, so the runtime
boundary tests never trust it alone: they also send real requests.
"""

from collections.abc import Iterator


def served_routes(app) -> Iterator[tuple[str, frozenset[str], bool]]:
    """Yield (path, methods, include_in_schema) for every leaf route."""

    def walk(items):
        for item in items:
            candidates = getattr(item, "effective_candidates", None)
            if callable(candidates):
                yield from walk(candidates())
                continue
            path = getattr(item, "path", None)
            if path:
                methods = frozenset(getattr(item, "methods", None) or ())
                yield path, methods, bool(getattr(item, "include_in_schema", False))

    yield from walk(app.routes)


def served_paths(app) -> set[str]:
    return {path for path, _, _ in served_routes(app)}
