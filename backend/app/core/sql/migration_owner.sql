-- One-time ownership transfer for a database that existed before PR-002.
--
-- Run once by a DBA (superuser), after migration_role.sql and app_role.sql and
-- before the first migration job run by homies_migrator:
--
--     psql -1 -d homies -f backend/app/core/sql/migration_owner.sql
--
-- Why. Before PR-002 the schema was created by whichever role ran
-- `alembic upgrade head` — typically the database's bootstrap or admin role.
-- The migration role can only evolve, and grant on, objects it owns
-- (PostgreSQL ties ALTER/DROP/GRANT to ownership, and ALTER DEFAULT PRIVILEGES
-- only to the role that ran it). Without this transfer the migration job
-- cannot update alembic_version (the migration fails and rolls back, the
-- database is unchanged), and privilege convergence cannot grant the
-- application role on the old tables (the job's post-verify fails, exit 3).
--
-- `REASSIGN OWNED BY <old> TO homies_migrator` is not used: it moves every
-- object of the old role in the database, and fails outright for the
-- bootstrap superuser ("required by the database system"). This moves exactly
-- the application's objects in schema public: tables, partitioned tables,
-- views, materialized views, standalone sequences, types and routines — never
-- an extension's members (PostGIS's functions and spatial_ref_sys stay the
-- DBA's). Sequences owned by a table column move with their table.
-- Idempotent; no BEGIN/COMMIT, no format(), no LIKE.

DO $$
DECLARE
    target record;
BEGIN
    FOR target IN
        SELECT c.oid::regclass AS rel, c.relkind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm')
          AND c.relowner <> 'homies_migrator'::regrole
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                          AND d.objid = c.oid AND d.deptype = 'e')
    LOOP
        EXECUTE 'ALTER '
                || CASE target.relkind WHEN 'v' THEN 'VIEW'
                                       WHEN 'm' THEN 'MATERIALIZED VIEW'
                                       ELSE 'TABLE' END
                || ' ' || target.rel::text || ' OWNER TO homies_migrator';
    END LOOP;

    -- Standalone sequences (a serial/identity sequence already moved with its table).
    FOR target IN
        SELECT c.oid::regclass AS rel
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'S'
          AND c.relowner <> 'homies_migrator'::regrole
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                          AND d.objid = c.oid AND d.deptype IN ('e', 'a', 'i'))
    LOOP
        EXECUTE 'ALTER SEQUENCE ' || target.rel::text || ' OWNER TO homies_migrator';
    END LOOP;

    -- Enum, domain and range types (a table's row type moves with the table).
    FOR target IN
        SELECT t.oid::regtype AS typ, t.typtype
        FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd', 'r')
          AND t.typowner <> 'homies_migrator'::regrole
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_type'::regclass
                          AND d.objid = t.oid AND d.deptype = 'e')
    LOOP
        EXECUTE 'ALTER ' || CASE target.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END
                || ' ' || target.typ::text || ' OWNER TO homies_migrator';
    END LOOP;

    -- Functions and procedures the migrations created (trigger functions).
    FOR target IN
        SELECT p.oid::regprocedure AS fn
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proowner <> 'homies_migrator'::regrole
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass
                          AND d.objid = p.oid AND d.deptype = 'e')
    LOOP
        EXECUTE 'ALTER ROUTINE ' || target.fn::text || ' OWNER TO homies_migrator';
    END LOOP;
END
$$;
