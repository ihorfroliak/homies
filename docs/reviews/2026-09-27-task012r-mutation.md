# TASK-012R — mutation evidence

Harnesses: [`task012r_mutants.py`](../../backend/scripts/mutation/task012r_mutants.py)
(new) and a regression rerun of [`task012_mutants.py`](../../backend/scripts/mutation/task012_mutants.py).
Run 2026-09-27 on the TASK-012R working tree, local disposable PostgreSQL
16.4 / PostGIS 3.4.3, Python 3.14.3. Green baseline per mutant; killed only
when pytest exits 1 with failures and no errors; original bytes restored and
SHA-256-verified per mutant, then `sha256sum -c` over every tracked and new
file under `app/` and `alembic/`: all restored. Each Z kill was re-run on its
own and its failure read.

Preconditions (same code): full SQLite 780 passed / 291 skipped; full
PostgreSQL/PostGIS 1070 passed / 1 skipped.

## Z01–Z06 — 6 / 6 killed, all by assertion

| Mutant | Invariant | Observed failure |
|---|---|---|
| Z01 SQL cutoff back to a day-bearing interval (`now - literal(timedelta)`) | 21 × 24 h in SQL, any session zone | "stale listing still on the board (Europe/Warsaw)" at autumn exactly 21 × 24 h |
| Z02 Python age without UTC normalisation | elapsed, not wall-clock, age | Warsaw autumn exactly 14 × 24 h shown FRESH instead of RECONFIRM_DUE |
| Z03 move-in on the session date (`now.date()`) | UTC date decides NOW/FROM_DATE | Kiritimati (+14) at 2026-09-27 20:25:21Z: `'NOW' == 'FROM_DATE'` |
| Z04 dedup key from offset-bearing `isoformat()` | one cycle identity per instant | UTC→Warsaw: second pass reminded again (`[[id], [id]]` vs `[[id], []]`) |
| Z05 `db_now` left in the session zone | DB instant handed on in UTC | `utcoffset() == 7200 s` under Warsaw |
| Z06 `canonical_instant` keeps the offset | canonical UTC spelling | Warsaw→UTC: second pass reminded again |

## Regression — F01–F16: 16 / 16 killed

Unchanged harness; every TASK-012 mutant still killed after the repair.

Not mutated: normalising the pinned `as_of` in `_now_sql` — psycopg sends an
aware datetime with its offset, so PostgreSQL receives the same instant
either way (equivalent).
