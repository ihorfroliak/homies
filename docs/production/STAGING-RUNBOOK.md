# Runbook — private alpha (and the deltas for future staging)

**NOT EXECUTED. Gate B documents the procedure; running any step that
creates, buys, configures or mutates something is Gate D and needs the
founder's explicit authorisation for that step.** Design:
[STAGING-ARCHITECTURE](STAGING-ARCHITECTURE.md). Variables:
[ENVIRONMENT-MATRIX](ENVIRONMENT-MATRIX.md). Checklist:
[DEPLOYMENT-CHECKLIST](DEPLOYMENT-CHECKLIST.md).

Each step lists: what → why → check → who approves. `<SHA>` is the full
40-hex commit chosen for the alpha; `$DB` is the alpha database name (e.g.
`homies_alpha_e2e`).

## 1. Preconditions

| Step | Why | Check | Approves |
|---|---|---|---|
| Choose `<SHA>`: a commit on `main` whose CI has all six checks green | deploy only what CI verified | GitHub Actions run on exactly `<SHA>` | founder |
| Gate D authorised: VPS purchase, DNS name, web Dockerfile, compose/Caddy files | none of these exist yet | written GO | founder |
| Web image definition exists (STAGING-ARCHITECTURE §7) | there is no web Dockerfile today | merged Gate D change | founder |
| Seed tooling decided (dev extras image or throwaway container) | the production image lacks `httpx` | Gate D change | founder |

## 2. Server

1. EU VPS (candidate: Hetzner Cloud, Germany; 8 GB RAM), SSH key login only,
   password login disabled, automatic security updates on.
2. Firewall: inbound 22 (restricted where possible), 80, 443; nothing else.
3. Docker Engine with the Compose plugin from the distribution's or Docker's
   official repository.
4. DNS `A`/`AAAA` record for `ALPHA_HOST` → the VPS.

Check: from outside, only 22/80/443 answer (`nmap` or the provider's
firewall view).

## 3. Secrets file

Create `/opt/homies/alpha.env` (owner root, mode `600`) with **values
generated on the server** (e.g. `openssl rand -base64 48`): `JWT_SECRET`,
`WEBHOOK_SECRET`, `POSTGRES_PASSWORD`, the `homies_app` and
`homies_migrator` passwords (embedded in `DATABASE_URL` /
`ALEMBIC_DATABASE_URL`), `ALPHA_USER`, `ALPHA_PASSWORD_HASH`. Never copy a
value into Git, a ticket, a PR or chat. Names and rules:
ENVIRONMENT-MATRIX.

## 4. Build the images (on the VPS from a clean checkout, or in CI later)

```bash
git clone https://github.com/ihorfroliak/homies.git /opt/homies/src
git -C /opt/homies/src checkout --detach <SHA>
docker build --build-arg GIT_SHA=<SHA> -t homies-api:<SHA> /opt/homies/src/backend
docker run --rm homies-api:<SHA> python -m app.scripts.release manifest
```

Check (the same checks CI's `image` job runs): `build_sha` in the manifest =
`<SHA>`; the label `org.opencontainers.image.revision` = `<SHA>`;
`printenv ENV` in the image prints `production`. The web image is built per
the Gate D definition with `MEDIA_VIA_EDGE=1` and
`NEXT_PUBLIC_APP_VERSION=<SHA>`.

## 5. Database bootstrap (fresh database, exact order)

Start only `db` (PostgreSQL 16 + PostGIS 3.4, `POSTGRES_DB=$DB`). As the
bootstrap superuser, with the role scripts mounted read-only from
`backend/app/core/sql/`:

```bash
psql -v ON_ERROR_STOP=1 -1 -d $DB -f migration_role.sql   # role + btree_gist, postgis
psql -v ON_ERROR_STOP=1 -d $DB -c "ALTER ROLE homies_migrator LOGIN PASSWORD '<from alpha.env>'"
psql -v ON_ERROR_STOP=1 -1 -d $DB -f app_role.sql         # NOLOGIN until a password is set
psql -v ON_ERROR_STOP=1 -1 -d $DB -f app_grants.sql       # idempotent; the job re-applies it
psql -v ON_ERROR_STOP=1 -d $DB -c "ALTER ROLE homies_app LOGIN PASSWORD '<from alpha.env>'"
```

* `migration_owner.sql` is **not** run: it is only for databases that existed
  before PR-002 ([RELEASE-AND-MIGRATION §7](RELEASE-AND-MIGRATION.md#7-roles)).
* Typing a password on the command line leaves it in shell history; prefer
  `\password` in an interactive `psql`, or a here-document from the secrets
  file.
* The application never connects as the superuser; the superuser password
  stays in `alpha.env` for DBA work only.
* UNKNOWN until Gate D: CI's `Migrate` step connects as the CI superuser, so
  this exact role-based bootstrap from an empty database is evidenced by the
  PostgreSQL release tests (REPORTED), not by that CI step. Rehearse it once
  on a disposable local database first.

## 6. Migration job

The migration job runs from `homies-api:<SHA>` with `ENV=alpha` and
`ALEMBIC_DATABASE_URL` (role `homies_migrator`) only.

1. **Plan, change nothing:** `python -m app.scripts.migrate --plan`. Expect the
   full chain from base to `23e89acb98b4`, 30 steps including 7 BARRIERs. A
   production-like `ENV` refuses BARRIERs without the flag (`BARRIER_NOT_ALLOWED`).
2. **Explicit BARRIER authorisation** (a fresh database crosses the historical
   BARRIERs; CI does the same): `python -m app.scripts.migrate --allow-barrier`.
   For the alpha's empty database this is the founder's Gate D GO; on any
   database with data it is a maintenance deploy with the old release stopped
   (RELEASE-AND-MIGRATION §8).
3. **Verify:** run `python -m app.scripts.migrate` again → no pending steps
   (no-op). The job's post-verify has already checked head, `schema_lineage`
   and the grants of `homies_app`; a failure prints
   `{"result": "verify_failed"}` and exits non-zero.
4. **Compatibility:** `python -m app.scripts.release check` with the
   application's `DATABASE_URL` → allowed.

Forbidden assumptions:

* there is no automatic downgrade;
* `git revert` does not undo a schema change;
* the current release is `rollback_to_previous = BLOCKED` — restarting an
  older image is not recovery.

Recovery is forward repair, or (alpha) recreate (§9).

## 7. Synthetic data (alpha only)

From a tools container built from the same `<SHA>` with the `dev` extras,
`ENV=test`, `DATABASE_URL` = the alpha database, both opt-ins set to `1`:

```bash
python -m app.scripts.seed_e2e
python -m app.scripts.seed_engagement_e2e --manifest /opt/homies/private/engagement-manifest.json
```

The seed refuses unless `ENV` is `local`/`test`/`ci` **and** the database name
ends in `_e2e`/`_test`/`_ci`
([seed_e2e.py](../../backend/app/scripts/seed_e2e.py)). The manifest lists
synthetic accounts (`seeker`, `provider` with a verified authority root, and
others) and the listing `approval`, whose provider confirms or declines
viewings ([FE-003-E2E-FIXTURES](../engineering/FE-003-E2E-FIXTURES.md)). Its
passwords are published in the repository — another reason the alpha sits
behind the access fence. UNKNOWN until rehearsed: whether the seed needs more
than `homies_app` DML.

## 8. Start and verify

Start order: `worker`, `api`, then `web`, then `caddy`. Instance flags as in
[STAGING-ARCHITECTURE §4](STAGING-ARCHITECTURE.md#4-worker-placement).

| Check | Expected |
|---|---|
| `api` and `worker` `/readyz` (inside `data`, e.g. `docker compose exec`) | 200 |
| `api` logs | JSON lines; no secret or DSN; `ENV=alpha`; build SHA = `<SHA>` |
| Worker placement | `worker`'s `/metrics` shows `homies_worker_passes_total` advancing for the notification and saved-search workers; `api`'s shows no passes |
| `https://ALPHA_HOST/` without credentials | 401 from the basic-auth fence |
| With credentials | home page; response header `X-Robots-Tag: noindex…` |
| `https://ALPHA_HOST/metrics` | 404 |
| `https://ALPHA_HOST/v1/media/<id of a seeded public photo>` | 200 image, served by `api` |
| Request with a forged `X-Forwarded-For` | rate limiting attributes the real client (Gate D probe) |
| External port scan | only 80/443 (+22) open |
| Founder journey with seeded accounts | search → listing → save → login → message → viewing request on `approval` → `provider` confirms or declines → `seeker` sees the state |
| Exact address / coordinates | never visible in public pages or BFF JSON |

Record `<SHA>`, image IDs, DB head and the date in the Gate D report.

## 9. Reset and recreate (alpha)

Alpha data is disposable; there is no recovery objective.

1. `docker compose down` and remove the `db` and `media` volumes.
2. Repeat §5 → §8 with the same or a newer `<SHA>`.

Optional training: run `backend/scripts/backup/backup.sh` and `restore.sh`
into a second database to learn the procedure. This proves nothing about
production RPO/RTO and is not a certification
([BACKUP-RESTORE](BACKUP-RESTORE.md)).

## 10. Deltas for future staging

* Images from a registry, tagged by full SHA, built by CI — never rebuilt on
  the host.
* Managed PostgreSQL/PostGIS: the provider's admin role runs §5; PITR on;
  restore verified into a separate database, including media.
* Migration job as a platform one-off task; worker as a separate service of
  the same image without ingress.
* No seed scripts: synthetic data comes from a dedicated, reviewed procedure
  (the E2E seed refuses production-like environments by design).
* Real alert destination, log retention, the secret store, and the
  sticky-session or grace-window decision before more than one web replica.
