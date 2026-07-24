"""Export the application's OpenAPI spec to docs/api/openapi.json (TST-01).

The project is code-first in practice: FastAPI + pydantic generate an accurate
spec from the real routes and models. This snapshot is the single source of
truth for the HTTP contract, and a CI drift-guard
(tests/test_tst01_openapi_contract.py) fails the build if it is out of date.

Usage: python -m app.scripts.export_openapi        # writes the file
       python -m app.scripts.export_openapi --check # exit 1 if out of date
"""

import json
import os
import sys
from pathlib import Path

# Deterministic import: never touch a real DB or start workers.
os.environ.setdefault("ENV", "test")

SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"


def generate() -> dict:
    from app.main import app

    return app.openapi()


def serialise(spec: dict) -> str:
    # sort_keys => stable output, so the drift-guard diff is meaningful.
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    text = serialise(generate())
    if "--check" in sys.argv:
        current = SPEC_PATH.read_text(encoding="utf-8") if SPEC_PATH.exists() else ""
        if current != text:
            print(
                "docs/api/openapi.json is out of date. "
                "Run: python -m app.scripts.export_openapi",
                file=sys.stderr,
            )
            return 1
        print("OpenAPI spec is up to date.")
        return 0
    SPEC_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {SPEC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
