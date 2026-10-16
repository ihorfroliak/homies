# BP-3 — Provider listing enumeration

Status: IMPLEMENTATION AUTHORIZED by HOMIES-DELIVERY-002 (2026-10-16).
Baseline: 4ed8fe8ab334a8d8e344b80e266da2be3b661aee.
Writer: parent Codex, isolated codex/BP-3-provider-listing-enumeration branch.
Risk: R2 authorization/private listing projection; separate exact-SHA review required.
Canon: 00 precedence; D-104/D-105; 04a section24; FE-003 sections3.9/6.10/10.1;
05 sections9/14. Full directive archived on documentation PR10 (D-112).

## Bounded contract
Extend GET /v1/me/classifieds with optional scope: PUBLISH_LISTING (default),
MANAGE_MESSAGES, or MANAGE_VIEWINGS. Omitted/default preserves the existing
publication-management response and authorization, including legitimate unverified
claimants preparing drafts. Engagement scope requires an in-force VERIFIED root
and the existing effective personal, organization, or mandate chain for that
specific scope. Return only id, title, status, scope for engagement enumeration.
No requester, contact, address, moderation-reason, quality, or authority metadata.
Enumeration grants no mutation capability. Downstream endpoints reauthorize;
BP-9 remains mandatory for private engagement access and FE-003 dependency acceptance.
This independent branch has no BP-9 or BP-11 implementation copied into it.

## Tests and limits
Test authenticated/anonymous, existing default output, distinct message/viewing
scopes, all three authority chains, expired/revoked/unverified roots and mandates,
missing scope, other-property isolation, invalid scope, and exact minimal DTO.
Run focused regression tests, Ruff, mypy, OpenAPI snapshot and generated API check,
required CI, and independent exact-SHA review. No migration, deployment, paid
provider or general audit. No merge authorization; deliver Draft PR.

## Builder verification — 2026-10-16

Python3.12 pinned test image: 35 passed (12 BP-3 cases plus existing property
authority regressions), 22.07s. OpenAPI drift6 passed,3.86s. Ruff clean;
mypy126 files clean. Generated frontend API check and TypeScript check passed.
Initial12-case run:8passed/4failed because new tests incorrectly expected the
existing listing status published instead of active, and mandate POST201 instead
of its enumeration-safe202. Corrected test expectations; production semantics
unchanged. Host Python314 lacked FastAPI, so it was not used as certification.
HostNode24.14 tooling reports inherited transitive engine warnings; generated
API/type checks passed. Required Linux CI remains a separate gate.
No migration, paid providers or deployment. No PostgreSQL concurrency claim:
this delta is a scalar SELECT using existing authorization chains. Full PG suite
will run in required CI. Separate exact-SHA review remains required before acceptance.
