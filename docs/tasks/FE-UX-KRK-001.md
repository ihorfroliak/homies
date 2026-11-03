# FE-UX-KRK-001 — Kraków-first interface refinement

Founder authorization 2026-11-03: deeply assess and improve predictability,
simplicity, trust, warm colour, header/footer, mobile burger and useful dropdowns.
First settle Kraków's reusable design, then extend to Warszawa, Poznań and Polish
cities with more than 300,000 residents; nationwide localities follow later.
This does not authorize staging, production, paid providers or merging candidates.

Primary writer: Codex in own design worktree, `codex/fe-vis-001b-home-map`,
Draft PR25 based on accepted main `d103a4c`. Existing map candidate and review
provenance remain intact. R1 presentation/navigation; do not alter auth, provider
authority, privacy, quotas, backend search or DB membership semantics.

## Evidence and bounded first implementation

Read-only frontend discovery at `110e745` identified:

1. Mobile navigation is a horizontally scrolling row; later account actions can
   be off-screen. Replace it with a compact labelled button-controlled disclosure, preserving
   existing session/capability-driven actions. Founder explicitly requests the
   burger approach here; this supersedes the old bottom-navigation prescription
   for this bounded header. Do not infer authority from the design export alone.
2. Footer contains copyright inside an empty navigation landmark. Supply useful
   existing destinations and factual orientation; no invented legal pages,
   support contacts, certifications, guarantees or testimonials.
3. Home advertises Kraków while an empty-city search silently becomes nationwide.
   Make the initial city explicit on Kraków Home; retain deliberate city changes
   and existing nationwide routes.
4. A late city suggestion can repopulate after clearing the field. Abort on input
   change and reject stale responses; regression-test the delayed result.

Warm surfaces follow preserved original designs. Preserve readable contrast,
semantic status colours and district identity colours. Avoid adding dropdowns
merely to hide important search/navigation controls. Desktop primary navigation
stays visible; mobile Menu is named, keyboard-operable and shows its state.

## Verification

Lint/types, focused tests (menu open/close, Escape/focus, navigation, auth entry,
session/provider preservation, stale suggestions, explicit city), production
build, existing browser E2E/axe and CI. Separate frontend exact-SHA review.
Visual acceptance requires real desktop/mobile captures and comparison with
the supplied design. Record blocked capture honestly; source inspection or web
research is not a completed visual audit. No conversion/retention uplift claimed.

## City rollout gates

Founder follow-up 2026-11-03 authorizes a homepage district/offers-map switch.
Use explicit click/touch/keyboard activation, not hover-only mode changes.
Reuse the existing public map endpoint, privacy-safe points and lazy map renderer.
Do not silently widen a failed Kraków lookup to nationwide. Keep incomplete
map coverage, approximate positions and unavailable street basemap explicit.
G-11 already permits a development-only source. A free, accountless basemap may
be configured in the isolated local preview after checking attribution and
network origins; no paid service or beta/production provider decision follows.
CI and the default application configuration keep the blank/no-network style.
A city preview
does not claim to apply unsubmitted search-form filters. Full map search remains
the existing filtered route; preserve the district design and selection on return.

Kraków is the design pilot. Use official GUS municipality population with a
dated snapshot, not metro-area estimates. Warszawa/Poznań are explicitly named
next; additional qualifying cities require the same population check. Before a
city becomes selectable as a supported experience: verify official geography,
reuse terms, area terminology/identifiers, actual search coverage, empty states
and listing availability. Existing nationwide browsing is not removed. No fake
city counts or links, and no copied Kraków district boundaries for other cities.
Detailed rollout data is evidence, not permission to activate all cities now.

## Research discipline

Compare external navigation/search patterns when useful, as explicitly requested
by founder. Keep named commercial comparisons outside committed product authority
under 07 §5; committed recommendations use independent Homies reasoning.
Use W3C/WAI and other primary design guidance with source links. Separate
code-proven defects, observed visual issues and untested usability hypotheses.
