# TASK-008 — mutation evidence

Harnesses: [`task008_mutants.py`](../../backend/scripts/mutation/task008_mutants.py)
(new), and the regression reruns of `task006_mutants.py`, `task004_mutants.py`
and the TASK-002 subset (M03, M04, M05, M19). Run 2026-09-25 on the TASK-008
working tree, local disposable PostgreSQL 16.4 / PostGIS 3.4 container, Python
3.14.3 venv. Rules as before: green baseline per mutant; killed only when
pytest exits 1 with failures and no errors; original bytes restored and
verified by SHA-256 after each mutant; a separate `sha256sum -c` of the five
touched/relevant source files after the run matched.

## TASK-008 mutants — 17 / 17 killed; 4 expected equivalents survived

| Mutant | Invariant | Verdict |
|---|---|---|
| D01 decision through the pre-lock proof keys (`within=proof`) | N-05: decide through rows the locks returned | killed |
| D02 single-key tables recorded as expected, not as returned | N-05 | killed |
| D03 (mandate, scope) rows recorded as expected | N-05 | killed |
| D04 (authority, scope) rows recorded as expected | N-05 | killed |
| D05 `Retry-After` dropped from the authority-change 409 | 409 contract | killed |
| D06 personal-link restriction dropped | N-06 | killed |
| D07 membership restriction dropped | N-06 | killed |
| D08 organisation-link restriction dropped | N-06 | killed |
| D09 (mandate, scope) pair restriction dropped | N-06 | killed |
| D10 whole mandate restriction dropped (id and pairs) | N-06: second mandate of the same principal | killed |
| D11 (authority, scope) restriction dropped | N-06 | killed |
| D12 whole authority restriction dropped (id and scope) | N-06: same holder's right verified during the wait | killed |
| D13 accept lock FOR SHARE instead of FOR UPDATE | N-07 | killed |
| D14 invitation reads the row unlocked | N-09 | killed |
| D15 invitation rewrites any non-INVITED row (demotes ACTIVE) | N-09 | killed |
| D16 invitation rewrites any non-ACTIVE row (re-roles a pending invitation) | N-09 | killed |
| D17 lost first-invitation INSERT not handled | N-10 | killed |
| E01 mandate-id restriction dropped | implied by the locked (mandate, scope) pairs: a mandate row cannot be replaced without cascading its scope rows | SURVIVED — equivalent |
| E02 organisation-id restriction dropped | implied: the locked membership and link fix the organisation, and an organisation row cannot be deleted while they reference it (RESTRICT) | SURVIVED — equivalent |
| E03 legal-party restriction dropped | implied: the locked authority fixes its holder, and a holder cannot be deleted while an authority references it (RESTRICT) | SURVIVED — equivalent |
| E04 authority-id restriction dropped | implied by the locked (authority, scope) pairs: an authority row cannot be replaced without cascading its scope rows | SURVIVED — equivalent |

The four equivalent restrictions are kept in the code as defence in depth; the
reasoning is the schema's foreign keys, so a future schema change that removes
a cascade or RESTRICT should revisit them.

## Regression reruns

* **TASK-006 B01–B07: 7 / 7 killed.** B03, B04 and B05 were re-pointed at the
  same invariants in the reshaped code (the lock results are now consumed;
  the decision now uses `within=locked`).
* **TASK-004 A01–A09: 9 / 9 killed.** A05 re-pointed (`locked = _lock_proof(…)`).
  Under TASK-008 a table dropped from the lock loop makes the decision fail
  closed; A01–A04 are still killed by their "the loss did not wait" /
  "publication never reached its protected decision" assertions.
* **TASK-002 subset: 4 / 4 killed.** M19's second half (the authority-row
  FOR SHARE) was re-pointed at the reshaped statement; the first run reported
  it NOT APPLIED, the re-pointed rerun killed it.

What this does not show: that every alternative implementation would be
caught — only that removing any load-bearing restriction, any of the
returned-row checks, the accept lock strength, or any part of the invitation
lifecycle guard is.
