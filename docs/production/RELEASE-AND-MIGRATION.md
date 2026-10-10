---
id: RELEASE-AND-MIGRATION
name: Release and migration compatibility
type: production_policy
status: builder_verified
verification: BUILDER VERIFIED · MILESTONE AUDIT DEFERRED
introduced_by: PR-002
---

# Release and migration compatibility (PR-002)

How a Homies release moves the database schema, whether the previous release
can keep running, and whether it can be restored. Code:
[app/core/release.py](../../backend/app/core/release.py) (manifest and
decision), [app/scripts/migrate.py](../../backend/app/scripts/migrate.py)
(migration job), [app/core/sql/](../../backend/app/core/sql/) (roles and
grants). **Production: NOT READY · NOT DEPLOYED** — nothing here has run
against a production database. Verification: **BUILDER VERIFIED · MILESTONE
AUDIT DEFERRED** — builder evidence and CI only; the independent review is part
of the later milestone / production-readiness audit, not a per-task audit.

### Terms kept apart

| Term | Means | Does not mean |
|---|---|---|
| schema compatibility | this build may run on this database schema (the decision, §5) | that the previous release may be restored |
| release rollback safety | the previous release may be restored (`rollback_to_previous`, §9) | that any schema is compatible |
| migration authority | the migration role (`homies_migrator`) through the migration job (§6) | anything the application process can do |
| application authority | the application role (`homies_app`): DML on application tables only (§7) | schema changes, the schema's record |
| release compatibility policy | the committed `app/release.json` (§3) | the build's identity |
| build identity | the commit the image was built from, injected at build time (§3) | a committed field |
| deployment | running an image against a real environment | anything done here: **NOT DEPLOYED** |
| production readiness | the milestone's production-readiness transition | "builder verified" or "integrated into main for continued development": **NOT READY** |

## 1. Two separate questions

| Question | Answered by | Values |
|---|---|---|
| Can this build run against this database schema? | the compatibility decision, at every start and by `python -m app.scripts.release check` | allowed: EXACT, BEHIND_SUPPORTED, AHEAD_COMPATIBLE · refused: UNMIGRATED, MULTIPLE_DB_HEADS, TOO_OLD, TOO_NEW, UNKNOWN_SCHEMA, DIVERGENT, LINEAGE_MISSING, LINEAGE_MISMATCH |
| May the previous release be restored? | the release manifest's explicit declaration, `python -m app.scripts.release rollback-allowed` | SAFE · BLOCKED |

They are independent. A migration can be purely additive while the previous
release is still unable to understand the new data (TASK-014 is one: see §4).
Rollback safety is never inferred from "the migration was additive", "a
downgrade exists" or "the old image starts".

## 2. Vocabulary

**Per migration step** — every migration from PR-002 on declares, as module
attributes (the template defaults to the fail-closed pair):

| Declaration | Meaning |
|---|---|
| `schema_transition = "EXPAND"` | the release before this step keeps working on the schema after it (new nullable column, new table, index, widening, a structure old code ignores) |
| `schema_transition = "BARRIER"` | it does not: a drop, a one-step NOT NULL, an incompatible enum/state, a contract step |
| `rollback_to_previous = "SAFE"` | the previous release may run on / return to this schema without reopening a fixed defect or losing an invariant |
| `rollback_to_previous = "BLOCKED"` | otherwise. A BARRIER is always BLOCKED |

**Per release** — the [release manifest](#3-release-manifest):

| Field | Meaning |
|---|---|
| `schema_transition` | `NO_SCHEMA_CHANGE` (no migration since the previous release), `EXPAND` (only EXPAND steps), `BARRIER` (at least one BARRIER). Checked against the migrations; a code-only release has no migration at all — never a fake one |
| `rollback_to_previous` | SAFE or BLOCKED, declared. Cannot be SAFE across a step that is BLOCKED; may be BLOCKED for code reasons alone |

## 3. Release manifest (policy) and build identity

Two things, kept apart and combined only at runtime:

* the **release compatibility policy** — committed as
  [`backend/app/release.json`](../../backend/app/release.json) and shipped in
  the image: schema head, lineage boundaries, transition, rollback policy,
  manifest version. It holds **no commit id**: a committed file cannot contain
  the SHA of the commit that contains it (writing that field changes the
  commit). A `build_sha` key in it is rejected;
* the **build identity** — the 40-hex commit the image was built from,
  injected by the build: `docker build --build-arg GIT_SHA=<commit>` →
  `HOMIES_BUILD_SHA`, and the OCI label `org.opencontainers.image.revision`.
  The Dockerfile has no default. Outside `ENV=local/test/ci` a missing
  identity refuses startup (`BuildIdentityError`) and `release manifest`
  (exit 1); a malformed one ("unknown", a short id, upper case) is refused in
  every environment.

`RuntimeReleaseIdentity` = policy + build identity, printed by
`python -m app.scripts.release manifest` and logged at startup.

```json
{
  "manifest_version": 1,
  "release": "PR-002 — release and migration compatibility",
  "schema_head": "0c4e6a8b2d91",
  "minimum_schema": "f3b5d7e9a1c2",
  "maximum_schema": "0c4e6a8b2d91",
  "schema_transition": "EXPAND",
  "rollback_to_previous": "BLOCKED",
  "rollback_note": "…why…",
  "previous_release": {"id": "IBB-001", "schema_head": "f3b5d7e9a1c2"}
}
```

* `schema_head` — this build's migration head (must equal the image's scripts).
* `minimum_schema` / `maximum_schema` are **lineage boundaries, not a string
  or numeric range**: a revision is inside when `minimum_schema` is one of its
  ancestors and it is one of the head's ancestors. No `min <= revision <= max`
  comparison exists anywhere.
* `minimum_schema` — the oldest revision this build runs on; an ancestor of the
  head. Lets the new build start before the migration job ("app first").
* `maximum_schema` — this build's head: the newest revision it contains. A
  database *beyond* it is admitted only through lineage steps each recorded
  EXPAND **and** SAFE (§5); anything else is TOO_NEW.
* Strict: unknown/missing keys, revisions the build does not carry, a range
  that is not an ancestry, or declarations contradicting the migrations are
  errors, and the application refuses to start.

The build SHA is **not** exposed on the public `/metrics` endpoint; a
`build_info` metric waits for internal metrics exposure (PR-001 ingress gap).

## 4. Schema lineage

Alembic revision ids are graph nodes, not versions: `0c4e6a8b2d91` (PR-002)
sorts before `f3b5d7e9a1c2` (its parent), and `b8d0f2a4c6e1` is much older than
`b8d0f2a4c6e8`. They are never compared as strings.

* The build knows its own graph (its migration scripts).
* The database records its own in `schema_lineage` (revision, parent,
  schema_transition, rollback_to_previous, recorded_by, applied_at), written
  by Alembic's `on_version_apply` hook in the migration transaction — so a
  newer database can tell an older build how it got there.
* PR-002's migration `0c4e6a8b2d91` creates the table and backfills the 26
  earlier steps from the frozen classification
  ([lineage_registry.py](../../backend/app/core/lineage_registry.py)); each
  later step records itself. Written by the migration role only.
* Once a database includes `0c4e6a8b2d91`, its lineage is part of the schema:
  a missing table is **LINEAGE_MISSING**, rows that disagree with the build's
  own migrations are **LINEAGE_MISMATCH** — both refused. The application never
  creates or repairs lineage; the migration job refuses too (it records
  lineage only for the steps it applies). A database *before* `0c4e6a8b2d91`
  (IBB-001 and older) has no lineage by definition and is decided by the
  build's own graph.
* The history is one chain. A merge revision (two parents) is refused when
  the build's graph is read and when lineage is recorded; the decision never
  guesses across a merge.

### Historical classification (26 steps before PR-002)

| Class | Steps |
|---|---|
| EXPAND / SAFE (14) | 87cebed1635f, f91f4ece13f6, 9010d2077493, e5a2c91b7d34, a1c6d2e8b407, a8b2c4d6e1f3, b3c5d7e9f1a2, c4d6e8f0a2b3, d5e7f9a1b3c4, a7c9e1f3b5d2, b8d0f2a4c6e1, d3f5b7a9c1e4, a7c9e1f3b5d7, d0f2b4c6e8a1 (TASK-013 indexes) |
| EXPAND / BLOCKED — additive but not rollback-safe (6) | d3f81ba0c47e (verified-phone gate), b7e4f19a2c60 (authority), f1a7c3d9e2b4 (location privacy), c1e3a5b7d9f2 (media GPS stripping), b8d0f2a4c6e8 (freshness/`stale`), **f3b5d7e9a1c2 (TASK-014)** |
| BARRIER / BLOCKED (6) | 2d9d18df4688 (base), b910997aa651, c4d2e77a1b30, c9d3a5e71f28, d4e8b2c61a95, e4f6a8b0c2d4 (one-step NOT NULL / drop) |

TASK-014 `f3b5d7e9a1c2` adds tables and a constant-default
column — additive — but the TASK-013 release publishes without the publicity
seam (no public generation, no episode, so alerts are missed and the N/N+1
identity drifts) and has no `/v1/notifications/unsubscribe` for links already
emailed: **EXPAND / BLOCKED**. PR-002's own `0c4e6a8b2d91` is **EXPAND /
BLOCKED**: one table the previous release never reads, but IBB-001 still
requires its exact head and refuses to start.

## 5. The compatibility decision

For database revision *D* and this build (head *H*, minimum *M*):

1. no revision → UNMIGRATED; more than one → MULTIPLE_DB_HEADS;
3. *D* in this build's graph: not an ancestor of *H* → DIVERGENT; at or after
   the lineage migration with the lineage absent → LINEAGE_MISSING, or with
   rows that disagree with *D*'s ancestry → LINEAGE_MISMATCH; *D = H* →
   **EXACT**; an ancestor of *H* and descendant of (or equal to) *M* →
   **BEHIND_SUPPORTED**; an ancestor older than *M* → TOO_OLD;
4. *D* unknown to this build: walk `schema_lineage` from *D* by parent; every
   step must be EXPAND and SAFE until the walk reaches *H* →
   **AHEAD_COMPATIBLE**; a BARRIER or BLOCKED step → TOO_NEW; a missing row or
   no table → UNKNOWN_SCHEMA; a root, a branch onto a revision the build knows,
   a cycle or 500 steps → DIVERGENT; the build's own part of the lineage must
   also agree (LINEAGE_MISMATCH otherwise).

Startup (every environment except `local` and `test`) refuses anything not
allowed — no warning-and-continue — and logs one `schema_compatibility` line
(decision, database revision, build SHA, release, range; never a URL). Outside
`local`/`test`/`ci` it then refuses a build without an injected identity (§3),
and an application role that can change the schema or write
`alembic_version` / `schema_lineage` / `spatial_ref_sys` (§7).

## 6. Migration job

```bash
ALEMBIC_DATABASE_URL=<migration role> python -m app.scripts.migrate --plan
ALEMBIC_DATABASE_URL=<migration role> python -m app.scripts.migrate [--allow-barrier]
```

1. Refuses the application role and any role without CREATE on the schema.
2. Takes the migration advisory lock. PostgreSQL advisory locks are
   session-scoped: the job takes `pg_advisory` key `homiesMG` on **one**
   connection and runs every Alembic statement on that same connection
   (`config.attributes["connection"]`), keeping it until the job ends; before
   Alembic starts it re-checks in `pg_locks` that its own backend holds the
   lock (`MIGRATION_LOCK_LOST` otherwise). The wait is **bounded by the job
   itself**: `pg_try_advisory_lock` polled against a monotonic 10 s deadline —
   never a blocking `pg_advisory_lock`, so the budget does not depend on the
   server applying `lock_timeout` to advisory locks. A second runner exits 1
   `MIGRATION_LOCK_TIMEOUT` after 10 s and changes nothing; one that gets the
   lock after the first finished finds nothing to do. Separately, the session's
   `lock_timeout = 10s` bounds each DDL statement's wait for table locks. Both
   are migration policy only — not the application's query timeout, not the
   readiness budget, not PR-003's client deadlines.
3. Plans; a pending BARRIER outside `local`/`test`/`ci` needs `--allow-barrier`
   (a maintenance deploy). A database newer than the build is left alone when
   the decision admits it.
4. Upgrades to the build's head only — no revision argument, never a downgrade
   — in one transaction (a failure leaves the database at its previous
   revision; exit 2).
5. Converges the application role's privileges
   ([app_grants.sql](../../backend/app/core/sql/app_grants.sql)) on every run,
   whichever role created a table (drift heals).
6. Verifies head, `schema_lineage` against every step's declarations and the
   application role's grants — none on the schema's record or on the
   append-only tables' UPDATE/DELETE, and the full intended set on **every**
   application table and sequence. A table the migration role cannot grant
   on (another owner) is named and the job exits 3.

## 7. Roles

| Role | Provisioned by | Can | Cannot |
|---|---|---|---|
| `homies_migrator` | DBA once: [migration_role.sql](../../backend/app/core/sql/migration_role.sql) (also creates `btree_gist`, `postgis`) | own the tables it creates, CREATE on schema, write `alembic_version` / `schema_lineage`, take the migration lock | superuser, create roles or databases, write `spatial_ref_sys` (DBA-owned) |
| `homies_app` | DBA once: [app_role.sql](../../backend/app/core/sql/app_role.sql); grants by every migration job | DML on application tables; read `alembic_version`, `schema_lineage`, `spatial_ref_sys` | CREATE/ALTER/DROP, TRUNCATE, write the schema's record or `spatial_ref_sys`, UPDATE/DELETE append-only tables, run the migration job |

**Future objects.** PostgreSQL default privileges (`ALTER DEFAULT
PRIVILEGES`) bind only the role that ran them, so they are not relied on:
nothing is granted to `homies_app` automatically when `homies_migrator`
creates a table or sequence. Every migration job converges the grants per
object the migration role owns, and its post-verify proves the full intended
set on every application table and sequence (tested on real PostgreSQL with a
table, its serial sequence and a standalone sequence created after
provisioning).

**Existing databases (pre-PR-002).** Their objects are owned by whichever role
ran `alembic upgrade head` (often the bootstrap superuser). Before the first job
as `homies_migrator`, the DBA runs
[migration_owner.sql](../../backend/app/core/sql/migration_owner.sql) once: it
transfers the application's tables, views, standalone sequences, types and
routines in `public` to `homies_migrator`, never an extension's members
(`spatial_ref_sys`, PostGIS functions). `REASSIGN OWNED` is not used — it fails
for the bootstrap superuser and moves more than the application's objects.
Without the transfer the job cannot read or advance `alembic_version` and fails
with the database unchanged; with an object it still cannot grant on, the
post-verify fails (exit 3). Provisioning order for an existing database:
`migration_role.sql` → `app_role.sql` → `migration_owner.sql` → the migration
job (which applies `app_grants.sql`).

## 8. Deployment patterns with Homies examples

| Release | Migration before or with rollout? | Old app coexists? | Rollback to previous? | Maintenance? |
|---|---|---|---|---|
| **NO_SCHEMA_CHANGE** — e.g. MICRO-001 (tests and docs only) | no migration | yes | as declared (SAFE unless the code changes a behaviour the old release breaks) | no |
| **EXPAND / SAFE** — e.g. `d0f2b4c6e8a1` (TASK-013 discovery indexes) | migrate first, then roll replicas; old replicas keep serving (AHEAD_COMPATIBLE) | yes | SAFE: redeploy the previous image; the database stays | no |
| **EXPAND / BLOCKED** — e.g. `f3b5d7e9a1c2` (TASK-014), `0c4e6a8b2d91` (PR-002) | migrate first; the new build may start before it (BEHIND_SUPPORTED within its minimum) | the running old replicas keep working, but a restarting one is refused (TOO_NEW) — keep the overlap short | **BLOCKED**: forward-fix, or restore to the recorded recovery point | no downtime needed, but no rollback path |
| **BARRIER** — e.g. `e4f6a8b0c2d4` (`address_id` NOT NULL + UNIQUE) | stop the old release → `migrate --allow-barrier` → start the new one | no | BLOCKED | yes — or split into EXPAND now + CONTRACT later |

Prefer expand → transition → contract: add the new shape (EXPAND), dual-write
and backfill in code releases, switch reads, and only then contract (BARRIER)
once no supported rollback target reads the old shape.

## 9. N−1 rollback policy (Phase 1)

A release may be rolled back to the previous release **only when its manifest
declares `rollback_to_previous = SAFE`** and the previous image's own `release
check` against the live database is allowed. Both commands must exit 0:

```bash
docker run --rm <new image>      python -m app.scripts.release rollback-allowed
docker run --rm <previous image> python -m app.scripts.release check
```

When `rollback_to_previous = BLOCKED` (PR-002 itself, TASK-014): restarting
the previous image is not a recovery path. Recovery is a forward repair
release, or — for data damage — a restore to the recovery point recorded
before the migration (BACKUP-RESTORE.md). The database is never downgraded
automatically; `alembic downgrade` is a development tool.

No universal N−1 promise is made; there is no promise beyond N−1.

## 10. Release runbook (outline, to rehearse on staging)

1. CI green on the exact SHA (image built with `GIT_SHA`; CI proves an image
   without it refuses).
2. `release manifest` from the image; read `schema_transition` and
   `rollback_to_previous`.
3. `migrate --plan` against the target. BARRIER → maintenance window;
   BLOCKED → record a recovery point first.
4. `migrate` (with `--allow-barrier` only for a planned BARRIER); stop on a
   non-zero exit.
5. Roll replicas; each start logs `schema_compatibility`.
6. Readiness, smoke, observe.
7. Record image, SHA, database revision before/after.


## Rollback barriers recorded per release

| Release | Schema | Rollback to previous | Why |
|---|---|---|---|
| **BP-10** (candidate, D-108; not merged) | `11d778ab87a3` (EXPAND) | **BLOCKED** | rolling back to the previous backend restores the unkeyed message-write path (its `MessageIn` silently drops `client_message_id`) and reopens the BP-10 / BB-11 duplicate-send invariant. The build needs its own head (`minimum_schema` = head: migrate first); keyed frontend sends stay off until every serving instance runs BP-10 |
| TASK-015 S1 | `a3c5e7f9b1d4` (EXPAND) | BLOCKED | the previous publication ignores moderation holds |
| TASK-015 S2+S3 | no change | BLOCKED (operational) | removes report intake and moderator operations |
| TASK-015 S5 | no change | BLOCKED (operational) | strands open review requests |
| **TASK-015 S4b** | no change | **BLOCKED — safety barrier** | the S4a build confirms viewings on a held listing, ignores the G-14 re-contact bar and does not lock a conversation before sending; the S4a privacy barrier stands behind it |
| **TASK-015 S4a** | no change | **BLOCKED — security/privacy barrier** | the S5 build serialises `messages.body` without reading `redacted_at`: rolling back re-exposes every removed message. Never restart an older image once a redaction exists |
