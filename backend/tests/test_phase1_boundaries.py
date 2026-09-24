"""Phase-1 modules must not depend on LEGACY_DORMANT modules.

booking, payments, ledger and the short-stay listings module are dormant until
their phases (docs/canonical/IMPLEMENTATION-CONVERGENCE.md). If Phase-1 code
imports them, dormant code quietly becomes load-bearing for the marketplace.
Checked statically on the source, so a lazy import inside a function counts.
"""

import ast
from pathlib import Path

import pytest

MODULES = Path(__file__).resolve().parents[1] / "app" / "modules"

PHASE_ONE = ("identity", "properties", "engagement", "media")
LEGACY = ("booking", "payments", "ledger", "listings")


def _imported_modules(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level >= 2 and node.module:
            # `from ..booking import x` inside app/modules/<m>/: a sibling module.
            names.add(f"app.modules.{node.module}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            # `from app.modules import booking`
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _legacy_hits(names: set[str]) -> list[str]:
    return sorted(
        name
        for name in names
        for legacy in LEGACY
        if name == f"app.modules.{legacy}" or name.startswith(f"app.modules.{legacy}.")
    )


@pytest.mark.parametrize("module", PHASE_ONE)
def test_phase_one_module_does_not_import_legacy(module):
    offenders = {}
    for path in sorted((MODULES / module).rglob("*.py")):
        hits = _legacy_hits(_imported_modules(path.read_text(encoding="utf-8")))
        if hits:
            offenders[str(path.relative_to(MODULES))] = hits
    assert offenders == {}


def test_detector_sees_every_import_form():
    source = (
        "import app.modules.booking.models\n"
        "from app.modules.ledger import service\n"
        "from app.modules import payments\n"
        "def f():\n"
        "    from app.modules.listings.models import Listing\n"
        "from app.modules.bookingx import y\n"
        "from ..booking.service import z\n"
    )
    assert _legacy_hits(_imported_modules(source)) == [
        "app.modules.booking.models",
        "app.modules.booking.service",
        "app.modules.ledger",
        "app.modules.ledger.service",
        "app.modules.listings.models",
        "app.modules.listings.models.Listing",
        "app.modules.payments",
    ]


def test_legacy_modules_carry_the_marker():
    for legacy in LEGACY:
        text = (MODULES / legacy / "__init__.py").read_text(encoding="utf-8")
        assert "LEGACY_DORMANT — DO NOT EXTEND FOR PHASE 1" in text, legacy
