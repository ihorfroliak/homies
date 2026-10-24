# FE-003 backend dependency composition — independent review

Date: 2026-10-18.
Verdict: FE003_BACKEND_COMPOSITION_REVIEW_PASS.
New composition findings: P0 CRITICAL 0; P1 HIGH 0; P2 MEDIUM 0; P3 LOW 0; NOTE 0.
This passes the bounded composition review only. Exact-candidate CI and the separate immutable BP-4 repair-review evidence remain independently required. No merge, new formal baseline or production certification is granted.

## Immutable identity and authority

Candidate ee19b3affc9f33d560c7624ebc6b562276c56000.
Tree 18a6c794d3d37c4eca63a57d4cb910c18c7048a8.
Branch codex/FE-003-backend-dependencies.
Own managed detached worktree C:/Users/ihorf/.codex/worktrees/fe003-composition-review/homies.
Task docs/tasks/FE-003-backend-dependencies.md, under HOMIES-DELIVERY-002 sections 10/12. Read current AGENTS, task and BP-4/BP-9 contracts; applied the previously read authority/governance and 04a section 24 rules. Reused completed feature review evidence, including this reviewer's BP-11 report; did not reopen feature/foundation audits.
Final HEAD/tree verified and git status --short empty. Source mounted read-only for all execution. No source edits, commits, pushes, main merges, production infrastructure, paid providers or production data actions.

## Ancestry and delta preservation

All four frozen input SHAs pass git merge-base --is-ancestor against the candidate:

- BP-9 fb5b3e57a6e4881ab14ad378a15e15f49475e682.
- BP-4 repair 2fc30a28939c7d8b8a5b6f62a71a920ad444d693, descended from BP-9.
- BP-3 repair 55c9d43d218b9fa749789348adeccc59306fe9ea.
- BP-11 e3841a638b4cc54bba10b2caed29569aaffd54e5.

Merge a2a9afaba5299b5cb89d4467cbd45afbec9752fa combines BP-4 and BP-3. Merge 210b1b04b20d7ed223477613f12b6d786b943867 adds BP-11. Independent git --remerge-diff inspection shows only docs/DEVLOG.md reconciliation in both merges; all entries are retained. Candidate ee19b3a adds only the dependency task record after those merges.

Production comparisons show no differences from the corresponding reviewed feature versions for:

- BP-4/BP-9 engagement router/access/display, property authority, trust decisions/notices.
- BP-3 properties router/schemas.
- BP-11 application composition, configuration, rate limiter, Dockerfile and environment example.

The shared backend/app/modules/engagement/viewings.py received a structural differential check. All 41 top-level function/class definitions exactly equal the expected union of the baseline and reviewed BP-4/BP-9 and BP-11 definitions. Zero conflicting definitions; zero unreviewed definition changes. The reviewer script and exact source snapshots are outside the checkout alongside this report. Direct diff inspection also covers the imports/constants not included in this AST comparison.

## Interaction findings and evidence

No canonical violation or blocking composition regression was demonstrated.

- viewings.py:241,271: provider-only requester_display_name and bulk name projection remain exactly BP-4, including repaired Unicode mark handling. They do not enter ViewingSlotsOut or requester projections.
- viewings.py:286,458,649,719,756: VERIFIED private provider gate and BP-9 post-wait rechecks remain intact. Settings update rechecks after settings-row acquisition; confirmation/decline, cancellation and outcome recheck after their waits. The five focused real-PostgreSQL revocation cases all observed the blocking schedule, refused with 404, preserved state and retained deadlock counts.
- viewings.py:351,518,554: BP-11 public derived slots remain anonymous and bounded, using the existing public eligibility rule; booking requests keep BP-9 conservative self-dealing detection and original capacity locking. The public-read/booking-write PostgreSQL race still waits and refuses occupied capacity correctly. The dedicated query-count regression and all three row-overflow refusals pass in the combined source.
- properties/router.py:798: BP-3 verified-scope enumeration remains a minimal projection and does not grant subsequent private access. Its focused enumeration suite passes with the combined authority/name code.
- Independent cross-feature HTTP check uses one engagement through all four features: provider enumeration returns only id/title/status/scope; authorized private viewings return the minimal display name; anonymous slots contain only slots/duration/timezone. After root revocation, enumeration is empty and private provider viewings return 404 without the name. Public slots remain unchanged for a still-public listing, and the requester still reads their own viewing without provider display fields. This also proves public accessibility does not accidentally inherit the private authority gate during merge.

## Actual reviewer execution

Cached Python 3.12 image bp10c-test:c385136; PostgreSQL/PostGIS postgis/postgis:16-3.4. Created only fe003-composition-review-pg-ee19, network none, tmpfs synthetic database compositionreview. Tests shared only that container's network namespace. Parent homies-fe003-deps-pg-20261017 and all other databases were untouched. Review database removed after completion; test containers used --rm.

1. Focused combined suite: 35 passed, one pre-existing Starlette/httpx deprecation warning, 32.60 seconds. Five BP-9 PostgreSQL viewing/settings post-wait revocation cases; BP-11 public read/write race, guest projection, constant query count and three row budgets; BP-4 provider projection, access-gate and fallback cases; BP-3 enumeration suite; six OpenAPI contract checks. PostgreSQL checks ran, not skipped. No failures or reruns.
2. Reviewer-authored cross-feature test: 1 passed, 2.59 seconds. Artifact test_fe003_independent_composition.py. SQLite-backed HTTP flow supplements, not replaces, the PostgreSQL checks.
3. Structural differential: 41 shared-module definitions preserved as the reviewed feature union. Artifact FE003-composition-ast.py.
4. Git ancestry, feature-file comparisons, merge reconciliation, exact HEAD/tree and clean status were independently inspected.

The builder's 200-pass/one-fixture-error run and unchanged single-case rerun are attributed to the builder and not relabeled as reviewer evidence. This reviewer did not rerun Ruff, Mypy, generated web TypeScript/typecheck, full feature suites, benchmark timings or mutation testing. Six OpenAPI checks did run independently here.

Required exact-composition CI: NOT VERIFIED by this reviewer; no run was retrieved. Separate BP-4 repair review final report/hash: not independently retrieved in this bounded composition assignment. The structural comparison confirms the repaired source is present, but does not replace that review's formal evidence.

## Retained limits

Existing feature notes/debt remain unchanged: BP-9 bounded post-wait current-side checks are not strict commit-time authority; BP-11 cursor timing, representative EXPLAIN and proxy/per-process limiter deployment limitations remain; BP-4 names remain unverified user-supplied display text under D-113. IBB-001 remains the formal baseline. BARRIER/rollback BLOCKED, BP-10 EXPAND/BB-11 and other recorded debt are not closed. FE-VIS-001 and production deployment remain unauthorized. A later candidate requires its own identity/delta checks.
