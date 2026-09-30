# TASK-004 — mutation evidence

Harnesses: [`task004_mutants.py`](../../backend/scripts/mutation/task004_mutants.py)
(new) and [`task002_mutants.py`](../../backend/scripts/mutation/task002_mutants.py)
(regression rerun). Run 2026-09-24 on the TASK-004 working tree, local
PostgreSQL 16.4 / PostGIS 3.4 disposable test container, Python 3.14 venv.
Same rules as TASK-002: green baseline per mutant; killed only when pytest
exits 1 with failures and no errors; original bytes restored and verified by
SHA-256 after each mutant (a separate `sha256sum -c` of `authority.py` after
the run also matched, and `git status` showed only the intended changes).

## TASK-004 mutants — 9 / 9 killed

| Mutant | Invariant | Verdict |
|---|---|---|
| A01 membership row not locked FOR SHARE | membership row protection | killed |
| A02 mandate row not locked | mandate row protection | killed |
| A03 organisation row not locked | organisation row protection | killed |
| A04 legal-party row not locked | legal-party row protection | killed |
| A05 `authorize_for_mutation` returns without locking or re-checking | final authorisation guard | killed |
| A06 organisation status dropped from the chain | organisation status | killed |
| A07 legal-party status dropped from the chain | legal-party status | killed |
| A08 protected decision uses the request's Python date | decision on the database clock | killed |
| A09 mandate `effective_until` not enforced | expiry predicate | killed |

## TASK-002 mutants rerun — 20 / 20 killed after two harness updates

* **M04** targeted the second `require()` call that TASK-004 replaced. It now
  removes the `authorize_for_mutation` call. Killed.
* **M19** (revoke without the Property lock) **SURVIVED** the first rerun.
  This is an equivalent mutant under TASK-004, not a regression: publication
  now holds the authority row FOR SHARE, so a revoke without the Property lock
  still waits at its UPDATE and then pauses the listing. The mutant was made
  compound (Property lock AND the authority-row share lock removed). Killed.
  Revoke keeps the Property lock as defence in depth.

All other 18 killed unchanged.

What this does not show: that every conceivable alternative locking
algorithm would be caught; several kills are observed as "the loss did not
wait" or "the loss finished before the publication" assertions, which test
this mechanism.
