"""The application's database role cannot rewrite the ledger (release plan B5).

The append-only triggers (D-04) stop a bug. They do not stop the account that
owns the tables, because the owner can turn them off:

    ALTER TABLE journal_lines DISABLE TRIGGER journal_lines_append_only;

Today the application connects as that owner, so anything able to run SQL
through the application can unbuckle the seatbelt, edit the money, and buckle
it again — leaving a ledger that reconciles and an audit trail that agrees,
because both were rewritten by the same hand.

`ops/sql/app_role.sql` gives the application a role that is not the owner and
holds no UPDATE or DELETE on the append-only tables. Tampering then needs the
migration credentials as well, which live where the application cannot reach.
Two compromises instead of one.

These tests connect AS that role and try the things it must not be able to do.
Reading `has_table_privilege` would only prove what the catalogue claims; the
statements below prove what the server actually refuses.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres privilege tests skipped"
)

SCRIPT = Path(__file__).resolve().parents[2] / "ops" / "sql" / "app_role.sql"
APP_PASSWORD = "role-test-only-not-a-secret"


def _as_app_url(url: str) -> str:
    """Same host and database, different credentials."""
    scheme, _, rest = url.partition("://")
    _, _, hostpart = rest.partition("@")
    return f"{scheme}://homies_app:{APP_PASSWORD}@{hostpart}"


@pytest.fixture
def app_role(pg_migrated_engine):
    """Provision the role from the real script, yield an engine using it.

    The script is executed rather than reimplemented: a test that applies its
    own idea of the grants proves the test's idea is safe, not the one that
    will be run in production.
    """
    with pg_migrated_engine.begin() as conn:
        conn.exec_driver_sql(SCRIPT.read_text(encoding="utf-8"))
        conn.exec_driver_sql(
            f"ALTER ROLE homies_app LOGIN PASSWORD '{APP_PASSWORD}'"  # noqa: S608
        )

    engine = create_engine(_as_app_url(TEST_DATABASE_URL))
    yield engine
    engine.dispose()
    with pg_migrated_engine.begin() as conn:
        conn.exec_driver_sql("ALTER ROLE homies_app NOLOGIN")


def _append_only_tables(conn) -> list[str]:
    """The definition of "append-only" is the trigger, not a list in a file."""
    return list(
        conn.scalars(
            text(
                "SELECT DISTINCT tgrelid::regclass::text FROM pg_trigger "
                "WHERE NOT tgisinternal AND tgname ~ '_append_only$' "
                "ORDER BY 1"
            )
        )
    )


# --- what the role must still be able to do -----------------------------------


def test_the_application_can_read_the_ledger(app_role):
    with app_role.connect() as conn:
        conn.execute(text("SELECT COUNT(*) FROM journal_lines")).scalar_one()


def test_the_application_can_append_to_the_ledger(app_role, pg_session):
    """Append-only means append. A role that could not INSERT would not be a
    tighter ledger, it would be a broken application."""
    with app_role.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ledger_accounts (id, code, kind, created_at) "
                "VALUES ('priv-probe', 'privilege_probe', 'asset', now())"
            )
        )
        assert conn.execute(
            text("SELECT COUNT(*) FROM ledger_accounts WHERE id = 'priv-probe'")
        ).scalar_one() == 1


def test_ordinary_tables_are_still_writable(app_role):
    """The restriction is surgical. Bookings change state constantly; if this
    role could not update them the application would not run at all."""
    with app_role.begin() as conn:
        conn.execute(text("UPDATE bookings SET status = status WHERE FALSE"))


# --- what it must not be able to do -------------------------------------------


def test_the_application_cannot_update_the_ledger(app_role):
    with app_role.begin() as conn, pytest.raises(ProgrammingError) as excinfo:
        conn.execute(text("UPDATE journal_lines SET amount = amount + 1"))
    # Refused by privilege, BEFORE the trigger is reached — which is the point:
    # the trigger is a guard the owner can switch off, this is not.
    assert "permission denied" in str(excinfo.value).lower()


def test_the_application_cannot_delete_from_the_ledger(app_role):
    with app_role.begin() as conn, pytest.raises(ProgrammingError) as excinfo:
        conn.execute(text("DELETE FROM journal_entries"))
    assert "permission denied" in str(excinfo.value).lower()


def test_the_application_cannot_rewrite_the_audit_trail(app_role):
    """An attacker who can edit the money and then edit the record of editing
    the money leaves nothing to find."""
    with app_role.begin() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("UPDATE audit_log SET action = 'nothing.happened'"))


def test_the_application_cannot_disable_the_trigger(app_role):
    """The whole reason the role exists. As the owner this statement succeeds
    and the append-only guarantee evaporates for as long as someone wants."""
    with app_role.begin() as conn, pytest.raises(ProgrammingError) as excinfo:
        conn.execute(
            text("ALTER TABLE journal_lines DISABLE TRIGGER journal_lines_append_only")
        )
    assert "must be owner" in str(excinfo.value).lower()


def test_the_application_cannot_drop_the_trigger(app_role):
    with app_role.begin() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("DROP TRIGGER journal_lines_append_only ON journal_lines"))


def test_the_application_cannot_truncate_the_ledger(app_role):
    """TRUNCATE fires no row triggers. Granted by accident it would empty the
    ledger without a single guard noticing."""
    with app_role.begin() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("TRUNCATE journal_lines"))


def test_the_application_cannot_drop_a_table(app_role):
    with app_role.begin() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("DROP TABLE journal_lines"))


# --- the rule holds for every append-only table, not just the ones above ------


def test_no_append_only_table_is_writable_by_the_application(app_role, pg_session):
    """Derived from the triggers, so a new append-only table added later is
    covered the day it exists. A hand-kept list in the grant script would be
    wrong exactly when someone adds the next one and forgets."""
    tables = _append_only_tables(pg_session)
    assert len(tables) >= 4, "the append-only triggers are missing from the schema"

    with app_role.connect() as conn:
        for table in tables:
            for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
                granted = conn.execute(
                    text("SELECT has_table_privilege('homies_app', :t, :p)"),
                    {"t": table, "p": privilege},
                ).scalar_one()
                assert granted is False, f"homies_app holds {privilege} on {table}"


def test_the_script_is_idempotent(pg_migrated_engine, app_role):
    """It has to be re-run after every migration that adds a table, so running
    it twice must be a no-op rather than an error."""
    with pg_migrated_engine.begin() as conn:
        conn.exec_driver_sql(SCRIPT.read_text(encoding="utf-8"))

    with app_role.begin() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("UPDATE journal_lines SET amount = amount + 1"))


def test_the_role_is_not_a_superuser_and_owns_nothing(app_role, pg_session):
    """A role that is a superuser, or that owns the tables, has every privilege
    regardless of what was revoked — the revokes would be decoration."""
    row = pg_session.execute(
        text(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
            "FROM pg_roles WHERE rolname = 'homies_app'"
        )
    ).one()
    assert row == (False, False, False, False)

    owned = pg_session.execute(
        text(
            "SELECT COUNT(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
            "WHERE r.rolname = 'homies_app'"
        )
    ).scalar_one()
    assert owned == 0


# --- the check that stops a deployment from skipping the provisioning --------


def test_startup_refuses_a_role_that_can_edit_the_ledger(app_role, monkeypatch):
    """`ops/sql/app_role.sql` is a step somebody has to remember to run. This
    proves the application notices when they did not, instead of serving
    traffic with a ledger it could rewrite."""
    from app.core import schema
    from app.core.config import settings

    monkeypatch.setattr(settings, "env", "production")
    # The owner role — the one the app uses today — must be rejected.
    monkeypatch.setattr(settings, "database_url", TEST_DATABASE_URL)
    with pytest.raises(schema.LedgerPrivilegeError) as excinfo:
        schema.verify_ledger_privileges()
    assert "journal_lines" in str(excinfo.value)


def test_startup_accepts_the_provisioned_role(app_role, monkeypatch):
    from app.core import schema
    from app.core.config import settings

    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "database_url", _as_app_url(TEST_DATABASE_URL))
    schema.verify_ledger_privileges()


def test_local_development_is_exempt(monkeypatch):
    """Local dev owns its own schema by design (TD-01); demanding a separate
    role there would mean `make up` no longer just works."""
    from app.core import schema
    from app.core.config import settings

    monkeypatch.setattr(settings, "env", "local")
    monkeypatch.setattr(settings, "database_url", TEST_DATABASE_URL)
    schema.verify_ledger_privileges()
