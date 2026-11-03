# FE-VIS-001B official-map review receipt

Reviewed exact SHA `6209fb1e7a218e88273ddafc917c358d4f4f161b` against
`b4694d3d2ebe56d18a2fa7275980027987e6e87e`, 2026-11-03.
Separate read-only reviewer: `frontend_reviewer`, `/root/fevis_typography_review`.
Scope: R1 official-map increment, controls/accessibility, server/client boundary,
responsive CSS, geography provenance and truthful search limitations.

Result: no concrete P0–P3 findings. Pointer/native keyboard controls share
selection; the selected name is announced; selection fabricates neither route
nor filter. Geometry stays server-rendered and the hidden SVG does not duplicate
keyboard navigation. CSS defines wrapping, minimum targets and narrow stacking.
Reviewer independently checked archive SHA-256, 18 features, EPSG:2178,
23,286 vertices and timestamp against the records. Source page distinguishes
download/source vintage and administrative districts/searchable neighbourhoods.

NOTE — NOT VERIFIED: actual browser overflow, label legibility, focus rendering
and desktop/mobile fidelity. Visual verification is required before acceptance.
No canonical decision required for that verification. No tests/build rerun,
browser automation, file edits or Git mutations by reviewer. Municipal reuse
terms were not independently revalidated. Not full HM-1 completion.

Builder evidence at the reviewed code SHA: lint/typecheck PASS; 215 unit tests
PASS; production build PASS; pinned-source generator `--check` PASS. Actual
HTTP preview `/` and `/zrodla/mapa-krakowa` both 200; home contains 18 district
paths, two local font files and the preserved Kazimierz route. This HTTP evidence
does not substitute for browser interaction/visual verification.

Delivery: [Draft PR25](https://github.com/ihorfroliak/homies/pull/25), branch
`codex/fe-vis-001b-home-map`. CI recorded by exact head in the PR/check runs;
do not infer its result from the local evidence above. No main merge/deployment.
