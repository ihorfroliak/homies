"""The restore-drill counter counts <testcase> elements, not lines (CONV-001A CV-N1)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "junit_drills.py"
spec = importlib.util.spec_from_file_location("junit_drills", SCRIPT)
junit_drills = importlib.util.module_from_spec(spec)
spec.loader.exec_module(junit_drills)


def _report(tmp_path, cases: list[str]) -> str:
    # One physical line, as pytest writes it.
    body = "".join(cases)
    path = tmp_path / "junit.xml"
    path.write_text('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" '
                    f'tests="{len(cases)}">{body}</testsuite></testsuites>', encoding="utf-8")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    return str(path)


def _case(module: str, name: str, inner: str = "") -> str:
    return f'<testcase classname="{module}" name="{name}" time="1.0">{inner}</testcase>'


DRILLS = [_case("tests.test_dr_restore_pg", f"test_drill_{i}") for i in range(7)] + \
         [_case("tests.test_dr_restore_phase1_pg", f"test_phase1_{i}") for i in range(3)]
OTHERS = [_case("tests.test_search", "test_other"),
          _case("tests.test_search", "test_other_skipped", '<skipped message="x"/>')]


def test_ten_drills_on_one_line_count_as_ten(tmp_path, capsys):
    path = _report(tmp_path, DRILLS + OTHERS)
    assert junit_drills.drill_outcomes(path) == {"passed": 10, "skipped": 0, "failed": 0}
    assert junit_drills.main(["junit_drills.py", path]) == 0
    assert "10 passed, 0 skipped, 0 failed" in capsys.readouterr().out


@pytest.mark.parametrize("inner, outcome", [
    ('<skipped message="drill tools missing"/>', "skipped"),
    ('<failure message="rows differ"/>', "failed"),
    ('<error message="setup"/>', "failed"),
])
def test_a_skipped_or_failed_drill_fails_the_check(tmp_path, inner, outcome):
    path = _report(tmp_path, DRILLS[:-1] + [_case("tests.test_dr_restore_phase1_pg", "t", inner)])
    assert junit_drills.drill_outcomes(path)[outcome] == 1
    assert junit_drills.main(["junit_drills.py", path]) == 1


def test_no_drill_at_all_fails_the_check(tmp_path):
    assert junit_drills.main(["junit_drills.py", _report(tmp_path, OTHERS)]) == 1
