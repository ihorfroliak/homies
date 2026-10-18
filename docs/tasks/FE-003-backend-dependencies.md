# FE-003 — Explicit backend dependency chain

Founder authorization: HOMIES-DELIVERY-002 sections10/12 (D-112, DraftPR10).
Parent Codex owns this bounded composition. It combines product prerequisites
with ancestry-preserving merges, not acceptance or integration into main.
AGENT-002 and documentation PR10 stay separate from the product chain.

## Frozen inputs

- Main4ed8fe8ab334a8d8e344b80e266da2be3b661aee: BP-1/2/5/6/7/8/10/12 integrated.
- BP-9 fb5b3e57a6e4881ab14ad378a15e15f49475e682 (PR13): independent
  PASS_WITH_NONBLOCKING_NOTES; CI38941516780 SUCCESS.
- BP-4 2fc30a28939c7d8b8a5b6f62a71a920ad444d693 (PR15 on BP-9): Unicode
  repair after original d138fadf; CI39060137761 SUCCESS; separate independent
  repair addendum closes BP4-IR-01, immutable archive tracked in PR10.
- BP-3 55c9d43d218b9fa749789348adeccc59306fe9ea (PR11): independent repair
  addendum PASS; CI39029843865 SUCCESS.
- BP-11 e3841a638b4cc54bba10b2caed29569aaffd54e5 (PR14): independent
  PASS_WITH_NONBLOCKING_NOTES; CI39007470216 SUCCESS.

Branch starts at BP-4; normal merge commits combine BP-3 then BP-11. Only
DEVLOG conflicts required manual reconciliation; both entries retained.
Production code and API files auto-merged. Combined OpenAPI exactly matches
application generation; generated TypeScript and typecheck pass. No new
business semantics, migrations, manual authorization edits or UI changes.

## Verification and implementation gate

Combined Python3.12 HTTP/PostgreSQL suite:200 passed,1 fixture setup error,
222.34s. BP-9 expired-mandate notification fixture failed while creating its
listing (response missing id); the actual test did not execute. No raw response
was captured, so no clock or product causality is asserted. The unchanged
single-case rerun is recorded in the delivery receipt. Selected tests cover
BP-3/4/9/11, existing viewings/DST/rate limits and OpenAPI. Disposable synthetic
PostgreSQL only, source mounted read-only. Ruff clean; mypy127 files clean;
frontend API comparison/typecheck passed (hostNode24.14 engine warnings retained).

Independent review is limited to composition interactions: preserve BP-9
post-wait checks together with BP-11 capacity/public slots and BP-4 provider
projection. Do not repeat completed feature or foundation audits. Required CI
runs on this exact composed candidate. FE-003 proceeds on the verified chain
as a separate stacked branch; it is not independently mergeable against
unprepared main. All new main merges still require founder authorization.

## Retained limits

BP-9 has bounded post-wait current-side rechecks, not strict commit-time
identity authority. BP-11 cursor timing excludes later ORM materialization;
representative EXPLAIN is not intercepted production SQL. Deployment requires
trusted CIDRs/hops, original socket peer and Uvicorn --no-proxy-headers;
per-process limiter scaling remains operational debt. Unicode marks follow
D-113; the projection is unverified display text, never legal identity.
IBB-001 remains formal baseline; BARRIER/rollback BLOCKED, BP-10 EXPAND/BB-11
and all debt retained. FE-VIS-001 unauthorized; no deployment, paid providers
or production data. Candidate integration/production readiness not asserted.