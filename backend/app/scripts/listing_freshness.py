"""Listing freshness maintenance (TASK-012).

    python -m app.scripts.listing_freshness preflight   # read-only
    python -m app.scripts.listing_freshness sweep       # changes status, emits events

`preflight` lists every active listing the freshness rule does not show right
now — what a deployment of TASK-012 onto real inventory takes off the board
at once (D-62). Run it before such a deployment and record the count in the
release notes. `sweep` moves those listings to `stale` and records the
reminder events; it is idempotent and safe to run concurrently.
"""

import argparse
import json


def main(argv: list[str] | None = None) -> None:
    from app.core.db import SessionLocal
    from app.modules.properties import freshness
    from app.modules.properties.freshness_worker import run_once

    parser = argparse.ArgumentParser(prog="listing_freshness")
    parser.add_argument("command", choices=("preflight", "sweep"))
    args = parser.parse_args(argv)
    if args.command == "preflight":
        with SessionLocal() as db:
            rows = freshness.preflight(db)
        print(json.dumps({"would_leave_public_board": len(rows), "listings": rows}, indent=2))
        return
    print(json.dumps(run_once()))


if __name__ == "__main__":
    main()
