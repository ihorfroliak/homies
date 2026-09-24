# TASK-002 — mutation evidence

Harness: [`backend/scripts/mutation/task002_mutants.py`](../../backend/scripts/mutation/task002_mutants.py).
Run 2026-09-24 against `58a4c5c` (R4 head, code identical to the handoff
SHA), local PostgreSQL 16 / PostGIS 3.4 test container, Python 3.14 venv.

Rules: each mutant is one exact textual replacement; its tests first run
green on the unmutated tree (baseline); the mutant counts as **killed** only
when pytest exits 1 with failures and no errors; the original bytes are
restored and verified by SHA-256 after every mutant. Migration mutants take
effect because the PostgreSQL test session rebuilds its schema from the
migrations.

| Mutant | Invariant challenged | Baseline | With mutant | Verdict |
|---|---|---|---|---|
| M01 legacy router in Phase-1 composition | legacy runtime isolation (routes) | 25 passed | 1 failed | killed |
| M02 booking-expiry worker in Phase-1 composition | legacy runtime isolation (workers) | 25 passed | 1 failed | killed |
| M03 coordination lock without FOR UPDATE | publication/revoke serialisation | 6 passed | 1 failed | killed |
| M04 publish without re-check under the lock | publication/revoke serialisation | 6 passed | 1 failed | killed |
| M05 publish status UPDATE unconditional | publication CAS | 1 passed | 1 failed | killed |
| M06 reveal without the viewer lock | contact quota serialisation | 1 passed | 1 failed | killed |
| M07 viewing: no re-lock, unconditional UPDATE | viewing state CAS | 1 passed | 1 failed | killed |
| M08 migration without `ck_viewings_cancelled_state` | viewing state (DB backstop) | 1 passed | 1 failed | killed |
| M09 conversation start without the sender lock | conversation serialisation | 2 passed | 1 failed | killed |
| M10 conversation index not UNIQUE | conversation uniqueness (DB) | 1 passed | 1 failed | killed |
| M11 latitude range removed from the API | coordinate range (API) | 33 passed | 1 failed | killed |
| M12 latitude CHECK widened to ±900 | coordinate range (DB) | 8 passed | 1 failed | killed |
| M13 re-encode keeps the source `info` | media metadata normalisation | 61 passed | 1 failed | killed |
| M14 original bytes stored instead of re-encoded | media metadata normalisation | 61 passed | 1 failed | killed |
| M15 body limit checked after reading everything | streaming body bound | 16 passed | 1 failed | killed |
| M16 no fold/offset uniqueness check | DST validity | 21 passed | 1 failed | killed |
| M17 no real-local-end check | slot inside its local window | 21 passed | 1 failed | killed |
| M18 price CHECK weakened to `>= -999` | negative price CHECK | 1 passed | 1 failed | killed |
| M19 revoke without the coordination lock | revoke side of serialisation | 1 passed | 1 failed | killed |
| M20 quarantined files treated as servable | old C8 bytes never served | 16 passed | 1 failed | killed |

**20 / 20 killed, 0 survived, 0 invalid.** Runs use `-x`, so "1 failed" is
the first failing assertion, not the count of tests that would fail.

M18 is the TASK-001 §13 case: the pre-TASK-002 version of that test passed
with this exact mutation.

What this does not show: that the tests catch every possible regression in
these contexts, or anything about code outside the twenty mutated lines.
