"""Migration c1e3a5b7d9f2 quarantines files the C8 walker produced (TASK-002 R3)."""

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from app.core.schema import alembic_config
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

BEFORE = "b8d0f2a4c6e1"
AFTER = "c1e3a5b7d9f2"


def _with_database(url: str, database: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{database}"


@pytest.fixture
def scratch_url(monkeypatch):
    name = f"homies_media_{uuid.uuid4().hex[:8]}"
    admin = create_engine(_with_database(TEST_DATABASE_URL, "postgres"),
                          isolation_level="AUTOCOMMIT")
    with admin.begin() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = _with_database(TEST_DATABASE_URL, name)
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    try:
        yield url
    finally:
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": name})
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


def _upgrade(url: str, revision: str) -> None:
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, revision)


def test_existing_media_files_are_quarantined_not_deleted(scratch_url):
    _upgrade(scratch_url, BEFORE)
    engine = create_engine(scratch_url)
    with engine.begin() as conn:
        uid = str(uuid.uuid4())
        conn.execute(text("INSERT INTO users (id, email, password_hash, full_name, role, "
                          "created_at) VALUES (:id, :e, 'x', '', 'host', now())"),
                     {"id": uid, "e": f"{uid}@example.com"})
        files = {}
        for state, access in (("READY", "PUBLIC"), ("READY", "PRIVATE"), ("REJECTED", "PRIVATE")):
            fid = str(uuid.uuid4())
            conn.execute(text(
                "INSERT INTO file_objects (id, uploader_user_id, purpose, storage_provider, "
                "storage_bucket, storage_key, access_class, state, created_at) VALUES "
                "(:id, :u, 'PROPERTY_MEDIA', 'local', 'media', :k, :a, :s, now())"),
                {"id": fid, "u": uid, "k": f"property-media/{fid}", "a": access, "s": state})
            files[(state, access)] = fid
    _upgrade(scratch_url, AFTER)
    with engine.connect() as conn:
        rows = {r.id: (r.state, r.access_class, r.processing_version) for r in conn.execute(
            text("SELECT id, state, access_class, processing_version FROM file_objects"))}
    assert len(rows) == 3
    assert rows[files[("READY", "PUBLIC")]] == ("QUARANTINED", "QUARANTINE", None)
    assert rows[files[("READY", "PRIVATE")]] == ("QUARANTINED", "QUARANTINE", None)
    # Already refused files stay as they were.
    assert rows[files[("REJECTED", "PRIVATE")]] == ("REJECTED", "PRIVATE", None)
    engine.dispose()
