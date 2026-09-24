"""Homies API — modular monolith entry point.

Each bounded context lives in app/modules/<context>/ and exposes an APIRouter.
Which of them a running process exposes is decided in app/composition.py and
only there. The deployable application is the Phase-1A composition; the
LEGACY_DORMANT short-stay, booking and payment runtime is not part of it.
See docs/adr/0001-modular-monolith.md and docs/canonical/IMPLEMENTATION-CONVERGENCE.md.
"""

from app.composition import create_phase1_app

app = create_phase1_app()
