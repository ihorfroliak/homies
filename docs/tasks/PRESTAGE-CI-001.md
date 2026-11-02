# PRESTAGE-CI-001 — PostgreSQL restore client selection

Founder authorization: 2026-11-02, close audit gaps step by step before staging. Primary writer Codex, isolated branch codex/prestage-ci-pg16. Base4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4.

Bounded R1 operational repair: select PostgreSQL16 pg_dump/pg_restore explicitly for CI's PG16 target even when runner PATH contains18.6. Install only when supported binaries absent; assert both versions; persist PG_BIN and PATH for subsequent tests. Existing mandatory restore/JUnit gates, server image, migration policy, production config and application code unchanged.

Evidence: run41221102851 failed SET transaction_timeout with client18.6/server16.4; 2089passed,1failed,9errors,2skipped. Candidate has no backend changes versus base. Acceptance: review workflow failure behavior; fresh exact-SHA CI incl both restore suites and following dependency audit. No skip/ignore workaround.

No merge, deployment, paid providers or shared DB mutation. Draft PR only. CI outcome must be recorded before closure.

## Runtime evidence and runner pin

Initial candidate 5383a75 passed independent source review, but run 41378000102 failed before tests: ubuntu-latest selected Ubuntu 26.04 and apt could not locate postgresql-client-16. Pin only the backend job to ubuntu-24.04; retain explicit client checks and all restore gates. Ubuntu Noble publishes the supported major (https://packages.ubuntu.com/noble/postgresql-client-16); runner reference: https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md (checked 2026-11-02). This changes the disposable CI host only, not application runtime or deployment. Fresh exact-SHA CI is still required.

## Continuation — dependency and test-isolation blockers

Founder requested completion of the previous bounded pre-staging repairs. CI41378926059 passed2099 backend tests and all10 restore drills; dependency audit then failed on two existing pins. Reuse source commit5b410c13708ac987676f71e6dba16a12d75b2eb2 with cherry-pick provenance: dnspython2.8.0→2.9.0 and msgpack1.2.2→1.2.3 only. No additional dependency/range changes. Publisher advisories confirm these patched versions: https://github.com/advisories/GHSA-45c3-73f7-pv4m and https://github.com/advisories/GHSA-j586-36cw-2gc2. Actual pinned installation/audit and full exact-SHA CI remain required.

CI41379937827 separately exposed a test fixture mismatch: map-cutoff seed uses21 calendar days whereas D-67 requires1814400 elapsed seconds. A separate test-engineer source review identified committed session-zone state left on pooled connections by timezone tests. Repair only test clock fixtures and session cleanup; no production freshness rule change. Verify both DST directions and session zones against a new disposable PostgreSQL16/PostGIS database, plus ordered timezone→search suites. Preserve the exact boundary exclusion, all assertions and mandatory CI gates. This R1 extension changes pins/test reliability only; no application or migration code. Risk-matched source review required before closure.
