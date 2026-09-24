"""Phase-1 code must not depend on LEGACY_DORMANT modules — static half.

booking, payments, ledger and the short-stay listings module are dormant until
their phases (docs/canonical/IMPLEMENTATION-CONVERGENCE.md). If Phase-1 code
imports them, dormant code quietly becomes load-bearing for the marketplace.

This is a static AST scan: it sees absolute, relative, aliased and lazy
imports and literal `importlib.import_module` / `__import__` calls. It cannot
see an import whose module name is computed at runtime, nor a re-export
through a third module. It is therefore NOT the proof for F-01 — the
authoritative check is test_phase1_runtime.py, which inspects the composed
application and a fresh interpreter. Both are kept.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
MODULES = APP / "modules"

LEGACY = ("booking", "payments", "ledger", "listings")

# Files that are part of the Phase-1 process. Legacy-only files inside
# otherwise Phase-1 packages are listed in LEGACY_FILES and excluded.
PHASE_ONE_PACKAGES = ("identity", "properties", "engagement", "media", "admin", "events")
PHASE_ONE_TOP_LEVEL = ("main.py", "composition.py", "core")
LEGACY_FILES = {
    "modules/admin/legacy.py",
    "modules/admin/kpi.py",
    "modules/identity/host_payouts.py",
}

# Known, justified exceptions: (file, imported module) -> reason.
ALLOWED = {
    ("modules/events/service.py", "app.modules.booking.models"):
        "resolves recipients of booking events; only legacy code emits those "
        "events, and the import is lazy inside _resolve_recipient",
    ("modules/events/service.py", "app.modules.listings.models"):
        "same: host lookup for booking events emitted only by legacy code",
}


def _module_name(path: Path) -> str:
    rel = path.relative_to(APP.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_relative(current: str, is_package: bool, level: int, module: str | None) -> str:
    base = current.split(".")
    if not is_package:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join(base + ([module] if module else []))


def imported_modules(source: str, current: str = "app.x", is_package: bool = False) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative(current, is_package, node.level, node.module)
                if node.level
                else node.module or ""
            )
            names.add(base)
            # `from app.modules import booking` / `from .. import booking`
            names.update(f"{base}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            called = (
                func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            )
            if called in ("import_module", "__import__") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.add(first.value)
    return names


def legacy_hits(names: set[str]) -> list[str]:
    return sorted(
        name
        for name in names
        for legacy in LEGACY
        if name == f"app.modules.{legacy}" or name.startswith(f"app.modules.{legacy}.")
    )


def _phase_one_files() -> list[Path]:
    files: list[Path] = []
    for package in PHASE_ONE_PACKAGES:
        files.extend(sorted((MODULES / package).rglob("*.py")))
    for entry in PHASE_ONE_TOP_LEVEL:
        target = APP / entry
        files.extend(sorted(target.rglob("*.py")) if target.is_dir() else [target])
    return [
        f for f in files
        if f.relative_to(APP).as_posix() not in LEGACY_FILES and "__pycache__" not in f.parts
    ]


def test_phase_one_code_does_not_import_legacy():
    offenders = {}
    for path in _phase_one_files():
        rel = path.relative_to(APP).as_posix()
        names = imported_modules(
            path.read_text(encoding="utf-8"),
            current=_module_name(path),
            is_package=path.name == "__init__.py",
        )
        hits = [
            h for h in legacy_hits(names)
            if not any(
                rel == a_rel and (h == a_mod or h.startswith(a_mod + "."))
                for a_rel, a_mod in ALLOWED
            )
        ]
        if hits:
            offenders[rel] = hits
    assert offenders == {}


def test_scanned_set_covers_the_composition_and_admin():
    scanned = {p.relative_to(APP).as_posix() for p in _phase_one_files()}
    assert {"main.py", "composition.py", "modules/admin/router.py"} <= scanned
    assert not scanned & LEGACY_FILES


def test_allowlist_entries_are_still_real():
    """A stale exception would silently widen the boundary later."""
    for rel, module in ALLOWED:
        path = APP / rel
        names = imported_modules(path.read_text(encoding="utf-8"), _module_name(path))
        assert module in names, (rel, module)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import app.modules.booking.models", ["app.modules.booking.models"]),
        ("from app.modules.ledger import service",
         ["app.modules.ledger", "app.modules.ledger.service"]),
        ("from app.modules import payments", ["app.modules.payments"]),
        ("def f():\n    from app.modules.listings.models import Listing",
         ["app.modules.listings.models", "app.modules.listings.models.Listing"]),
        ("from ..booking.service import z", ["app.modules.booking.service",
                                             "app.modules.booking.service.z"]),
        ("from .. import booking", ["app.modules.booking"]),
        ("import importlib\nimportlib.import_module('app.modules.payments.router')",
         ["app.modules.payments.router"]),
        ("__import__('app.modules.ledger')", ["app.modules.ledger"]),
        ("from app.modules.bookingx import y", []),
        ("import app.modules.properties", []),
    ],
)
def test_detector_sees_every_static_import_form(source, expected):
    # As if the source lived in app/modules/media/router.py.
    names = imported_modules(source, current="app.modules.media.router")
    assert legacy_hits(names) == expected


def test_legacy_modules_carry_the_marker():
    for legacy in LEGACY:
        text = (MODULES / legacy / "__init__.py").read_text(encoding="utf-8")
        assert "LEGACY_DORMANT — DO NOT EXTEND FOR PHASE 1" in text, legacy
    for rel in LEGACY_FILES - {"modules/admin/kpi.py"}:
        text = (APP / rel).read_text(encoding="utf-8")
        assert "LEGACY_DORMANT — DO NOT EXTEND FOR PHASE 1" in text, rel
