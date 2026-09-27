# TASK-012 — mutation evidence

Harness: [`task012_mutants.py`](../../backend/scripts/mutation/task012_mutants.py)
(runner shared with `task002_mutants.py`). Run 2026-09-27 on the TASK-012
working tree, local disposable PostgreSQL 16.4 / PostGIS 3.4.3, Python 3.14.3.
Rules: green baseline per mutant; killed only when pytest exits 1 with
failures and no errors; original bytes restored and SHA-256-verified after
each mutant; afterwards `sha256sum -c` over every tracked and new file under
`app/` and `alembic/` matched. Every kill was then re-run individually and
its failure read (below).

Preconditions (same code): full SQLite 779 passed / 245 skipped; full
PostgreSQL/PostGIS 1024 passed / 1 skipped.

## 16 / 16 killed

| Mutant | Invariant | Observed failure |
|---|---|---|
| F01 visibility clause ignores freshness | stale listing not public (shared SQL rule: list, media) | assertion: stale listing still on the board |
| F02 detail page checks status only | detail follows the same rule | assertion: 200 instead of 404 |
| F03 SQL stale boundary `>` → `>=` | exactly 21 days is stale (DB) | assertion: the 21-day listing still public |
| F04 Python due boundary `<` → `<=` | exactly 14 days is RECONFIRM_DUE | assertion: `'FRESH' == 'RECONFIRM_DUE'` |
| F05 sweep without skip-locked and without the re-check | a newer confirmation beats the sweep | assertion: "the sweep waited on the confirmation's row lock" |
| F06 confirm without authorisation | only verified authority confirms/reactivates | assertion: stranger gets 200 instead of 404 |
| F07 `archived` confirmable | archived never resurrected | assertion: 200 instead of 409 |
| F08 reactivation skips the listable-space check | stale → active only through publication checks | assertion: 200 instead of 409 |
| F09 sweep also takes paused/archived | the sweep only moves active listings | assertion: paused/archived rows staled |
| F10 events keyed per call, not per cycle | reruns emit no duplicates | assertion: a second reminder emitted |
| F11 publication does not stamp confirmation | publication counts as confirmation | assertion: "publication did not confirm" |
| F12 `available_by` matches NULL again | unknown date is not "available now" | assertion: undated listing returned |
| F13 availability term validation removed | minimum lease > 0 | the database CHECK `ck_classified_offers_min_term_positive` refuses the write inside the request (IntegrityError) instead of the API answering 422 — the DB backstop, not an `assert` |
| F14 a recommendation marked required | recommendations never block | assertion: `['add_photos'] == []` |
| F15 backfill uses `now()` | confirmation from publication evidence only | assertion: backfilled time ≠ `published_at` |
| F16 migration moves old listings to `stale` | the migration changes no status | assertion: row differs (status) |

F11's test was tightened during inspection: it first failed with an
`AttributeError` on the missing timestamp; it now asserts the timestamp
exists, so the kill is an explicit assertion.

Not mutated: the outer re-check in the sweep's UPDATE alone (with the
skip-locked subquery still in place it is redundant — the subquery's row
locks already re-evaluate the condition); F05 removes both together.

What this does not show: that every alternative implementation would be
caught; production behaviour.
