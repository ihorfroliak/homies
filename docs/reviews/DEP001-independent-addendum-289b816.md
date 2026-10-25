# DEP-001 independent focused filelock addendum

Date: 2026-10-24. Reviewer: independent read-only Codex review agent; not the writer.

Exact candidate: `289b816d76757ced905bc565e548170bd461d830`.
Tree: `e832526908e56b9d2060aee90ee8ae527bac17d9`.
Reviewed predecessor: `47b1be51002f6b28764a15cef12cf8d1b4bcec8a`.
Own detached review checkout: `C:/Users/ihorf/.codex/worktrees/dep001-filelock-review/homies`.
Draft PR: https://github.com/ihorfroliak/homies/pull/18.

## Disposition

Focused independent delta review complete. No introduced P0 CRITICAL, P1 HIGH, P2 MEDIUM or P3 LOW finding was substantiated. No canonical decision is required. The filelock extension passes the independent checks described below. Required exact-candidate full CI and rebuilt-image validation remain separate coordinator acceptance gates. This addendum authorizes neither a main merge nor deployment.

This report supplements, and does not rewrite, `DEP001-independent-review-47b1be5.md` (SHA-256 `b3420c0293b2807b0e37672ba05856ab25df01965035d3705a418f39001efc05`). That report's NOTE N1 remains: 80 media cases passed and one fixture setup errored; the unchanged targeted case subsequently passed with classified creation HTTP 201. Its original failing response was not captured and cause remains unknown. The contract's phrase “environment NOTE” is not a causal conclusion. No media tests or general application re-audit were repeated for this extension.

## Exact scope and authority

The founder-authorized extension is recorded in `docs/tasks/DEP-001-security-refresh.md:17-25`, under the authority hierarchy and independent review requirements already inspected in the original review. Compared with the reviewed predecessor, the entire diff consists of:

- `backend/constraints.txt:24`: filelock 4.0.5 to 4.2.1.
- Ten added contract lines recording the narrow approval, prior CI result, focused evidence and retained review limitation.

No application source, migration, media sanitizer, other package pin, audit suppression, canary logic or CI configuration changed. All constraint lines match the builder's metadata-regenerated `constraints.filelock-candidate.txt`; newline byte equivalence is not claimed. Final Git identity remained the exact SHA above, status was clean and diff-check passed. The review created its own detached worktree because the previous reviewer path was unavailable; the writer's checkout was not used.

## Independent checks actually executed

A disposable Linux container used cached image `homies-dep001-py312@sha256:1e56ae8c7fd60f35cfecfbfbafb3627680bb9d1c3b51f5113f7baea2be2ee354`, with the entire exact candidate mounted read-only. Evidence and temporary cache/lock files were outside the source. Network access was used only for the approved package installation and public dependency advisory lookups. No application service, PostgreSQL database, production data or external target was exercised.

This was an ephemeral installation into the old verified image, not an independent test of the newly rebuilt image. The probe first checked all 70 predecessor pins, then installed only `filelock==4.2.1` with `--no-deps --only-binary=:all:`. It compared complete installed distribution metadata before and after and asserted the sole change was filelock 4.0.5 to 4.2.1.

| Check | Reviewer result |
|---|---|
| Supported interpreter | Python 3.12.15 |
| filelock metadata compatibility | Requires-Python >=3.11; current interpreter satisfies it |
| Candidate constraint matching | All 70 pins exact; no missing or changed unrelated package; only extra package pip 25.0.1 |
| pip check | PASS, no broken requirements |
| FileLock cross-process exclusion | PASS: child process times out while parent holds lock |
| FileLock release | PASS: child process acquires after parent releases |
| CacheControl FileCache | PASS: missing key, set/get, replace/get and delete/missing-key semantics |
| Exact candidate dependency audit | PASS: all 70 pins audited, zero vulnerable packages in JSON, filelock 4.2.1 present |
| Positive audit canary | PASS: unchanged repository canary detects urllib3 1.26.4 as vulnerable; underlying audit exit 1, wrapper exit 0; 11 known vulnerabilities reported |
| Final checkout identity/status/diff-check | PASS |

The deliberately vulnerable canary pin was queried, never installed. The audit used `python -m pip_audit -r /repo/backend/constraints.txt --no-deps --disable-pip --progress-spinner off -f json`. The canary used the unchanged `backend/scripts/ci/audit_canary.py` and `ops/ci/pip-audit-canary.pins` from this exact candidate. Thus an audit that silently fails to query advisory data is not being accepted as green.

## Consumer and security compatibility assessment

A repository search found no direct application filelock import. Installed package metadata identifies CacheControl's optional filecache requirement as `filelock>=3.8.0`; the approved version satisfies it. The focused test exercises the actual CacheControl file-cache implementation and a genuine second process contending for a FileLock. These assertions would fail if exclusion, release or cache persistence behavior broke. They are compatibility checks, not exploit reproductions or comprehensive concurrency fuzzing.

The upstream package release declares Python >=3.11 and a platform-independent wheel, consistent with the observed Python 3.12 runtime. [filelock 4.2.1 release](https://pypi.org/project/filelock/4.2.1/).

Each of the three reported advisory records identifies 4.2.1 as patched: [GHSA-v4x8-3wr5-3wq8](https://github.com/advisories/GHSA-v4x8-3wr5-3wq8), [GHSA-9vhv-jxww-xfm5](https://github.com/advisories/GHSA-9vhv-jxww-xfm5), [GHSA-567q-5qvw-pf92](https://github.com/advisories/GHSA-567q-5qvw-pf92). The records concern local shared-directory locking behavior, including SQLite-backed reader/writer locks and Windows soft locks. Version remediation is supported by those records and the fresh exact-pin audit. No platform-specific exploit reproduction, package provenance verification or supply-chain certification is claimed.

## Retained limits and evidence

Prior CI run 40069367584 at 47b1be5 is recorded by the contract/coordinator as 1992 backend tests passed with one skip, 10 restore tests passed and five other successful jobs, but failed on three filelock advisories. Those numbers are not checks executed by this reviewer and are not results for 289b816. The coordinator remains responsible for the new exact-SHA full CI, rebuilt image and combined FE-003 integration CI before the authorized normal branch integration.

Reviewer-owned evidence is in `../dep001-289b816/`: probe.py, results.json, installed-versions.json and separate installation, pip-check, dependency-audit and audit-canary stdout/stderr. The JSON audit and installed metadata are retained. A SHA-256 evidence manifest accompanies this immutable report. The original report and its evidence remain unchanged.

No source repair, commit, push, branch integration, deployment or production mutation was performed by this reviewer. No new optional improvement is proposed. Prior NOTE N1 retains its original evidence, expected fixture-success behavior and recommendation to capture the failing response if it recurs; no canonical decision is required for that NOTE.

Deployment status: NOT DEPLOYED. Main merge: NOT AUTHORIZED by this review.
