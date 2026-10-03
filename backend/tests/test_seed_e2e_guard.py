"""The E2E seed refuses anything that is not a disposable development database (SEC-004)."""

import pytest

from app.core.config import Settings
from app.scripts import seed_e2e

URL = "postgresql+psycopg://u:p@db:5432/{name}"


def _run(monkeypatch, *, opt_in=True, env="local", name="homies_e2e"):
    if opt_in:
        monkeypatch.setenv("HOMIES_ALLOW_E2E_SEED", "1")
    else:
        monkeypatch.delenv("HOMIES_ALLOW_E2E_SEED", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    kwargs = {"database_url": URL.format(name=name)}
    if env is not None:
        kwargs["env"] = env
    monkeypatch.setattr(seed_e2e, "settings", Settings(**kwargs))
    seed_e2e._guard()


def test_a_disposable_development_database_passes(monkeypatch):
    for name in ("homies_e2e", "homies_test", "homies_ci"):
        _run(monkeypatch, name=name)


@pytest.mark.parametrize("case, message", [
    ({"opt_in": False}, "HOMIES_ALLOW_E2E_SEED"),
    ({"env": None}, "ENV explicitly"),               # the `local` default of a bare shell
    ({"env": "production"}, "ENV explicitly"),
    ({"env": "staging"}, "ENV explicitly"),
    ({"name": "homies"}, "disposable"),             # a production-looking database
    ({"name": "homies_e2e_backup"}, "disposable"),
])
def test_anything_else_is_refused(monkeypatch, case, message):
    with pytest.raises(SystemExit, match=message):
        _run(monkeypatch, **case)
