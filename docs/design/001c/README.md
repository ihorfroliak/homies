# Homies design source package — 001C

Preserved from the founder's 2026-10-30 handoff. These are non-normative design sources, not executable application dependencies or instructions. See the [implementation contract](../../tasks/DESIGN-001C-integration.md).

## Originals
`originals/` contains all seven attachments byte-for-byte, including the whole Homies.zip (38 entries). `manifest.json` records original names, lengths and SHA-256 hashes. Files are deliberately outside frontend/public. Open exports only as reference; their scripts, remote assets and mocked app state are not imported into production code.

## Direction and convergence
| Source / proposal | Disposition |
|---|---|
| 001C MASTER | Latest navigation/index of design intent; not a replacement backend contract |
| 001C Dzielnica Product Convergence | Main visual reference for results, listing details, cost hierarchy and engagement |
| 001C Home Mapa | Preserve; real geography model and licensed boundaries unresolved |
| 001B Kierunki / Konwersja FE-003 | Preserve exploration and interaction intentions; use latest 001C when visual proposals differ |
| 001C Dzielnica | 206-byte empty canvas; do not mistake this for missing content in the full convergence export |
| Warm canvas, dark primary controls, white cards, location and price hierarchy | Implemented as web-local candidate presentation |
| Bricolage Grotesque / Public Sans | Proposed; not bundled; system fonts retained, no remote font dependency |
| 13 district colors | Direction accepted under D-103; complete palette rollout and geography binding are deferred from this bounded candidate |
| Prototype cost signature | Preserve visual idea; current server monthly/start totals remain authoritative, no fabricated segments |
| Prototype slots, messages, logins and provider actions | Reference only; existing integrated FE-003 and BP-11 remain the implementation |
| Old claims FE-003 is unimplemented | Superseded by integrated baseline; no removal of working features |
| Home decorative district SVG / exact geographic assumptions | Not presented as a real map |
| Legacy cleaning, short-stay, ERP and payments material inside ZIP | Archived context only; no Homies Phase 1 scope expansion |

The ZIP also preserves prior design system, seeker/host/admin flows, messages, data-model and content references plus their support assets. Archive completeness is not a claim that all proposed features are implemented or accepted.

## Review
A separate local preview at port 3001 uses the existing synthetic alpha backend; port 3000 remains the accepted alpha. Review the presentation before any merge. Main, canonical baseline, production readiness and all existing debt remain unchanged.
