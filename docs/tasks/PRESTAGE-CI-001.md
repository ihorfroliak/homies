# PRESTAGE-CI-001 — PostgreSQL restore client selection

Founder authorization: 2026-11-02, close audit gaps step by step before staging. Primary writer Codex, isolated branch codex/prestage-ci-pg16. Base4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4.

Bounded R1 operational repair: select PostgreSQL16 pg_dump/pg_restore explicitly for CI's PG16 target even when runner PATH contains18.6. Install only when supported binaries absent; assert both versions; persist PG_BIN and PATH for subsequent tests. Existing mandatory restore/JUnit gates, server image, migration policy, production config and application code unchanged.

Evidence: run41221102851 failed SET transaction_timeout with client18.6/server16.4; 2089passed,1failed,9errors,2skipped. Candidate has no backend changes versus base. Acceptance: review workflow failure behavior; fresh exact-SHA CI incl both restore suites and following dependency audit. No skip/ignore workaround.

No merge, deployment, paid providers or shared DB mutation. Draft PR only. CI outcome must be recorded before closure.
