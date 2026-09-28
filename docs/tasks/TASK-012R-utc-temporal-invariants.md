# TASK-012R — UTC temporal invariants repair

| Field | Value |
|---|---|
| Status | **ACCEPTED** — TASK-012RA: TASK_012R_ACCEPTED_WITH_NONBLOCKING_NOTES; TASK_012_PHASE_1A_SLICE_ACCEPTED at `879bf56` ([archive](../reviews/2026-09-28-task012ra-codex-task012r-audit.md)) |
| Owner (writer) | Claude Code |
| Starting SHA | TASK-012 candidate `c4c8bfac7f59a0930d9403d1100f35dccf003ae6` |
| Accepted parent | `ed9cf1b49f70716bd214a3212b2e7497ca5078ec` (TASK-010 slice) |
| Branch | `claude/TASK-012R-utc-temporal-invariants` |
| Audit | TASK-012A (Codex) — TASK_012_REQUIRES_TARGETED_FIXES, P2 ×1 (F12A-01); [archived verbatim](../reviews/2026-09-27-task012a-codex-task012-audit.md) |
| Decision | D-67; 04a §20 |

## Scope

Bounded repair of F12A-01 only. TASK-012's concurrency, migration, quality,
privacy/security, NULL-availability and CAS behaviour were accepted by
TASK-012A and are not redesigned. No migration, no lock-order change, no
TASK-013 work.

## Canonical temporal invariant (D-67)

```text
The same stored instant and the same decision instant
MUST produce the same business result
regardless of PostgreSQL session TimeZone.

14 days = 14 × 24 h elapsed;  21 days = 21 × 24 h elapsed
"today" (move-in) = UTC date of the database decision instant
event-cycle identity = canonical UTC spelling of the instant
```

## Reproduction on `c4c8bfa` (before any production change)

`tests/test_listing_freshness_tz_pg.py`, run against the candidate under
session zones UTC, Europe/Warsaw and Pacific/Kiritimati (+14), zone set on
every pooled connection after connect, decision instant pinned and read back
from the database: **14 failed / 31 passed**, all assertion failures:

| Manifestation | Failing cases on the candidate |
|---|---|
| A. DST moves the lines | Warsaw: autumn exactly 21 × 24 h still listed (list + detail); autumn exactly 14 × 24 h shown FRESH; spring 20 d 23 h 30 m hidden; spring just-before-14 × 24 h wrong; all-seven-paths both directions |
| B. move-in on the session date | Kiritimati at 2026-09-27 20:25:21Z → NOW for 2026-09-28 (and the last µs of the 27th); Warsaw at 23:59:59.999999Z → NOW |
| C. one cycle, two reminders | UTC→Warsaw, Warsaw→UTC, Kiritimati→Warsaw: two `ListingReconfirmationDue` rows |
| (clock representation) | `db_now` returned the session zone (Warsaw +2 h, Kiritimati +14 h) |

UTC-session cases passed on the candidate, as TASK-012A found.

## Repair

| Where | Change |
|---|---|
| `freshness.py` | small temporal boundary: `to_utc`, `utc_date`, `canonical_instant`; `db_now` returns the DB instant in UTC; pinned `as_of` normalised |
| SQL cutoff | `now − make_interval(secs => N)` — a seconds-only interval, applied as exact elapsed time in every session zone (was a day-bearing interval) |
| Python age / derived dates | `to_utc(now) − to_utc(last)`; `reconfirm_at` / `stale_at` = UTC instant + duration |
| Move-in | `available_from ≤ utc_date(now)`; `confirmed_on` = UTC date |
| Event identity & payload | `canonical_instant()` (`YYYY-MM-DDTHH:MM:SS.ffffffZ`) instead of offset-bearing `isoformat()` |
| Defence in depth | application engine connects with `options=-c timezone=UTC`; tests deliberately set other zones after connect |

The sweep and the public rule share `_minus`/`_now_sql`, so maintenance and
visibility draw the same line by construction (tested in every zone).

Mutation details: [TASK-012R mutation evidence](../reviews/2026-09-27-task012r-mutation.md).

## Evidence (2026-09-27, local; Python 3.14.3 venv, PostgreSQL 16.4 / PostGIS 3.4.3)

| Check | Result |
|---|---|
| Reproduction on `c4c8bfa` | `test_listing_freshness_tz_pg.py`: 14 failed / 31 passed (all assertions) |
| Same file after the repair | 46 passed (45 + defence-in-depth check) |
| Full suite, SQLite | 780 passed, 291 skipped |
| Full suite, PostgreSQL/PostGIS | 1070 passed, 1 skipped (Stripe Test Mode suite) — includes TASK-012 freshness, concurrency races, migration, privacy, geography, foundation races |
| ruff · mypy · OpenAPI `--check` | clean · no issues (86 files) · up to date (no API change) |
| Mutation | Z01–Z06 6/6 killed (assertions); F01–F16 regression 16/16 |

Python 3.12 and CI not run.

## Known debt

* The due-reminder scan is unbounded (TASK-012A note); public `place` N+1 and
  owner-view amplification unchanged.
* Other pre-existing Python time helpers outside TASK-012 (e.g. the contact
  reveal quota window) use elapsed timedeltas and were not changed.
