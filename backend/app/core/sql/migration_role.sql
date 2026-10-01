-- The role that evolves the schema (PR-002). Run once per database by a DBA
-- (superuser), before the first migration:
--
--     psql -1 -d homies -f backend/app/core/sql/migration_role.sql
--     psql -d homies -c "ALTER ROLE homies_migrator LOGIN PASSWORD '<from the secret store>'"
--
-- The migration job (python -m app.scripts.migrate) connects as this role via
-- ALEMBIC_DATABASE_URL; application replicas never do. It owns the schema's
-- tables because it creates them, holds CREATE on the schema, and writes
-- alembic_version and schema_lineage. It is not a superuser: extensions the
-- migrations need are created here by the DBA, and spatial_ref_sys stays the
-- DBA's (neither role may write it).
--
-- An existing database whose objects were created by another role needs a
-- one-time ownership transfer by the DBA: migration_owner.sql, run after this
-- file and app_role.sql — kept separate because only an existing database
-- needs it.
-- Idempotent; no BEGIN/COMMIT, no format(), no LIKE.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'homies_migrator') THEN
        CREATE ROLE homies_migrator NOLOGIN;
    END IF;
END
$$;

ALTER ROLE homies_migrator NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

DO $$
BEGIN
    EXECUTE 'GRANT CONNECT ON DATABASE ' || quote_ident(current_database())
            || ' TO homies_migrator';
END
$$;

GRANT USAGE, CREATE ON SCHEMA public TO homies_migrator;

-- Extensions the migrations use. CREATE EXTENSION IF NOT EXISTS in a migration
-- is then a no-op for the non-superuser migration role.
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS postgis;
