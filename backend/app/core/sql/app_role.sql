-- The role the application connects as (release plan B5; PR-002).
--
-- Why a separate role at all. The ledger is already append-only, enforced by
-- triggers (D-04). But a trigger protects against a bug, not against the
-- account that owns the table: the owner can run
--
--     ALTER TABLE journal_lines DISABLE TRIGGER journal_lines_append_only;
--
-- and then edit freely. If the application connects as the owner, anything
-- that can run SQL through the application can switch the guarantee off and
-- put it back. The trigger is a seatbelt the driver can unbuckle.
--
-- So the application gets a role that is NOT the owner, cannot create or alter
-- schema, cannot write the schema's own record (alembic_version,
-- schema_lineage — the revision the compatibility decision trusts, PR-002) and
-- has no UPDATE or DELETE on the append-only tables. Tampering then requires
-- the migration role's credentials, which the application never holds.
--
-- Two files, two owners of the work:
--   * this file   — the role itself; run once per database by a DBA
--                   (superuser or CREATEROLE + database owner);
--   * app_grants.sql — the role's object privileges; run by the migration
--                   runner as the migration role after EVERY migration, so
--                   privileges converge whichever role created a table.
--
-- What this script does NOT do: set a password. Secrets do not belong in a
-- repository. Provision with:
--
--     psql -1 -d homies -f backend/app/core/sql/app_role.sql
--     psql -1 -d homies -f backend/app/core/sql/app_grants.sql
--     psql -d homies -c "ALTER ROLE homies_app LOGIN PASSWORD '<from the secret store>'"
--
-- `-1` wraps it in one transaction; the file carries no BEGIN/COMMIT of its
-- own so it can also be executed from a caller that already has one open.
-- It is idempotent.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'homies_app') THEN
        -- NOLOGIN until a password is set, so a window where the role exists
        -- and accepts connections without one cannot open.
        CREATE ROLE homies_app NOLOGIN;
    END IF;
END
$$;

-- Asserted every run, not only at creation. Idempotency by "skip if it exists"
-- means a role that already exists with the wrong attributes stays wrong for
-- ever — and this file would look like it had handled it. A superuser role
-- holds every privilege regardless of what is revoked below, which would make
-- the rest of this script decoration.
ALTER ROLE homies_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;

-- GRANT ... ON DATABASE takes a name, not an expression, so the current
-- database's name is concatenated in. No format() and no LIKE anywhere in this
-- file: a percent sign here is read as a bind placeholder by the drivers that
-- execute it programmatically, and the script has to run from psql AND from
-- the provisioning test unchanged.
DO $$
BEGIN
    EXECUTE 'GRANT CONNECT ON DATABASE ' || quote_ident(current_database())
            || ' TO homies_app';
END
$$;

-- Reads and writes data; never creates schema objects (PostgreSQL 15+ already
-- withholds CREATE on public from PUBLIC; this states it for the role itself).
GRANT USAGE ON SCHEMA public TO homies_app;
REVOKE CREATE ON SCHEMA public FROM homies_app;
