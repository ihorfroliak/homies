"""Schema management (TD-01). Alembic migrations are the single source of truth
for the database schema. The application never creates or mutates schema through
ORM metadata (`create_all`) any more.

- local dev: `ensure_schema()` applies migrations for convenience (`make up`
  just works) through the same locked runner as a deploy
  (app/scripts/migrate.py), then requires the exact head.
- staging / production: migrations are a separate deploy step, run by the
  migration role. The app only *evaluates compatibility* (PR-002): its release
  manifest and migration graph against the database's revision and
  `schema_lineage` (app/core/release.py). Anything but an allowed decision
  refuses to start — never silently creates schema, never "warn and continue".
- test: tests own their engine (conftest); `ensure_schema()` is not called.
"""

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core import release
from app.core.config import settings

log = logging.getLogger("homies.schema")

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Environments where the app may apply migrations itself as a dev convenience.
SELF_MIGRATING_ENVIRONMENTS = frozenset({"local"})


class SchemaNotMigratedError(RuntimeError):
    """The database schema is not one this build may run against. A
    production-like deployment runs the migration job before starting the app."""


class SchemaIncompatibleError(SchemaNotMigratedError):
    """The compatibility decision refused this build for this database (PR-002).
    `decision.code` is machine-readable; the message carries revision ids only."""

    def __init__(self, decision: "release.Decision", manifest: "release.ReleaseManifest"):
        self.decision = decision
        super().__init__(
            f"schema incompatible: {decision.code} — database at {decision.db_revision!r}, "
            f"this build supports {manifest.minimum_schema}..{manifest.maximum_schema} "
            f"(head {manifest.schema_head}). {decision.detail}".strip())


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # configparser treats '%' as interpolation: a percent-encoded password made
    # this raise a ValueError whose text is the whole URL, password included.
    cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    # Called inside the running application: its logging is already configured
    # (app/core/logging_config.py), and alembic.ini's fileConfig would replace
    # the root handlers and disable every existing logger (PR-001R F5).
    cfg.attributes["configure_logger"] = False
    return cfg


def _head_revision() -> str:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:
        # No revisions found at all — the migration directory is missing or
        # empty (e.g. an image built without alembic/). Without this guard both
        # head and current are None, `current != head` is False, and the app
        # would report "schema verified" against a completely empty database.
        raise SchemaNotMigratedError(
            "No Alembic revisions found. The migration directory is missing or "
            "empty, so the schema cannot be verified."
        )
    return head


def build_graph() -> "release.Graph":
    """This build's migration graph, with every step's declarations."""
    _head_revision()  # refuses an image without migrations before anything else
    try:
        return release.graph_from_scripts(ScriptDirectory.from_config(alembic_config()))
    except release.ReleaseManifestError as exc:
        raise SchemaNotMigratedError(f"invalid migration declarations: {exc}") from None


def read_lineage(conn) -> dict[str, "release.Step"] | None:
    """The database's schema_lineage (revision → Step), None before PR-002."""
    if not inspect(conn).has_table("schema_lineage"):
        return None
    rows = conn.execute(text(
        "SELECT revision, down_revision, schema_transition, rollback_to_previous "
        "FROM schema_lineage")).all()
    return {r[0]: release.Step(r[0], r[1], r[2], r[3]) for r in rows}


def _database_state(url: str | None = None) -> tuple[tuple[str, ...], dict | None]:
    """(Alembic heads recorded in the database, its schema_lineage)."""
    engine = create_engine(url or settings.database_url)
    try:
        with engine.connect() as conn:
            heads = tuple(MigrationContext.configure(conn).get_current_heads())
            return heads, read_lineage(conn)
    finally:
        engine.dispose()


def check_compatibility(url: str | None = None) -> tuple["release.Decision",
                                                          "release.ReleaseManifest"]:
    """The compatibility decision for this build against the database. No writes."""
    graph = build_graph()
    try:
        manifest = release.load_manifest(graph)
    except release.ReleaseManifestError as exc:
        raise SchemaNotMigratedError(f"invalid release manifest: {exc}") from None
    heads, lineage = _database_state(url)
    return release.evaluate(manifest, graph, heads, lineage), manifest


def ensure_schema() -> None:
    """Migrate (local) or evaluate compatibility (everything else). Never `create_all`."""
    if settings.env in SELF_MIGRATING_ENVIRONMENTS:
        from app.scripts import migrate

        log.info("applying migrations (env=%s)", settings.env)
        migrate.upgrade(settings.database_url)
    decision, manifest = check_compatibility()
    # A malformed identity is refused everywhere; a missing one is tolerated in
    # development only and refused below, after the decision is logged.
    identity = release.runtime_identity(manifest, required=False)
    log.info(
        "schema_compatibility decision=%s db_revision=%s build_sha=%s release=%s "
        "schema_head=%s minimum_schema=%s maximum_schema=%s steps_ahead=%d "
        "rollback_to_previous=%s",
        decision.code, decision.db_revision, identity.build_sha or "-", manifest.release,
        manifest.schema_head, manifest.minimum_schema, manifest.maximum_schema,
        decision.steps_ahead, manifest.rollback_to_previous)
    if settings.env in SELF_MIGRATING_ENVIRONMENTS and decision.code != release.EXACT:
        raise SchemaIncompatibleError(decision, manifest)
    if not decision.allowed:
        raise SchemaIncompatibleError(decision, manifest)
    if identity.build_sha is None and release.identity_required(settings.env):
        raise release.BuildIdentityError(
            f"env={settings.env} requires the build identity {release.BUILD_SHA_ENV}")


class LedgerPrivilegeError(RuntimeError):
    """The application's database role can rewrite the ledger.

    Append-only is enforced by triggers, but a trigger does not bind the role
    that owns the table — the owner can disable it, edit, and re-enable. So a
    production deployment must connect as a role without UPDATE or DELETE on
    the append-only tables (`app/core/sql/app_role.sql`). This is raised when it
    does not.
    """


def verify_ledger_privileges() -> None:
    """Refuse to serve production traffic with a role that can edit the money.

    Checked rather than documented, for the same reason SEC-02 checks secrets:
    "run this SQL when you provision" is a step that gets skipped, and the
    skipping is invisible until the day someone needs the ledger to be
    evidence. A local or test database is deliberately exempt — there the app
    owns its schema by design.

    Tables are taken from the triggers, so a new append-only table is covered
    the day it exists rather than the day someone remembers this function.
    """
    if settings.env in SELF_MIGRATING_ENVIRONMENTS or settings.env == "test":
        return
    if not settings.database_url.startswith("postgresql"):
        return

    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            writable = list(
                conn.scalars(
                    text(
                        "SELECT tbl FROM (SELECT DISTINCT tgrelid::regclass::text AS tbl "
                        "FROM pg_trigger WHERE NOT tgisinternal "
                        "AND tgname ~ '_append_only$') t "
                        "WHERE has_table_privilege(current_user, tbl, 'UPDATE') "
                        "OR has_table_privilege(current_user, tbl, 'DELETE')"
                    )
                )
            )
    finally:
        engine.dispose()

    if writable:
        raise LedgerPrivilegeError(
            "The application role holds UPDATE/DELETE on append-only tables: "
            f"{', '.join(writable)}. Apply app/core/sql/app_role.sql and connect as "
            "homies_app (release plan B5)."
        )
    log.info("ledger privileges verified: append-only tables are not writable")


class SchemaPrivilegeError(RuntimeError):
    """The application's database role can change the schema or its record
    (PR-002): it could forge the revision and lineage the compatibility
    decision trusts. A production role reads them and nothing more."""


# Release metadata the application role may read but never write.
RELEASE_TABLES = ("alembic_version", "schema_lineage")


def schema_privilege_problems(conn) -> list[str]:
    """What the connected role can do to the schema that it must not."""
    problems = []
    for table in RELEASE_TABLES:
        if not inspect(conn).has_table(table):
            continue
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            if conn.scalar(text("SELECT has_table_privilege(current_user, :t, :p)"),
                           {"t": table, "p": privilege}):
                problems.append(f"{privilege} on {table}")
    if conn.scalar(text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")):
        problems.append("CREATE on schema public")
    owned = conn.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                             "AND tableowner = current_user"))
    if owned:
        problems.append(f"owns {owned} table(s) in public")
    if conn.scalar(text("SELECT to_regclass('public.spatial_ref_sys') IS NOT NULL")) and \
            conn.scalar(text("SELECT has_table_privilege(current_user, 'spatial_ref_sys', "
                             "'INSERT') OR has_table_privilege(current_user, "
                             "'spatial_ref_sys', 'UPDATE') OR has_table_privilege("
                             "current_user, 'spatial_ref_sys', 'DELETE')")):
        problems.append("write on spatial_ref_sys")
    return problems


def verify_schema_privileges() -> None:
    """Refuse a production role that could change the schema or forge its record."""
    if settings.env in SELF_MIGRATING_ENVIRONMENTS or settings.env == "test":
        return
    if not settings.database_url.startswith("postgresql"):
        return
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            problems = schema_privilege_problems(conn)
    finally:
        engine.dispose()
    if problems:
        raise SchemaPrivilegeError(
            "The application role can change the schema or its record: "
            f"{'; '.join(problems)}. Connect as homies_app provisioned by "
            "app/core/sql/app_role.sql; migrations run as the migration role.")
    log.info("schema privileges verified: the application role cannot alter the schema")
