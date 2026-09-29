"""CONV-001 integration sentinels on a private copy (/tmp/w) of /repo.

Product: selected mutants from the committed TASK-014R runner
(backend/scripts/mutation/task014r_mutants.py). Infra: m12 / c01 / c02
(PR-001R2) and M01 / M06 / M07 / M08 (PR-001R), re-stated here because their
runners were never committed. Rules: green baseline first (one recorded rerun
for the Docker clock); KILLED only on pytest exit 1 with FAILED tests and no
pytest ERROR lines; original bytes restored and SHA-256 verified.
Output: /out/conv-sentinels.json
"""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

SRC, WORK = Path("/repo"), Path("/tmp/w")
if WORK.exists():
    shutil.rmtree(WORK)
shutil.copytree(SRC, WORK, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv",
                                                         ".mypy_cache", "build", "*.egg-info"))
B = WORK / "backend"

# Product: load the committed runner's MUTANTS without running it.
spec = importlib.util.spec_from_file_location("t14r", B / "scripts/mutation/task014r_mutants.py")
t14r = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(B / "scripts/mutation"))
spec.loader.exec_module(t14r)
harness = sys.modules["task002_mutants"]
PRODUCT = {"F2-a", "F2-b", "X13", "X18", "F1-a", "F1-b"}
mutants = [(m["id"], m["invariant"], "backend/" + m["file"], [(m["old"], m["new"])] + list(m.get("extra", [])),
            m["tests"]) for m in harness.MUTANTS if m["id"] in PRODUCT]
assert {m[0] for m in mutants} == PRODUCT

HEALTH = "backend/app/core/health.py"
CANARY = "backend/scripts/ci/audit_canary.py"
RID = "backend/app/core/request_id.py"
CONFIG = "backend/app/core/config.py"
DOCKER = "backend/Dockerfile"
FREEZE = ("tests/test_readiness_faults_pg.py::"
          "test_a_freeze_after_the_connection_is_established_is_a_finite_503")
mutants += [
    ("m12", "readiness wall-clock deadline removed", HEALTH,
     [("        await asyncio.wait_for(probe(), PROBE_DEADLINE_S)\n", "        await probe()\n")],
     [FREEZE]),
    ("c01", "dependency canary back to package-name-only detection", CANARY,
     [("    try:\n        report = json.loads(raw)\n",
       "    if CANARY_PACKAGE in raw:\n        return True\n"
       "    try:\n        report = json.loads(raw)\n")],
     ["tests/test_ci_contract.py"]),
    ("c02", "dependency canary accepts any version", CANARY,
     [("            and dep.get(\"version\") == CANARY_VERSION\n", "")],
     ["tests/test_ci_contract.py"]),
    ("M01", "unhandled exception escapes the request-id middleware", RID,
     [("    except Exception:\n        # Path only", "    except ZeroDivisionError:\n        # Path only")],
     ["tests/test_request_id.py::test_an_unhandled_exception_is_a_generic_500_with_the_request_id"]),
    ("M06", "production guard: published dev credentials accepted", CONFIG,
     [("    if (url.username, url.password) == DEV_DATABASE_CREDENTIALS:", "    if False:")],
     ["tests/test_sec02_secret_config.py"]),
    ("M07", "production guard: exact-string comparison only", CONFIG,
     [("    problems.extend(development_database_problems(cfg.database_url))",
       "    if cfg.database_url == Settings.model_fields['database_url'].default:\n"
       "        problems.append('DATABASE_URL is the repository default')")],
     ["tests/test_sec02_secret_config.py"]),
    ("M08", "production image without ENV=production", DOCKER,
     [("ENV ENV=production\n", "")],
     ["tests/test_sec02_secret_config.py::"
      "test_the_production_image_defaults_to_production_and_dev_tooling_opts_in",
      "tests/test_ci_contract.py"]),
]


def run(tests):
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
                          cwd=B, capture_output=True, text=True, timeout=1500)
    lines = proc.stdout.splitlines()
    summary = next((ln for ln in reversed(lines) if " passed" in ln or " failed" in ln
                    or " error" in ln), "")
    failed = [ln for ln in lines if ln.startswith("FAILED")]
    errored = [ln for ln in lines if ln.startswith("ERROR tests/")]
    return proc.returncode, summary, failed, errored, [ln for ln in lines if ln.startswith("E   ")][:2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


results = []
for mid, desc, rel, edits, tests in mutants:
    path = WORK / rel
    code, summary, *_ = run(tests)
    note = "green"
    if code != 0:
        first = summary
        code, summary, *_ = run(tests)
        note = f"green on rerun (first: {first})"
    assert code == 0, (mid, "baseline must be green", summary)
    original, before = path.read_bytes(), digest(path)
    text = original.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        assert text.count(old) == 1, (mid, "anchor", old[:70])
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    try:
        code, summary, failed, errored, evidence = run(tests)
    finally:
        path.write_bytes(original)
    assert digest(path) == before, (mid, "restoration failed")
    killed = code == 1 and failed and not errored
    results.append({"id": mid, "mutant": desc, "baseline": note,
                    "result": "KILLED" if killed else ("SURVIVED" if code == 0 else f"INVALID(exit {code})"),
                    "summary": summary, "failed": failed[:2], "evidence": evidence})
    print(mid, results[-1]["result"], "|", note, "|", summary, "|", (failed[:1] or [""])[0][:110], flush=True)
Path("/out/conv-sentinels.json").write_text(json.dumps(results, indent=2))
