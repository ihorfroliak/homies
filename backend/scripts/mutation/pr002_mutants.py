"""PR-002 mutation / fault harness — release and migration compatibility.

Same rules and runner as task002_mutants.py: green baseline first; killed only
on test failures with no errors; original bytes restored and SHA-256 verified.
Usage from backend/ (PostgreSQL tests create and drop scratch databases):

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/pr002_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

UNIT = "tests/test_schema_compat.py"
MANIFEST = "tests/test_release_manifest.py"
PG = "tests/test_release_pg.py"
TD01 = "tests/test_td01_migrations.py"
RELEASE = "app/core/release.py"
SCHEMA = "app/core/schema.py"
MIGRATE = "app/scripts/migrate.py"
GRANTS = "app/core/sql/app_grants.sql"
APP_ROLE_SQL = "app/core/sql/app_role.sql"
ENVPY = "alembic/env.py"
PRIV = "tests/test_db_privileges_pg.py"

harness.MUTANTS = [
    {
        "id": "P01-startup-always-compatible",
        "invariant": "startup refuses every decision that is not allowed",
        "file": SCHEMA,
        "old": "    if not decision.allowed:\n        raise SchemaIncompatibleError(decision, manifest)\n",
        "new": "",
        "tests": [PG + "::test_startup_decides_from_the_real_database"],
    },
    {
        "id": "P01a-evaluator-always-compatible",
        "invariant": "the compatibility evaluator decides; it never answers 'compatible' blindly",
        "file": RELEASE,
        "old": "    heads = list(db_heads)\n",
        "new": "    return Decision(EXACT, None)\n    heads = list(db_heads)\n",
        "tests": [UNIT],
    },
    {
        "id": "P01b-every-decision-allowed",
        "invariant": "only EXACT / BEHIND_SUPPORTED / AHEAD_COMPATIBLE are allowed",
        "file": RELEASE,
        "old": "        return self.code in ALLOWED\n",
        "new": "        return True\n",
        "tests": [UNIT],
    },
    {
        "id": "P02-lexical-minimum",
        "invariant": "the minimum is an ancestry bound, not a string comparison",
        "file": RELEASE,
        "old": "        if graph.is_ancestor_or_equal(manifest.minimum_schema, db):\n",
        "new": "        if db >= manifest.minimum_schema:\n",
        "tests": [UNIT],
    },
    {
        "id": "P03-app-role-writes-alembic-version",
        "invariant": "the application role cannot write alembic_version / schema_lineage",
        "file": GRANTS,
        "old": ("        EXECUTE 'REVOKE ALL ON ' || target.rel::text || ' FROM homies_app';\n"
                "        EXECUTE 'GRANT SELECT ON ' || target.rel::text || ' TO homies_app';\n"),
        "new": ("        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ' || target.rel::text "
                "|| ' TO homies_app';\n"),
        "tests": ["tests/test_db_privileges_pg.py::test_the_grants_leave_the_schema_record_read_only"],
    },
    {
        "id": "P04-no-migration-lock",
        "invariant": "two runners never migrate at once; a waiting runner is bounded",
        "file": MIGRATE,
        "old": '        got = conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})\n',
        "new": "        got = True\n",
        "tests": [PG + "::test_a_second_runner_waits_at_most_the_lock_timeout",
                  PG + "::test_two_concurrent_runners_migrate_exactly_once"],
    },
    {
        "id": "P04b-lock-and-ownership-check-bypassed",
        "invariant": "without the lock two runners race; the race is detected",
        "file": MIGRATE,
        "old": '        got = conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})\n',
        "new": "        got = True\n",
        "extra": [("                if not holds_lock(conn):", "                if False:")],
        "tests": [PG + "::test_two_concurrent_runners_migrate_exactly_once"],
    },
    {
        "id": "P04c-blocking-lock-without-deadline",
        "invariant": "the wait is bounded by the runner's own budget, not by lock_timeout",
        "file": MIGRATE,
        "old": '        got = conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})\n',
        "new": ('        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": LOCK_KEY})\n'
                "        got = True\n"),
        "tests": [PG + "::test_the_lock_budget_is_enforced_by_the_runner_not_by_lock_timeout"],
    },
    {
        "id": "P04d-alembic-on-another-connection",
        "invariant": "Alembic runs on the connection that holds the lock (A), never on B",
        "file": ENVPY,
        "old": '    given = config.attributes.get("connection")\n',
        "new": "    given = None\n",
        "tests": [PG + "::test_the_migrating_session_holds_the_lock_for_the_whole_migration"],
    },
    {
        "id": "P04e-lock-ownership-not-rechecked",
        "invariant": "a session that does not hold the lock never migrates",
        "file": MIGRATE,
        "old": "                if not holds_lock(conn):",
        "new": "                if False:",
        "tests": [PG + "::test_a_runner_whose_session_lost_the_lock_does_not_migrate"],
    },
    {
        "id": "P05-rollback-defaults-to-safe",
        "invariant": "missing rollback metadata is invalid, never SAFE",
        "file": RELEASE,
        "old": "    if not isinstance(data, dict) or set(data) != _KEYS:\n",
        "new": "    if not isinstance(data, dict) or not set(data) <= _KEYS:\n",
        "extra": [('data["rollback_to_previous"]\n', 'data.get("rollback_to_previous", "SAFE")\n')],
        "tests": [MANIFEST + "::test_missing_rollback_metadata_is_never_safe"],
    },
    {
        "id": "P05b-rollback-allowed-unless-blocked",
        "invariant": "rollback is allowed only for an explicit SAFE",
        "file": RELEASE,
        "old": "        return self.rollback_to_previous == SAFE\n",
        "new": "        return self.rollback_to_previous != BLOCKED\n",
        "tests": [MANIFEST],
    },
    {
        "id": "P06-barrier-ahead-admitted",
        "invariant": "a newer schema is admitted only through EXPAND and SAFE steps",
        "file": RELEASE,
        "old": "        if step.schema_transition != EXPAND or step.rollback_to_previous != SAFE:\n",
        "new": "        if False:\n",
        "tests": [UNIT],
    },
    {
        "id": "P07-lineage-not-recorded",
        "invariant": "every applied migration step is recorded in schema_lineage",
        "file": ENVPY,
        "old": "    conn = ctx.connection\n",
        "new": "    return\n    conn = ctx.connection\n",
        "tests": [PG + "::test_a_fresh_database_records_its_whole_lineage"],
    },
    {
        "id": "P08-production-self-migrates",
        "invariant": "only ENV=local applies migrations at startup",
        "file": SCHEMA,
        "old": "    if settings.env in SELF_MIGRATING_ENVIRONMENTS:\n        from app.scripts import migrate\n",
        "new": "    if True:\n        from app.scripts import migrate\n",
        "tests": [TD01 + "::test_ensure_schema_verify_mode_raises_on_unmigrated_db"],
    },
    {
        "id": "P09-runner-accepts-the-application-role",
        "invariant": "the application role cannot run migrations",
        "file": MIGRATE,
        "old": "    if user == APP_ROLE or not creates:\n",
        "new": "    if False:\n",
        "tests": [PG + "::test_the_runner_refuses_the_application_role"],
    },
    {
        "id": "P10-barrier-without-permission",
        "invariant": "a pending BARRIER needs an explicit maintenance flag",
        "file": MIGRATE,
        "old": "                if barriers and not allow_barrier:\n",
        "new": "                if False:\n",
        "tests": [PG + "::test_the_plan_changes_nothing_and_a_barrier_needs_permission"],
    },
    {
        "id": "P11-missing-lineage-tolerated",
        "invariant": "a schema that includes the lineage migration must carry a matching lineage",
        "file": RELEASE,
        "old": "    if not graph.expects_lineage(revision):\n        return None\n",
        "new": "    if True:\n        return None\n",
        "tests": [UNIT, PG + "::test_a_missing_or_altered_lineage_is_refused_not_fabricated"],
    },
    {
        "id": "P12-build-identity-optional",
        "invariant": "a missing build identity fails closed where identity is required",
        "file": RELEASE,
        "old": "        if required:\n",
        "new": "        if False:\n",
        "tests": [MANIFEST],
    },
    {
        "id": "P12b-startup-ignores-missing-identity",
        "invariant": "production-like startup refuses a build without identity",
        "file": SCHEMA,
        "old": "    if identity.build_sha is None and release.identity_required(settings.env):\n",
        "new": "    if False:\n",
        "tests": [MANIFEST + "::test_production_startup_refuses_a_build_without_identity"],
    },
    {
        "id": "P13-privilege-gaps-not-verified",
        "invariant": "the job fails when the application role lacks privileges on any table",
        "file": MIGRATE,
        "old": "        if wrong:\n",
        "new": "        if False:\n",
        "tests": [PG + "::test_a_table_the_migration_role_cannot_grant_on_fails_the_job"],
    },
    {
        "id": "P14-app-role-may-ddl",
        "invariant": "the application role cannot create or alter schema objects",
        "file": APP_ROLE_SQL,
        "old": "REVOKE CREATE ON SCHEMA public FROM homies_app;\n",
        "new": "GRANT CREATE ON SCHEMA public TO homies_app;\n",
        "tests": [PG + "::test_the_application_role_cannot_change_the_schema_or_its_record"],
    },
]


if __name__ == "__main__":
    harness.main()
