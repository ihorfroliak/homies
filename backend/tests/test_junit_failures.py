"""Failed tests become public check-run annotations (PROGRAM-001 P0)."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "junit_failures.py"
spec = importlib.util.spec_from_file_location("junit_failures", SCRIPT)
junit_failures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(junit_failures)


def _report(tmp_path, cases: str) -> str:
    path = tmp_path / "junit.xml"
    path.write_text('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">'
                    f"{cases}</testsuite></testsuites>", encoding="utf-8")
    return str(path)


def _case(name: str, inner: str = "") -> str:
    return f'<testcase classname="tests.test_x" name="{name}" time="1.0">{inner}</testcase>'


def test_each_failed_or_errored_case_is_one_error_annotation(tmp_path, capsys):
    path = _report(tmp_path, _case("test_ok")
                   + _case("test_bad", '<failure message="assert 1 == 2&#10;more">trace</failure>')
                   + _case("test_err", '<error message="KeyError: \'id\'">trace</error>')
                   + _case("test_skip", '<skipped message="x"/>'))
    assert junit_failures.main(["x", path]) == 0
    out = capsys.readouterr().out
    assert "failed test cases: 2" in out
    assert "::error title=pytest failed::tests.test_x::test_bad — assert 1 == 2" in out
    assert "more" not in out  # first message line only
    assert "::error title=pytest failed::tests.test_x::test_err — KeyError: 'id'" in out
    assert "test_ok" not in out and "test_skip" not in out


def test_annotations_are_capped(tmp_path, capsys):
    cases = "".join(_case(f"test_{i}", '<failure message="no"/>') for i in range(25))
    junit_failures.main(["x", _report(tmp_path, cases)])
    out = capsys.readouterr().out
    assert out.count("::error") == junit_failures.MAX_ANNOTATIONS + 1
    assert "and 5 more" in out


def test_a_missing_or_broken_report_is_named_not_raised(tmp_path, capsys):
    assert junit_failures.main(["x", str(tmp_path / "absent.xml")]) == 0
    assert "no JUnit report" in capsys.readouterr().out
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuites><testcase", encoding="utf-8")
    assert junit_failures.main(["x", str(broken)]) == 0
    assert "unreadable JUnit report" in capsys.readouterr().out
