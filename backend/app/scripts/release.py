"""Release identity and compatibility for deploy tooling (PR-002).

    python -m app.scripts.release manifest          # this build's runtime release identity
    python -m app.scripts.release check             # may this build run on DATABASE_URL?
    python -m app.scripts.release rollback-allowed  # may the previous release be restored?

`check` is read-only and answers exactly what startup would decide (exit 0
allowed, 1 refused). Before rolling back, run the *previous* image's `check`
against the live database — its own graph and manifest decide — and this
image's `rollback-allowed`: both must succeed. `rollback-allowed` exits 0 only
for an explicit SAFE. Output carries revision ids and codes, never a URL.

`manifest` prints the RuntimeReleaseIdentity: the committed release policy
(app/release.json) plus the injected build identity (HOMIES_BUILD_SHA). Outside
development (ENV local/test/ci) a missing identity is an error, exit 1 — deploy
tooling never records a release it cannot tie to a commit. A malformed one is
an error everywhere.
"""

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    from app.core import release
    from app.core.config import settings
    from app.core.schema import SchemaNotMigratedError, build_graph, check_compatibility

    parser = argparse.ArgumentParser(prog="release")
    parser.add_argument("command", choices=("manifest", "check", "rollback-allowed"))
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            decision, manifest = check_compatibility()
            print(json.dumps({"decision": decision.code, "allowed": decision.allowed,
                              "db_revision": decision.db_revision,
                              "steps_ahead": decision.steps_ahead,
                              "minimum_schema": manifest.minimum_schema,
                              "maximum_schema": manifest.maximum_schema,
                              "detail": decision.detail}))
            return 0 if decision.allowed else 1
        manifest = release.load_manifest(build_graph())
        if args.command == "manifest":
            identity = release.runtime_identity(
                manifest, required=release.identity_required(settings.env))
            print(json.dumps(identity.as_dict(), indent=2))
            return 0
    except (release.ReleaseManifestError, SchemaNotMigratedError) as exc:
        print(json.dumps({"error": "INVALID_RELEASE", "detail": str(exc)}))
        return 1
    print(json.dumps({"rollback_to_previous": manifest.rollback_to_previous,
                      "previous_release": manifest.previous_release,
                      "note": manifest.rollback_note}))
    return 0 if manifest.rollback_allowed() else 1


if __name__ == "__main__":
    sys.exit(main())
