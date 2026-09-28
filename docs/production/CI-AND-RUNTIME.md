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
| backend | Python 3.12; pinned install; runtime versions printed; **single Alembic head**; ruff; mypy; `alembic upgrade head` on PostGIS 16-3.4 (digest-pinned service, health-checked) with PostgreSQL 16 / PostGIS asserted; full test suite with coverage (SQLite + PostgreSQL suites incl. OpenAPI drift and both restore drills); coverage ≥ 80 %; pip-audit of declared deps |
| image | production image builds and carries `alembic/` |
| secrets | gitleaks over full history |
| monitoring | promtool config/rules/unit tests; amtool |
| contracts | Spectral (OpenAPI), AsyncAPI validation |

Triggers (PR-001): pushes to `main` and `claude/**`, pull requests, manual.
Newer pushes cancel older runs of the same ref. No secrets are needed.
