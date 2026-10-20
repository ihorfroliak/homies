# FE-003 seed repair — independent F-SEED-01 closure

Date: 2026-10-20. Reviewer: the independent `fe003_seed_independent_review` session that reproduced F-SEED-01; not the repair builder.

Exact reviewed SHA: `81ef509837eb3f1a113455f6e17343d2877f4d24`.
Tree: `eb7211c84467ee8f14586094688073fe52bbb60e`.
Direct parent: `b44e7bdbff4bf5da6b8e904bec29cc57bd16818f`.
Own pinned worktree: `C:/Users/ihorf/.codex/worktrees/fe003-seed-repair-review/homies`.

## Outcome

**PASS — F-SEED-01 CLOSED.** No remaining findings or new P0/P1/P2/P3 findings in the bounded two-file repair. No canonical decision is required.

This addendum supplements, and does not replace or modify, `FE003-seed-review-b44e7bd.md`, whose SHA-256 remains `64fafb0fedbccbf14774e58661b75c06e77e3a6675cb4731cb3f17bcdbb75d91`. All original scope limits and observations outside F-SEED-01 remain applicable. This is not a frontend acceptance, general backend re-audit, CI certification or production approval.

## Reviewed change and closure evidence

Only `backend/app/scripts/seed_engagement_e2e.py` and `backend/tests/test_seed_engagement_e2e_pg.py` differ from the reviewed parent.

- Seed lines 236–239 check each of the seven named account roles using the authenticated `/v1/me` projection. The guest provider remains a guest, while the host without authority remains a host; successful access alone no longer substitutes for this fixture distinction.
- Seed lines 248–258 explicitly check all seven scheduled listing booking modes. The exact persisted configuration is read without mutation because the public derived-slot response intentionally does not expose booking mode.
- Mismatches use the existing fail-closed `_require` mechanism before the completion message. New diagnostics contain project/key identifiers, not credentials, tokens or phone numbers. No silent repair, new output field, business rule change or guard relaxation was introduced.

The updated real-PostgreSQL regression independently executed and rejected four isolated mutations:

1. `instant`: INSTANT_BOOKING → REQUEST_APPROVAL, reproducing the earlier accepted mutation.
2. `approval`: REQUEST_APPROVAL → INSTANT_BOOKING.
3. `guest_provider`: guest → host, reproducing the earlier accepted mutation.
4. `host_without_authority`: host → guest.

For each case the test asserts nonzero seed exit with the specific mode/role refusal and confirms the changed database value remains unchanged by the verifier. The test then explicitly restores the fixture. After all restorations, another seed invocation passes with the same manifest bytes and fixture-row counts. Missing-manifest and consumed-viewing rejection remain covered by this same targeted regression.

These are causal checks against real persisted data, not assertions of the implementation's internal expected-value constants. Removing the added guards would allow seed success and fail the negative cases, matching the originally observed defect.

## Checks actually run

In cached `bp10c-test:c385136` (Python 3.12 runtime), against a new isolated disposable `postgis/postgis:16-3.4` database:

```text
python -m pytest -p no:cacheprovider -q tests/test_seed_engagement_e2e_pg.py
1 passed, 1 warning in 218.60s (0:03:38)
```

The warning is the existing Starlette/httpx TestClient deprecation. Source was mounted read-only, `PYTHONDONTWRITEBYTECODE=1`, with no external network or exposed host port. The same completed test session was recovered after a temporary approval-review usage limit; the test was not restarted and no failed runtime result was discarded.

Exact SHA, tree, direct parent and two-file delta were verified. The two reviewed worktree files match their committed Git blobs after normalizing checkout CRLF. Final `git status --short` under normal approved access returned clean; SHA was unchanged. An earlier un-escalated status command failed because of managed-worktree access; normal approved read-only verification succeeded after the temporary approval-service limit cleared.

I did not rerun the previous guard suite, Ruff, mypy, the full backend suite or CI. The original independent 13-test result remains in the parent report; builder-reported repair checks are not counted as independent runs here.

## Cleanup and unchanged boundaries

Review-owned container `homies-fe003-seed-repair-review-pg-20261020`, ID `18716e851fe3e6ae1935b764220c5f6bf90e2394d83e2382c5dc629126235de5`, was removed only after exact ID and ownership-label verification. Its data directory was temporary. The test container exited and auto-removed. Shared databases were not touched.

No repository source edits, commits, pushes, deployments, paid services or production/external targets were used. The original report is unchanged.
