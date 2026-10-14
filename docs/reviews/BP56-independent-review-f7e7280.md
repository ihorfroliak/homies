# Independent BP-5 / BP-6 exact-SHA review

Date: 2026-10-12. Reviewer: separate Codex reviewer context, not the implementation writer.

- Audited commit: `f7e7280ba2afdc8ea1c467499b9a28b5a08972ed`.
- Tree: `b24737acc7e610b63d9cb230683435cb8d6b4df3`.
- Base: `74a7065e167e6cea8d4251a17138ffe775b02a54`.
- Own isolated checkout: `C:/Users/ihorf/.codex/worktrees/bp56-independent-review/homies`.
- HEAD/tree and clean status verified before and after source review. No product files, commits, pushes, merges, deployment or production resources changed by this reviewer.

## Verdict at this SHA

**REQUIRES BOUNDED TEST CORRECTION.** One P2 verification finding covers four reproducible obsolete regression assertions. No new product implementation defect established in the bounded review. Do not call the exact candidate green until those tests are corrected and required candidate checks pass. A subsequent test-only correction can receive a bounded exact-SHA addendum; unchanged implementation does not require another general audit.

The founder retains final acceptance and separate new-PR merge authority. This report grants neither deployment readiness nor merge authorization.

## Authority and scope

Read the checkout AGENTS.md, 00-AUTHORITY, governance 05 sections 9/10, D-104/D-105/D-110, 04a section 24, the approved BP-5/BP-6 task contract, relevant FE-003 cancellation and BP-9 dispositions, and release/migration policy section 2. The attached final founder authorization explicitly permits the temporary writer and requires this separate exact-SHA review. Existing BP-10/AGENT-001 audit programs were not repeated.

Inspected the complete implementation delta: migration/model guards, cancellation writes and API projection, moderation effects/lock ordering, neutral notices, release metadata, generated contract changes and relevant tests. Checked all application Viewing cancellation writers. Relevant unchanged helpers were read to understand authority, database time, event identity and lock evidence.

## P2 MEDIUM — reconcile required regressions with the new guards and lock order

**Locations:** `backend/tests/test_engagement_safety_pg.py:232`, `:263`, `:815` (failing assertion `:831`); `backend/tests/test_concurrency_r4_pg.py:170`.

**Invariant / contract:** BP-5/BP-6 verification gates require relevant PostgreSQL regressions to pass and concurrency tests to demonstrate real blocking and committed final states. BP-6 intentionally takes the listing lock before the conversation, and BP-5 adds a second CHECK that rejects inconsistent cancelled states.

**Executed evidence:** The bounded PostgreSQL regression command below completed with **65 passed, 3 failed**. `test_e_r1c_continuing_a_thread_waits_for_its_closure_and_is_barred` and `test_e_r2_two_moderators_restrict_once` still require a blocked query on `conversations`; `_blocked_on(...)` returned false because the new restriction lock serializes the contender at `classified_offers` first. `test_f6b_a_restriction_in_flight_neither_blocks_the_request_nor_is_bypassed_after` deliberately withholds the restriction commit while expecting the request to finish successfully. It received `OperationalError / LockNotAvailable`, with PostgreSQL reporting a lock timeout on `classified_offers`, instead of its expected viewing ID.

A separate independent reproduction of `test_no_viewing_is_ever_confirmed_with_a_cancellation_time` failed at line 170: SQLSTATE was correctly `23514`, but PostgreSQL named `ck_viewings_cancellation_source_state` rather than the asserted `ck_viewings_cancelled_state`. The attempted contradictory state was rejected; this is not evidence of an invalid persisted state.

**Expected:** Observe the actual listing wait, release the first transaction, then assert the final restriction/refusal and single-effect states. Invalid cancellation shape must be rejected without depending on which of two applicable CHECKs PostgreSQL reports first.

**Suggested repair:** Update only these stale assertions/schedules. Preserve blocker-PID observation, committed final-state and duplicate-effect checks; release/rollback and join all workers in finally paths. For the overlapping CHECK test, accept the applicable named guard and inspect the unchanged persisted row; independently exercise the original timestamp CHECK using a non-cancelled row with NULL source if distinct coverage is retained. Do not weaken the new production locks or constraints.

**Canonical decision required:** No. The approved contract already determines the desired behavior. This finding concerns verification completeness, not a newly discovered contradiction in product semantics.

## NOTE — inherited BP-9 gate also covers the new provider notice surface

**Location:** `backend/app/modules/trust/notices.py:110`, through `backend/app/modules/properties/authority.py:209`.

**Evidence:** Provider recipients come from `authority.holders(..., "MANAGE_VIEWINGS")`. That existing helper evaluates the three in-force authority chains but does not filter the root PropertyAuthority to VERIFIED. The existing private engagement paths similarly retain their explicitly deferred BP-9 verification debt.

**Rule / disposition:** D-105 / 04a section 24 and FE-003 section 3.9 require verified private-engagement authority before provider beta; BP-9 / BB-10 is expressly deferred by the current bounded authorization. This is recorded as an inherited dependency, not a demand to expand BP-5/BP-6 into an unrelated authorization rewrite.

**Expected / suggested follow-up:** Include provider cancellation notices in BP-9 recipient authorization coverage, including personal, organizational and representation chains and unverified-root refusal. Preserve BB-10 until implemented and independently verified.

**Canonical decision required:** No; rule already decided. No additional P0/P1/P2/P3 product defect established. Optional enhancements are not promoted to blockers.

## Executed independent verification

All repository mounts were read-only, containers had `--read-only --tmpfs /tmp`, and pytest cache writes were disabled. Tests used synthetic fixtures only. A new reviewer-only PostGIS container `homies-bp56-review-20261012` was created with tmpfs PGDATA. Port 55557 could not bind due to Windows socket permission/reservation, so Docker assigned **127.0.0.1:60116**. The parent's port 55556 database and existing port 5432 database were never connected to or mutated.

Observed runtime: Python 3.12.15, PostgreSQL 16.4, PostGIS 3.4.3, pg_dump 16.15. Test image `bp10c-test:c385136`, image ID `sha256:86026a4e11a8589ddbd331ff5ddbf8491bebe398c38b76c812ebf5cc981cb23a`.

Common test invocation: Docker image above, `-v C:/Users/ihorf/.codex/worktrees/bp56-independent-review/homies:/repo:ro -w /repo/backend`, `PYTHONPATH=/repo/backend`, `DATABASE_URL=sqlite://`, and reviewer-only `TEST_DATABASE_URL` pointing to host.docker.internal:60116 with synthetic user/database `bp56review`. Command entrypoint: `python -m pytest -q -p no:cacheprovider`.

1. **106 passed, 1 warning, 97.62 seconds.** Modules: `tests/test_bp5_cancellation_source.py`, `tests/test_bp5_cancellation_source_pg.py`, `tests/test_bp6_restriction.py`, `tests/test_bp6_restriction_pg.py`, `tests/test_release_manifest.py`, `tests/test_schema_compat.py`, `tests/test_tst01_openapi_contract.py`.
2. **65 passed, 3 failed, 1 warning, 543.32 seconds.** Modules: `tests/test_dr_restore_phase1_pg.py`, `tests/test_viewings_pg.py`, `tests/test_engagement_safety_pg.py`, `tests/test_release_pg.py`, `tests/test_td01_migrations.py`. `HOMIES_REQUIRE_RESTORE_DRILL=1` was set; actual pg_dump/pg_restore drill executed. The three failures are the P2 finding above.
3. **2 passed, 1 warning, 24.27 seconds.** Independently authored semantic probes in adjacent `test_independent_bp56_probe.py`, mounted read-only at `/review`, pytest target `/review/test_independent_bp56_probe.py`, separate synthetic database `bp56probe` in the same reviewer-only container. A structurally otherwise valid cancellation with source UNKNOWN was rejected specifically by `ck_viewings_cancelled_by`; an actor who was simultaneously requester and current provider persisted REQUESTER and emitted exactly one REQUESTER cancellation fact. The second probe used explicitly synthetic historical role state, not a claim about an allowed self-request flow.
4. **1 failed, 1 warning, 15.55 seconds.** Isolated command `python -m pytest -q --tb=short -p no:cacheprovider tests/test_concurrency_r4_pg.py::test_no_viewing_is_ever_confirmed_with_a_cancellation_time`, separate reviewer database `bp56probe`. Failure exactly as recorded above.
5. **Ruff clean:** `python -m ruff check --no-cache app tests alembic/versions/23e89acb98b4_viewing_cancellation_source.py`.
6. **mypy clean, 126 source files:** `python -m mypy --cache-dir /tmp/mypy-cache app`. It emitted the existing notes that untyped function bodies are not checked in three worker modules.
7. **git diff --check clean:** base-to-audited-HEAD comparison.

The pytest warning was Starlette's existing httpx TestClient deprecation. No mutation-kill claim is made.

## What the evidence demonstrates and its limits

The new tests actually ran all eight PostgreSQL orderings against confirm, request, requester cancellation and provider cancellation. Their paused-before-commit harness and `pg_blocking_pids` observation are meaningful lock evidence; final status/source, fact decision ID, timestamp and notice assertions go beyond thread completion order. Strict microsecond equality, unrelated requester/listing and terminal isolation, rollback, repeat refusal without duplicate effects, cross-generation cleanup and the separately preserved F6 gate were exercised.

BP-5 tests exercised actor persistence, compatibility projections, old-writer rejection, immutable source/legacy guards, authoritative/missing/malformed/conflicting historical evidence, and non-destructive development round trips. The actual restore drill verified persisted REQUESTER attribution and restored rejection guards; this report does not claim every historical/source variant was separately seeded into the restore drill. BARRIER/BLOCKED is consistent with the reproduced previous-writer failure and preserves the historical BP-10 metadata.

The neutral notice tests check exact allowed data keys and absence of private moderation reason/explanation through the API. They do not resolve the explicitly deferred BP-9 gate.

This reviewer did not run the entire repository suite, frontend generation/typecheck, remote CI, production-volume migration/restore, or production operations. Builder results and later CI must remain separately attributed. The exact commit has known failing regressions until the P2 correction is verified. No score or unconditional acceptance is implied.
