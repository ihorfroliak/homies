---
name: micro-cycle
description: Run one development micro-cycle on Homies — plan, implement the smallest safe change, verify with tests and adversarial harnesses, update project state, commit, push, confirm CI. Use whenever starting or finishing a unit of work in this repository.
---

# Micro-cycle

The only sanctioned way work advances in this repo. One cycle = one small,
shippable, verified change.

## 1. PLAN
State objective, scope, files touched, risks, and the tests that will prove it.
If the change spans more than ~3 modules, split the cycle.

## 2. IMPLEMENT
Smallest safe change. Never rewrite a working subsystem to make a change
convenient. Preserve existing behaviour unless the cycle's objective is to
change it.

## 3. VERIFY (nothing is done because it compiles)
```bash
cd backend
./.venv/Scripts/python -m pytest -q            # whole suite, must be green
./.venv/Scripts/python -m ruff check app tests alembic scripts
```
If the change touches money, bookings, concurrency or the DB schema, also run
the adversarial harnesses against the live stack — they have caught real races
that unit tests missed:
```bash
./.venv/Scripts/python scripts/warfare/warfare.py      # expect all VERDICT ... PASS
./.venv/Scripts/python scripts/warfare/live_smoke.py
```
Schema changes: reset the dev DB rather than trusting `create_all` — it does
**not** add columns to existing tables (this has bitten us).

## 4. AUDIT
Security regression (does the change widen access?), financial invariants
(`/v1/admin/payments/reconciliation` must report `ok: true`), performance.

## 5. DOCUMENT
Update `docs/PROJECT_STATE.md`, append a row to `docs/BUILD_HISTORY.md`, record
any non-obvious choice in `docs/DECISIONS.md`, refresh `RELEASE.md`'s three
questions (what is proven / what still blocks / single next task).

## 6. COMMIT → PUSH → VERIFY CI
Conventional commits, English, one logical change. Push to `main`, then confirm
CI is green before starting the next cycle:
```bash
curl -s "https://api.github.com/repos/ihorfroliak/homies/actions/runs?per_page=1"
```
If a cycle fails: commit only the safe part, document the failure, never push
broken code.

## Guardrails
- Do not introduce brokers, microservices or distributed infrastructure without
  a recorded decision — pilot scale does not justify them.
- Do not weaken a proven invariant to make a feature easier.
- Every recommendation names the metric or risk it moves.
