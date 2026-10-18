# BP-3 independent bounded review

Date: 2026-10-16. Reviewer: separate Codex review context; not the builder.
Candidate: 94935fa132ef821f3d67ffe95ebc1526a5ec9d5e
Tree: 60083dc7615ab19fbbe2978a9c883ff2178b2ca6
Baseline: 4ed8fe8ab334a8d8e344b80e266da2be3b661aee
Worktree: C:/Users/ihorf/.codex/worktrees/delivery002-bp3-audit/homies
Draft PR: 11 (identity supplied in handoff; PR state not independently queried).

## Verdict
PASS for the bounded BP-3 candidate. P0: 0; P1: 0; P2: 0; P3: 0. No canonical decision required. This is independent review evidence, not merge approval or production readiness.

## Scope and canonical checks
Read AGENTS.md, canon 00, 02 authority/address invariants, 04a section 24, governance 05 including section 14, implementation convergence dispositions, BP-3 contract and relevant FE-003 provider dependencies. Reviewed the candidate diff in properties/router.py, properties/schemas.py, the BP-3 tests, committed OpenAPI and generated TypeScript API types. Inspected the unchanged authority helper only to establish the call's effective semantics; no whole-repository audit.

- router.py:797-824 preserves the existing PUBLISH_LISTING branch and adds an explicit verified=True engagement query. Personal, active organization membership with a permitted role and active organization, and active/verified/in-date scoped mandate paths all terminate at an active legal party and in-force VERIFIED root holding that same scope (authority.py:105-230). No cross-scope grant is introduced.
- Engagement selects only id/title/status and returns ProviderListingOut with scope (schemas.py:399-410). The HTTP regression asserts the exact four-field response, excluding address, requester/contact, moderation, quality and authority metadata. No private ORM relationship is materialized by this branch.
- Omitted and explicit PUBLISH_LISTING return the existing owner projection, including draft preparation by an unverified legitimate claimant. Anonymous access is denied and unsupported scopes are rejected.
- Tests cover both engagement scopes, other-property isolation, root scope removal, root unverified/revoked/expired states, mandate scope and lifecycle restrictions, membership role/revocation and denial of a publication mutation to a message/viewing-only representative.
- API schema/types express the optional query, default, exact minimal DTO and response union consistently. Runtime OpenAPI drift test passed.

## Independently executed checks
Using image bp10c-test:c385136, image ID sha256:86026a4e11a8589ddbd331ff5ddbf8491bebe398c38b76c812ebf5cc981cb23a, Python 3.12; network disabled; candidate backend mounted read-only at /app and docs read-only at /docs; PYTHONDONTWRITEBYTECODE=1; pytest cache disabled; DATABASE_URL and TEST_DATABASE_URL explicitly sqlite://.

Command: python -m pytest -p no:cacheprovider -q tests/test_bp3_provider_enumeration.py tests/test_property_authority.py tests/test_tst01_openapi_contract.py
Result: 41 passed, 1 warning in 39.35s. Warning: inherited Starlette TestClient httpx deprecation.
Command: python -m ruff check --no-cache app/modules/properties/router.py app/modules/properties/schemas.py tests/test_bp3_provider_enumeration.py
Result: All checks passed.
Git verified the exact candidate/tree, detached HEAD and clean worktree (empty status). Initial sandbox-only Git/Docker access attempts were denied; authorized read-only verification and isolated test execution succeeded through escalation. No automatic approval rejection occurred.

## Limitations and nonblocking notes
No PostgreSQL/concurrency/full-suite, mypy, frontend generator/typecheck or remote CI run was independently executed. Builder claims for these remain builder evidence. This change is a scalar read using existing authority helpers; no migration or mutation introduced. This does not validate downstream private engagement endpoints: BP-9 remains mandatory and FE-003 dependency acceptance is not granted. Organization MANAGE_MESSAGES and future-start/inactive-party states are established by shared helper inspection, not new dedicated BP-3 test cases. No code, source, commits, pushes, deployment, paid providers or application databases were modified.
