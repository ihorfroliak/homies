"""Dependency-audit canary (PR-001R F2, repaired in PR-001R2 / PR-001RA RA-2).

CI audits the shipped pins with pip-audit. The canary proves that the audit
really inspects the exact pins it is given: it audits a deliberately old,
vulnerable pin (`ops/ci/pip-audit-canary.pins`, never installed) and must see
that pin reported vulnerable.

The first version grepped pip-audit's combined output for "urllib3". When the
advisory lookup failed (no network, PyPI/OSV unavailable), the traceback also
mentioned urllib3, so the canary went green on a failure. Now the canary
passes only on positive, structured evidence: pip-audit's JSON report lists
urllib3 at exactly 1.26.4 with at least one PYSEC/GHSA/CVE advisory id.
Anything else — an error, empty output, other JSON, the package without
advisories, another version — is a failure.

Usage (CI, from backend/):
    python scripts/ci/audit_canary.py ../ops/ci/pip-audit-canary.pins
"""

import json
import re
import subprocess
import sys

CANARY_PACKAGE = "urllib3"
CANARY_VERSION = "1.26.4"
VULN_ID = re.compile(r"^(PYSEC|GHSA|CVE)-")


def detected(raw: str) -> bool:
    """True only when `raw` is a pip-audit JSON report naming the canary pin
    with at least one advisory id."""
    try:
        report = json.loads(raw)
    except ValueError:
        return False
    deps = report.get("dependencies") if isinstance(report, dict) else None
    for dep in deps if isinstance(deps, list) else []:
        if (
            isinstance(dep, dict)
            and str(dep.get("name", "")).lower() == CANARY_PACKAGE
            and dep.get("version") == CANARY_VERSION
        ):
            ids = [str(v.get("id", "")) for v in dep.get("vulns") or [] if isinstance(v, dict)]
            return any(VULN_ID.match(vid) for vid in ids)
    return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: audit_canary.py <canary-pins-file>", file=sys.stderr)
        return 2
    proc = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", argv[1], "--no-deps", "--disable-pip",
         "--progress-spinner", "off", "-f", "json"],
        capture_output=True, text=True, check=False,
    )
    # Only stdout is the report; stderr (tracebacks, warnings) is shown, never parsed.
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if detected(proc.stdout):
        print(f"canary OK: {CANARY_PACKAGE}=={CANARY_VERSION} reported vulnerable "
              f"(pip-audit exit {proc.returncode})")
        return 0
    print(f"canary FAILED: pip-audit did not report {CANARY_PACKAGE}=={CANARY_VERSION} as "
          f"vulnerable (exit {proc.returncode}); an audit that cannot see a known "
          "vulnerable pin proves nothing", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
