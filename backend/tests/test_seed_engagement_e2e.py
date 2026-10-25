"""Engagement fixture opt-in must fail before touching database or output."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.scripts import seed_e2e, seed_engagement_e2e
from tests.test_seed_e2e_guard import _run


def test_engagement_seed_requires_both_opt_ins(monkeypatch):
    _run(monkeypatch)
    monkeypatch.delenv("HOMIES_ALLOW_ENGAGEMENT_E2E_SEED", raising=False)
    with pytest.raises(SystemExit, match="HOMIES_ALLOW_ENGAGEMENT_E2E_SEED"):
        seed_engagement_e2e._guard()
    monkeypatch.setenv("HOMIES_ALLOW_ENGAGEMENT_E2E_SEED", "1")
    seed_engagement_e2e._guard()
    monkeypatch.delenv("HOMIES_ALLOW_E2E_SEED")
    with pytest.raises(SystemExit, match="HOMIES_ALLOW_E2E_SEED"):
        seed_engagement_e2e._guard()


@pytest.mark.parametrize("case", [{"env": None}, {"env": "production"}, {"name": "homies"}])
def test_engagement_opt_in_cannot_bypass_existing_guards(monkeypatch, case):
    monkeypatch.setenv("HOMIES_ALLOW_ENGAGEMENT_E2E_SEED", "1")
    with pytest.raises(SystemExit):
        _run(monkeypatch, **case)
    with pytest.raises(SystemExit):
        seed_engagement_e2e._guard()


def test_refusal_happens_before_database_or_file_access(monkeypatch, tmp_path):
    monkeypatch.delenv("HOMIES_ALLOW_E2E_SEED", raising=False)
    db = Mock(side_effect=AssertionError("database accessed"))
    api = Mock(side_effect=AssertionError("client created"))
    monkeypatch.setattr(seed_engagement_e2e, "SessionLocal", db)
    monkeypatch.setattr(seed_e2e, "_Api", api)
    path = tmp_path / "manifest.json"
    with pytest.raises(SystemExit, match="HOMIES_ALLOW_E2E_SEED"):
        seed_engagement_e2e.run(Path(path))
    db.assert_not_called()
    api.assert_not_called()
    assert not path.exists()
