# Environment matrix

Names, classes and relationships of the configuration a deployment needs.
**Never values.** Real secrets live only in the host's secret store or an
access-restricted file on the server — never in Git, images, logs, PRs or
chat. Verified at `4f2fc43`; design context:
[STAGING-ARCHITECTURE](STAGING-ARCHITECTURE.md).

Columns:

* **Class:** SECRET or PUBLIC.
* **Read:** BUILD = fixed into the image or bundle at build time; RUNTIME = read when the process starts.
* **Alpha / Staging:** REQUIRED, OPTIONAL (safe default exists), FORBIDDEN, or a fixed value.

The backend reads its settings through pydantic-settings ([config.py](../../backend/app/core/config.py)): the variable is the field name in upper case, list values are JSON, and unknown variables are ignored.

## 1. Backend — `api` and `worker` (same image)

| Variable | Class | Read | Alpha | Staging | Default / rule | Source |
|---|---|---|---|---|---|---|
| `ENV` | PUBLIC | RUNTIME | REQUIRED `alpha` | REQUIRED `staging` | image default `production`. `local` self-migrates (never deploy it). `local`/`test`/`ci` skip the secret checks. Anything else is production-like, but live Stripe keys are accepted only with `production` | config.py, schema.py, Dockerfile |
| `DATABASE_URL` | SECRET | RUNTIME | REQUIRED | REQUIRED | role `homies_app`. Refused: non-PostgreSQL URLs, the published `homies`/`homies` credentials, the loopback dev endpoint. The owner/superuser role is refused at startup (B5) | config.py, schema.py |
| `JWT_SECRET` | SECRET | RUNTIME | REQUIRED, ≥ 32 chars | REQUIRED | must be identical on every instance; validated on `worker` too (same lifespan) | config.py |
| `WEBHOOK_SECRET` | SECRET | RUNTIME | REQUIRED, ≥ 16 chars | REQUIRED | legacy simulated webhook; still validated | config.py |
| `GIT_SHA` | PUBLIC | BUILD (`--build-arg`) | REQUIRED, 40 hex | REQUIRED | no default: without it the image refuses to start outside `local/test/ci` | Dockerfile, release.py |
| `HOMIES_BUILD_SHA` | PUBLIC | derived | do **not** set | do not set | set inside the image from `GIT_SHA`; overriding it at runtime would misreport identity | Dockerfile |
| `TRUST_PROXY_HOPS` | PUBLIC | RUNTIME | `api`: `1`; `worker`: `0` | per ingress | default `0` = forwarded headers never trusted | ratelimit.py |
| `TRUSTED_PROXY_CIDRS` | PUBLIC | RUNTIME | `api`: JSON list of the Caddy and web `/32`s; `worker`: `[]` | the platform's real proxy peers | default `[]`; hops without a matching peer trust nothing | ratelimit.py, STAGING-ARCHITECTURE §3 |
| `RATE_LIMIT_ENABLED` | PUBLIC | RUNTIME | OPTIONAL, keep `true` | keep `true` | default `true`; buckets are per process | ratelimit.py |
| `PUBLIC_WEB_BASE_URL` | PUBLIC | RUNTIME | REQUIRED in practice | REQUIRED | default `http://localhost:3000`; links in notifications; **equal to web `PUBLIC_ORIGIN`** | config.py |
| `NOTIFICATION_WORKER_ENABLED` | PUBLIC | RUNTIME | `api` **false**, `worker` true | same | default **true** | config.py, composition.py |
| `SAVED_SEARCH_WORKER_ENABLED` | PUBLIC | RUNTIME | `api` **false**, `worker` true | same | default **true** | config.py |
| `LISTING_FRESHNESS_WORKER_ENABLED` | PUBLIC | RUNTIME | `api` false, `worker` false or true | `worker` true | default false | config.py |
| `MEDIA_ROOT` | PUBLIC | RUNTIME | REQUIRED in practice: a path on the media volume (e.g. `/srv/var/media`) | object store decision | default `var/media` relative to `/srv`; `api` only | media/storage.py |
| `MEDIA_MAX_BYTES`, `MEDIA_PROCESSING_*` | PUBLIC | RUNTIME | OPTIONAL | OPTIONAL | defaults in config.py | config.py |
| `EMAIL_PROVIDER` | PUBLIC | RUNTIME | `stub` (default) | `stub` | the stub logs recipient and subject, never the body | events/providers.py |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_FROM` | PUBLIC | RUNTIME | FORBIDDEN (unset) | unset until a provider decision | | config.py |
| `SMTP_PASSWORD` | SECRET | RUNTIME | FORBIDDEN | unset | not validated (PRODUCTION-READINESS gap) | config.py |
| `PAYMENT_PROVIDER` | PUBLIC | RUNTIME | `simulation` (default) | `simulation` | Phase 1A collects no money | config.py |
| `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` | SECRET | RUNTIME | FORBIDDEN | FORBIDDEN | live keys refused outside `production` | config.py |
| `LOG_FORMAT`, `LOG_LEVEL` | PUBLIC | RUNTIME | OPTIONAL: `json`, `INFO` | `json` | defaults `text`, `INFO` | logging_config.py |
| `DB_*_TIMEOUT_*`, `DB_CLIENT_*` | PUBLIC | RUNTIME | OPTIONAL | OPTIONAL | PR-003 deadline policy; an unworkable combination refuses startup | config.py |
| `ACCESS_TOKEN_TTL_SECONDS` | PUBLIC | RUNTIME | OPTIONAL | OPTIONAL | 1800 | config.py |
| `REFRESH_TOKEN_TTL_DAYS` | PUBLIC | RUNTIME | OPTIONAL, **do not change** | do not change | 30. Web's refresh cookie `Max-Age` is hard-coded to 30 days (session.ts), so the two must change together | config.py, session.ts |
| `CONTACT_REVEAL_DAILY_QUOTA`, `CONVERSATION_DAILY_QUOTA`, `SAVED_*_PER_USER` | PUBLIC | RUNTIME | OPTIONAL | OPTIONAL | abuse bounds | config.py |
| `BOOKING_*`, `PLATFORM_FEE_BPS`, `DEFAULT_CURRENCY` | PUBLIC | RUNTIME | leave unset | leave unset | dormant | config.py |

## 2. Backend one-off jobs

| Variable | Job | Class | Rule |
|---|---|---|---|
| `ALEMBIC_DATABASE_URL` | `migrate` | SECRET | REQUIRED outside `local/test/ci`; role `homies_migrator`; the job refuses `homies_app` or a role without CREATE on the schema. **Never set on `api` or `worker`** |
| `ENV` | `migrate` | PUBLIC | same value as the release's `api` (`alpha` / `staging`), so BARRIERs need `--allow-barrier` |
| `HOMIES_ALLOW_E2E_SEED`, `HOMIES_ALLOW_ENGAGEMENT_E2E_SEED` | `seed` (alpha only) | PUBLIC | `1` on the seed job only; never on serving instances |
| `ENV` | `seed` | PUBLIC | must be `local`, `test` or `ci`, and the database name must end in `_e2e`, `_test` or `_ci` — enforced by [seed_e2e.py](../../backend/app/scripts/seed_e2e.py) |
| `DATABASE_URL` | `seed` | SECRET | the alpha database (name ending `_e2e`) |
| `BACKUP_KEY` | backup/restore scripts | SECRET | the published development key is refused |
| `TEST_DATABASE_URL`, `PG_BIN`, `E2E_ENGAGEMENT_MANIFEST` | tests/CI | — | never in a deployed environment. The seed's `--manifest` file holds **synthetic** credentials: keep it on the server outside the web tree, never in Git |

The seed scripts need the `dev` extras (`httpx` for `TestClient`), which
the production image does not install (VERIFIED pyproject.toml). Gate D must
choose a tools image or a throwaway container built from the same SHA.

## 3. Web — `web`

| Variable | Class | Read | Alpha / Staging | Rule | Source |
|---|---|---|---|---|---|
| `NODE_ENV` | PUBLIC | BUILD + RUNTIME | `production` (set by `next build` / `next start`) | | next.config.ts, server/env.ts |
| `HOMIES_WEB_ENV` | PUBLIC | BUILD + RUNTIME | **unset** | `development` turns off production checks, the HTTPS-only behaviour and edge media routing — E2E builds only | next.config.ts, proxy.ts, server/env.ts |
| `MEDIA_VIA_EDGE` | PUBLIC | BUILD | REQUIRED `1` | a production build fails without it; then the app does not proxy `/v1/media`, so the edge must (STAGING-ARCHITECTURE §5) | next.config.ts |
| `API_INTERNAL_URL` | PUBLIC (internal address) | RUNTIME (also BUILD only when `MEDIA_VIA_EDGE` ≠ 1) | REQUIRED, e.g. `http://172.30.10.20:8000` | startup error in production when missing | server/env.ts |
| `PUBLIC_ORIGIN` | PUBLIC | RUNTIME | REQUIRED, `https://<alpha host>` | must be https in production; CSRF compares the request origin against it — scheme, host and port must match exactly what the browser uses; equal to backend `PUBLIC_WEB_BASE_URL` | server/env.ts |
| `TRUST_PROXY_HOPS` | PUBLIC | RUNTIME | REQUIRED `1` (Caddy) | production refuses `< 1` | server/env.ts, client-ip.ts |
| `INDEXING_ENABLED` | PUBLIC | RUNTIME (`X-Robots-Tag` in proxy.ts, server env) and wherever page metadata is evaluated | **unset** (anything but `1` = noindex) | set identically at build and runtime: metadata of a prerendered page is evaluated at build time (INFERRED) | proxy.ts, seo/index.ts |
| `NEXT_PUBLIC_MAP_STYLE_URL` | PUBLIC | BUILD (inlined) | OPTIONAL | unset = plain background map; its origin joins the CSP. Choose a tile provider whose terms allow this use — a decision, not a default | map-canvas.tsx, proxy.ts |
| `MAP_EXTRA_ORIGINS` | PUBLIC | RUNTIME (CSP in proxy.ts) | OPTIONAL | comma-separated extra tile/glyph origins | proxy.ts |
| `NEXT_PUBLIC_ANALYTICS_SINK` | PUBLIC | BUILD | unset (noop) | `console` / `memory` are development sinks; consent is empty, so nothing is emitted anyway | analytics/client.ts |
| `NEXT_PUBLIC_APP_VERSION` | PUBLIC | BUILD | OPTIONAL, = `GIT_SHA` | default `dev` | analytics/client.ts |
| `NEXT_PUBLIC_E2E_HOOKS` | PUBLIC | BUILD | **FORBIDDEN** | exposes the consent store on `window` — E2E builds only | analytics/client.ts |

## 4. Edge and database containers (alpha)

| Variable | Container | Class | Rule |
|---|---|---|---|
| `ALPHA_HOST` | caddy | PUBLIC | DNS name of the alpha (needed for the certificate and `__Host-` cookies) |
| `ALPHA_USER`, `ALPHA_PASSWORD_HASH` | caddy | SECRET | basic-auth fence; the hash comes from `caddy hash-password`; the plain password is never stored on the server |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | db | SECRET | bootstrap superuser (DBA). Used only for the role scripts; the application never connects with it |
| `POSTGRES_DB` | db | PUBLIC | e.g. `homies_alpha_e2e` — the `_e2e` suffix is what lets the synthetic seed run |

## 5. Relationships to keep true

* `PUBLIC_ORIGIN` (web) = `PUBLIC_WEB_BASE_URL` (api) = `https://` + `ALPHA_HOST`.
* `TRUSTED_PROXY_CIDRS` (api) = exactly the addresses of Caddy and web; their `TRUST_PROXY_HOPS` = 1.
* `JWT_SECRET` is identical on every backend instance of one environment; staging and alpha never share a secret.
* `ALEMBIC_DATABASE_URL` and `DATABASE_URL` point at the same database with **different** roles.
* `GIT_SHA` of the API image = the commit the web image was built from (`NEXT_PUBLIC_APP_VERSION`), for one release.
* Worker flags are explicitly `false` on every serving instance.
