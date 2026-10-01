-- The application role's object privileges (B5; PR-002 privilege convergence).
--
-- Run by the migration runner (app/scripts/migrate.py) as the migration role
-- after EVERY migration, and by provisioning after app_role.sql. The result is
-- the same whichever role created a table: privileges are granted per object
-- the running role owns, not left to ALTER DEFAULT PRIVILEGES (which binds only
-- the role that ran it — PR-002 Phase A F-A4). Idempotent; no BEGIN/COMMIT, no
-- format() and no LIKE (a percent sign is a bind placeholder for the drivers
-- that execute it programmatically).
--
-- Requires the role homies_app (app_role.sql).

-- Ordinary application tables and sequences: full data access.
DO $$
DECLARE
    target record;
BEGIN
    FOR target IN
        SELECT c.oid::regclass AS rel, c.relkind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'S')
          AND pg_has_role(current_user, c.relowner, 'MEMBER')
          AND c.relname NOT IN ('alembic_version', 'schema_lineage', 'spatial_ref_sys')
    LOOP
        IF target.relkind = 'S' THEN
            EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE ' || target.rel::text || ' TO homies_app';
        ELSE
            EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ' || target.rel::text
                    || ' TO homies_app';
            -- TRUNCATE bypasses row triggers entirely: it would empty the ledger
            -- without one of them firing. Never granted; stated anyway.
            EXECUTE 'REVOKE TRUNCATE, REFERENCES, TRIGGER ON ' || target.rel::text
                    || ' FROM homies_app';
        END IF;
    END LOOP;
END
$$;

-- The schema's own record and the PostGIS catalogue: read, never write
-- (PR-002 Phase A F-A3). A role able to write alembic_version or
-- schema_lineage could forge the revision the compatibility decision trusts.
DO $$
DECLARE
    target record;
BEGIN
    FOR target IN
        SELECT c.oid::regclass AS rel
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND c.relname IN ('alembic_version', 'schema_lineage', 'spatial_ref_sys')
          AND pg_has_role(current_user, c.relowner, 'MEMBER')
    LOOP
        EXECUTE 'REVOKE ALL ON ' || target.rel::text || ' FROM homies_app';
        EXECUTE 'GRANT SELECT ON ' || target.rel::text || ' TO homies_app';
    END LOOP;
END
$$;

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
