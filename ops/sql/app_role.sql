-- The role the application connects as (release plan B5).
--
-- Why a separate role at all. The ledger is already append-only, enforced by
-- triggers (D-04). But a trigger protects against a bug, not against the
-- account that owns the table: the owner can run
--
--     ALTER TABLE journal_lines DISABLE TRIGGER journal_lines_append_only;
--
-- and then edit freely. If the application connects as the owner — which it
-- does today — then anything that can run SQL through the application can
-- switch the guarantee off and put it back. The trigger is a seatbelt the
-- driver can unbuckle.
--
-- So the application gets a role that is NOT the owner and has no UPDATE or
-- DELETE on the append-only tables. Tampering with the ledger then requires
-- the migration/owner credentials, which live somewhere the application does
-- not reach. Two different compromises are needed instead of one.
--
-- What this script does NOT do: set a password. Secrets do not belong in a
-- repository. Provision with:
--
--     psql -1 -d homies -f ops/sql/app_role.sql
--     psql -d homies -c "ALTER ROLE homies_app LOGIN PASSWORD '<from the secret store>'"
--
-- `-1` wraps it in one transaction; the file carries no BEGIN/COMMIT of its
-- own so it can also be executed from a caller that already has one open.
-- Re-run it after every migration that adds tables. It is idempotent.

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

GRANT USAGE ON SCHEMA public TO homies_app;

-- Ordinary application tables: full read/write.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO homies_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO homies_app;

-- Tables created by future migrations inherit the same starting point, so a
-- new table is not silently unreadable until someone remembers this file.
-- The revoke below still has to be re-applied for a new append-only table,
-- which is why a test derives the list from the triggers rather than trusting
-- anyone to remember.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO homies_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO homies_app;

-- The append-only tables, identified by the trigger that makes them so rather
-- than by a list kept here. A list would be the thing that is out of date on
-- the day it matters; the trigger is the definition.
DO $$
DECLARE
    target regclass;
BEGIN
    FOR target IN
        SELECT DISTINCT tgrelid::regclass
        FROM pg_trigger
        WHERE NOT tgisinternal AND tgname ~ '_append_only$'
    LOOP
        -- regclass::text is already schema-qualified and quoted as needed.
        EXECUTE 'REVOKE UPDATE, DELETE ON ' || target::text || ' FROM homies_app';
    END LOOP;
END
$$;

-- TRUNCATE bypasses row triggers entirely, which would empty the ledger
-- without a single one of them firing. It is not granted by the statement
-- above, but stating it is cheap and the failure it prevents is total.
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM homies_app;
