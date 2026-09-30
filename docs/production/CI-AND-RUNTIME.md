# CI and runtime (PR-001)

## Supported runtime

Python **3.12** (`requires-python >=3.12`, ruff/mypy target 3.12, production
image `python:3.12-slim`). Developers may run newer Pythons locally; the
authoritative gates run on 3.12.

## Dependency set

`backend/constraints.txt` is the exact package set verified on Python 3.12
(full SQLite and PostgreSQL/PostGIS suites green). CI, the test image and the
production image install with `pip install -c constraints.txt …`, so an
upstream release cannot change a build without a commit. Refresh deliberately:

    docker build -f ops/test/Dockerfile.py312 -t homies-test-py312 backend   # without -c, to resolve anew
    docker run --rm homies-test-py312 pip freeze --exclude-editable > constraints.txt   # then add the header back
    # run every gate below on the new set before committing it

## Reproducible local run (Python 3.12 + PostgreSQL 16 / PostGIS 3.4)

    docker build -f ops/test/Dockerfile.py312 -t homies-test-py312 backend
    docker run -d --name homies-test-db -e POSTGRES_USER=homies -e POSTGRES_PASSWORD=homies \
      -e POSTGRES_DB=homies_ci postgis/postgis:16-3.4
    docker run --rm --network container:homies-test-db -v "$PWD:/repo" -w /repo/backend \
      -e PYTHONPATH=/repo/backend \
      -e TEST_DATABASE_URL=postgresql+psycopg://homies:homies@127.0.0.1:5432/homies_ci \
      homies-test-py312 sh -c "ruff check app tests alembic scripts --no-cache && \
        python -m mypy && python -m app.scripts.export_openapi --check && \
        python -m pytest -q -p no:cacheprovider"

Mount the whole repository: the OpenAPI drift test and the design-system
tests read `docs/` and `frontend/` outside `backend/`. PostgreSQL tests
recreate the schema — never point `TEST_DATABASE_URL` at a database you keep.

## CI gates (`.github/workflows/ci.yml`)

| Job | Gates |
|---|---|
| backend | Python 3.12 (asserted); pinned install **proven equal to `constraints.txt`** (PR-001R F2); runtime versions printed and `pg_dump`/`pg_restore` required; **single Alembic head**; ruff; mypy; `alembic upgrade head` on PostGIS 16-3.4 (digest-pinned service, health-checked) with PostgreSQL 16 / PostGIS asserted; full test suite with coverage (SQLite + PostgreSQL suites incl. OpenAPI drift and both restore drills, **mandatory** via `HOMIES_REQUIRE_RESTORE_DRILL=1`, skips listed with `-rs`); coverage ≥ 80 %; `pip-audit -r constraints.txt --no-deps --disable-pip` (the shipped pins, no resolution) and a canary that must be flagged |
| image | production image builds, carries `alembic/`, runs Python 3.12 and defaults to `ENV=production` (PR-001R F3/F8) |
| secrets | gitleaks over full history |
| monitoring | promtool config/rules/unit tests; amtool |
| contracts | Spectral (OpenAPI), AsyncAPI validation — pinned toolchain in `ops/contracts` (Node 24, `npm ci` from the committed lockfile; locally: `cd ops/contracts && npm ci && npm run lint:openapi && npm run validate:asyncapi`) |

Triggers (PR-001): pushes to `main` and `claude/**`, pull requests, manual.
On a task branch a newer push cancels the older run; on `main` every commit
keeps its own run and record (PR-001R F10). No secrets are needed.

## Runtime drift guard (PR-001R F8)

The image job asserts Python 3.12; Dependabot ignores `python` minor/major
bumps for the backend image (a move to 3.13/3.14 is a deliberate cycle with its
own evidence). The already-open Dependabot branch proposing `python:3.14-slim`
should be closed by the founder. `requires-python` stays `>=3.12`.

## Dependency audit (PR-001R F2)

What is tested, audited and shipped is one set: `constraints.txt`. CI proves
the installed environment equals it; the production image installs from it
(all 37 runtime packages verified at their pins); `pip-audit` reads it with
`--no-deps --disable-pip`, so it inspects each pin as written. The canary
`ops/ci/pip-audit-canary.pins` (an old `urllib3`, never installed) must be
flagged — if the audit ever resolved to newer releases instead, CI goes red.
Since PR-001R2 (PR-001RA RA-2) "flagged" means structured proof:
`scripts/ci/audit_canary.py` passes only when pip-audit's JSON report lists
`urllib3==1.26.4` with a PYSEC/GHSA/CVE advisory id. A failed advisory lookup
(no network, PyPI/OSV down) is a red step, not a detection — the first version
grepped for "urllib3" and passed on the lookup's own traceback.
