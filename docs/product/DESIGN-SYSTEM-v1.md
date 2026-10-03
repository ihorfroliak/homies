# DESIGN-SYSTEM-v1 — tokens and component contracts

Part of [DESIGN-001](DESIGN-001-product-ui-foundation.md). Token source:
[`frontend/design-system/tokens.css`](../../frontend/design-system/tokens.css)
(the web app imports it; Figma mirrors the Light values). Converges the UI-01
system (`docs/design/DESIGN_SYSTEM.md`, now historical for booking-era parts).

## 1. Tokens

| Group | Tokens | v1 change |
|---|---|---|
| brand | `--c-brand-50…700` | **primary buttons use brand-600** (white text ≈ 5.1:1; brand-500 ≈ 3.4:1 fails AA); hover brand-700 |
| neutrals | `--c-ink-900/700/500/300`, `--c-line`, **`--c-line-strong`**, `--c-surface/-2/-3` | `--c-line-strong` added (input borders, 3:1); `--c-ink-300` never for meaningful text |
| semantic | `--c-{success,warning,danger,info}-{fg,bg}`, **`--c-trust-{fg,bg}`** | `--c-verified` kept as deprecated alias |
| status | **`--c-fresh-*`, `--c-held-*` (owner only), `--c-requested-*`, `--c-confirmed-*`, `--c-cancelled-*`, `--c-removed-fg`** | new; always with text + icon |
| map | **`--c-map-bg`, `--c-cell-fill`, `--c-cell-stroke`, `--c-marker-*`** | new; the public cell, never a pin |
| focus | `--c-focus`, **`--focus-ring`** (two-tone) | ring added |
| type | `--font-sans` (system-ui stack), `--fs-*`, **`--fs-body: 1rem`**, **`--fs-price(-lg)`, `--fs-caption`**, `--num: tabular-nums` | body 15 → 16 px |
| space | `--sp-1…8`, **`--sp-0-5`, `--sp-9`**, **`--size-control-sm/md/lg` (36/44/52)**, **`--icon-sm/md/lg`** | additions |
| shape | `--r-sm/md/lg/pill`, **`--r-xl`**, **`--bw-1/2`** | additions |
| elevation | `--sh-1…3` | — |
| motion | **`--dur-fast/base/slow`, `--ease-standard`** (reduced motion → 0.01 ms) | `--motion*` deprecated |
| layers | **`--z-sticky 10 · map-ui 20 · drawer 40 · modal 50 · toast 60`** | new |
| layout | `--container` 1120, **`--container-wide` 1440**, `--tap-min` 44; breakpoints sm 0 · md 480 · lg 768 · xl 1024 · 2xl 1440 (mirrored in `frontend/web/src/ui/breakpoints.ts`) | documented |
| deprecated | `--c-promoted-*`, `--c-free-*` (and `.badge--promoted/free/expired`) | kept only for the UI-01 showcase; "promoted" conflicts with P8/P9 in 1A |

Dark theme: defined under `[data-theme="dark"]`, **not shipped at launch**
(D1-7); before shipping it needs its own contrast pass (brand-600 in dark
does not carry white text).

## 2. Component contracts (near-term only — production components emerge in FE-002)

Common: every interactive control ≥ 24 px (primary ≥ 44 px), visible
`:focus-visible`, disabled/loading states that do not change size.

| Component | Anatomy / variants | States | Keyboard / screen reader |
|---|---|---|---|
| Button | label (+ icon); primary · secondary · ghost · danger; sm/md/lg | default, hover, active, focus, loading (`aria-busy`), disabled | Enter/Space; loading keeps its label |
| IconButton | icon + required `aria-label` | as Button; toggles use `aria-pressed` | tooltip mirrors the label |
| Link | inline · standalone | external: icon + "(otwiera nową kartę)" | native |
| Input / Select | visible label, hint, error, prefix/suffix; native select on mobile | focus, invalid (`aria-invalid` + `aria-describedby`), disabled | errors announced on submit, not per keystroke |
| ComboBox | input + listbox, async (geo) | idle, loading, results, none ("Brak miejscowości"), error | ARIA 1.2 combobox; ↑↓ Enter Esc; `aria-activedescendant`; polite result count |
| Checkbox / Radio / Switch | label right, hint | checked, mixed, disabled | Space; Switch `role="switch"` |
| SearchBox | ComboBox + PriceInput + submit | — | `role="search"` |
| PriceInput | "zł" suffix, `inputmode="numeric"`, whole units → ×100 | invalid when min > max (mirrors the API 422) | label states the unit |
| ListingCard | cover · Save · monthly total · rent/move-in line · title · place · move-in · FreshnessBadge; variants list, rail, map, tombstone | loading skeleton, tombstone | the card is one link (name = title + total + district); Save is a separate control outside the link |
| FilterChip | label + remove | selected, removable | remove `aria-label="Usuń filtr: {label}"`; focus moves to the next chip |
| FilterPanel | groups, sticky footer with live count | counting, zero warning | count in a polite live region; heading per group |
| Drawer / Sheet / Modal | header (title, close), body, footer | open/closed | `role="dialog"` `aria-modal`, focus trap, Esc, focus return; never an auth wall over content |
| Tabs | tablist/tab/tabpanel | selected | roving tabindex, ← → Home End |
| Tooltip | one sentence | — | hover **and** focus; Esc; persistent while hovered; never the only carrier of essential information |
| Toast / Alert | message (+ action); info/success/warning/danger | — | Toast `role="status"` ≥ 6 s; blocking errors use an Alert (`role="alert"`) |
| Skeleton | block/text/card | static under reduced motion | `aria-hidden`; container `aria-busy="true"` |
| EmptyState | icon, title, body, ≤ 2 actions, suggestions slot | — | heading level fits the outline |
| Pagination | "Pokaż więcej" + numbered links | loading, end | `nav aria-label="Strony wyników"`; focus moves to the first new card |
| MediaGallery | track, counter, prev/next, fullscreen | loading placeholder, error tile | ← →; alt from the API (gap G5) or "Zdjęcie 3 z 12: {title}" |
| MapMarker / Stack | price pill · count bubble · stack pill | default, hover, selected, visited | markers are not individually in the tab order; "Pokaż jako listę" alternative |
| SaveButton | heart + `aria-label` | unsaved, saving, saved, error | `aria-pressed`; anonymous → auth → completes the save |
| FreshnessBadge | clock + relative time + `<time>` | FRESH, RECONFIRM_DUE (neutral), hidden when null | "Potwierdzona jako aktualna 3 dni temu, 30 września 2026" |
| CostBreakdown | `<dl>` rows, totals, captions; compact/expanded | estimated, lower bound | totals `aria-describedby` their basis caption |
| ModerationState | owner-only panel: action, label, since, review state, CTA | NONE (hidden), HELD (review NONE / OPEN / ANSWERED) | never rendered on public routes |
| ListMapToggle | segmented Lista / Mapa | — | radio-group semantics; keeps filters and scroll |

The Figma file holds Button (3 variants), FilterChip, FreshnessBadge,
SaveButton, MapPricePill, ListMapToggle, CostRow, ListingCard and SearchBox,
bound to the color/space/radius variables and text styles.
