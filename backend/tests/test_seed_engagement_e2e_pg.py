"""Real migrated PostGIS seed contract; TEST_DATABASE_URL must be disposable."""
import json
import os
import subprocess
import sys

from sqlalchemy import text

from app.scripts.seed_engagement_e2e import PROJECTS


def test_seed_twice_preserves_discovery_and_rejects_partial_state(pg_session, tmp_path):
    url = pg_session.bind.url.render_as_string(hide_password=False)
    manifest = tmp_path / "engagement.json"
    env = {**os.environ, "DATABASE_URL": url, "ENV": "test", "HOMIES_ALLOW_E2E_SEED": "1",
           "HOMIES_ALLOW_ENGAGEMENT_E2E_SEED": "1", "MEDIA_ROOT": str(tmp_path / "media")}

    def run(module, *args, ok=True):
        result = subprocess.run([sys.executable, "-m", module, *map(str, args)],
                                env=env, capture_output=True, text=True, timeout=240)
        if ok:
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            assert result.returncode != 0
        return result

    def counts():
        # These are the fixture records, not normal login refresh tokens.
        return {table: pg_session.scalar(text(f"SELECT count(*) FROM {table}")) for table in (
            "users", "properties", "classified_offers", "conversations", "messages", "viewings",
            "saved_listings", "contact_reveals", "moderation_decisions", "representation_mandates",
        )}

    run("app.scripts.seed_e2e")
    run("app.scripts.seed_engagement_e2e", "--manifest", manifest)
    first_bytes = manifest.read_bytes()
    first_counts = counts()
    run("app.scripts.seed_engagement_e2e", "--manifest", manifest)
    assert manifest.read_bytes() == first_bytes
    assert counts() == first_counts
    run("app.scripts.seed_e2e")  # original seed still recognizes its exact twelve
    assert counts() == first_counts
    assert pg_session.scalar(text("""
        SELECT count(*) FROM classified_offers c JOIN properties p ON p.id = c.property_id
        JOIN users u ON u.id = p.owner_id
        WHERE u.email LIKE 'e2e-owner-%@example.com' AND c.status = 'active'
    """)) == 12
    data = json.loads(first_bytes)
    assert set(data["projects"]) == set(PROJECTS)
    for key in ("listings", "conversations", "viewings"):
        assert set(data["projects"]["desktop"][key].values()).isdisjoint(
            data["projects"]["mobile"][key].values())
    assert "admin" not in first_bytes.decode()
    # Completion file loss must never silently append another fixture set.
    absent = run("app.scripts.seed_engagement_e2e", "--manifest", tmp_path / "absent.json", ok=False)
    assert "existing fixtures without their completion manifest" in absent.stderr
    assert counts() == first_counts
    # F-SEED-01: slots and provider access alone cannot prove the named fixtures.
    # Flip both promised modes and both role directions, changing nothing else.
    # A failed verification must preserve the mutation; fixture repair is explicit.
    desktop = data["projects"]["desktop"]
    for key, original, changed in (
        ("instant", "INSTANT_BOOKING", "REQUEST_APPROVAL"),
        ("approval", "REQUEST_APPROVAL", "INSTANT_BOOKING"),
    ):
        params = {"id": desktop["listings"][key], "value": changed}
        pg_session.execute(text("UPDATE viewing_settings SET booking_mode = :value WHERE listing_id = :id"), params)
        pg_session.commit()
        refused = run("app.scripts.seed_engagement_e2e", "--manifest", manifest, ok=False)
        assert f"booking mode: desktop/{key}" in refused.stderr
        assert pg_session.scalar(text("SELECT booking_mode FROM viewing_settings WHERE listing_id = :id"), params) == changed
        pg_session.execute(text("UPDATE viewing_settings SET booking_mode = :value WHERE listing_id = :id"),
                           {**params, "value": original})
        pg_session.commit()
    for key, original, changed in (
        ("guest_provider", "guest", "host"),
        ("host_without_authority", "host", "guest"),
    ):
        params = {"email": desktop["accounts"][key]["email"], "value": changed}
        pg_session.execute(text("UPDATE users SET role = :value WHERE email = :email"), params)
        pg_session.commit()
        refused = run("app.scripts.seed_engagement_e2e", "--manifest", manifest, ok=False)
        assert f"account role: desktop/{key}" in refused.stderr
        assert pg_session.scalar(text("SELECT role FROM users WHERE email = :email"), params) == changed
        pg_session.execute(text("UPDATE users SET role = :value WHERE email = :email"),
                           {**params, "value": original})
        pg_session.commit()
    run("app.scripts.seed_engagement_e2e", "--manifest", manifest)
    assert counts() == first_counts
    assert manifest.read_bytes() == first_bytes
    # A partially consumed fixture is refused, not silently reset or accepted.
    pg_session.execute(text("UPDATE viewings SET status = 'DECLINED' WHERE id = :id"),
                       {"id": desktop["viewings"]["held"]})
    pg_session.commit()
    consumed = run("app.scripts.seed_engagement_e2e", "--manifest", manifest, ok=False)
    assert "viewing state" in consumed.stderr
    assert manifest.read_bytes() == first_bytes
