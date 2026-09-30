"""The migration job (PR-002).

    python -m app.scripts.migrate [--plan] [--allow-barrier]

Run once per deploy, from the release's own image, as the MIGRATION role
(ALEMBIC_DATABASE_URL); application replicas never migrate. It:

1. refuses a connection that is not a migration role (the application role
   homies_app, or any role without CREATE on the schema);
2. takes the migration advisory lock — a session-level lock held by the one
   connection that then runs every Alembic statement, until the job ends. It
   is polled with `pg_try_advisory_lock` against a monotonic 10 s deadline
   (never a blocking `pg_advisory_lock`, whose wait is not left to
   `lock_timeout` to bound): a second runner fails cleanly after 10 s
   (MIGRATION_LOCK_TIMEOUT); one that gets the lock after the first finished
   finds nothing to do. Before Alembic runs, the runner re-checks in
   `pg_locks` that its own backend holds the lock (MIGRATION_LOCK_LOST);
3. plans: the pending steps with their declarations; a pending BARRIER in a
   production-like environment needs --allow-barrier (a maintenance deploy);
   a database newer than this build is left alone when the compatibility
   decision admits it, refused otherwise; `--plan` stops here;
4. upgrades to this build's head only — no revision argument, never a
   downgrade — with DDL under the same 10 s lock_timeout, in one transaction;
5. converges the application role's privileges (app/core/sql/app_grants.sql),
   whichever role created the new tables;
6. verifies: the database is at head, schema_lineage matches every step's
   declarations, the application role cannot write the schema's record or
   the append-only tables, and it holds its data privileges on every
   application table and sequence — a table the migration role could not
   grant on (owned by another role; see app/core/sql/migration_owner.sql)
   fails the job instead of failing the application later.

The 10 s lock budget and lock_timeout are migration policy only. It is not the application's
query timeout, the readiness deadline or PR-003's client deadlines.

Exit codes: 0 migrated or nothing to do · 1 refused (role, lock, barrier,
incompatible database) · 2 the migration failed (rolled back) · 3 post-verify
failed. Logs carry revision ids and codes only, never a URL or credentials.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core import release
from app.core.config import settings
from app.core.schema import SchemaNotMigratedError

log = logging.getLogger("homies.migrate")

# One fixed key for "the schema is being migrated": ASCII "homiesMG".
LOCK_KEY = 0x686F6D6965734D47
# The lock budget: how long a runner waits for another one, measured by this
# process's monotonic clock. lock_timeout bounds each DDL statement's wait for
# a table lock during the migration itself.
LOCK_WAIT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.2
LOCK_TIMEOUT = "10s"
GRANTS_SQL = Path(__file__).resolve().parents[1] / "core" / "sql" / "app_grants.sql"
APP_ROLE = "homies_app"
# Environments where the runner may use the application's DATABASE_URL and
# apply a BARRIER without the explicit flag.
DEVELOPMENT_ENVIRONMENTS = frozenset({"local", "test", "ci"})

EXIT_OK, EXIT_REFUSED, EXIT_FAILED, EXIT_VERIFY = 0, 1, 2, 3


class MigrationRefused(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class MigrationVerifyError(RuntimeError):
    pass


def _url() -> str:
    url = os.environ.get("ALEMBIC_DATABASE_URL", "").strip()
    if url:
        return url
    if settings.env in DEVELOPMENT_ENVIRONMENTS:
        return settings.database_url
    raise MigrationRefused("MIGRATION_URL_REQUIRED",
                           "set ALEMBIC_DATABASE_URL to the migration role's connection")


def _check_role(conn) -> None:
    user = conn.scalar(text("SELECT current_user"))
    creates = conn.scalar(text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')"))
    if user == APP_ROLE or not creates:
        raise MigrationRefused("MIGRATION_ROLE_REQUIRED",
                               "the connected role cannot evolve the schema")


def _acquire_lock(conn) -> None:
    """Take the session-level migration lock on `conn`, waiting at most
    LOCK_WAIT_SECONDS. Never a blocking pg_advisory_lock: the wait is bounded
    here, by this process, whatever the server's timeouts are."""
    conn.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
    conn.commit()
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        got = conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})
        conn.commit()  # a session-level advisory lock outlives the transaction
        if got:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MigrationRefused("MIGRATION_LOCK_TIMEOUT",
                                   f"another migration holds the lock ({LOCK_WAIT_SECONDS:g} s)")
        time.sleep(min(LOCK_POLL_SECONDS, remaining))
    log.info("migration lock acquired key=%d wait_budget=%gs lock_timeout=%s", LOCK_KEY,
             LOCK_WAIT_SECONDS, LOCK_TIMEOUT)


def holds_lock(conn) -> bool:
    """Does the backend behind `conn` hold the migration lock right now?"""
    return bool(conn.scalar(text(
        "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND granted "
        "AND pid = pg_backend_pid() AND objsubid = 1 "
        "AND ((classid::bigint << 32) | objid::bigint) = :k)"), {"k": LOCK_KEY}))


def _app_role_exists(conn) -> bool:
    return bool(conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}))


def converge_grants(conn) -> bool:
    """Apply app_grants.sql when the application role exists. Returns whether it ran."""
    if not _app_role_exists(conn):
        log.info("application role %s not provisioned here: no grants to converge", APP_ROLE)
        return False
    conn.exec_driver_sql(GRANTS_SQL.read_text(encoding="utf-8"))
    conn.commit()
    return True


def _verify(conn, graph: release.Graph, grants_applied: bool) -> None:
    from app.core.schema import read_lineage

    heads = tuple(MigrationContext.configure(conn).get_current_heads())
    if heads != (graph.head,):
        raise MigrationVerifyError(f"database at {heads}, expected ({graph.head},)")
    lineage = read_lineage(conn) or {}
    for revision in graph.ancestors(graph.head):
        expected, found = graph.steps[revision], lineage.get(revision)
        if found != expected:
            raise MigrationVerifyError(f"schema_lineage disagrees with migration {revision}")
    if grants_applied:
        writable = conn.scalars(text(
            "SELECT t FROM unnest(ARRAY['alembic_version', 'schema_lineage']) t "
            "WHERE has_table_privilege(:r, t, 'INSERT') OR has_table_privilege(:r, t, 'UPDATE') "
            "OR has_table_privilege(:r, t, 'DELETE') OR has_table_privilege(:r, t, 'TRUNCATE')"),
            {"r": APP_ROLE}).all()
        if writable:
            raise MigrationVerifyError(f"{APP_ROLE} can write {', '.join(writable)}")
        wrong = conn.execute(text(_APP_PRIVILEGE_GAPS), {"r": APP_ROLE}).all()
        if wrong:
            raise MigrationVerifyError(
                f"{APP_ROLE} privileges did not converge on: "
                + ", ".join(f"{name} (owner {owner})" for name, owner in wrong))


# Every application table and sequence in public — not the schema's record, not
# an extension's objects (spatial_ref_sys) — where the application role's
# privileges are not exactly the intended ones: SELECT/INSERT/UPDATE/DELETE and
# no TRUNCATE on tables (no UPDATE/DELETE on the append-only ones), USAGE on
# sequences.
_APP_PRIVILEGE_GAPS = """
SELECT c.relname, pg_get_userbyid(c.relowner)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN LATERAL (SELECT EXISTS (
    SELECT 1 FROM pg_trigger t WHERE t.tgrelid = c.oid AND NOT t.tgisinternal
      AND t.tgname ~ '_append_only$')) a(append_only)
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'S')
  AND c.relname NOT IN ('alembic_version', 'schema_lineage', 'spatial_ref_sys')
  AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                  AND d.objid = c.oid AND d.deptype = 'e')
  AND CASE WHEN c.relkind = 'S' THEN NOT has_sequence_privilege(:r, c.oid, 'USAGE')
      ELSE NOT (has_table_privilege(:r, c.oid, 'SELECT')
                AND has_table_privilege(:r, c.oid, 'INSERT')
                AND NOT has_table_privilege(:r, c.oid, 'TRUNCATE')
                AND CASE WHEN a.append_only
                         THEN NOT has_table_privilege(:r, c.oid, 'UPDATE')
                              AND NOT has_table_privilege(:r, c.oid, 'DELETE')
                         ELSE has_table_privilege(:r, c.oid, 'UPDATE')
                              AND has_table_privilege(:r, c.oid, 'DELETE') END)
  END
ORDER BY c.relname
"""


def upgrade(url: str | None = None, *, allow_barrier: bool | None = None,
            plan_only: bool = False) -> dict:
    """Migrate the database at `url` to this build's head. Returns the plan/result."""
    from app.core.schema import alembic_config, build_graph, read_lineage

    url = url or _url()
    if allow_barrier is None:
        allow_barrier = settings.env in DEVELOPMENT_ENVIRONMENTS
    graph = build_graph()
    manifest = release.load_manifest(graph)
    build_sha = release.build_identity(required=False)  # malformed: refused
    log.info("migration job release=%s schema_head=%s build_sha=%s", manifest.release,
             graph.head, build_sha or "-")
    if not url.startswith("postgresql"):  # SQLite development convenience: no roles, no locks
        cfg = alembic_config()
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(cfg, "head")
        return {"result": "migrated", "to": graph.head}

    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            _check_role(conn)
            _acquire_lock(conn)
            try:
                heads = tuple(MigrationContext.configure(conn).get_current_heads())
                decision = release.evaluate(manifest, graph, heads, read_lineage(conn))
                conn.commit()
                before = heads[0] if len(heads) == 1 else None
                if decision.code in (release.EXACT, release.AHEAD_COMPATIBLE):
                    log.info("migration not needed decision=%s db_revision=%s head=%s",
                             decision.code, decision.db_revision, graph.head)
                    applied = False
                    if decision.code == release.EXACT and not plan_only:
                        # Privileges converge on every run, so drift heals
                        # without a schema change.
                        applied = converge_grants(conn)
                        _verify(conn, graph, applied)
                    return {"result": "nothing_to_do", "decision": decision.code,
                            "db_revision": before, "head": graph.head,
                            "grants_converged": applied}
                if decision.code not in (release.UNMIGRATED, release.BEHIND_SUPPORTED,
                                         release.TOO_OLD):
                    raise MigrationRefused(decision.code, decision.detail)
                pending = (graph.between(before, graph.head) if before
                           else [graph.steps[r] for r in graph.ancestors(graph.head)])
                plan = [{"revision": s.revision, "schema_transition": s.schema_transition,
                         "rollback_to_previous": s.rollback_to_previous}
                        for s in reversed(pending)]
                barriers = [s.revision for s in pending if s.schema_transition == release.BARRIER]
                log.info("migration plan from=%s to=%s steps=%d barriers=%s",
                         before, graph.head, len(plan), ",".join(barriers) or "-")
                if plan_only:
                    return {"result": "plan", "from": before, "to": graph.head, "steps": plan}
                if barriers and not allow_barrier:
                    raise MigrationRefused("BARRIER_NOT_ALLOWED",
                                           f"pending BARRIER {', '.join(barriers)}; this is a "
                                           "maintenance deploy — rerun with --allow-barrier")
                if not holds_lock(conn):  # the connection Alembic is about to use
                    raise MigrationRefused("MIGRATION_LOCK_LOST",
                                           "this session does not hold the migration lock")
                cfg = alembic_config()
                cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
                cfg.attributes["connection"] = conn
                try:
                    command.upgrade(cfg, "head")
                    if conn.in_transaction():
                        conn.commit()
                except Exception:
                    if conn.in_transaction():
                        conn.rollback()
                    raise
                log.info("migration completed from=%s to=%s", before, graph.head)
                applied = converge_grants(conn)
                _verify(conn, graph, applied)
                return {"result": "migrated", "from": before, "to": graph.head, "steps": plan,
                        "grants_converged": applied}
            finally:
                if conn.in_transaction():
                    conn.rollback()
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
                conn.commit()
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="migrate")
    parser.add_argument("--plan", action="store_true", help="print the plan and change nothing")
    parser.add_argument("--allow-barrier", action="store_true",
                        help="apply a pending BARRIER (maintenance deploy)")
    args = parser.parse_args(argv)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        result = upgrade(allow_barrier=True if args.allow_barrier else None,
                         plan_only=args.plan)
    except MigrationRefused as exc:
        log.error("migration refused code=%s", exc.code)
        print(json.dumps({"result": "refused", "code": exc.code}))
        return EXIT_REFUSED
    except (release.ReleaseManifestError, SchemaNotMigratedError) as exc:
        log.error("migration refused: %s", exc)  # revision ids and rule names only
        print(json.dumps({"result": "refused", "code": "INVALID_RELEASE"}))
        return EXIT_REFUSED
    except MigrationVerifyError as exc:
        log.error("migration post-verify failed: %s", exc)
        print(json.dumps({"result": "verify_failed"}))
        return EXIT_VERIFY
    except Exception as exc:  # the transaction rolled back: the database is unchanged
        log.error("migration failed error=%s", type(exc).__name__)
        print(json.dumps({"result": "failed", "error": type(exc).__name__}))
        return EXIT_FAILED
    print(json.dumps(result))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
