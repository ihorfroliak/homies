"""The CI and runtime contract PR-001R repaired, pinned by tests.

These read the workflow, Dependabot and image definitions: a later edit that
quietly reverts one of the repairs fails here, in the ordinary suite, instead
of being discovered from a CI history nobody reads.
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))


def _steps(job: str) -> list[dict]:
    return WORKFLOW["jobs"][job]["steps"]


def _runs(job: str) -> str:
    return "\n".join(step.get("run", "") for step in _steps(job))


# --- F2: the audit covers what ships ----------------------------------------
def test_the_dependency_audit_targets_the_pinned_set_without_resolution():
    runs = _runs("backend")
    assert "pip_audit -r constraints.txt --no-deps --disable-pip" in runs
    assert "pip_audit ." not in runs, "resolving pyproject may audit other versions"


def test_ci_installs_and_proves_exactly_the_pinned_set():
    runs = _runs("backend")
    assert 'pip install -c constraints.txt ".[dev]"' in runs
    assert "diff -u /tmp/pinned.txt /tmp/installed.txt" in runs


def test_every_image_installs_from_the_same_pins():
    for dockerfile in (BACKEND / "Dockerfile", ROOT / "ops/test/Dockerfile.py312"):
        text = dockerfile.read_text(encoding="utf-8")
        assert "-c constraints.txt" in text, dockerfile


def test_the_audit_canary_is_a_real_old_pin_and_ci_requires_it_to_be_flagged():
    pins = [line for line in (ROOT / "ops/ci/pip-audit-canary.pins").read_text(
        encoding="utf-8").splitlines() if line and not line.startswith("#")]
    assert pins == ["urllib3==1.26.4"]
    runs = _runs("backend")
    assert "pip-audit-canary.pins --no-deps --disable-pip" in runs
    assert 'grep -qi "urllib3"' in runs


# --- F7: the restore drill is mandatory in CI -------------------------------
def test_ci_declares_the_restore_drill_mandatory_and_shows_skips():
    job = WORKFLOW["jobs"]["backend"]
    assert job["env"]["HOMIES_REQUIRE_RESTORE_DRILL"] == "1"
    assert "pytest -q -rs" in _runs("backend")
    assert "restore drills will skip" not in _runs("backend")
    assert "\npg_dump --version\npg_restore --version\n" in _runs("backend")


def _collect_drills(env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "HOMIES_REQUIRE_RESTORE_DRILL"}
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "tests/test_dr_restore_pg.py", "tests/test_dr_restore_phase1_pg.py"],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120,
    )


def test_a_required_restore_drill_without_its_tools_fails_instead_of_skipping(tmp_path):
    # An empty PG_BIN and a PATH holding only the interpreter's directory: no
    # pg_dump can be found, as on a runner without the PostgreSQL client.
    python_dir = str(Path(sys.executable).parent)
    missing = {"PATH": python_dir, "PG_BIN": str(tmp_path),
               "TEST_DATABASE_URL": "postgresql+psycopg://u:p@127.0.0.1:1/x"}
    required = _collect_drills({**missing, "HOMIES_REQUIRE_RESTORE_DRILL": "1"})
    assert required.returncode != 0, required.stdout
    assert "HOMIES_REQUIRE_RESTORE_DRILL=1 but the restore drill cannot run" in (
        required.stdout + required.stderr)
    assert "pg_dump=missing" in required.stdout + required.stderr

    optional = _collect_drills(missing)
    assert optional.returncode == 0, optional.stdout + optional.stderr


# --- F8: the supported runtime stays Python 3.12 ----------------------------
def test_the_production_image_is_python_312_and_ci_asserts_it():
    assert (BACKEND / "Dockerfile").read_text(encoding="utf-8").startswith(
        "FROM python:3.12-slim")
    image_runs = _runs("image")
    assert "sys.version_info[:2] == (3, 12)" in image_runs
    assert 'printenv ENV)" = "production"' in image_runs


def test_dependabot_cannot_propose_a_python_minor_or_major_bump():
    config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text(encoding="utf-8"))
    docker = next(u for u in config["updates"] if u["package-ecosystem"] == "docker")
    python = next(i for i in docker["ignore"] if i["dependency-name"] == "python")
    assert set(python["update-types"]) == {
        "version-update:semver-major", "version-update:semver-minor"}


# --- F10: main keeps every commit's CI record -------------------------------
def test_superseded_runs_are_cancelled_on_branches_but_never_on_main():
    concurrency = WORKFLOW["concurrency"]
    assert "github.ref == 'refs/heads/main' && github.sha" in concurrency["group"]
    assert concurrency["cancel-in-progress"] == "${{ github.ref != 'refs/heads/main' }}"
