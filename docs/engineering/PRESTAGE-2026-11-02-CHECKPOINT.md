# Pre-staging checkpoint — 2026-11-02

Historical handoff snapshot, not a replacement for PROJECT-STATUS or live GitHub check results. Founder requests gradual repairs, design fidelity, durable context and an explanation of integration before future Phase1A staging. No new main merge or staging deployment authorized. Do not reopen HOMIES-DELIVERY-002 or repeat foundation audits.

## Integration state

Remote main verified by ls-remote:4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4. IBB-001 remains5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98. Main contains the accepted delivery002 package. Local branch inventory against that exact remote SHA:85 total;73 tips already ancestors;12 tips not ancestors. Local refs/heads/main is stale at be150da11b9838409fcf8ee2d8ca4bd8b0311307; an initial45/40count against that obsolete pointer was incorrect for current integration and is superseded. These counts are not a count of missing features or approval to merge historical branches. Classify/reconcile them before cleanup; delete none on inference.

| Candidate | Exact snapshot | Disposition |
|---|---|---|
| PR20, codex/design-001c-integration | 7941c396859dc9a36bb7822ca10bf11f8d5a5be5 | Draft; frontend source review at4f33466, unchanged frontend tree;211localtests/build/lint/types and real browser smoke passed. Web CI passed. Backend CI41379937827:2098passed/1failed/2skipped; investigate21-day cutoff map-count test, not presumed flaky. |
| PR23, codex/prestage-ci-pg16 | f0d163e0cbab1b90493f04480c5224e02391116a | Draft; source-reviewed PG16 client/Ubuntu24.04 repair; CI41378926059:2099backend tests and10restore drills passed, dependency audit failed; overall CI notgreen. |
| PRESTAGE-API-001, codex/prestage-window-range | Child of PR23; exact candidate resolved from Git/PR | Two-line validity validator,12new cases; original500 reproduced twice;90viewing/DST tests,ruff,mypy128passed; exact-SHA review/fullCI required. |
| PR21 | dfe5f7c110ef68868cfad0b9e96b2fc4995475b4 | Dependabot4Actions updates; not accepted. |
| PR22 | c44c33e1f437bf79291e07359e76a0ae67be8151 | Dependabot27backend updates; not accepted; do not blindly merge the group. |

PR23 ancestry is already incorporated into PR20's feature branch. API repair also descends from PR23. This is feature-branch convergence, not main integration. Candidate review receipts are under docs/reviews on PR20. No new formal backend baseline.

## Known immediate gates

1. Security dependency findings: dnspython2.8.0 GHSA-45c3-73f7-pv4m (fixed2.9.0), msgpack1.2.2 GHSA-j586-36cw-2gc2 (fixed1.2.3), from actual CI. Existing local branch claude/CI-PG16-CLIENT already holds exactly these two pin updates at5b410c13708ac987676f71e6dba16a12d75b2eb2 (2026-10-31), plus two antecedent CI/tool-contract commits. Inspect and reuse its verified work rather than duplicating it. It is not in remote main; runtime/independent evidence still needs reconciliation. Do not suppress the dependency audit.
2. Investigate PR20's map cutoff failure at test_search_validation_pg.py:173 (expected2/2/0, got1/1/0); same backend passed in PR23. Evidence is insufficient to label it a product defect or flake.
3. Finish API candidate review/CI; combine only verified commits and obtain a concrete integration decision. Preserve ancestry and branch protection; merge is separate from deployment.
4. Design remains partial: source Home Mapa composition and logo integrated, real four-area synthetic data used. Licensed geometry/geography decision, final fonts/palette, synchronized controls and mobile navigation refinement remain. Do not claim1:1parity.

## Local access and staging boundary

Last observed preview http://localhost:3001/healthz200 and backend http://127.0.0.1:8000/readyz200. Preview uses existing disposable homies_alpha_e2e; no reseed or real providers. Main alpha port3000 was not modified. Preview source worktree homies-design-001c; active API repair worktree homies-prestage-ci reused after the CI branch was clean. Do not modify the founder's shared checkout.

Phase1A closed staging can use synthetic verified accounts and disabled external providers. It does not require Phase1B sales, Phase1.5 broad owner/agency OS, Phase2 contracts/payments/deposits or Phase3 short stay. Before calling staging ready: accepted combined mainSHA/green checks, isolated access-restricted host, TLS/separate secrets and database, safe migration and restore rehearsal, then requester-to-provider journey on that actual environment. Hosting and deployment are not yet authorized. External beta/production remainNOTREADY/NOTDEPLOYED; existing security/privacy/operational debts remain, including BARRIER/rollbackBLOCKED.

Working web seeker/provider surfaces exist; admin backend functionality is not a complete admin UI; native iOS/Android apps are not delivered. Preserve this distinction in founder reports.


## Later same-day integration authorization — supersedes prior open gates

Founder now authorizes merging ready verified work into main. PR23 merged as f3385f91c1b339bee529b751ab27782c54325c15 (candidate7c67a43, CI41422655013 SUCCESS6/6). PR24 retargeted to main and merged as a44d0b26f42834c9c8f493d54aa0f20edfd9e82b (candidatec7febf7, CI41422708063 SUCCESS6/6). CI dependency audit/canary and restore gates passed. Both old CI blockers resolved without weakening production freshness or removing checks. Local ordered PG93passed; source receipt a2c7d6e is durable.

Design candidate48c2e3c passed CI41422734006 SUCCESS6/6 and was refreshed with accepted main in51f2c89. Frontend tree unchanged; new final CI required for the combined version before PR20 merge. Actual final head/merge and CI are GitHub evidence, not reconstructed from this pre-merge checkpoint. Repository PROJECT-STATUS owns current status. No deployment or automatic acceptance of PR21/22. Preserve remaining design parity work and staging gates; do not restart delivery002 or repeat completed audits.
