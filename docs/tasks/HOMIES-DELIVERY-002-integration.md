# HOMIES — founder-authorized integration contract, 2026-10-24

Status: AUTHORIZED by direct founder confirmation on 2026-10-24 (D-114). Implementation integration executed on 2026-10-24/25; final documentation reconciliation is delivered through PR10. Exact receipts and current status: [PROJECT-STATUS](../PROJECT-STATUS.md#delivery-integration--2026-10-25).

Starting main (before authorized integration): 4ed8fe8ab334a8d8e344b80e266da2be3b661aee; tree b29e0ceac644c026ecaa3d3e5dd01cc625b27f27.

Reviewed candidate identities:
| PR | Context | Candidate |
|---|---|---|
|18|DEP-001|289b816d76757ced905bc565e548170bd461d830|
|11|BP-3|55c9d43d218b9fa749789348adeccc59306fe9ea|
|12|AGENT-002|ff972255587d4737604073993dd88278e1af1c07|
|13|BP-9|fb5b3e57a6e4881ab14ad378a15e15f49475e682|
|14|BP-11|e3841a638b4cc54bba10b2caed29569aaffd54e5|
|15|BP-4|2fc30a28939c7d8b8a5b6f62a71a920ad444d693|
|16|Backend composition|ee19b3affc9f33d560c7624ebc6b562276c56000|
|17|FE-003 including DEP-001|c831ea616a6fe022b08b4fba106761a9d4c6cdd1|
|10|Program documentation/report archive|d373a8a3ebc55ef38607caacf60054c83887ddf5|

Authorized execution:
1. Integrate DEP-001 PR18 first, after rechecking exact head, review, six required checks, base identity and mergeability; transition Draft to ready as needed, normal GitHub merge commit only. Verify actual main SHA, original candidate ancestry and post-merge checks.
2. Refresh the remaining feature branches against that verified main in their own worktrees, using normal merges and preserving all reviewed candidate ancestry. Re-run required CI for changed combined heads; do not use historical CI as a current-base exemption.
3. Integrate BP-3/BP-11/BP-9 and AGENT-002, then BP-4, respecting actual dependencies and green current-base checks. Retarget stacked PRs to main only after their prerequisite commits are integrated. If a composition PR has become entirely included, verify ancestry and tree differences and record that incorporation instead of manufacturing an empty merge.
4. Integrate FE-003 only after every backend prerequisite and DEP-001 is present, exact combined checks pass and any changed implementation has appropriate independent delta review. Existing unchanged review evidence is reused; no new general audit.
5. Integrate the documentation archive after reconciling status with actual merge SHAs, retaining byte-exact reports/hashes, accepted limitations and all debt. Verify each included candidate is an ancestor of main and required post-merge checks pass.

Scope boundaries: no squash, rebase, force push, branch-protection bypass, production deployment, paid providers, new product semantics or FE-VIS-001. A material conflict/defect or semantic change is reported and resolved within existing bounded authorization or returned to the founder if outside it. Do not treat approval of integration as approval of production or external beta.

Retained limitations: IBB-001 remains the last formal backend baseline; BARRIER/rollback BLOCKED; existing beta gates and technical debt remain; native vendor invocation for AGENT-002 remains NOT VERIFIED; all independent nonblocking notes and unknown-cause fixture errors remain documented. The documentation branch originally retained main's old dependency pins. It now includes the integrated DEP-001 repair and FE-003 main, and still requires its own exact-candidate CI; FE-003's result is not substituted for it.

Successful completion means the founder-approved candidates are integrated through normal protected GitHub flow, evidence is durable and current, and no deployment occurred.
