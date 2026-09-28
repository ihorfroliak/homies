# Backup and restore (PR-001)

## What exists

* `backend/scripts/backup/backup.sh` — `pg_dump -Fc` → gzip → AES-256-CBC
  (PBKDF2) → SHA-256 checksum; refuses the published development key.
* `backend/scripts/backup/restore.sh`, `dr_drill.sh`, `verify_restore.py` — the
  2026-07 drill (legacy booking/ledger focus).
* `backend/tests/test_dr_restore_pg.py` — CI restore cycle, legacy data.
* **`backend/tests/test_dr_restore_phase1_pg.py` (PR-001)** — the Phase-1A
  drill, run on every CI build with PostgreSQL:
  1. create synthetic data through the real API and import seams — reference
     geography, structured addresses, properties with exact points, spaces,
     published listings with price components, one listing past its
     freshness window, authorities;
  2. `pg_dump --format=custom` (streamed);
  3. create a brand-new database;
  4. `pg_restore --exit-on-error` into it;
  5. validate: same Alembic head (= the code's head); every row of 16 core
     tables identical; generated PostGIS columns (`exact_geog`, `public_geog`)
     identical; the GiST index present; **the same public search answer**
     (stale listing still hidden); and on the copy the invariants still refuse:
     public EXACT precision, unknown listing status, a cycle in the
     administrative hierarchy (trigger), two properties sharing one address.

Run locally (disposable database only):

    TEST_DATABASE_URL=postgresql+psycopg://homies:homies@<host>:<port>/homies_ci \
      python -m pytest tests/test_dr_restore_phase1_pg.py -q

The client (`pg_dump`/`pg_restore`) must be PostgreSQL 16: the test image
`ops/test/Dockerfile.py312` carries it; `PG_BIN` can point at another.

## What this proves

The schema, data, generated columns, indexes, constraints and triggers of the
current migration head survive a logical dump and restore into an empty
database, and the restored copy answers public search identically.

## What this does NOT prove

* that any backup job runs on a schedule, or that backups are stored offsite,
  retained or encrypted with a managed key (none exists);
* point-in-time recovery or an RPO below the backup interval;
* restore time or behaviour at production volume;
* restore of uploaded media files (`MEDIA_ROOT`) — pg_dump does not contain them;
* restore of roles/privileges (`--no-owner --no-privileges`; re-run
  `ops/sql/app_role.sql` after a restore);
* recovery of a real production incident.

Targets (RPO/RTO) are a pending founder decision — PRODUCTION-READINESS.md §4.
