# Homies Design System

UI-01. A framework-agnostic design system: design tokens + reference component
implementations. **No frontend framework exists in the repo yet** (`apps/` is
empty), so this establishes the token and component contract that the future
web app (recommended: Next.js — SSR/SEO matters for Product B) and mobile app
(recommended: React Native / Expo) will consume. Files live in
`frontend/design-system/`; the runnable showcase is `index.html`.

## Running it

```
cd frontend/design-system && python -m http.server 8137
# open http://localhost:8137/index.html
```

No build step, no dependencies. All data in the showcase is **mock** and
labelled as such; it makes **no backend calls**.

## Tokens (`tokens.css`)

CSS custom properties, light + dark (via `:root[data-theme="dark"]`), honouring
`prefers-reduced-motion`.

- **Colour** — brand (trust green) 50/300/500/600/700; ink 900/700/500/300 for
  text hierarchy; surface 1/2/3; semantic pairs (fg+bg) for success / warning /
  danger / info; status colours for verified / promoted / free listing; a
  dedicated `--c-focus` distinct from brand.
- **Typography** — display / h1 / h2 / h3 / body / small with matched
  line-heights; weights regular / medium / bold; system font stack.
- **Spacing** — 4px base scale `--sp-1..8`.
- **Radius / shadow / motion** — `--r-sm..pill`, `--sh-1..3`, `--motion*`.
- **Layout** — `--container`, `--tap-min: 44px`.

A future React app imports these same names (CSS vars or a generated JS token
file) so web and native stay visually identical.

## Components (`components.css`, `mobile.css`)

Buttons (primary / secondary / ghost / danger / disabled / block), inputs &
selects, badges (verified / promoted / free / pending / confirmed / expired /
cancelled), alerts (info / success / warning / danger), cards + listing cards
with media / badges / favourite / price, **price breakdown** (transparent fees),
tabs (ARIA), empty / loading (skeleton) / error states, modal (focus-trapped),
and mobile: device frame, bottom nav, sticky CTA, bottom sheet, map/list
segmented control, full-bleed gallery.

## Accessibility (target: WCAG 2.2 AA)

Validated in a real browser (`javascript_tool` against the running page):

- **Colour contrast** — text/background pairs use AA-targeted values; secondary
  text (`--c-ink-500`) is ~4.6:1 on white.
- **Focus visible** (2.4.7) — global `:focus-visible` ring in `--c-focus`.
- **Target size (2.5.8, AA = 24px)** — primary controls are ≥44px; chips and
  segmented controls are 36px (pass AA). The one sub-24px element is the inline
  “Retry” link inside the error-state sentence, which qualifies for the **2.5.8
  inline exception**. No non-inline control is below 24px.
- **Keyboard** — tabs are arrow-navigable with roving `tabindex`; the modal
  traps focus and closes on `Escape`; a skip-to-content link is first in tab
  order.
- **Semantics** — `role="tablist/tab/tabpanel"`, `aria-selected`,
  `aria-pressed`, `aria-current`, `aria-live` search status, `role="dialog"
  aria-modal`.
- **Motion** — all transitions disabled under `prefers-reduced-motion`.

Known gap: contrast ratios were targeted by design, not yet machine-audited
with an axe/Lighthouse pass — recommended for the production frontend cycle.

## Responsive

Verified: no horizontal overflow (`scrollWidth == clientWidth`, zero elements
wider than the viewport) at the tested desktop width; layouts use
`auto-fill`/`minmax` grids and `flex-wrap`, and the two-column property/booking
layout collapses to one column under 860px. Tablet and mobile breakpoints
inherit the same fluid grids.

## UX principles encoded

Trust (verified badges, “Homies never sees your card”), clarity & **no hidden
fees** (the price breakdown always lists the service fee and city tax before
payment), safe booking (clear cancellation modal shown before pay), honest
status (pending / expired / cancelled states mirror the real BK-01 lifecycle).
No dark patterns, no fake urgency.

## Not in scope (recommended next)

Framework selection + production component library (React), a real analytics
sink, an automated axe/Lighthouse audit, and incremental migration of real
pages once the framework is chosen.
