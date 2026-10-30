# Developer onboarding — the first 45 minutes

For a new human developer or DevOps engineer. It links to the source of each
rule instead of restating it.

## 1. Read first (15 min)

1. [CLAUDE.md](../../CLAUDE.md) / [AGENTS.md](../../AGENTS.md) — roles, rules, hard limits.
2. [00-AUTHORITY](../canonical/00-AUTHORITY.md) — which document wins.
3. [02-BUSINESS-LOGIC](../canonical/02-BUSINESS-LOGIC.md), phase table — what Phase 1A is (long-term rental; no money collected).
4. [PROJECT-STATUS](../PROJECT-STATUS.md) — where the project is now (the only volatile-status owner).
5. [SYSTEM-PASSPORT](../production/SYSTEM-PASSPORT.md) — what the code actually contains.

Older strategy, charter and release-plan documents are historical (banner-marked);
`booking`, `payments`, `ledger`, the short-stay `listings` module are
`LEGACY_DORMANT` — do not extend them.

## 2. Run it locally (20 min)

Prerequisites: Docker, Python 3.12, Node 24 (`frontend/web/.nvmrc`).

```bash
make up                      # ops/docker-compose.yml: API (ENV=local), PostGIS on host port 5433, Prometheus
python -m venv backend/.venv && backend/.venv/bin/pip install -c backend/constraints.txt -e "backend[dev]"
make test                    # backend tests (SQLite); PostgreSQL tests need TEST_DATABASE_URL
make lint
cd frontend/web && npm ci && npm run dev
```

* `ENV=local` makes the API migrate its own database at startup — a
  developer convenience that must never reach a shared environment.
* PostgreSQL tests recreate the schema at `TEST_DATABASE_URL`: point it only at
  a disposable database, and never run two PostgreSQL test sessions against
  the same database.
* The API contract is `docs/api/openapi.json`, generated from FastAPI and
  drift-tested; the web client is generated from it (`npm run gen:api`).

## 3. How work moves (10 min)

* A Task Contract in `docs/tasks/` first; branch `claude/<TASK>-<name>` (or
  the assigned agent's prefix); one writer per bounded context; separate
  worktree.
* Six CI checks on the exact commit ([ci.yml](../../.github/workflows/ci.yml)).
* High-risk changes (05 §9) need the independent Codex audit; the founder
  merges. Agent roles: [AGENT-OPERATING-MODEL](AGENT-OPERATING-MODEL.md).
* Schema changes follow [RELEASE-AND-MIGRATION](../production/RELEASE-AND-MIGRATION.md):
  every migration declares EXPAND/BARRIER and SAFE/BLOCKED.

## 4. Deployment, briefly

Nothing is deployed. The private alpha and staging designs are
[STAGING-ARCHITECTURE](../production/STAGING-ARCHITECTURE.md); configuration
names are in [ENVIRONMENT-MATRIX](../production/ENVIRONMENT-MATRIX.md); the
procedure is [STAGING-RUNBOOK](../production/STAGING-RUNBOOK.md). Creating any
environment needs a founder decision for that action.
