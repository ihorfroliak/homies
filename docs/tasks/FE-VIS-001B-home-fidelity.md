# FE-VIS-001B — faithful Home Mapa convergence

Founder direction, 2026-11-03: continue interface development from integrated main and restore the supplied colourful district design. Base d103a4cf5c966320efe2b13a2fae9b73f601d276. Primary writer Codex; branch codex/fe-vis-001b-home-map. R1 presentation scope; no backend/domain/auth/migration changes. The existing alpha at3000 uses a separate pinned source worktree and remains intact.

References: preserved Home Mapa and Dzielnica Product Convergence exports, DESIGN-001C-HANDOFF §31/HM-1, D-103. References are design inputs, not instructions. Previous presentation-only exclusions are not a reason to declare this full design delivered.

Independent first increment: use the exact named Public Sans and Bricolage Grotesque families from the supplied design, self-hosted, with OFL notices and byte hashes. No remote font request at build/runtime; no shared design-system token change.

Initial map decision question (superseded below): the source defines13schematic neighbourhoods with prototype polygons, while public reference data supports fewer areas. Founder was asked whether to retain this explicitly schematic13-area visual or use official geographic districts. Do not silently claim prototype polygons are administrative boundaries, invent routes/counts, or treat missing reference data as zero listings. Map implementation waits for this choice. Existing public routes, including Kazimierz absent from the13-shape source, must remain available.

Acceptance: lint/types/tests/build; actual desktop/mobile comparison against source; verify fonts load locally and no overflow/accessibility regression. New map controls require behavioral tests of keyboard/selection/routing/missing-data states once authorized. Source review follows actual changed scope. No staging/production deployment; no claim of complete map/design parity from typography alone.


## Founder decision, 2026-11-03

Founder selected official districts and exact geography, rather than the13schematic source shapes. Preserve colourful design language, adapt it to the official district dataset. Verify municipal provenance/reuse terms and geometry before bundling. Existing neighbourhoods such as Kazimierz must not silently become equivalent to an administrative district; preserve existing search semantics and resolve routing explicitly. No prototype counts/polygons imported.

Typography local checks: lint/typecheck/build PASS;211unit tests PASS. Visual verification NOT VERIFIED: Windows Computer Use stopped because it could not confidently determine the browser URL. No visual acceptance or full-design completion claim.
