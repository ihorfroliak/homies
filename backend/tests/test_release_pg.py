"""Release and migration compatibility on real PostgreSQL/PostGIS (PR-002).

Each test gets its own scratch database. Covered: the lineage recorded by a
fresh migration and by the bootstrap from IBB-001, startup decisions against
real revisions (including a lineage that went missing), the migration lock
(ownership by the migrating session, bounded wait, hand-over), two concurrent
runners, and the separation of the migration role from the application role
with real, non-superuser roles — on a fresh database and on an existing
IBB-001 database, for tables that exist and tables created later.
"""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.core import release, schema
from app.core.config import settings
from app.scripts import migrate
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login
from tests.test_geography_pg import _migrate, scratch_url  # noqa: F401 — fixture

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

IBB001_HEAD = "f3b5d7e9a1c2"
MIGRATOR_PASSWORD = "migrator-test-only-not-a-secret"
BUILD_SHA = "5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98"
APP_PASSWORD = "role-test-only-not-a-secret"
SQL = migrate.GRANTS_SQL.parent


def _graph():
    return schema.build_graph()


def _lineage(url):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return schema.read_lineage(conn)
    finally:
        engine.dispose()


def _scalar(url, sql, **params):
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()
    finally:
        engine.dispose()


def _exec(url, statement):
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text(statement))
    finally:
        engine.dispose()


def _as(url, user, password):
    scheme, _, rest = url.partition("://")
    return f"{scheme}://{user}:{password}@{rest.partition('@')[2]}"


# --- lineage -----------------------------------------------------------------------------------


def test_a_fresh_database_records_its_whole_lineage(scratch_url):  # noqa: F811
    result = migrate.upgrade(scratch_url)
    graph = _graph()
    assert result["result"] == "migrated" and result["from"] is None
    lineage = _lineage(scratch_url)
    assert lineage == {r: graph.steps[r] for r in graph.ancestors(graph.head)}
    recorded = dict(_scalar(scratch_url, "SELECT json_object_agg(revision, recorded_by) "
                                         "FROM schema_lineage"))
    assert recorded.pop(graph.head) == "MIGRATION"
    assert set(recorded.values()) == {"BACKFILL"} and len(recorded) == len(graph.steps) - 1
    # a second run changes nothing
    assert migrate.upgrade(scratch_url)["result"] == "nothing_to_do"


def test_the_plan_changes_nothing_and_a_barrier_needs_permission(scratch_url):  # noqa: F811
    plan = migrate.upgrade(scratch_url, plan_only=True)
    assert plan["result"] == "plan" and plan["steps"][0]["revision"] == "2d9d18df4688"
    assert _scalar(scratch_url, "SELECT to_regclass('alembic_version') IS NULL")
    with pytest.raises(migrate.MigrationRefused) as caught:
        migrate.upgrade(scratch_url, allow_barrier=False)
    assert caught.value.code == "BARRIER_NOT_ALLOWED"
    assert _scalar(scratch_url, "SELECT to_regclass('alembic_version') IS NULL")


def test_bootstrap_from_ibb001_and_back(scratch_url, monkeypatch):  # noqa: F811
    """An IBB-001 database has no lineage: this build still runs on it (its
    minimum schema), the migration job adds the lineage, and a dev downgrade
    removes it again."""
    _migrate(scratch_url, IBB001_HEAD)
    monkeypatch.setattr(settings, "database_url", scratch_url)
    decision, _ = schema.check_compatibility()
    assert decision.code == release.BEHIND_SUPPORTED
    result = migrate.upgrade(scratch_url)
    assert (result["from"], result["to"]) == (IBB001_HEAD, _graph().head)
    assert [s["revision"] for s in result["steps"]] == [_graph().head]
    assert len(_lineage(scratch_url)) == len(_graph().steps)
    assert schema.check_compatibility()[0].code == release.EXACT
    _migrate(scratch_url, IBB001_HEAD, down=True)
    assert _lineage(scratch_url) is None
    assert schema.check_compatibility()[0].code == release.BEHIND_SUPPORTED


# --- startup decisions against real revisions --------------------------------------------------


def test_startup_decides_from_the_real_database(scratch_url, monkeypatch):  # noqa: F811
    migrate.upgrade(scratch_url)
    head = _graph().head
    monkeypatch.setattr(settings, "database_url", scratch_url)
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setenv(release.BUILD_SHA_ENV, BUILD_SHA)
    schema.ensure_schema()  # EXACT

    def at(revision, row=None):
        engine = create_engine(scratch_url)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM schema_lineage WHERE revision = 'fedcba987654'"))
            conn.execute(text("UPDATE alembic_version SET version_num = :r"), {"r": revision})
            if row:
                conn.execute(text("INSERT INTO schema_lineage (revision, down_revision, "
                                  "schema_transition, rollback_to_previous, recorded_by) "
                                  "VALUES ('fedcba987654', :h, :t, :rb, 'MIGRATION')"),
                             {"h": head, "t": row[0], "rb": row[1]})
        engine.dispose()

    at("fedcba987654", ("EXPAND", "SAFE"))
    schema.ensure_schema()  # a newer, expanded schema: this build keeps running
    for row, code in (((("BARRIER", "BLOCKED")), release.TOO_NEW),
                      ((("EXPAND", "BLOCKED")), release.TOO_NEW),
                      (None, release.UNKNOWN_SCHEMA)):
        at("fedcba987654", row)
        with pytest.raises(schema.SchemaIncompatibleError) as caught:
            schema.ensure_schema()
        assert caught.value.decision.code == code
        assert "homies:homies" not in str(caught.value) and "postgresql" not in str(caught.value)
    at("d0f2b4c6e8a1")
    with pytest.raises(schema.SchemaIncompatibleError) as caught:
        schema.ensure_schema()
    assert caught.value.decision.code == release.TOO_OLD
    at(head)
    schema.ensure_schema()


def test_a_missing_or_altered_lineage_is_refused_not_fabricated(scratch_url, monkeypatch):  # noqa: F811
    """After PR-002 is applied the lineage is part of the schema. If it goes
    missing, neither the application nor the migration job invents one."""
    migrate.upgrade(scratch_url)
    monkeypatch.setattr(settings, "database_url", scratch_url)
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setenv(release.BUILD_SHA_ENV, BUILD_SHA)
    _scalar(scratch_url, "UPDATE schema_lineage SET rollback_to_previous = 'SAFE' "
                         "WHERE revision = 'f3b5d7e9a1c2' RETURNING 1")
    with pytest.raises(schema.SchemaIncompatibleError) as caught:
        schema.ensure_schema()
    assert caught.value.decision.code == release.LINEAGE_MISMATCH
    _exec(scratch_url, "DROP TABLE schema_lineage")
    with pytest.raises(schema.SchemaIncompatibleError) as caught:
        schema.ensure_schema()
    assert caught.value.decision.code == release.LINEAGE_MISSING
    with pytest.raises(migrate.MigrationRefused) as refused:
        migrate.upgrade(scratch_url)
    assert refused.value.code == release.LINEAGE_MISSING
    assert _lineage(scratch_url) is None  # nothing fabricated


# --- the migration lock ------------------------------------------------------------------------


def _hold_lock(url):
    engine = create_engine(url)
    conn = engine.connect()
    conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": migrate.LOCK_KEY})
    conn.commit()
    return engine, conn


def test_a_second_runner_waits_at_most_the_lock_timeout(scratch_url):  # noqa: F811
    migrate.upgrade(scratch_url)
    engine, holder = _hold_lock(scratch_url)
    try:
        started = time.monotonic()
        with pytest.raises(migrate.MigrationRefused) as caught:
            migrate.upgrade(scratch_url)
        waited = time.monotonic() - started
    finally:
        holder.close()
        engine.dispose()
    assert caught.value.code == "MIGRATION_LOCK_TIMEOUT"
    assert 9.5 <= waited < 12, waited


def test_the_lock_budget_is_enforced_by_the_runner_not_by_lock_timeout(scratch_url, monkeypatch):  # noqa: F811
    """The session keeps lock_timeout = 10 s; the runner's own 1 s budget must
    still end the wait — a blocking pg_advisory_lock would sit for 10 s (or
    for ever with lock_timeout = 0)."""
    migrate.upgrade(scratch_url)
    monkeypatch.setattr(migrate, "LOCK_WAIT_SECONDS", 1.0)
    engine, holder = _hold_lock(scratch_url)
    try:
        started = time.monotonic()
        with pytest.raises(migrate.MigrationRefused) as caught:
            migrate.upgrade(scratch_url)
        waited = time.monotonic() - started
    finally:
        holder.close()
        engine.dispose()
    assert caught.value.code == "MIGRATION_LOCK_TIMEOUT"
    assert 0.9 <= waited < 4, waited


def test_the_migrating_session_holds_the_lock_for_the_whole_migration(scratch_url, monkeypatch):  # noqa: F811
    """The lock and every Alembic statement share one backend: the lock is
    held by the connection that migrates, while it migrates. Meanwhile a
    second runner cannot get the lock and changes nothing."""
    _migrate(scratch_url, IBB001_HEAD)
    real_upgrade = migrate.command.upgrade
    seen: dict = {"pids": set()}

    def capture(conn, cursor, statement, *args):
        if "schema_lineage" in statement or "alembic_version" in statement:
            seen["pids"].add(cursor.connection.info.backend_pid)

    def observed_upgrade(cfg, revision):
        conn = cfg.attributes["connection"]
        seen["pid"] = conn.scalar(text("SELECT pg_backend_pid()"))
        seen["held_before"] = migrate.holds_lock(conn)
        other = create_engine(scratch_url)
        try:
            with other.connect() as probe:
                seen["other_got_lock"] = probe.scalar(
                    text("SELECT pg_try_advisory_lock(:k)"), {"k": migrate.LOCK_KEY})
        finally:
            other.dispose()
        monkeypatch.setattr(migrate, "LOCK_WAIT_SECONDS", 1.0)
        try:
            migrate.upgrade(scratch_url)
        except migrate.MigrationRefused as exc:
            seen["second_runner"] = exc.code
        seen["revision_after_second"] = _scalar(scratch_url,
                                                "SELECT version_num FROM alembic_version")
        event.listen(Engine, "before_cursor_execute", capture)
        try:
            real_upgrade(cfg, revision)
        finally:
            event.remove(Engine, "before_cursor_execute", capture)
        seen["held_after"] = migrate.holds_lock(conn)

    monkeypatch.setattr(migrate.command, "upgrade", observed_upgrade)
    result = migrate.upgrade(scratch_url)
    assert result["result"] == "migrated"
    assert seen["held_before"] is True and seen["held_after"] is True
    assert seen["other_got_lock"] is False
    assert seen["second_runner"] == "MIGRATION_LOCK_TIMEOUT"
    assert seen["revision_after_second"] == IBB001_HEAD
    assert seen["pids"] == {seen["pid"]}, seen
    # released when the job ends
    assert _scalar(scratch_url, "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND database = "
                         "(SELECT oid FROM pg_database WHERE datname = current_database())") == 0


def test_a_runner_whose_session_lost_the_lock_does_not_migrate(scratch_url, monkeypatch):  # noqa: F811
    _migrate(scratch_url, IBB001_HEAD)
    monkeypatch.setattr(migrate, "_acquire_lock", lambda conn: None)  # "locked" elsewhere
    with pytest.raises(migrate.MigrationRefused) as caught:
        migrate.upgrade(scratch_url)
    assert caught.value.code == "MIGRATION_LOCK_LOST"
    assert _lineage(scratch_url) is None


def test_a_runner_proceeds_when_the_lock_is_released_in_time(scratch_url):  # noqa: F811
    migrate.upgrade(scratch_url)
    engine, holder = _hold_lock(scratch_url)
    timer = threading.Timer(2.0, lambda: (holder.execute(
        text("SELECT pg_advisory_unlock(:k)"), {"k": migrate.LOCK_KEY}), holder.commit()))
    timer.start()
    try:
        started = time.monotonic()
        assert migrate.upgrade(scratch_url)["result"] == "nothing_to_do"
        assert time.monotonic() - started >= 1.5
    finally:
        timer.join()
        holder.close()
        engine.dispose()


def test_two_concurrent_runners_migrate_exactly_once(scratch_url):  # noqa: F811
    _migrate(scratch_url, IBB001_HEAD)
    gate, results = threading.Barrier(2), []

    def run():
        gate.wait()
        try:
            results.append(migrate.upgrade(scratch_url)["result"])
        except Exception as exc:  # recorded, asserted below
            results.append(f"error:{type(exc).__name__}:{exc}")

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert sorted(results) == ["migrated", "nothing_to_do"], results
    assert _scalar(scratch_url, "SELECT count(*) FROM alembic_version") == 1
    assert _scalar(scratch_url, "SELECT count(*) FROM schema_lineage WHERE recorded_by = "
                                "'MIGRATION'") == 1


# --- roles: a real, non-superuser migration role and the application role ------------------


@pytest.fixture
def roles(scratch_url):  # noqa: F811
    """A DBA provisions both roles; the migration role then migrates the
    database from nothing; the runner converges the application's grants."""
    admin = create_engine(scratch_url)
    with admin.begin() as conn:
        conn.exec_driver_sql((SQL / "migration_role.sql").read_text(encoding="utf-8"))
        conn.exec_driver_sql((SQL / "app_role.sql").read_text(encoding="utf-8"))
        conn.exec_driver_sql(f"ALTER ROLE homies_migrator LOGIN PASSWORD '{MIGRATOR_PASSWORD}'")
        conn.exec_driver_sql(f"ALTER ROLE homies_app LOGIN PASSWORD '{APP_PASSWORD}'")
    migrator_url = _as(scratch_url, "homies_migrator", MIGRATOR_PASSWORD)
    app_url = _as(scratch_url, "homies_app", APP_PASSWORD)
    result = migrate.upgrade(migrator_url)
    assert result["result"] == "migrated" and result["grants_converged"] is True
    yield {"admin": scratch_url, "migrator": migrator_url, "app": app_url}
    with admin.begin() as conn:
        conn.exec_driver_sql("ALTER ROLE homies_migrator NOLOGIN")
        conn.exec_driver_sql("ALTER ROLE homies_app NOLOGIN")
    admin.dispose()


def test_the_migration_role_owns_the_schema_and_its_record(roles):
    assert _scalar(roles["admin"], "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                                   "AND tableowner NOT IN ('homies_migrator') "
                                   "AND tablename <> 'spatial_ref_sys'") == 0
    assert _scalar(roles["admin"], "SELECT tableowner FROM pg_tables WHERE tablename = "
                                   "'schema_lineage'") == "homies_migrator"
    assert _scalar(roles["admin"], "SELECT rolsuper FROM pg_roles WHERE rolname = "
                                   "'homies_migrator'") is False
    assert _scalar(roles["migrator"], "SELECT count(*) FROM schema_lineage") == len(_graph().steps)


@pytest.mark.parametrize("statement", [
    "CREATE TABLE pr002_intruder (id int)",
    "ALTER TABLE users ADD COLUMN pr002_intruder int",
    "DROP TABLE saved_searches",
    "UPDATE alembic_version SET version_num = 'fedcba987654'",
    "DELETE FROM alembic_version",
    "INSERT INTO schema_lineage (revision, down_revision, schema_transition, "
    "rollback_to_previous, recorded_by) VALUES ('fedcba987654', NULL, 'EXPAND', 'SAFE', "
    "'MIGRATION')",
    "UPDATE schema_lineage SET schema_transition = 'EXPAND'",
    "DELETE FROM schema_lineage",
    "UPDATE spatial_ref_sys SET srtext = srtext WHERE srid = 4326",
    "DELETE FROM spatial_ref_sys WHERE srid = 4326",
])
def test_the_application_role_cannot_change_the_schema_or_its_record(roles, statement):
    engine = create_engine(roles["app"])
    try:
        with pytest.raises(DBAPIError) as caught, engine.begin() as conn:
            conn.execute(text(statement))
        assert caught.value.orig.sqlstate == "42501", caught.value.orig.sqlstate  # insufficient_privilege
    finally:
        engine.dispose()


def test_the_application_role_reads_the_record_and_passes_its_own_checks(roles, monkeypatch):
    engine = create_engine(roles["app"])
    try:
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == _graph().head
            assert conn.scalar(text("SELECT count(*) FROM schema_lineage")) > 0
            assert schema.schema_privilege_problems(conn) == []
    finally:
        engine.dispose()
    owner = create_engine(roles["migrator"])
    with owner.connect() as conn:  # the migration role is exactly what the app must not be
        assert any("owns" in p for p in schema.schema_privilege_problems(conn))
    owner.dispose()
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "database_url", roles["app"])
    monkeypatch.setenv(release.BUILD_SHA_ENV, BUILD_SHA)
    schema.ensure_schema()
    schema.verify_ledger_privileges()
    schema.verify_schema_privileges()
    monkeypatch.setattr(settings, "database_url", roles["migrator"])
    with pytest.raises(schema.SchemaPrivilegeError):
        schema.verify_schema_privileges()


def test_the_application_role_serves_ordinary_phase1_requests(roles, monkeypatch):
    from app.core.db import get_db
    from app.main import app

    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    engine = create_engine(roles["app"])
    local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        db = local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            owner = register_and_login(client, "pr002-owner@example.com", "host")
            made = client.post("/v1/properties", headers=auth(owner), json={
                "category": "APARTMENT", "city": "Opole", "address": "ul. Rolowa 1",
                "area_m2": 40, "rooms": 2, "capacity": 2})
            assert made.status_code == 201, made.text
            renter = register_and_login(client, "pr002-renter@example.com", "guest")
            saved = client.post("/v1/me/saved-searches", headers=auth(renter),
                                json={"name": "Opole", "query": "city=Opole"})
            assert saved.status_code == 201, saved.text
            assert client.get("/v1/classifieds").status_code == 200
            assert client.get("/v1/me/inbox", headers=auth(renter)).status_code == 200
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _denied(url, statement):
    engine = create_engine(url)
    try:
        with pytest.raises(DBAPIError) as caught, engine.begin() as conn:
            conn.execute(text(statement))
        return caught.value.orig.sqlstate
    finally:
        engine.dispose()


def test_privileges_converge_on_every_run(roles):
    """Future objects: a table (with its serial sequence) and a standalone
    sequence the migration role creates later, and a grant that drifted away,
    all end in the intended state after the next migration job. The mechanism
    is the runner's convergence, not ALTER DEFAULT PRIVILEGES: before it runs,
    the application role has nothing on the new objects."""
    migrator = create_engine(roles["migrator"])
    with migrator.begin() as conn:
        conn.execute(text("CREATE TABLE pr002_later (id bigserial PRIMARY KEY, note text)"))
        conn.execute(text("CREATE SEQUENCE pr002_counter"))
        conn.execute(text("REVOKE INSERT ON users FROM homies_app"))
    migrator.dispose()
    assert not _scalar(roles["admin"], "SELECT has_table_privilege('homies_app', "
                                       "'pr002_later', 'INSERT')")
    assert not _scalar(roles["admin"], "SELECT has_sequence_privilege('homies_app', "
                                       "'pr002_counter', 'USAGE')")
    assert migrate.upgrade(roles["migrator"])["grants_converged"] is True
    app_engine = create_engine(roles["app"])
    try:
        with app_engine.begin() as conn:  # DML on the new table uses its sequence
            new_id = conn.scalar(text("INSERT INTO pr002_later (note) VALUES ('x') RETURNING id"))
            conn.execute(text("UPDATE pr002_later SET note = 'y' WHERE id = :i"), {"i": new_id})
            assert conn.scalar(text("SELECT nextval('pr002_counter')")) == 1
            conn.execute(text("DELETE FROM pr002_later WHERE id = :i"), {"i": new_id})
            assert conn.scalar(text("SELECT has_table_privilege('users', 'INSERT')"))
    finally:
        app_engine.dispose()
    for statement in ("ALTER TABLE pr002_later ADD COLUMN intruder int",
                      "CREATE INDEX pr002_intruder ON pr002_later (note)",
                      "DROP TABLE pr002_later",
                      "TRUNCATE pr002_later",
                      "ALTER SEQUENCE pr002_counter RESTART",
                      "UPDATE alembic_version SET version_num = version_num",
                      "DELETE FROM schema_lineage",
                      "DELETE FROM spatial_ref_sys WHERE srid = 4326"):
        assert _denied(roles["app"], statement) == "42501", statement


def test_a_table_the_migration_role_cannot_grant_on_fails_the_job(roles, monkeypatch):
    """Ownership differs: a table created by the DBA/bootstrap role, not the
    migration role. Convergence cannot grant on it; the post-verify names it
    and the job exits 3 rather than leaving the application to fail later."""
    _exec(roles["admin"], "CREATE TABLE pr002_admin_owned (id int)")
    with pytest.raises(migrate.MigrationVerifyError, match=r"pr002_admin_owned \(owner "):
        migrate.upgrade(roles["migrator"])
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", roles["migrator"])
    assert migrate.main([]) == migrate.EXIT_VERIFY
    _exec(roles["admin"], "ALTER TABLE pr002_admin_owned OWNER TO homies_migrator")
    assert migrate.upgrade(roles["migrator"])["result"] == "nothing_to_do"


def _provision(admin_url):
    engine = create_engine(admin_url)
    with engine.begin() as conn:
        conn.exec_driver_sql((SQL / "migration_role.sql").read_text(encoding="utf-8"))
        conn.exec_driver_sql((SQL / "app_role.sql").read_text(encoding="utf-8"))
        conn.exec_driver_sql(f"ALTER ROLE homies_migrator LOGIN PASSWORD '{MIGRATOR_PASSWORD}'")
        conn.exec_driver_sql(f"ALTER ROLE homies_app LOGIN PASSWORD '{APP_PASSWORD}'")
    engine.dispose()
    return (_as(admin_url, "homies_migrator", MIGRATOR_PASSWORD),
            _as(admin_url, "homies_app", APP_PASSWORD))


def test_an_existing_ibb001_database_upgrades_under_the_migration_role(scratch_url, monkeypatch):  # noqa: F811
    """The real upgrade path: an IBB-001 database (f3b5d7e9a1c2, no lineage,
    every object owned by the role that ran `alembic upgrade head`).

    Without the one-time ownership transfer the migration role can neither
    read nor advance alembic_version: the job fails, rolls back, and the
    database is exactly as before. After migration_owner.sql it upgrades, backfills the
    lineage, converges the grants, and the application role starts on it."""
    _migrate(scratch_url, IBB001_HEAD)
    migrator_url, app_url = _provision(scratch_url)

    with pytest.raises(DBAPIError):
        migrate.upgrade(migrator_url)
    assert _scalar(scratch_url, "SELECT version_num FROM alembic_version") == IBB001_HEAD
    assert _lineage(scratch_url) is None

    engine = create_engine(scratch_url)
    with engine.begin() as conn:
        conn.exec_driver_sql((SQL / "migration_owner.sql").read_text(encoding="utf-8"))
        conn.exec_driver_sql((SQL / "migration_owner.sql").read_text(encoding="utf-8"))  # idempotent
    engine.dispose()
    assert _scalar(scratch_url, "SELECT count(*) FROM pg_class c JOIN pg_namespace n "
                                "ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
                                "AND c.relkind IN ('r', 'S', 'v', 'm', 'p') "
                                "AND c.relowner <> 'homies_migrator'::regrole "
                                "AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid "
                                "AND d.classid = 'pg_class'::regclass AND d.deptype = 'e')") == 0
    assert _scalar(scratch_url, "SELECT pg_get_userbyid(relowner) FROM pg_class "
                                "WHERE relname = 'spatial_ref_sys'") != "homies_migrator"

    result = migrate.upgrade(migrator_url)
    graph = _graph()
    assert (result["result"], result["from"], result["to"]) == ("migrated", IBB001_HEAD,
                                                                graph.head)
    assert result["grants_converged"] is True
    assert _lineage(scratch_url) == {r: graph.steps[r] for r in graph.ancestors(graph.head)}
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "database_url", app_url)
    monkeypatch.setenv(release.BUILD_SHA_ENV, BUILD_SHA)
    schema.ensure_schema()
    schema.verify_ledger_privileges()
    schema.verify_schema_privileges()
    for statement in ("CREATE TABLE pr002_intruder (id int)",
                      "UPDATE alembic_version SET version_num = version_num",
                      "DELETE FROM schema_lineage"):
        assert _denied(app_url, statement) == "42501", statement
    engine = create_engine(scratch_url)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER ROLE homies_migrator NOLOGIN")
        conn.exec_driver_sql("ALTER ROLE homies_app NOLOGIN")
    engine.dispose()


def test_the_runner_refuses_the_application_role(roles):
    with pytest.raises(migrate.MigrationRefused) as caught:
        migrate.upgrade(roles["app"])
    assert caught.value.code == "MIGRATION_ROLE_REQUIRED"


def test_the_runner_does_not_finish_when_the_grants_leak(roles, monkeypatch, tmp_path):
    """Post-verify: a grants script that lets the application write the
    schema's record is caught, and the job exits 3 instead of reporting success."""
    leaky = tmp_path / "app_grants.sql"
    leaky.write_text(migrate.GRANTS_SQL.read_text(encoding="utf-8") +
                     "\nGRANT INSERT ON alembic_version TO homies_app;\n", encoding="utf-8")
    monkeypatch.setattr(migrate, "GRANTS_SQL", leaky)
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", roles["migrator"])
    assert migrate.main([]) == migrate.EXIT_VERIFY

