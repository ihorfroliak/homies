# AGENT-002 independent bounded review

Date: 2026-10-17. Reviewer: separate Codex context; not the implementer.
Candidate: 7d8e0923f31ac568e93cc9dff99049bd4d70545e
Tree: 59e8d779646aef1c86afc2083ccf8a9d141630fa
Baseline: 4ed8fe8ab334a8d8e344b80e266da2be3b661aee
Worktree: C:/Users/ihorf/.codex/worktrees/delivery002-agent002-audit/homies
Draft PR: 12 (identity from handoff; PR state not independently queried).

## Verdict
CHANGES REQUIRED. P0: 0; P1: 0; P2: 2; P3: 0. No canonical decision required. Findings concern the bounded task's promised ownership/recovery enforcement. No product/domain semantics are reopened. No merge or deployment approval.

## P2 MEDIUM — A-01: orphan operation markers do not block new writers
File: docs/engineering/delivery_policy.py:170-195; also CLI plan at line 300.
Rule: AGENT-002 contract requires fail-closed interrupted claims; AGENT-002-DELIVERY.md, Interrupted or failed ownership operations, explicitly says a partial claim or .busy marker fails closed and requires reconciliation. Governance 05 section 3 requires explicit single-writer ownership.
Evidence/reproduction: in a disposable repository with a valid ready task and clean correct branch/base, create the context's .busy file without its .json claim (the state left if release is interrupted after line 315 unlinks the claim and before line 221 removes the marker). Call acquire. The independent probe returned owner writer-1 and left the .busy file present. acquire and plan enumerate only *.json; exclusive creation only protects the .json claim. Thus the helper dispatch gate treats unresolved ownership operation state as available. Subsequent checkpoint/resume cannot operate until someone repairs the marker, even though a new writer has already been authorized locally.
Expected: both selection and acquisition treat an unresolved .busy marker as blocked, with no new claim or writer dispatch until explicit reconciliation. Acquire must participate in the same operation lock to avoid check/create races with release.
Suggested repair: consistently account for busy markers when enumerating active contexts and serialize acquisition against the per-context operation marker (with interrupted ownership still requiring explicit reconciliation). Add a synthetic regression for interrupted release/orphan busy and a contention case covering acquire versus release.
CANONICAL DECISION REQUIRED: NO; enforce the existing bounded contract.

## P2 MEDIUM — A-02: checkpoint branch metadata is not bound to its actual writer branch
File: docs/engineering/delivery_policy.py:199-208, checkpoint at 224-257, resume at 268-276, draft_payload at 279-288.
Rule: AGENT-002 requires exact-identity recovery and Draft preparation. The delivery guide promises resume checks branch identity; governance 05 sections 4-5 require isolated worktrees and exact handoffs.
Evidence/reproduction: acquire a task on codex/TEST-001; build valid exact-head CI evidence; change only the input task branch to codex/DIFFERENT-NONEXISTENT; checkpoint, resume and draft_payload all succeed. Output: actual branch codex/TEST-001; saved and resumed branch codex/DIFFERENT-NONEXISTENT; Draft head codex/DIFFERENT-NONEXISTENT. owned compares the claim's branch against Git but never compares the supplied task branch, which checkpoint then serializes unchanged. The saved recovery artifact therefore describes a different branch from the one checked, and a later Draft payload targets that incorrect branch.
Expected: a changed branch identity is rejected before checkpoint persistence; recovered identity agrees with both the claim and actual branch. An intentional branch change requires explicit reconciliation.
Suggested repair: require claim branch == supplied task branch == actual branch; validate the saved checkpoint branch on resume as well. Add a regression that changes only task branch while leaving HEAD/tree/claim/contract unchanged and asserts rejection and preservation of the prior checkpoint.
CANONICAL DECISION REQUIRED: NO; enforce the existing identity contract. The documented operator check against live GitHub remains necessary but does not repair this local consistency defect.

## Verification actually performed
Read the contract, AGENT-002 delivery/evidence records, both new role definitions, policy and tests, operating-model/interoperability/Copilot and CI diffs; used canon 00 and governance 05. Scope stayed within AGENT-002.

Executed on Python 3.14.3:
python -B -m unittest discover -s docs/engineering -p test_delivery_policy.py -v
Result: 21 tests passed in 20.362s. These include deterministic routing, ordinary exclusive ownership across worktrees, partial JSON claims, stale evidence, independent review, operational/merge gates, stack base identity, configuration preservation and Draft-only payloads. Their green result does not cover the two probe failures above.

Executed external agent002_independent_probes.py against the candidate module. It creates/removes only disposable synthetic Git fixtures using the existing fixture setup; no candidate changes. Both defects reproduced. The probe output is retained separately. Git independently confirmed exact HEAD/tree, clean worktree and detached HEAD; symbolic-ref returned 1 as expected for detached HEAD.

The configuration-preservation tests independently verify all twelve inherited specialist files, project config, AGENT-001 settings/hooks and checks against the baseline. Each vendor has exactly seven roles. The candidate adds only one orchestrator per vendor, an existing CI job step and local tooling/docs. The helper has no network, merge, deployment or model executor.

## Evidence and runtime limits
Tests, review, CI and R3 operational evidence are bound to candidate SHA; review checks a distinct named reviewer and separate_context. Mandatory section 9 surfaces cannot bypass review by assigning R0. Merge checkpoint gates require a SHA-bound founder reference. Trusted operator attestations remain explicitly unauthenticated, and remote head/tree/CI/reviewer independence require external verification. This is not a distributed lock across hosts/clones.

No native Claude or Codex role invocation was run in this review, and no authentication was attempted. Builder claims of Claude discovery and Codex strict-config loading are not independently certified here. The committed record honestly labels actual role invocation/delegation NOT VERIFIED, provider cache synchronization absent and token/context/cycle savings NOT MEASURED. No measured runtime-success claim is upgraded by this review. No independent Ruff, Python 3.12 CI, product tests, database checks or whole-repository audit was run.

No repository files, commits, pushes, shared claims, live application databases or production resources were changed. Only the isolated review worktree was created and authorized external report/probe files written. Candidate must receive bounded fixes and a new exact-SHA review addendum before this review can pass.
