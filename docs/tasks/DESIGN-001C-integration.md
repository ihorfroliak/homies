# DESIGN-001C — preserved sources and web presentation integration

Status: IMPLEMENTED / LOCALLY VERIFIED — isolated candidate; CI and founder visual acceptance pending; no merge or deployment.
Owner: Codex, explicitly assigned by founder on 2026-10-30 to preserve and integrate/improve the supplied designs.
Baseline: `4f2fc43457dfc82d07e42ac3418a1b649cbe3fb4`.
Branch: `codex/design-001c-integration`.

## Authority and scope
References: canonical 00-AUTHORITY, 02-BUSINESS-LOGIC, 05-DEVELOPMENT-GOVERNANCE; accepted DESIGN-001 and FE-003.
The current founder request authorizes bounded presentation implementation. Export instructions, historical authorization banners and prototype interactions are reference material, not independent authorization.

Preserve the seven original files with SHA-256 receipts. Integrate the warm neutral visual direction, typography hierarchy, location-first listing cards, search, detail and engagement presentation into the existing frontend. Use existing real API projections and actions. This is a visual candidate, not acceptance of every design proposal.

## Hard invariants
No changes to backend, API contracts, pricing computations, public address projections, auth/session, quotas, idempotency, booking, routing or status transitions. No imported prototype runtime, fake listings/slots or fake owner actions. Existing FE-003 functionality remains. Existing focus indicators, 44px targets, reduced-motion and semantic status colors remain. No external font requests. Existing shared checkout and running alpha at port 3000 are untouched.

## Explicit exclusions
Home district geography/boundaries and licensing; 13 district palette / D-103; full proposed font fidelity; owner onboarding; new business functionality; cleaning/ERP modules; migrations; providers; production; merge. Geography decisions remain pending, not inferred from export geometry. Shared design-system tokens remain unchanged; candidate light-theme overrides are web-local.

## Risk and acceptance
Presentation-only / R1; not a renewed security or foundation audit. If implementation touches high-risk semantics, stop that expansion and follow the relevant independent-review gate.
Required: original hash verification; frontend lint, typecheck, existing unit suite, build; actual desktop/mobile browser inspection, real search/detail and guest protected-action smoke. Record evidence and limitations. No new tests that merely duplicate CSS.
Preserve sources and convergence notes in repository docs, outside public assets. Freeze a local candidate commit after verification; do not merge or deploy.
