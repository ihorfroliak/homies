# FE-003 synthetic seed — independent narrow review

Date: 2026-10-19. Reviewer: independent `fe003_seed_independent_review` session; did not build the candidate.

Exact SHA: `b44e7bdbff4bf5da6b8e904bec29cc57bd16818f`.
Tree: `c7c850c465b31798d48c9897650449c2caf08d09`.
Comparison base: `ee19b3affc9f33d560c7624ebc6b562276c56000`.
Own pinned worktree: `C:/Users/ihorf/.codex/worktrees/fe003-seed-independent-review/homies`.

## Outcome

No P0, P1 or P2 findings. One **P3 LOW fixture-validation gap**, F-SEED-01, remains below. This is a test-fixture quality defect, not evidence of a product authorization defect. The new opt-in and inherited environment/database-name guard are effective in the checked cases. The supplied targeted suite independently passed **13 tests**. No production readiness, frontend completion or full backend certification is implied.

## Scope and authority

Read AGENTS.md, canonical 00 authority and relevant governance requirements, FE-003 task contract's fixture/privacy/authority requirements, and `docs/engineering/FE-003-E2E-FIXTURES.md`. Scope is exclusively the five changed files: existing seed helper, new engagement seed, its two tests and fixture document. No unrelated completed backend audit was repeated. Source was mounted read-only for runtime checks; no source modifications, commits, pushes, deployment or external target access occurred.

## F-SEED-01 — P3 LOW: repeat validation accepts changes to promised mode and role fixtures

**Location:** `backend/app/scripts/seed_engagement_e2e.py:242`–244 (offered-slot check), 233–235 and 261–266 (account login/access checks). These checks run before the completion claim at line 332, via `verify()` at line 324.

**Violated requirement:** `docs/engineering/FE-003-E2E-FIXTURES.md` promises named approval/instant and guest-role/host-role account fixtures, and says repeated runs verify required states and reject changed fixtures. FE-003 parity requirements use authority fixtures rather than `role`. A host with authority is not equivalent evidence for the promised guest-with-authority case.

**Independent causal reproduction:**

1. On a fresh isolated migrated PostGIS database, run the supplied targeted tests. Their full seed/repeat regression passes; its last negative test intentionally changes desktop `held` viewing to DECLINED.
2. Restore only that synthetic test row to REQUESTED. Load its generated completion manifest. Call the exact candidate's `verify(api, manifest)`; baseline succeeds.
3. In the review-owned database, change desktop `instant` listing's `viewing_settings.booking_mode` from INSTANT_BOOKING to REQUEST_APPROVAL. Call `verify()` again: it succeeds. Restore the original value.
4. Change the desktop `guest_provider` user's role from guest to host. Call `verify()` again: it succeeds. Restore the original value.

Both mutations preserve the currently checked slots or authority, so validation cannot distinguish them. The newly created initial fixture was correct; the demonstrated gap concerns reuse/changed-state detection. There is no demonstrated cross-account data disclosure or application authorization bypass.

**Expected:** reject a changed named booking-mode fixture or changed promised account role before reporting the fixture set verified.

**Suggested repair:** assert the promised booking modes and role values from the real fixture state, preferably via existing authorized API projections where available; add causal negative regression tests for each case. Keep rejection fail-closed without automatic fixture repair. No new product semantics or broad seed redesign is needed.

**CANONICAL DECISION REQUIRED:** No. This enforces the existing documented fixture contract.

## Checks actually run

- Cached `bp10c-test:c385136`, image ID `sha256:86026a4e11a8589ddbd331ff5ddbf8491bebe398c38b76c812ebf5cc981cb23a`; Python 3.12 test runtime.
- Own PostgreSQL **16.4**, PostGIS **3.4.3**. Container had no external network or host port and a tmpfs data directory. Only the test runner shared this container's network namespace.
- `python -m pytest -p no:cacheprovider -q tests/test_seed_e2e_guard.py tests/test_seed_engagement_e2e.py tests/test_seed_engagement_e2e_pg.py`: **13 passed**, one existing Starlette/httpx deprecation warning, **112.04 s**.
- This independently exercises both opt-ins, explicit development ENV, database suffix rejection, pre-access refusal, actual migrations/API fixture construction, repeated seed preserving manifest bytes and fixture-row counts, original twelve default listings, separate desktop/mobile listing/conversation/viewing IDs, missing completion file refusal and consumed viewing rejection.
- Independent real-database causal probes: intact manifest verification succeeds; both F-SEED-01 mutations are incorrectly accepted; each field restored afterward.
- Independent missing-second-opt-in probe against `run()` (not just `_guard()`): refused before database client, HTTP client or output file access.
- Final explicit worktree status clean; exact SHA unchanged.

The independent probe source is retained beside this report under `seed-b44e7bd-probes/probe.py`; no administrator credentials or access tokens were written into the report. Runtime output is retained in `seed-b44e7bd-probes/results.txt`.

## Security/privacy observations and limits

The seed delegates the original three checks (opt-in, explicitly set development ENV, disposable-looking database name), then requires the second opt-in before reading/writing data or the manifest. These are configuration guards, not proof that any arbitrarily named remote database is disposable. This review connected only to its own disposable database; it did not attempt any external connection.

New accounts, names, addresses, messages, notes and phone fixtures are generated synthetic values. The verification delivery channel is captured in process; no SMS is sent. Manifest fields contain deterministic synthetic user credentials and generated fixture IDs, with no administrator credentials/token. Exclusive file creation with mode 0600 is used on Linux. The documented runner-temp/private-artifact boundary is still a caller obligation; this script does not forbid choosing a web-public output path.

Initial partial failures deliberately leave no completion marker and require a recreated disposable environment. Existing partial/mutated states are not silently deleted or repaired. Two direct fixture database edits (moving viewing times and withdrawing verification while retaining an active root) are explicitly documented; they are not historical event replay or product API evidence.

I did not independently rerun Ruff/mypy, a full backend suite, CI, browser tests, concurrent seed invocations, or failure injection at every seed step. Builder claims for those checks are not promoted to independent evidence. Test-time Docker clock stability was not certified; all stated targeted runtime checks completed successfully and no application clock defect is inferred.

## Cleanup

Owned database container `homies-fe003-seed-review-pg-20261019`, ID `3015b4eb163c41db944d6288d1332752ea3b12b5bfc3d30bf2af1dd9c4dbda40`, was removed after verifying its exact ID and ownership label. Ephemeral test/probe containers exited and auto-removed. No shared service was touched.
