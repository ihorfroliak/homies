"""Saved-search alerts maintenance (TASK-014).

    python -m app.scripts.saved_search_alerts run-once    # one worker pass
    python -m app.scripts.saved_search_alerts reconcile   # bounded recovery

`run-once` evaluates pending public-generation work items and sends due
deliveries (with send-time revalidation) — what the background worker does
every few seconds. `reconcile` returns claims abandoned by a crashed worker to
`pending` and restores a missing work item for a listing whose current public
episode began within the last 7 days. Neither ever crosses every saved search
with every listing; both are idempotent and safe to run concurrently with the
worker (claims are FOR UPDATE SKIP LOCKED, results are unique in the database).
"""

import argparse
import json


def main(argv: list[str] | None = None) -> None:
    from app.core.db import SessionLocal
    from app.modules.alerts import worker

    parser = argparse.ArgumentParser(prog="saved_search_alerts")
    parser.add_argument("command", choices=("run-once", "reconcile"))
    args = parser.parse_args(argv)
    if args.command == "reconcile":
        with SessionLocal() as db:
            result = worker.reconcile(db)
            db.commit()
        print(json.dumps(result))
        return
    print(json.dumps(worker.run_once()))


if __name__ == "__main__":
    main()
