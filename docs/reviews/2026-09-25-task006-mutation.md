# TASK-006 — mutation evidence

Harnesses: [`task006_mutants.py`](../../backend/scripts/mutation/task006_mutants.py)
(new), [`task004_mutants.py`](../../backend/scripts/mutation/task004_mutants.py)
and [`task002_mutants.py`](../../backend/scripts/mutation/task002_mutants.py)
(regression). Run 2026-09-25 on the TASK-006 working tree, local disposable
PostgreSQL 16.4 / PostGIS 3.4 container, Python 3.14.3 venv. Rules as before:
green baseline per mutant; killed only when pytest exits 1 with failures and
no errors; original bytes restored and verified by SHA-256 after each mutant;
a separate `sha256sum -c` of the four touched source files after the run
matched, and `git status` showed only the intended changes.

## TASK-006 mutants — 7 / 7 killed

| Mutant | Invariant | Killing test | Verdict |
|---|---|---|---|
| B01 personal-link row not locked | `person_legal_parties` protection | `…waits_for_the_publication[person_link_sql]` | killed |
| B02 organisation-link row not locked | `organization_legal_parties` protection | `…[org_link_sql]` | killed |
| B03 mandate scope row not locked | `representation_mandate_scopes` protection | `…[mandate_scope_sql]` | killed |
| B04 authority scope row not locked | `property_authority_scopes` protection | `…[authority_scope_sql]` | killed |
| B05 decision evaluated over all chains (`within=None`) | N-01: decision rests on locked rows only | `test_publication_chain_gain_race_pg.py` | killed |
| B06 accept reads without the lock | N-02: accept ordered with revoke | `test_membership_accept_race_pg.py` | killed |
| B07 accept without the INVITED re-check | N-02: a revoked row is not reactivated | `test_membership_accept_race_pg.py` | killed |

B01–B04 are the TASK-005 audit's custom mutants, which survived the TASK-004
builder suite; they are now killed by repository tests.

## TASK-004 mutants rerun — 9 / 9 killed after three harness updates

TASK-006 moved the text three mutants targeted; each was re-pointed at the
same invariant (none was weakened):

* **A05** (no protected decision): the call is now `proof = _proof(…)` /
  `_lock_proof(db, proof)`; both lines are replaced by `return`. Killed.
* **A06 / A07** (organisation / legal-party status ignored): the proof query
  checks the status too, and the decision now sees only proof rows, so
  removing only the `_chains` copy refuses with 409 instead of publishing. The
  mutants remove the status from both places, and are judged on the
  publication outcome (`test_no_invalid_chain_passes_the_protected_decision`
  `[suspended_org]` / `[inactive_party]`) rather than on `can_act`, which
  shares the mutated code (a TASK-005 observation). Killed.
* **A08** (request clock): the decision is now the `protected` evaluation.
  Killed.

A01–A04 and A09 unchanged, killed.

## TASK-002 subset rerun — 4 / 4 killed

M03 (publish without Property lock), M04 (no protected re-check), M05
(unconditional status write), M19 (compound: revoke without Property lock and
without the authority FOR SHARE). The other sixteen TASK-002 mutants target
code TASK-006 does not touch and were not rerun.

What this does not show: that every alternative implementation of the
restricted decision would be caught — only that removing it, or any of the
four row locks, or either half of the accept repair, is.
