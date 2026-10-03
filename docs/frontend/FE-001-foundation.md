# FE-001 — Public web foundation (`frontend/web`)

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED** on its branch — part of the PROGRAM-001 candidate, **not merged to `main`**; **NOT DEPLOYED** |
| Risk class | **R2** (session handling, CSRF, CSP, request forwarding to the rate limiter) |
| Branch | `claude/FE-001-frontend-foundation` (from DESIGN-001) |
| Canon | 03 §3 (Next.js + TypeScript public web), 07 (product growth), DESIGN-001, GROWTH-001 (EVENTS/ATTRIBUTION/EXPERIMENTS/PRIVACY-CONSENT) |
| Founder decisions | G-11 (provider-agnostic map, development-only source), G-12 (no vendor analytics/ad SDK), G-13 (Polish first, i18n-ready) |

FE-001 is the platform the seeker slice (FE-002) is built on. It renders a
static, factual home frame only; it does not claim any designed screen as
done (founder: a developer-built placeholder is not high-fidelity design).

## 1. Stack (exact pins, `package-lock.json`, `npm ci`)

Node 24 · Next.js 16.3.8 (App Router, `proxy.ts`) · React 19.3.0 ·
TypeScript 5.9.3 (strict, `noUncheckedIndexedAccess`) · openapi-fetch 0.17.0 +
openapi-typescript 7.13.0 · maplibre-gl 6.11.2 (lazy, FE-002) · ESLint 9.39.5 +
eslint-config-next · Vitest 5.0.3 + Testing Library · Playwright 1.63.0 +
@axe-core/playwright 4.13.0.

Deliberately **not** used: a data-fetching cache library (Server Components
fetch; the few client reads are hand-rolled with abort), an i18n framework
(typed catalogue + `Intl`), a CSS framework (Design System v1 tokens + CSS
Modules), `next/image` for `/v1/media` (the optimiser would fetch every photo
from one server IP and drain one rate-limit bucket).

## 2. Layout

```
frontend/web/
  src/app/            routes (App Router); bff/ = the browser-facing API
  src/proxy.ts        per-request CSP nonce, request id, security headers, noindex
  src/server/         server-only: env, session, BFF guards, backend access
  src/api/            generated OpenAPI types, browser client, error model
  src/i18n/           pl catalogue + Intl formatting (money, plurals, dates)
  src/analytics/      event catalogue, consent gate, sinks (noop/memory/console)
  src/attribution/    privacy-safe touch capture
  src/experiments/    deterministic assignment seam (no experiment registered)
  src/seo/            indexing rules + metadata helper
  e2e/                Playwright: foundation, accessibility, budget
```

Design tokens are imported from `frontend/design-system/tokens.css` and
`components.css` (single source with the showcase and Figma).

## 3. Session and BFF

* The backend issues a bearer pair (`/v1/auth/login`, 30-min access, 30-day
  refresh, **rotated and revoked on every refresh, no grace window**). The BFF
  keeps both in `__Host-hm_at` / `__Host-hm_rt` cookies — `HttpOnly; Secure;
  SameSite=Lax; Path=/` — and never returns a token to the browser.
* `/bff/v1/...` proxies an **allowlist** (`src/server/bff-routes.ts`) of method +
  path shapes; anything else is 404 at the BFF; admin routes are never
  proxied (separate admin app, canon 03). Dot segments and encoded separators
  are refused.
* **Refresh is single-flight per token** in the process (concurrent requests
  share one backend refresh; the settled result is kept 10 s for stragglers).
  With several web replicas this needs sticky sessions or a shared lock —
  scaling item **FE-S1**.
* A 401 from the backend means the request was not executed, so the BFF
  refreshes once and repeats it. A dead session never breaks a public read:
  routes marked `optional` are answered anonymously.
* `/bff/auth/login` · `/bff/auth/logout` · `/bff/auth/session`. Login refusals
  pass through unchanged (same wording for unknown e-mail and wrong password;
  429 with Retry-After).
* **CSRF:** every non-GET BFF request needs `Sec-Fetch-Site: same-origin` (when
  sent), `Origin` = the public origin, and `X-Homies-CSRF: 1`; the BFF grants no
  CORS, so a cross-site page cannot add the header.

## 4. Forwarding to the backend rate limiter

The backend keys rate limits on the client IP and trusts `X-Forwarded-For`
only for `TRUST_PROXY_HOPS` hops. Every backend call from the web server
**overwrites** `X-Forwarded-For` with the end user's address (taken from the
ingress for `TRUST_PROXY_HOPS` hops on the web side) and forwards
`X-Request-ID`. Deployment rule: the backend runs with `TRUST_PROXY_HOPS=1`
and is reachable **only** from the web server (and the edge for `/v1/media`),
otherwise a client could spoof its bucket. The web server refuses to start in
production with `TRUST_PROXY_HOPS=0` (it cannot read socket addresses, so
every user would share one bucket).

## 5. Photos

`/v1/media/{id}` is served by the backend. In development a Next rewrite
proxies it; in production the edge routes `/v1/media/*` straight to the
backend (`MEDIA_VIA_EDGE=1` turns the rewrite off) so photo requests keep the
user's IP. Photos use plain `<img loading="lazy">` with explicit size.

## 6. Security headers (proxy.ts)

Per-request nonce CSP: `script-src 'self' 'nonce-…' 'strict-dynamic'`, no
third-party script origin (G-12), `frame-ancestors 'none'`, `object-src
'none'`, `base-uri 'self'`, `form-action 'self'`; map origins only in
`img-src`/`connect-src` and only when configured (G-11). Every page renders
dynamically (`connection()` in the root layout) so Next stamps the nonce.
Plus `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, a closed
`Permissions-Policy`, COOP `same-origin`, `X-Frame-Options: DENY`, HSTS on HTTPS
deployments, `X-Request-ID` on every response, no `X-Powered-By`.

**Indexing kill switch:** `X-Robots-Tag: noindex, nofollow` on every response
and `noindex` page metadata unless `INDEXING_ENABLED=1`. `robots.txt` allows
crawling (so crawlers see the noindex) and disallows private surfaces. The
indexable set when enabled is DESIGN-001 §8 (`src/seo`).

## 7. Errors, i18n, accessibility, performance

* One error model (`src/api/errors.ts`): network · timeout · unauthorized ·
  forbidden · not_found · conflict · validation · rate_limited (Retry-After) ·
  unavailable · **outcome_unknown** · server, plus the domain code from a
  `CODE: message` detail and the request id. A 503 on a write is always
  `outcome_unknown` and never auto-retried (the backend's commit-unknown answer
  has no stable code yet — gap G10).
* Polish catalogue `src/i18n/pl.ts` (DESIGN-001 §7 rules are tested: no
  "zweryfikowana", no "wygasła", no exclamation marks); `Intl.PluralRules`
  one/few/many; money from integer minor units with grouping always on
  ("3 450 zł"); dates in Europe/Warsaw; calendar dates never shift a day.
* Accessibility: `lang="pl"`, skip link to a focusable `main`, visible two-tone
  focus ring, reduced motion honoured, 44 px targets; axe (WCAG 2.2 AA tags)
  runs in E2E on every page FE-001 renders.
* Budget: ≤ 220 KB compressed JavaScript on the first view of `/`; the map
  library must never be in the initial load (E2E `budget.spec.ts`).

## 8. Measurement seams (GROWTH-001; G-12)

* `analytics.track(name, props, {route})` is the only door. The catalogue is
  closed (EVENTS-v1 §3); properties are typed and checked; values shaped like
  e-mail, phone, URL or free text are refused; routes must be templates.
* **Consent gate:** without `ANALYTICS_FIRST_PARTY` nothing is emitted at all.
  Sinks are in-process only (noop default, memory, console). No banner is
  shown (no non-essential category does anything yet); first-party ingestion,
  consent evidence and retention stay privacy/legal-gated (G-12).
* Session id in memory (30-min idle, Warsaw midnight, new non-direct touch);
  `anonymous_id` only with consent; `user_id` never sent by the client;
  logout/withdrawal rotate identity.
* Attribution: allowlisted lowercase UTM codes, click-id **presence** and
  platform only, referrer **domain** only, channel classification.
* Experiments: `SHA-256(salt ‖ key ‖ unit) mod 10 000`, sticky; no consent →
  control + excluded; the registry is empty in PROGRAM-001.

## 9. Backend gaps found (not invented in the client)

| # | Gap | Effect now |
|---|---|---|
| BG-1 | no logout / refresh-token revocation endpoint | logout clears this device's cookies; the refresh token stays valid server-side until expiry |
| BG-2 | no slug → locality lookup | resolved in FE-002: `GET /v1/geo/localities/by-slug` |
| BG-3 | commit-unknown has no stable code | any 503 on a write → `outcome_unknown` (G10) |
| BG-4 | no E2E seed | resolved in FE-002: `app/scripts/seed_e2e.py` (fictional, dev/CI only) |

## 10. Verification

`npm run check:api` (generated types equal a fresh generation from
`docs/api/openapi.json`) · `typecheck` · `lint` · `test` (Vitest) · `build` ·
`e2e` (Playwright, desktop + mobile, axe, budget). CI job `web`. Results of
the actual runs are in the PROGRAM-001 evidence and the handoff.
