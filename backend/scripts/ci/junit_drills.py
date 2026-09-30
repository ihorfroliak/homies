"""Restore-drill evidence from a JUnit XML report (MICRO-001, CONV-001A CV-N1).

CI requires the backup/restore drills (HOMIES_REQUIRE_RESTORE_DRILL=1), and
this makes their execution visible as a number: it counts the drill
*<testcase> elements* and their outcomes. The CONV-001 evidence harness
counted matching *lines* instead; pytest writes the whole report on one line,
so it reported "1" for ten drills that had all passed.

Exit status 0 only when at least one drill test case ran and passed and none
was skipped, failed or errored.

Usage (CI, from backend/):
    python scripts/ci/junit_drills.py junit.xml
"""

import sys
import xml.etree.ElementTree as ET  # noqa: S405 — a report our own CI run just wrote

DRILL_MODULES = ("tests.test_dr_restore_pg", "tests.test_dr_restore_phase1_pg")


def drill_outcomes(path: str) -> dict[str, int]:
    """Counts of drill test cases by outcome: passed, skipped, failed."""
    counts = {"passed": 0, "skipped": 0, "failed": 0}
    for case in ET.parse(path).getroot().iter("testcase"):  # noqa: S314
        if not case.get("classname", "").startswith(DRILL_MODULES):
            continue
        if case.find("failure") is not None or case.find("error") is not None:
            counts["failed"] += 1
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    return counts


def main(argv: list[str]) -> int:
    counts = drill_outcomes(argv[1])
    summary = (f"restore drill test cases: {counts['passed']} passed, "
               f"{counts['skipped']} skipped, {counts['failed']} failed")
    print(summary)
    print(f"::notice title=restore-drills::{summary}")
    return 0 if counts["passed"] and not counts["skipped"] and not counts["failed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
