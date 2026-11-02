# Home Mapa fidelity repair — 2026-11-02

Founder requested bounded gap closure before future staging. This is an R1 presentation increment on DESIGN-001C, not a backend baseline or external-beta certification.

## Source comparison

Source: preserved `Homies 001C Home Mapa.dc.html` (latest home composition), with the cost explanation from `Homies 001C Dzielnica Product Convergence.dc.html`. Prior candidate captured warm styling but not the source's home composition. The source itself marks its 13-area geography as a product decision pending and its geometry as schematic.

Adopted: 5/7 desktop split from 1024px; source headline and lead; original logo path from Homies.zip (hash in BrandMark); warm rounded search form; area navigation populated by existing public reference API; separate monthly/start-cost explanation. No copy of prototype runtime, invented counts, prices, districts or map boundaries. Existing server-projected prices, search URL handling, auth and engagement remain unchanged.

Partial: a keyboard-accessible district link list replaces the not-yet-approved map. Public reference rows with null slugs do not generate broken routes. Whole-city search remains available on loading or missing reference data. The data source in this synthetic environment contains four areas, not the prototype's thirteen; that is intentional.

Still open: approved/licensed geometry and geography model; map/list/form synchronized selection; final district palette; exact font fidelity; prototype budget/room control composition; mobile header/navigation refinement; full end-to-end visual parity on other pages. This increment is not a claim of a 1:1 reproduction.

## Executed validation

- Node 24 isolated preview environment: lint PASS, TypeScript PASS, all 211 unit tests PASS in one invocation (23 files), production build PASS.
- Five new behavioral tests: actual district route; no route for null slug; empty reference fallback; separate loading state; escaped name/contained URL segment.
- Browser desktop: home renders the real four-area list and six real synthetic listing cards. Kazimierz link resolves to `/wynajem/krakow/kazimierz`, showing three listings. Opened real detail, observed backend-projected costs and approximate public location. Guest save opens the real login dialog; no authenticated write submitted.
- Browser mobile viewport requested 390x844 (content width 375 due to scrollbar): home and filtered result scrollWidth equals clientWidth 375. Entered Kraków and 4000 in the real form; URL became `/wynajem/krakow?koszt_do=4000` with the city result heading. Temporary viewport override reset.
- Screenshots saved locally under the existing DESIGN-001C evidence directory as `home-20261102-desktop.png` and `home-20261102-mobile.png`; local artifacts are not independent repository authority.

Runtime preview: http://localhost:3001. Separate from the main alpha at port3000; existing synthetic backend and database reused without reseeding. Main, production and providers untouched. Exact-commit source review and CI are recorded separately; no new full authenticated viewing journey was rerun for this presentation-only delta.

## CI repair dependency

Draft PR23 selects PostgreSQL16 tools and pins its backend CI host to Ubuntu24.04. Initial candidate5383a75 passed source review but failed installation on the changed ubuntu-latest host (run41378000102); successor f0d163e0cbab1b90493f04480c5224e02391116a passed independent devops source review, with actual CI required. No restore assertion or security check was removed. The design candidate needs this repair before its full CI can be accepted.

## Next bounded work

Complete this increment's exact-candidate verification. Then address the audit's inverted availability-date validation gap in a separate backend contract and synthetic regression environment. Preserve existing external-beta debts and staging gates. No new PR merge or staging deployment authorized.
