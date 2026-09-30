# TASK-013 — mutation evidence

Harness: [`task013_mutants.py`](../../backend/scripts/mutation/task013_mutants.py)
(new), plus regression reruns of `task012_mutants.py`, `task012r_mutants.py`,
`task010r_mutants.py` and `task010_mutants.py`. Run 2026-09-28 on the TASK-013
working tree, local disposable PostgreSQL 16.4 / PostGIS 3.4.3, Python 3.14.3.
Green baseline per mutant; killed only when pytest exits 1 with failures and
no errors; original bytes restored and SHA-256-verified per mutant, and
`sha256sum -c` over every tracked and new file under `app/` and `alembic/`
after each batch: all restored. Every S kill was re-run on its own and its
failure read.

Preconditions (same code): full SQLite 802 passed / 301 skipped; full
PostgreSQL/PostGIS 1102 passed / 1 skipped.

## S01–S12 — 12 / 12 killed, all by assertion

| Mutant | Invariant | Observed failure |
|---|---|---|
| S01 eligibility replaced by status ∈ {active, paused, stale} | search never resurrects | stale/paused listings returned |
| S02 viewport on `properties.exact_geog` | public point only (D-70) | a box around the exact home found the listing |
| S03 admin descendants ignored | region covers everything beneath | `set() == {…}` for a voivodeship query |
| S04 UNKNOWN matches `available_by` | D-64 | undated listing returned |
| S05 rent ceiling exclusive | inclusive boundaries | listing at exactly the ceiling missing |
| S06 city filter trusts the mirror | D-57 | stale mirror name finds the listing |
| S07 no id tie-breaker | deterministic paging | page order differs at index 1 (`price_asc`) |
| S08 map ignores the filters | list ≡ map | `max_rent` map shows a listing the list excludes |
| S09 map serves the exact point | map projects the public point | `'51.248811'` in the map payload |
| S10 place preload / selectin removed | fixed queries per page | counts `{1: 9, 10: 40, 24: 82}` — the N+1 returns |
| S11 cross-country contradiction accepted | 422, not an empty page | 200 instead of 422 |
| S12 subtype outside category accepted | 422, not an empty page | 200 instead of 422 |

**S08 survived the first run** — the test's listings all had the same rent,
so a map ignoring `max_rent` looked identical. The test was strengthened
(listings a filter must exclude: a dearer one, a house) and S08 is now killed.
This is recorded because it was a real test weakness, not a harness error.

## Regression

| Harness | Result | Notes |
|---|---|---|
| TASK-012 F01–F16 | 16 / 16 killed | F12 re-pointed to `search.py`; F13's anchor moved (a new schema class follows it) — first run NOT APPLIED, rerun killed |
| TASK-012R Z01–Z06 | 6 / 6 killed | unchanged |
| TASK-010R R01–R12 | 12 / 12 killed | R05/R06 re-pointed to `search.py`. In the long batch the R03 subprocess hit the harness's 900 s timeout once; rerun alone it killed in 9 s and no stuck session was found — transient, not reproduced |
| TASK-010 G01–G10 | 10 / 10 killed | G10 re-pointed to `search.py` |

What this does not show: that every alternative implementation would be
caught; production behaviour.
