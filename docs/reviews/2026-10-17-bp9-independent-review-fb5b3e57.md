# BP-9 independent exact-SHA review — HOMIES-DELIVERY-002

Date: 2026-10-17. Reviewer: independent Codex review agent `/root/bp9_independent_review`, not the BP-9 implementer.

Verdict: **PASS_WITH_NONBLOCKING_NOTES for the bounded BP-9 candidate.** No P0, P1, P2 or P3 defect established. This is review evidence, not founder acceptance, merge authorization, production readiness or deployment authorization.

## Immutable identity and scope

- Candidate commit: `fb5b3e57a6e4881ab14ad378a15e15f49475e682`.
- Candidate tree: `92511f173a4c6c0ff6d237087be725c74793a638`.
- Comparison baseline: `4ed8fe8ab334a8d8e344b80e266da2be3b661aee`.
- Independent detached managed worktree: `C:/Users/ihorf/.codex/worktrees/bp9-independent-audit/homies`.
- Exact SHA/tree checked directly with Git before and after review. Final `git status --porcelain` empty. Source mounted read-only for all executable checks; no source edits, commits, pushes, PR creation, migrations added, deployment or production access.
- Reviewed the complete production diff in six modules: engagement/access.py, engagement/router.py, engagement/viewings.py, properties/authority.py, trust/decisions.py, trust/notices.py; both new BP-9 test modules and relevant existing helpers/callers. No broad BP-8 or BP-5/BP-6 re-audit.
- Governing sources read: AGENTS.md, canonical 00 authority, 02 section2, 04a section24, 05 including sections9/14, D-105, D-109/CX-02 and BP-10 section8, implementation-convergence dispositions, FE-003 section3.9, and `docs/tasks/BP-9-verified-engagement-authority.md`.

## Findings

| Class | Count |
|---|---:|
| P0 CRITICAL | 0 |
| P1 HIGH | 0 |
| P2 MEDIUM | 0 |
| P3 LOW | 0 |
| NOTE | 2 |

No canonical violation established within this scope.

**NOTE-01 — Retain the additional independent regression controls (optional test improvement).**

- Locations: `backend/tests/test_bp9_verified_engagement_pg.py:21`; `backend/app/modules/engagement/router.py:666` and `:686`; external `test_bp9_independent.py` supplied with this review.
- Relevant invariant: BP-9 current-side authorization after waits and rollback recovery; assignment targets must independently hold current effective MANAGE_MESSAGES authority.
- Evidence: the permanent new PG tests exercise root revocation across ten observed waits and a cached property-link replacement. Independent probes additionally exercised mandate and organization membership revocation during a conversation-row wait, target mandate revocation during assignment, and real uniqueness-error rollback recovery with valid and subsequently unverified provider authority. All passed; target revocation refused assignment with 422 and no assignment write; revoked provider actions refused with neutral 404; rollback recovery returned the existing winner only for the still-authorized positive control.
- Expected behavior: preserve those observed results under future edits. Suggested repair: optionally incorporate equivalent durable regressions when the test context is next touched. The reviewer did not edit source tests. This is evidence-retention advice, not a demonstrated product defect or acceptance blocker.
- CANONICAL DECISION REQUIRED: **NO**.

**NOTE-02 — Bounded temporal guarantee remains bounded (retained limitation).**

- Locations: `backend/app/modules/engagement/router.py:638`, `backend/app/modules/engagement/viewings.py:577`, task BP-9 scope section, BP-10 section8 DEBT-1/CX-02.
- Relevant rule: D-109 explicitly distinguishes post-wait current-side rechecks from transaction-atomic/strict commit-time authorization.
- Evidence: provider reads are gated on verified current chains; writes recheck after their explicit advisory/row waits and append rollback recovery. These checks do not lock all authority-chain rows through commit. The contract correctly says later concurrent revocation remains outside its promise. The independent tests establish the tested causal schedules, not all interleavings or strict commit-time safety.
- Expected behavior: retain the bounded description. Suggested repair: none within BP-9; any stronger protocol must be separately specified and authorized. Existing unrelated BP-10 dispositions, raw PG DETAIL limitation, BARRIER/rollback BLOCKED and production NOT READY/NOT DEPLOYED are unchanged.
- CANONICAL DECISION REQUIRED: **NO for this candidate; YES before proposing strict commit-time semantics**.

## Evidence supporting the bounded verdict

1. **Three authority chains and verification.** `engagement/access.py:26`, `router.py:594`, `viewings.py:272`, and `properties/authority.py:168` require VERIFIED roots for private provider access while retaining current scopes, dates, active legal parties, active organization membership and organization status, and active verified scoped mandates. The root requirement is not inferred from legacy host role, historical participation or assignment.
2. **Private surface coverage.** Read/thread, inbox, append/replay, assignment, stage, provider viewing reads/actions, settings/windows/blackouts use the verified provider checks. HTTP negative controls cover unverified, revoked, expired, missing-scope and unrelated actors; requester ownership remains independent and continues to allow own reads/messages/cancellation. Response refusals do not contain the seeded requester message or provider-only requester identifier.
3. **Provider participant capture.** `router.py:249` now selects a VERIFIED in-force MANAGE_MESSAGES root held by an active legal party; organization capture checks active organization status. Participant rows remain historical records and grant no independent access. The unverified-root test verifies no provider participant is captured.
4. **Current post-wait state.** `access.py:19` queries the listing property scalar; `_load` refreshes Conversation state. The permanent PG suite demonstrates ten actual waits using `pg_blocking_pids`, then commits revocation before releasing the blocker. All deny 404, preserve message/assignment/stage/viewing/settings state, and leave the database deadlock count unchanged. Cached listing/root objects do not keep former authority. Additional independent schedules cover membership/mandate loss, assignment-target loss and the confirmation listing lock.
5. **Rollback recovery and idempotency.** The independent rollback probes deliberately hide the first keyed lookup so the genuine database unique constraint fires. One control preserves authority and returns the original winner without an extra message; the other changes root verification after the real rollback and gets 404 before winner lookup. The complete selected BP-10 HTTP/PG suites passed, including T10/T12 uncertain-COMMIT controls on Linux Python3.12. No quotas/idempotency semantics changed in the production diff.
6. **Conservative guards and recipients.** `trust/decisions.py:427/:549` and own-listing checks explicitly retain `verified=False` for conflict/self-dealing refusal. Two new moderation controls passed. `trust/notices.py:110` uses verified MANAGE_VIEWINGS holders through the existing three chains. Recipient tests cover root verification/status/date/scope and independently revoked/expired/missing-scope mandates; requester recipient continuity is preserved.
7. **Change boundaries.** No schema migration or API-shape diff. OpenAPI drift passed. General property authority defaults remain unchanged; stricter verification is explicitly requested by the private engagement callers and BP-6 cancellation recipients.

## Checks actually executed

Environment: Linux Python **3.12.15**, pytest **9.1.1**, cached image `bp10c-test:c385136` with image SHA256 `86026a4e11a8589ddbd331ff5ddbf8491bebe398c38b76c812ebf5cc981cb23a`. PostgreSQL **16.4**, disposable `postgis/postgis:16-3.4` image SHA256 `44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5`.

Independent database isolation: newly created container `homies-bp9-independent-pg-20261017`, private network `homies-bp9-independent-20261017`, tmpfs data, synthetic database `bp9_independent`, no host port. TEST_DATABASE_URL pointed only at this container. The schema fixture dropped/recreated only that disposable schema. No connection to shared homies-postgres, hh-test-pg or other agents' databases. Test containers used `--rm`; the audit PG container and network were removed successfully after completion.

**Repository tests: 121 passed, 2 warnings, 180.38 seconds, exit0.** Executed from the read-only candidate backend:

```text
python -m pytest -p no:cacheprovider 
  tests/test_bp9_verified_engagement.py
  tests/test_bp9_verified_engagement_pg.py
  tests/test_bp10_message_idempotency.py
  tests/test_bp10_message_idempotency_pg.py
  tests/test_bp5_cancellation_source.py
  tests/test_bp6_restriction.py
  tests/test_bp6_restriction_pg.py
  tests/test_tst01_openapi_contract.py -q
```

This includes all **26 new BP-9 HTTP cases and 11 new BP-9 PG cases**. The selected regression suite is not claimed to be the full repository suite.

**Independent external probes: seven distinct passing cases.** Six passed in the external run (33.14 seconds); the seventh passed alone after fixing its test blocker (27.50 seconds). These are not represented as a single seven-pass invocation or a single 128-test run.

- Two causal send waits: representative mandate revoked / organization membership revoked; 404, no extra message or lead-stage update.
- Assignment target mandate revoked while authorized caller waits; 422, assignment unchanged.
- Two genuine uniqueness-error rollback controls: valid provider replays the original winner; newly unverified provider gets 404 before winner lookup.
- Confirmation blocked on listing row, root unverified before release; 404, viewing stays REQUESTED.
- Unverified provider HTTP window/blackout configuration attempts; both 404.

External probe execution requires `ENV=test`, `PYTHONPATH=/src/backend` and the isolated `TEST_DATABASE_URL` set before imports; probe file mounted read-only at `/audit/test_bp9_independent.py`. Exact probe SHA256: `10cec665d5b9e03c254be570817f3864653f200ddbe6129fcf1082c08752f465`.

Other executed checks:

- `python -m ruff check --no-cache app tests/test_bp9_verified_engagement.py tests/test_bp9_verified_engagement_pg.py`: **All checks passed**.
- `python -m mypy --cache-dir=/tmp/bp9-mypy app`: **126 source files, no issues**; existing untyped-worker-body notes remain.
- `git diff --check` baseline to candidate: **passed**.
- Final exact HEAD/tree verification and source status: **unchanged and clean**.

Warnings were dependency deprecation notices (Starlette/httpx and the older 422 constant name), not product assertion failures.

## Failed review invocations retained transparently

- A pre-limit read/diff/Docker inspection call was not executed because automatic approval review hit the account usage limit. It was resumed after reset; no safety rejection was bypassed.
- The first test invocation misspelled the BP-10 filenames; it failed before collection and contributes no test evidence.
- The first external probe invocation had seven fixture setup errors: the probe module imported application settings before conftest enabled test mode, so startup attempted container-local localhost:5433 and got connection-refused. No host or other-agent database was contacted. Runner ENV=test corrected this review harness only.
- The next external run passed six probes and failed one review blocker before the product action: selecting an eagerly joined ClassifiedOffer entity FOR UPDATE attempted to lock a nullable outer-join side. The external probe was corrected to select the scalar listing ID; its single rerun passed. Production lock_row code was unchanged.

## Limits and disposition

No full-suite, semantic mutation score, independent CI result, full transaction-atomic authority guarantee, provider beta release, production safety, restore/rollback or deployment claim. The parent separately reported exact-candidate CI run 38941516780 SUCCESS; this reviewer did not independently retrieve that remote result and does not count it as an executed check. Founder acceptance and integration remain separate governance steps. The parent's later work stacked on BP-9 was not audited here.

This report, external probes and execution/checkpoint records were written only outside the repository for parent archival under governance 05 section14. The report's SHA256 is supplied in the adjacent checksum sidecar to avoid a self-referential hash.
