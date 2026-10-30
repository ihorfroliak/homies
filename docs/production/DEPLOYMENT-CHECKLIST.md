# Deployment checklist

A gate list, not a status page: ticking a box records evidence for one
deployment at one SHA. Current state lives in
[PROJECT-STATUS](../PROJECT-STATUS.md). Procedure:
[STAGING-RUNBOOK](STAGING-RUNBOOK.md).

Separate states (never merged into one "done"):
**BUILT** (images for `<SHA>`) → **VERIFIED** (CI 6/6 on `<SHA>`) →
**ACCEPTED** (founder GO for this environment) → **DEPLOYED** (running) →
**SMOKE-PASSED** (§4 evidence recorded). A green CI is not a deployment
approval; an alpha deployment is not a production approval.

## 1. Before anything is created (Gate D authorisation)

- [ ] Founder GO names the environment (alpha / staging), the provider, the region and the resources to create.
- [ ] `<SHA>` is on `main`; all six CI checks are green on exactly `<SHA>`.
- [ ] Release manifest read: `schema_transition` and `rollback_to_previous` of `<SHA>` understood; for BARRIER/BLOCKED the recovery path is forward repair or recreate.
- [ ] No live provider: `EMAIL_PROVIDER=stub`, `PAYMENT_PROVIDER=simulation`, no `STRIPE_*`, no `SMTP_*`.
- [ ] Data is synthetic only.

## 2. Configuration

- [ ] Secrets generated on the target and stored only there (ENVIRONMENT-MATRIX); none in Git, images, PRs or chat.
- [ ] `ENV` is `alpha` / `staging` — never `local`.
- [ ] `PUBLIC_ORIGIN` = `PUBLIC_WEB_BASE_URL` = the real https origin.
- [ ] `TRUSTED_PROXY_CIDRS` lists only the edge and web peers; `TRUST_PROXY_HOPS=1` on api and web.
- [ ] Worker flags explicitly `false` on every serving instance; enabled only on the non-ingress worker.
- [ ] `INDEXING_ENABLED` unset; `HOMIES_WEB_ENV` unset; `NEXT_PUBLIC_E2E_HOOKS` unset.
- [ ] Only the HTTPS entry point publishes ports.

## 3. Database and release

- [ ] Role bootstrap in order: `migration_role.sql` → migrator password → `app_role.sql` → `app_grants.sql` → app password.
- [ ] `migrate --plan` reviewed (head `23e89acb98b4` at the time of writing; 7 BARRIERs from an empty database).
- [ ] `--allow-barrier` used only under an explicit GO.
- [ ] Second `migrate` run is a no-op; `release check` allowed.
- [ ] The application connects as `homies_app`; the migrator credential is not present on serving instances.

## 4. Smoke evidence (record, don't assume)

- [ ] `/readyz` 200 on api and worker; restart of `db` → `/readyz` 503 → recovers to 200.
- [ ] Unauthenticated request → access fence (alpha).
- [ ] `X-Robots-Tag: noindex` on public pages.
- [ ] `/metrics` not reachable from outside.
- [ ] `/v1/media/<id>` served by the API through the edge; no cookies forwarded.
- [ ] A forged `X-Forwarded-For` does not change the attributed client.
- [ ] Founder journey: search → listing → save → login → message → viewing request → provider confirms/declines → requester sees the state.
- [ ] Another user cannot read the conversation or viewing (403/404).
- [ ] No exact address or coordinates in public pages or BFF responses.
- [ ] Logs contain no secret, DSN, token or message body.

## 5. Recovery

- [ ] Alpha: reset and recreate procedure known (STAGING-RUNBOOK §9).
- [ ] Staging/production: backup taken and restore verified into a separate database, including media; RPO/RTO measured. Targets RPO ≤ 15 min / RTO ≤ 4 h are PROPOSED, not accepted (STAGING-ARCHITECTURE §9).

## 6. Not on this checklist

Production launch, legal and privacy gates, indexing, real providers and
real users are outside private alpha and staging; they need their own
founder decisions (02, PRODUCTION-READINESS).
