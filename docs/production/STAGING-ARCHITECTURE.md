# Deployment architecture — private alpha and future staging

**PROPOSAL (DEVOPS-FOUNDATION-001 Gate B). Nothing here is provisioned,
purchased, configured or deployed.** Implementing it is Gate D and needs its
own founder authorisation. Inventory: [SYSTEM-PASSPORT](SYSTEM-PASSPORT.md).
Variables: [ENVIRONMENT-MATRIX](ENVIRONMENT-MATRIX.md). Procedure:
[STAGING-RUNBOOK](STAGING-RUNBOOK.md).

Markers: VERIFIED (source at `4f2fc43`), PROPOSED, UNKNOWN.

## 1. Two environments, two purposes

| | Private alpha | Future staging |
|---|---|---|
| Question it answers | Can the founder use the real Homies journey in a browser? | Does a production-like release (image, migration job, rollout, restore) work? |
| Journey | search → listing → save → register/login → message → viewing request → provider confirms or declines → requester sees the state | the same, plus release and recovery rehearsal |
| Hosting | one EU VPS, Docker Compose, Caddy (Option B) — candidate Hetzner Cloud, Germany | EU container hosting with private networking, dedicated HTTPS ingress, managed PostgreSQL/PostGIS (Option A′) |
| Data | synthetic, disposable; no real users or business data | synthetic |
| Providers | email/SMS `stub`, payments `simulation`, no live integration | sandbox only after a separate decision |
| Search engines | never indexed | never indexed |
| Access | protected (HTTP basic auth or IP allowlist at Caddy) | protected |
| Recovery objective | none: reset and recreate (§9) | measure real RPO/RTO in drills |

Not authorised by either design: Kubernetes (03 §8), new search engines,
caches or queues (03 §5–§7), live payments or SMS, real user data.

## 2. Private alpha topology (PROPOSED)

```
Internet ── 443/80 ──► caddy ─┬─ /v1/media/*  ──► api      (edge network)
                              └─ everything else ► web ──► api (BFF, /v1/*)
                     data network (internal, no outbound route):
                              api, worker ──► db (PostGIS)
                              prometheus ──► api:8000/metrics, worker:8000/metrics
                              migrate / seed (one-off jobs) ──► db
```

* **Only Caddy publishes ports** (80 for the ACME challenge and redirect,
  443). API, worker, database, Prometheus and Alertmanager publish nothing;
  operators reach them with an SSH tunnel.
* Two Docker networks with fixed subnets and static addresses so the
  backend's trust list can name exact peers:

| Network | Subnet (example) | Members |
|---|---|---|
| `edge` | `172.30.10.0/24` | caddy `.10`, web `.11`, api `.20` |
| `data` (`internal: true`) | `172.30.20.0/24` | web, api, worker, db, prometheus, migrate, seed |

  (Web joins `data` only if it must reach the API there; one shared network
  for web→api is enough. The addresses are examples; Gate D fixes them.)
* The VPS firewall (provider firewall and/or host firewall) allows inbound 22
  (restricted to the founder's addresses where possible), 80, 443 only.

## 3. Proxy trust and client IP

VERIFIED behaviour:

* Backend ([ratelimit.py `client_ip`](../../backend/app/core/ratelimit.py)):
  the socket peer must be inside `TRUSTED_PROXY_CIDRS` **and**
  `TRUST_PROXY_HOPS > 0`; then it takes the entry `TRUST_PROXY_HOPS` from the
  right of `X-Forwarded-For`, and every hop after it must also be trusted.
  Otherwise the socket peer is the client. uvicorn runs with
  `--no-proxy-headers`, so the peer is the real TCP peer.
* Web BFF ([client-ip.ts](../../frontend/web/src/server/client-ip.ts),
  [backend.ts](../../frontend/web/src/server/backend.ts)): takes the entry
  `TRUST_PROXY_HOPS` from the right of the incoming `X-Forwarded-For` and sends
  the backend a **single-value** `X-Forwarded-For: <client>`. Production web
  refuses `TRUST_PROXY_HOPS < 1`.

Two paths, one rule:

| Path | Backend socket peer | `X-Forwarded-For` the backend sees | Result with hops=1 |
|---|---|---|---|
| Browser → Caddy → API (`/v1/media/*`) | caddy `172.30.10.10` | set by Caddy | client IP |
| Browser → Caddy → web BFF → API | web `172.30.10.11` | `<client>` set by the BFF | client IP |

PROPOSED values: backend `TRUST_PROXY_HOPS=1`,
`TRUSTED_PROXY_CIDRS=["172.30.10.10/32","172.30.10.11/32"]`; web
`TRUST_PROXY_HOPS=1`.

Why exactly two `/32`s and not the `/24`: anything else that can open a TCP
connection to the API would be allowed to name an arbitrary client IP —
another container on the network, or the Docker bridge gateway (`.1`), which
is the peer for traffic arriving through any port published on the host. A
mistakenly published API port with a trusted `/24` would let anyone on the
internet choose the IP the rate limiter charges. The worker, Prometheus and
the jobs never need to forward an end user's address, so they are not trusted.

Caddy: by default `reverse_proxy` ignores incoming `X-Forwarded-For` from
untrusted clients and sets it from the connection (Caddy documentation;
**UNKNOWN until probed** in Gate D). Gate D probe: a browser request carrying
a forged `X-Forwarded-For` must be attributed to the real client on both paths.

## 4. Worker placement

| Instance | Serves ingress | `NOTIFICATION_WORKER_ENABLED` | `SAVED_SEARCH_WORKER_ENABLED` | `LISTING_FRESHNESS_WORKER_ENABLED` |
|---|---|---|---|---|
| `api` | yes (Caddy, web) | **false** (default true) | **false** (default true) | false (default false) |
| `worker` | **no** — not in Caddy, not trusted, no published port | true | true | false for alpha (owner reminders and `stale` transitions only; public visibility is evaluated on read); true is allowed |

* `worker` is the **same image and SHA** running the same uvicorn command with
  the worker flags on. It is not a dedicated worker executable; it still
  listens on 8000 inside `data` (used for `/readyz` and `/metrics`).
* Defaults matter: an API instance started without explicit `false` flags
  runs two workers. Gate D must set them explicitly on every instance.
* If a duplicate does happen, `FOR UPDATE SKIP LOCKED` claims prevent
  duplicate delivery (VERIFIED in the worker docstrings; tests REPORTED).

## 5. Ingress rules (Caddy, PROPOSED — not operational)

```caddyfile
{$ALPHA_HOST} {
	basic_auth {
		{$ALPHA_USER} {$ALPHA_PASSWORD_HASH}
	}
	header X-Robots-Tag "noindex, nofollow"

	# The API's metrics are never public (PRODUCTION-READINESS row 8). Only
	# /v1/media/* reaches the API anyway; this is defence in depth. A `handle`
	# block, because a bare `respond` sorts after `handle` and would never run.
	handle /metrics* {
		respond 404
	}

	# Photos go straight to the API (next.config.ts: MEDIA_VIA_EDGE=1), keeping
	# the client's IP for the media rate limiter and never forwarding cookies.
	handle /v1/media/* {
		reverse_proxy 172.30.10.20:8000 {
			header_up -Cookie
			header_up -Authorization
		}
	}

	handle {
		reverse_proxy 172.30.10.11:3000 {
			header_up -Authorization
		}
	}
}
```

* Only `/v1/media/*` reaches the API from the edge. All other API routes are
  reachable only through the BFF allowlist (`/bff/v1/*`); `/metrics`,
  `/readyz`, `/docs` of the API are not routed at all.
* `header_up -Authorization` keeps the basic-auth credential out of the
  upstreams (the media route takes no auth; the BFF never reads the browser's
  `Authorization`).
* Basic auth is an access fence for an internal alpha, not user
  authentication; the password hash comes from `caddy hash-password` and lives
  only on the VPS. An IP allowlist is the alternative.
* `__Host-` cookies need HTTPS and one site: a DNS name (e.g. a subdomain the
  founder controls) and Caddy's automatic certificate. A bare IP with a
  self-signed certificate is not supported by this design.

## 6. Media

* Alpha: `MEDIA_ROOT` on a named Docker volume mounted in `api` only (workers
  do not touch media — VERIFIED worker set). Synthetic photos only.
* Staging and production: durable object storage with access control and its
  own backup is a founder decision (PRODUCTION-READINESS row 12); `pg_dump`
  never contains photo bytes.

## 7. Web image requirements (for Gate D — not implemented)

| Requirement | Source fact |
|---|---|
| Node 24 (`engines >=24 <27`, `.nvmrc` 24) | VERIFIED package.json |
| `npm ci` from `frontend/web/package-lock.json` | lockfile present |
| Build context `frontend/`, not `frontend/web`: design tokens live in `frontend/design-system` and `outputFileTracingRoot` is `frontend/` | VERIFIED next.config.ts |
| `prebuild` copies the map worker (`scripts/copy-map-worker.mjs`) — run `npm run build`, not `next build` directly | VERIFIED package.json |
| Build-time: `NODE_ENV=production`, `MEDIA_VIA_EDGE=1`, `HOMIES_WEB_ENV` unset, `NEXT_PUBLIC_*` values final (inlined) | VERIFIED next.config.ts; ENVIRONMENT-MATRIX |
| Runtime: `API_INTERNAL_URL`, `PUBLIC_ORIGIN` (https), `TRUST_PROXY_HOPS>=1`, `INDEXING_ENABLED` unset | VERIFIED server/env.ts, proxy.ts |
| `output: "standalone"` is **not** configured; choose `next start` with production `node_modules`, or add standalone output as an explicit Gate D code change | VERIFIED absence |
| Non-root user; only `.next`, `public`, `package.json`, runtime `node_modules` in the final stage | PROPOSED |
| `LABEL org.opencontainers.image.revision=<GIT_SHA>`; `NEXT_PUBLIC_APP_VERSION=<GIT_SHA>` | PROPOSED, mirrors backend/Dockerfile |
| Health check `GET /healthz` (web liveness route exists) | VERIFIED app/healthz/route.ts |
| Listens on 3000 inside `edge` only; Caddy is the only client | PROPOSED |

## 8. Future staging (Option A′, PROPOSED direction)

* EU container hosting with a **private network** whose peers can be named
  for `TRUSTED_PROXY_CIDRS` (or an equivalent trusted-peer guarantee). A
  platform that only offers changing egress IPs does not satisfy §3 without
  an additional edge (UNKNOWN per provider).
* Dedicated HTTPS ingress implementing §5 (media to API, `/metrics` closed).
* Managed PostgreSQL 16 with PostGIS 3.4 and `btree_gist`, a DBA-capable role
  for the one-time role scripts, PITR, EU region, data processing agreement.
* Immutable images in a registry, tagged by full commit SHA; the migration job
  runs from the same image; the worker is a separate instance of that image.
* Secrets in the platform's secret store; observability with a real alert
  destination; restore verification into a separate database.
* Multiple web replicas require sticky sessions or a refresh grace window
  first (SYSTEM-PASSPORT §6).

## 9. Recovery objectives

* **Private alpha:** disposable synthetic data. Recovery = recreate: drop the
  volumes, re-run bootstrap, migration and seed (STAGING-RUNBOOK §9). No RPO or
  RTO is claimed.
* **Production (PROPOSED targets, not accepted):** RPO ≤ 15 min, RTO ≤ 4 h —
  PRODUCTION-READINESS §4 candidate B. These are not current guarantees or
  canonical commitments; they need the founder's explicit operational
  decision, a PITR-capable database and a rehearsed restore including media.

## 10. Cost model (private alpha)

Public Hetzner Cloud prices read on 2026-10-30, EUR per month, **excluding
VAT**. Pages showed "currently unavailable" for several plans at capture; stock
and prices change (Hetzner repriced during 2026). Not a budget.

| Item | Assumption | Price | Source |
|---|---|---|---|
| Compute | 8 GB RAM recommended (PostGIS + API + worker + Next + Prometheus; Next build is memory-hungry): CX33 4 vCPU / 8 GB / 80 GB | €8.99 | VERIFIED hetzner.com/cloud/cost-optimized |
| Compute (fallback) | CPX32 4 vCPU / 8 GB / 160 GB (NBG1) — or CPX22 2 vCPU / 4 GB / 80 GB at €19.99 if images are built elsewhere | €35.99 | VERIFIED hetzner.com/cloud/regular-performance |
| IPv4 | plan pages state prices include IPv4; third-party sources report a separate primary-IPv4 fee (~€0.50) | €0–0.50 | conflicting — check the console |
| Traffic | 20 TB included in EU; overage €1/TB | €0 | VERIFIED plan pages |
| Persistent storage | local NVMe of the plan; no volume needed for alpha (volumes reported ~€0.057/GB) | €0 | third-party, UNVERIFIED |
| Server backups | optional for disposable data; "from €1.198" equals 20 % of the cheapest plan | ~20 % of the server | INFERRED |
| Snapshots | €0.0143/GB | ~€1 for a 60 GB image | VERIFIED |
| Domain / DNS | subdomain of a domain the founder already holds, or a new domain | UNKNOWN | founder input |
| Monitoring | Prometheus/Alertmanager on the same VPS | €0 | design |
| Managed database | not used in alpha | — | — |

Example: CX33 + backups ≈ €10.8; CPX32 + backups ≈ €43.2 (excl. VAT; VAT
treatment depends on the company's status — accountant). Future staging needs
its own estimate (managed PostgreSQL with PostGIS, registry, ingress, object
storage, observability); none was collected here.
