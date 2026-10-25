# AGENT-002 independent repair addendum

Date: 2026-10-17. Exact candidate: ff972255587d4737604073993dd88278e1af1c07.
Tree: a50eedd5985da67f3d7e9e4433baffa1d167f1bc.
Prior reviewed candidate: 7d8e0923f31ac568e93cc9dff99049bd4d70545e.
Worktree: C:/Users/ihorf/.codex/worktrees/delivery002-agent002-repair-audit/homies.

Verdict: PASS for the focused A-01/A-02 repair and original bounded review, read together. Both prior P2 findings CLOSED at this exact SHA. P0/P1/P2/P3 open findings: 0. No canonical decision required. No merge, runtime-delegation or production-readiness approval.

Scope: the six-file repair diff, causal ownership/recovery regression tests, adjusted Draft payload caller and repair documentation. The original report remains immutable; no broad audit repeated.

A-01 CLOSED: delivery_policy.py:170-173 includes unresolved .busy markers in active contexts for planning and acquisition. Acquisition at 201-203 uses the same exclusive operation marker as release. A marker present after a stale selection snapshot therefore still blocks claim creation. Focused regressions exercise orphan markers, release paused after claim removal, stale selection and preservation of the unresolved marker. The independent original orphan-marker probe now rejects acquire with 'task is not next authorized unblocked work'; no claim is created and the marker remains.

A-02 CLOSED: owned at 211-212 now binds saved claim branch, supplied task branch and actual Git branch. resume at 284 also checks the saved checkpoint against ownership. Draft preparation at 292-297 now takes root/owner, validates ownership and clean exact candidate HEAD, with CLI/docs updated. The independent probe now rejects changed branch metadata at checkpoint, resume and Draft preparation with 'writer branch changed'; the prior checkpoint remains byte-identical and normal resume still works. Tests also reject changed saved branch metadata. No intentional branch transfer is silently accepted.

Independently executed on Python 3.14.3:
python -B -m unittest discover -s docs/engineering -p test_delivery_policy.py -v
Result: 26 passed in 41.762s, including preservation of all twelve specialists and AGENT-001 settings/hooks/config, prior gates and the new repair cases. Fixtures are disposable synthetic Git repositories.

Executed external agent002_repair_independent_probes.py against this candidate: A-01 rejected; A-02 checkpoint/resume/draft each rejected; checkpoint_preserved true. This repeats the causal independent reproduction as an expected rejection without modifying candidate source.

Focused Ruff on delivery_policy.py and test_delivery_policy.py in the isolated Python 3.12 test image: All checks passed (same invocation also checked BP-3's changed Python files). Candidate engineering source mounted read-only and container networking disabled.
Git confirmed exact HEAD/tree, empty status and detached HEAD. No candidate edits, commits, pushes, shared live ownership claims or application databases touched.

Limits: no native Claude/Codex role invocation, authentication, Linux CI, model dispatch or remote GitHub evidence was verified. Native-role invocation/delegation remains NOT VERIFIED; performance/token/context savings remain NOT MEASURED. This still coordinates cooperating worktrees sharing one Git common directory, not independent clones/hosts, and evidence remains trusted operator attestation. Live GitHub identity/CI and founder merge authorization are separate gates. No broader production or repository audit implied.
