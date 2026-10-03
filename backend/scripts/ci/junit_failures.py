"""Failed test cases from a JUnit XML report, as GitHub annotations (PROGRAM-001 P0).

Job logs of this repository need admin rights to read, but check-run
annotations are public. When the Test step fails, this step turns each failed
or errored <testcase> into one `::error` line, so the failing test is named in
the run's annotations instead of only in a log nobody can open.

Prints at most MAX_ANNOTATIONS lines; each carries the test id and the first
line of the failure message, cut to MAX_MESSAGE characters. Always exits 0 —
it reports a failure, it does not decide one.

Usage (CI, from backend/):
    python scripts/ci/junit_failures.py junit.xml
"""

import os
import sys
import xml.etree.ElementTree as ET  # noqa: S405 — a report our own CI run just wrote

MAX_ANNOTATIONS = 20
MAX_MESSAGE = 300


def failures(path: str) -> list[tuple[str, str]]:
    """(test id, first message line) for every failed or errored test case."""
    found = []
    for case in ET.parse(path).getroot().iter("testcase"):  # noqa: S314
        bad = case.find("failure")
        if bad is None:
            bad = case.find("error")
        if bad is None:
            continue
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        message = (bad.get("message") or (bad.text or "")).strip().splitlines()
        found.append((test_id, message[0][:MAX_MESSAGE] if message else ""))
    return found


def _escape(value: str) -> str:
    # GitHub workflow-command escaping for the message part.
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(argv: list[str]) -> int:
    path = argv[1]
    if not os.path.exists(path):
        print(f"::error title=pytest::no JUnit report at {path} (the run ended before writing it)")
        return 0
    try:
        found = failures(path)
    except ET.ParseError as exc:
        print(f"::error title=pytest::unreadable JUnit report: {_escape(str(exc))}")
        return 0
    print(f"failed test cases: {len(found)}")
    for test_id, message in found[:MAX_ANNOTATIONS]:
        print(f"::error title=pytest failed::{_escape(test_id)} — {_escape(message)}")
    if len(found) > MAX_ANNOTATIONS:
        print(f"::error title=pytest failed::… and {len(found) - MAX_ANNOTATIONS} more")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
