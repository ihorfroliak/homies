"""The CI and runtime contract PR-001R repaired, pinned by tests.

These read the workflow, Dependabot and image definitions: a later edit that
quietly reverts one of the repairs fails here, in the ordinary suite, instead
of being discovered from a CI history nobody reads.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
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


def test_the_audit_canary_is_a_real_old_pin_and_ci_runs_the_structured_check():
    pins = [line for line in (ROOT / "ops/ci/pip-audit-canary.pins").read_text(
        encoding="utf-8").splitlines() if line and not line.startswith("#")]
    assert pins == [f"{_canary().CANARY_PACKAGE}=={_canary().CANARY_VERSION}"]
    runs = _runs("backend")
    assert "python scripts/ci/audit_canary.py ../ops/ci/pip-audit-canary.pins" in runs
    assert 'grep -qi "urllib3"' not in runs, "a package-name grep passes on a failed lookup"


# --- RA-2: the canary passes only on proof of detection ---------------------
FIXTURES = BACKEND / "tests/fixtures/pip_audit"


def _canary():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_canary", BACKEND / "scripts/ci/audit_canary.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_real_vulnerable_report_is_a_canary_success():
    """Recorded pip-audit 2.9.0 JSON for urllib3==1.26.4 (9 advisories)."""
    raw = (FIXTURES / "canary-vulnerable.json").read_text(encoding="utf-8")
    assert _canary().detected(raw) is True


def test_an_advisory_lookup_failure_is_a_canary_failure():
    """Recorded pip-audit run without network: exit 1, empty stdout, and a
    traceback that mentions urllib3 13 times — the old grep's false success."""
    failure = (FIXTURES / "canary-network-failure.stderr.txt").read_text(encoding="utf-8")
    assert failure.count("urllib3") > 1 and "Failed to resolve" in failure
    canary = _canary()
    assert canary.detected("") is False                 # what stdout held
    assert canary.detected(failure) is False            # even if both streams were mixed
    assert canary.detected(failure + "\n" + "urllib3 1.26.4") is False


@pytest.mark.parametrize("report", [
    {"dependencies": [{"name": "urllib3", "version": "1.26.4", "vulns": []}]},
    {"dependencies": [{"name": "urllib3", "version": "1.26.5",
                       "vulns": [{"id": "PYSEC-2023-192"}]}]},
    {"dependencies": [{"name": "requests", "version": "2.0.0",
                       "vulns": [{"id": "PYSEC-2014-13"}]}]},
    {"dependencies": [{"name": "urllib3", "version": "1.26.4",
                       "vulns": [{"id": "not-an-advisory"}]}]},
    {"error": "advisory service unavailable"},
    [],
])
def test_anything_short_of_the_canary_pin_with_an_advisory_is_a_failure(report):
    assert _canary().detected(json.dumps(report)) is False


def test_the_canary_command_fails_closed_when_pip_audit_fails(monkeypatch, capsys):
    """The CI entry point, with pip-audit replaced by the recorded failure."""
    canary = _canary()
    failure = (FIXTURES / "canary-network-failure.stderr.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(canary.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a[0], 1, stdout="", stderr=failure))
    assert canary.main(["audit_canary.py", "x.pins"]) == 1
    assert "canary FAILED" in capsys.readouterr().err

    vulnerable = (FIXTURES / "canary-vulnerable.json").read_text(encoding="utf-8")
    monkeypatch.setattr(canary.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a[0], 1, stdout=vulnerable, stderr=""))
    assert canary.main(["audit_canary.py", "x.pins"]) == 0


# --- F7: the restore drill is mandatory in CI -------------------------------
def test_ci_declares_the_restore_drill_mandatory_and_shows_skips():
    job = WORKFLOW["jobs"]["backend"]
    assert job["env"]["HOMIES_REQUIRE_RESTORE_DRILL"] == "1"
    assert "pytest -q -rs" in _runs("backend")
    assert "restore drills will skip" not in _runs("backend")
    assert "\npg_dump --version\npg_restore --version\n" in _runs("backend")


def test_ci_counts_the_restore_drill_test_cases_it_ran():
    """CONV-001A CV-N1: the drill evidence is a count of JUnit <testcase>
    elements from this very run, and it fails the job when none passed."""
    assert "pytest -q -rs --junitxml=junit.xml" in _runs("backend")
    names = [step.get("name", "") for step in _steps("backend")]
    test_at = next(i for i, step in enumerate(_steps("backend"))
                   if "--junitxml=junit.xml" in step.get("run", ""))
    drills = names.index("Restore drills ran (JUnit test cases)")
    assert drills == test_at + 1
    assert _steps("backend")[drills]["run"] == "python scripts/ci/junit_drills.py junit.xml"


def test_ci_names_failed_tests_in_public_annotations():
    """PROGRAM-001 P0: job logs need admin rights; when Test fails, a later
    step (if: failure()) turns each failed JUnit case into an annotation."""
    steps = _steps("backend")
    test_at = next(i for i, step in enumerate(steps)
                   if "--junitxml=junit.xml" in step.get("run", ""))
    [named] = [(i, s) for i, s in enumerate(steps)
               if s.get("run") == "python scripts/ci/junit_failures.py junit.xml"]
    assert named[0] > test_at and named[1].get("if") == "failure()"


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


def test_ci_builds_the_image_with_its_identity_and_proves_it_fails_closed():
    """PR-002: identity is injected at build time and a production-like image
    without it refuses (it never reports a placeholder)."""
    build = next(s["run"] for s in _steps("image") if s.get("name") == "Build backend image")
    assert "--build-arg GIT_SHA=${{ github.sha }}" in build
    image_runs = _runs("image")
    assert "m['build_sha'] == '${{ github.sha }}'" in image_runs
    assert "org.opencontainers.image.revision" in image_runs
    assert "-e HOMIES_BUILD_SHA= homies-backend:ci python -m app.scripts.release manifest" \
        in image_runs


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
