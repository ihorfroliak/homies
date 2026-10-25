# FE-003 independent BFF boundary review

Date: 2026-10-21. Reviewer: independent Codex read-only review agent.

**Disposition: PASS for the bounded BFF server changes described below.** No established P0 CRITICAL, P1 HIGH, P2 MEDIUM or P3 LOW finding. This is not acceptance of the complete FE-003 frontend, deployment, or a repeat backend audit.

## Immutable identity and scope

- Audited commit: `dbf06681a78c128c27bfcf3a2ae94f485dec6cb2`.
- Audited tree: `d7242618ce84b4f299739ba218a833aa6b012108`.
- Comparison base: `ee19b3affc9f33d560c7624ebc6b562276c56000`.
- Own pinned worktree: `C:/Users/ihorf/.codex/worktrees/fe003-bff-independent-review/homies`.
- Initial and final `git status --short`: empty. No repository file edits, commits, push, deployment, backend runtime, database use or external test target.
- Changed scope: `frontend/web/src/app/bff/auth/register/route.ts` and its test; `auth/session/route.ts`; `bff/v1/[...path]/route.ts`; `frontend/web/src/server/bff-routes.ts`.
- Unchanged helpers inspected as boundary dependencies: backend request forwarding, BFF session orchestration, body cap, CSRF, environment, session cookies/refresh, proxy headers. Accepted backend routes were read only to confirm auth levels, response semantics and the duplicate saved-search Location shape; backend authorization/concurrency internals were not re-audited.

Authority read: own AGENTS.md; canonical 00 and governance 05; FE-003 contract sections 1.6, 3.7, auth/contact/provider clauses, API/BFF component clauses and acceptance criteria; FE-003-execution; DESIGN-001C auth/privacy invariants and handoff checks; FE-001 sections 3–4 and accepted environment/security qualifications; relevant 04a section 24 and implementation-convergence dispositions. Current HOMIES-DELIVERY-002 authorization takes precedence over the historical implementation-NO labels.

## Evidence and assessed invariants

1. **Registration shape, role exclusion and session creation** — register route lines 11–29. CSRF precedes body reading; the actual streamed byte count is capped at 4096; null, arrays, primitives and wrong field types are rejected. A new object forwards only email/password/full_name, defaulting the optional name to an empty string. Neither supplied role/verification/contact fields nor existing bearer credentials reach registration or chained login. Registration success alone does not create a session: login must succeed first. Cookie writing uses the existing `__Host-`, HttpOnly, Secure, SameSite=Lax, Path=/ helper. The browser response is only `{authenticated:true}`. Evidence: four repository registration tests plus independent malformed shape, byte cap, CSRF variants, field stripping, chained-login failure and actual cookie-helper probes. Matches FE-003 section 3.7, AC-A2/AC-G8 and DESIGN-001C I-12/I-13.

2. **Session minimization** — session route lines 21–25. `phoneVerified` derives from `phone_verified_at`, not phone presence; missing/null timestamps are false. Only id/name/emailVerified/phoneVerified are projected. Phone, email, role and other upstream properties are omitted. Responses are no-store. Independent probes covered a present phone with null/missing/verified timestamps and anonymous session behavior. Matches FE-003 CF-13 and auth/privacy constraints.

3. **Explicit routes and authenticated private operations** — bff-routes lines 19–42. Each new method/path shape is explicit and auth-required. Independent calls through the real `withSession` helper returned 401 without reaching the mocked upstream for all 26 expanded private method/path cases. Negative paths rejected admin, auth-through-generic-proxy, settings/windows and extra suffixes. Public viewing-slots remains optional, consistent with the accepted BP-11 public derived-slot endpoint; the backend route has no account dependency. Backend route declarations confirm account dependencies for the added private calls. The BFF does not claim to replace backend per-object authority checks. Matches AC-G5, FE-001 section 3 and DESIGN-001C handoff allowlist requirements.

4. **Paths, queries, caches and response headers** — generic proxy lines 24–64; bff-routes lines 50–56; backend helper lines 30–44. Path validation rejects dot/empty segments, separators, percent escapes, query and fragment delimiters. Queries remain the query portion of the validated internal API path; they cannot select a different origin or route. The backend request helper uses server-only configuration, no-store and manual redirects; user-supplied bearer headers are not forwarded. Personal upstream responses and required-auth refusals are no-store. Upstream Set-Cookie, CORS and cache-control are not passed through. CSRF and the 64 KiB stream cap apply before writes. Independent probes verified path/query containment, no-store, header removal and refusal before upstream work.

5. **Duplicate saved-search reference** — generic proxy lines 61–63. Only `/v1/me/saved-searches/{safe-id}` survives as Location; scheme-relative/absolute URLs, unrelated routes, traversal, encoded separators and query-bearing locations are dropped. The accepted backend emits that same relative API reference on a duplicate 409. The header is a reference for client duplicate handling, not a new broad proxy route. Independent probes verified the safe case and six unsafe cases. Matches FE-003 AC-S5.

6. **Errors and environment** — register route lines 25–36. Local parse/type/CSRF/size refusals and thrown upstream failures use fixed bodies and no-store. Expected backend refusals retain status/body and Retry-After while excluding upstream cookies/location; this deliberately relies on the accepted backend error contract, like the existing login route. No registration token or returned UserOut is emitted on success. The unchanged production guard rejects missing internal URL/public origin, insecure production public origin and missing/invalid trusted-proxy count; existing tests passed. `HOMIES_WEB_ENV=development` remains the previously documented explicit local/E2E escape, unchanged by this boundary diff. No claim is made that arbitrary malformed or malicious upstream payloads are sanitized by the generic proxy.

## Tests actually executed

Successful run: Docker `node:24`, observed **Node v24.21.0**, **Vitest 5.0.3**, repository jsdom configuration. Network disabled. Pinned source and existing Linux `homies-fe-nm` dependency volume mounted read-only, then copied into private ephemeral container storage. No shared dependency caches were written. The container was removed after execution.

- `src/server/server.test.ts`: **26 passed** (CSRF, IP/request id, production environment guards, allowlist/path checks, cookie flags, refresh memory/single-flight and headers).
- `src/app/bff/auth/register/route.test.ts`: **4 passed**.
- Independent `boundary.test.ts`: **75 passed**.
- Total: **105 passed / 105**, three files, test-run duration 10.73 seconds; exit code 0.

Independent probes and complete successful output are preserved in adjacent `FE003-bff-probes-dbf0668/boundary.test.ts` and `test-output.txt`. The probes run actual pinned handlers/body/CSRF/session/path code with synthetic upstream responses and synthetic cookie values; Next request context, backend transport and server environment are mocked. They are not HTTP/browser end-to-end evidence or backend authorization proof.

An earlier attempt using the builder's Windows node_modules mounted read-only under Linux failed **before test collection** because `std-env` was missing. It is not counted as a passing run. The successful run used the separate Linux cache. Vite emitted a non-failing notice that the existing configuration uses `__dirname`, unsupported by a planned future native config loader default; the current configured run passed. Host Node 24.14 was not used. No pytest, PostgreSQL/PostGIS, build, typecheck, lint, browser flow or OpenAPI regeneration was run for this narrow review.

## Optional improvement — NOTE BFF-N1 (not a canonical violation)

Location: repository registration tests (`frontend/web/src/app/bff/auth/register/route.test.ts:11`) and server tests (`frontend/web/src/server/server.test.ts:111`). The committed tests cover registration basics and general guards, but not all changed session projections/new private route expansions/Location filtering checked by this review. Consider retaining focused versions of the independent regression cases in the builder-owned test suite. Expected benefit: future regressions in these specific boundaries become CI failures. Repair is optional for this reviewed SHA; no current boundary failure was demonstrated. **CANONICAL DECISION REQUIRED: No.**

## Reuse condition and limits

The final FE-003 candidate may reuse this bounded review only after an explicit hash comparison confirms the audited BFF/server production boundary and its security-relevant helpers remain identical to this SHA. At minimum compare all of `frontend/web/src/app/bff/` and `frontend/web/src/server/`, plus `src/proxy.ts` and relevant runtime/config/dependency changes. Any changed production boundary/helper requires a focused delta review; additions cannot be excluded merely because the five original files are unchanged. Evidence: adjacent `FE003-bff-probes-dbf0668/boundary-git-blobs.txt` records the complete BFF/server file identities and associated config/dependency identities.

Core changed blob identities:

| File | Git blob |
|---|---|
| auth/register/route.ts | `c719514f783001cc8ad725a1e0ee8d06fd4c0cba` |
| auth/register/route.test.ts | `7488156a35a90294a70ce7e93e5ce10520550b5c` |
| auth/session/route.ts | `45a658d55927a2ff1e545349e7a935788dfc5538` |
| v1/[...path]/route.ts | `2dfb319ddd795fdccadce886819887955e2fa523` |
| src/server/bff-routes.ts | `ba3e4affb702b027371ae5fbbad40de888aadf9f` |

The separate final frontend review still owns UI auth interruption, session/account transitions, contact display/clearing, stale responses, saved-state behavior, provider navigation and end-to-end behavior. This report does not close those gates, backend prerequisites, combined CI, founder acceptance or deployment permission.
