# TD-01 — Alembic as the single schema source of truth

Micro-cycle TD-01. Removes schema drift risk by making Alembic migrations the
only way the database schema is created or evolved.

## Audit — schema-creation paths found (before)

Repo-wide grep for `create_all`/`drop_all`/`ALTER TABLE`/etc. found **three**
schema sources that could drift:

1. **App startup** (`main.py` lifespan): `Base.metadata.create_all(engine)` +
   `_apply_postgres_guards()` (raw DDL for the exclusion constraint and
   append-only triggers) — ran for any non-test env, so production would build
   schema implicitly.
2. **Ops script** (`create_admin.py`): `Base.metadata.create_all(engine)`.
3. **Tests** (`conftest.py`): SQLite + `create_all` / `drop_all`.

The exclusion-constraint + trigger DDL was **duplicated** between the Alembic
migration and `_apply_postgres_guards` — the exact drift the objective targets.

## Fresh-DB parity (verified on real Postgres)

`DROP DATABASE; CREATE DATABASE; alembic upgrade head` produces the full
production schema — inspected, not just exit-code:

- 15 tables (+ `alembic_version`)
- exclusion constraint `excl_booking_overlap` (booking concurrency guard)
- 4 append-only triggers (`journal_entries/journal_lines/audit_log/domain_events`)
- `btree_gist` extension
- booking idempotency unique (`guest_id`,`idempotency_key`), payment/webhook
  dedup uniques, foreign keys
- head revision `2d9d18df4688`

So the migration already encoded everything the startup guard did — the guard
was redundant DDL, now removed.

## Changes

- **App startup no longer creates schema.** `create_all` and
  `_apply_postgres_guards` removed. New `app/core/schema.py::ensure_schema()`:
  - `env == local` → applies migrations (`alembic upgrade head`) as a dev
    convenience — same path as production, so no drift;
  - other envs → **verifies** the DB is at head, raising
    `SchemaNotMigratedError` (fails loudly) — never builds schema implicitly;
  - `env == test` → not called (tests own their engine).
- **Ops script** (`create_admin.py`): `create_all` removed; assumes migrations
  applied.
- **Dockerfile** now ships `alembic/` + `alembic.ini` so the image can
  apply/verify migrations.
- **`alembic/env.py`** URL resolution unified: `ALEMBIC_DATABASE_URL` override
  else `settings.database_url` (was a hard-coded scratch DB) — CLI and
  programmatic runs migrate the same database.

## Startup policy (documented, per prompt §5)

The app **does** run migrations at startup, but **only in `local`**. This is a
deliberate dev convenience (`make up` just works). In staging/production the app
assumes a separate deploy step ran `alembic upgrade head` and only verifies —
it never migrates or creates schema on its own. Risk: a local dev restart
applies pending migrations automatically; acceptable for dev, and impossible in
prod (verify-only).

## Tests

Fast unit suite stays on **SQLite** (business logic; Postgres-only DDL can't run
there — D-29). A dedicated **Postgres** suite (`test_td01_migrations.py`, 13
tests) builds schema via Alembic and validates the real structure, gated by
`TEST_DATABASE_URL`:

- fresh DB migrates base→head; single Alembic head; all expected tables;
  exclusion constraint; `btree_gist`; append-only triggers; idempotency/dedup
  uniques; foreign keys; migrated schema ⊇ ORM tables (drift guard);
  deterministic; **`ensure_schema` verify-mode raises on an un-migrated DB**;
  **local-mode applies migrations**.
- Source guards (run everywhere, no DB): `main.py`/`create_admin.py` contain no
  `create_all`; exactly one migration head.

Run locally: `TEST_DATABASE_URL=postgresql+psycopg://homies:homies@localhost:5433/homies_ci make test-pg`

## Live verification

Rebuilt the image (ships alembic), reset the dev DB, restarted: the app booted
via migrations (`Running upgrade -> 2d9d18df4688`, `alembic_version` populated),
`/healthz` ok, and a full money-flow smoke on the migration-built schema passed
(double-book → 409 via the exclusion constraint, payout, reconciliation = 0).

## Developer commands

- Fresh dev DB: `make up` (app migrates on boot in local), or `make db-upgrade`
  against an existing DB.
- Apply migrations explicitly: `make db-upgrade` (`alembic upgrade head`).
- Postgres tests: `make test-pg` with `TEST_DATABASE_URL` set.

## Migration quality

One migration (`2d9d18df4688_initial_schema`) — not yet deployed anywhere, so it
remains the single initial migration (edited in place across earlier cycles is
acceptable since it has never been applied to a persistent shared environment).
Reversible (down-revision drops everything), deterministic, no implicit-state
dependencies. Future schema changes must be **new** migrations.

## Remaining risk

CI does not yet run the Postgres suite (no Postgres service) — closed in the
next phase, **CI-03**. Until then the migration/DB-guard tests skip in CI and
are validated locally.
