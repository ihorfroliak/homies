# PRESTAGE-API-001 — viewing-window validity range

Founder authorization: 2026-11-02, gradual closure of identified audit gaps before future staging. Primary writer Codex; isolated branch codex/prestage-window-range based on CI repair f0d163e0cbab1b90493f04480c5224e02391116a (main ancestor4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4).

R1 bounded input validation: WindowIn currently accepts valid_until earlier than valid_from although ck_viewing_windows_validity rejects it. Reproduced with the actual request model on Python3.12 in a network-disabled, read-only-source container: 2026-12-10 to2026-12-01 accepted. API500 consequence must be tested, not inferred as an executed result.

Require422 before persistence for an inverted pair, for both WEEKLY and ONE_OFF. Preserve inclusive equal-day validity and either/both missing bounds. Match the existing DB constraint; no migration, scheduling, authority, locking, slots, privacy or canonical semantics change. No database-constraint weakening.

Acceptance: negative API regression fails on original implementation; repaired API returns422 with no row and a subsequent valid write works; allowed bounds persist unchanged. Run relevant viewings/DST regressions, lint/typecheck and required CI. Separate backend source review. Disposable synthetic test data only; no alpha/shared DB use. Draft PR only; no merge or deployment.

## Executed evidence — 2026-11-02

Original implementation: both new inverted-range API cases failed with actual HTTP500 instead of422, caused by ck_viewing_windows_validity. This was exercised through the real FastAPI test application with synthetic SQLite data, not an inferred result.

Repair: two-line request validator aligns with the existing database constraint. Relevant suites test_viewings.py and test_viewing_dst.py:90passed (including12 new parametrized cases). Ruff passed; mypy passed all128 source files. Python3.12 disposable container, no network, read-only source mount, in-memory SQLite fixtures. No shared database accessed. PostgreSQL and full CI must be recorded separately; they were not executed locally for this delta.

Inherited integration blockers: PR23 CI41378926059 passed2099 backend tests and10 restore drills, then rejected dnspython2.8.0 and msgpack1.2.2 in the security dependency audit. PR20 CI41379937827 separately failed test_the_21_day_cutoff_applies_to_the_map_counts. Neither failure is waived or repaired in this bounded API change.
