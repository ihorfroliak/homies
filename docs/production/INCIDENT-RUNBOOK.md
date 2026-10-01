# Incident runbook — outline (PR-001)

Not rehearsed. No production, no on-call, no alert destination exists yet;
this is the outline staging must exercise. Database recovery details:
`docs/runbooks/dr-database-recovery.md` and `BACKUP-RESTORE.md`.

## First five minutes (any incident)

1. Open an incident record (time, reporter, symptom).
2. Check `/readyz` on each instance and the Prometheus alerts page. A frozen
   database answers 503 within the 3 s decision budget. With PR-003 (candidate,
   not merged) the probes no longer queue behind hung business requests; on a
   build without it they can (RA-3) — set orchestrator probe timeouts
   accordingly.
3. Collect request ids (`X-Request-ID`) from failing responses; search the
   logs by them (`request_id` field in `LOG_FORMAT=json`).
4. Freeze deploys.

## Monitoring and alerting matrix

| Condition | Signal | Source | Condition concept | Destination (wanted) | Implemented |
|---|---|---|---|---|---|
| Application unavailable | scrape fails | Prometheus `up{job="homies-api"}` | `== 0` for 2 m (`ApiDown`) | page | rule **yes**; destination **no** |
| Database unavailable | readiness | `homies_database_up`, `homies_database_last_check_timestamp_seconds`, `/readyz` 503 | `== 0` / stale > 5 m (`DatabaseUnreachable`, `DatabaseHealthStale`) | page | rule **yes**; destination **no** |
| Elevated 5xx | HTTP metrics | `homies_http_requests_total` | 5xx ratio (`HighServerErrorRate`) | page | rule **yes**; destination **no** |
| Latency | HTTP histogram | `homies_http_request_duration_seconds` | p95 (`HighRequestLatency`) | ticket | rule **yes** |
| Migration / startup failure | process exits; readiness never green | container logs (`SchemaNotMigratedError`, `InsecureConfigurationError`, `LedgerPrivilegeError`) + `up` | deploy step fails; instance never ready | deploy pipeline + page | **no** pipeline exists |
| Notification backlog | outbox depth as last reported by a running worker | `homies_notification_queue_depth` (DB-wide, same on every replica), `homies_notifications_dead_total` | `sum(max by (status)(…pending|failed)) > 100` for 15 m (`NotificationBacklogGrowing`; replica-safe, PR-001R F6); any dead (`NotificationsDeadLettered`) | ticket | rules **yes** |
| Worker hung, dead or failing (notifications, saved-search-alerts, listing-freshness) | worker liveness | `homies_worker_next_pass_due_timestamp_seconds`, `homies_worker_consecutive_failures`, `homies_worker_passes_total` | overdue > 5 m (`WorkerOverdue`); ≥ 5 failed passes for 10 m (`WorkerFailing`) | ticket | rules **yes** (PR-003 candidate) |
| Database stops answering established sessions | client deadline | `homies_db_client_deadline_exceeded_total{operation}` | ≥ 3 in 5 m for 5 m (`DatabaseStoppedAnswering`) | ticket | rule **yes** (PR-003 candidate) |
| Write with unknown outcome | abandoned COMMIT | `homies_db_unavailable_responses_total{reason="commit_unknown"}` | any in 1 h (`DatabaseWriteOutcomeUnknown`) | ticket | rule **yes** (PR-003 candidate) |
| Requests refused for database reasons | 503 by reason | `homies_db_unavailable_responses_total{reason}`; pool / thread-pool gauges | counted in `HighServerErrorRate` | page | rule **yes** |
| Disk / storage | node metrics | node-exporter / provider | < 15 % free | page | **no** (no infrastructure) |
| Backup failure | job exit / artifact age | backup job metrics | no successful backup in 26 h | page | **no** (no scheduled job) |
| Restore verification failure | drill result | CI restore drills; scheduled staging drill | drill red | ticket | CI **yes**; scheduled **no** |

Rules live in `ops/monitoring/rules/homies.rules.yml` and are unit-tested by
promtool in CI. Payment/refund/chargeback/booking-expiry rules watch the
dormant legacy modules and fire on nothing in Phase 1A.

## Playbooks (outline)

* **API down / not ready:** check logs for the startup errors above; DB
  reachable? schema at head? app role correct? → fix config or run the
  migration step; never self-migrate from the app outside `local`.
* **Database down:** instances go not-ready (by design, they stay alive);
  restore service per provider; if data is lost → BACKUP-RESTORE.md.
* **5xx spike:** find the request ids, the endpoint, the exception; roll back
  code by image (PRODUCTION-READINESS.md §5) if introduced by a release.
* **Notification backlog:** worker running? provider failing?
  `homies_notifications_failed_total` by channel; dead letters need manual
  replay (no tooling yet).
* **Suspected data exposure:** stop the affected surface, preserve logs,
  founder decision on disclosure — legal review required.

## Database stall — frozen, partitioned or overloaded database (PR-003)

What the application does by itself (PR-003 candidate): every database wait is
bounded (connect 3 s, pool 5 s, lock 2 s, statement 5 s, no answer at all 7 s);
requests get 503 + `Retry-After: 5`; health, readiness and metrics keep
answering; workers back off; nothing needs a restart when the database returns.

1. Signals: `DatabaseUnreachable` (readiness), `DatabaseStoppedAnswering`,
   `HighServerErrorRate`; `homies_db_unavailable_responses_total` by reason
   says *which* wait failed (`lock_timeout`/`statement_timeout` = the database
   is alive but contended or slow; `client_deadline`/`connection` = it is not
   answering or not reachable; `pool_timeout` = this instance's pool is
   exhausted — check `homies_db_pool_connections_in_use`).
2. Do **not** restart healthy-but-waiting replicas: liveness does not depend on
   the database by design; restarting stampedes the database at recovery.
3. Database host: paused or stalled VM, CPU steal, storage latency, network
   path; `pg_stat_activity` for long `active` / `idle in transaction` sessions
   and lock chains.
4. After recovery, `DatabaseWriteOutcomeUnknown`: list the affected requests by
   request id in the logs (`database unavailable (commit_unknown)`), and check
   for duplicated creates (property, classified, message) from client retries.
5. The migration job is **not** bounded by PR-003: run it under the job
   runner's own timeout.

## Schema incompatible at startup / migration job refused (PR-002)

* Startup log `schema_compatibility decision=<CODE>` and the process exits:
  * `TOO_OLD` / `UNMIGRATED` — the migration job has not run for this release:
    run `python -m app.scripts.migrate` (migration role) from the same image;
  * `TOO_NEW` — the database crossed a BARRIER or a rollback-BLOCKED step after
    this build: this image is not a valid rollback target; deploy the current
    release or forward-fix;
  * `UNKNOWN_SCHEMA` / `DIVERGENT` / `MULTIPLE_DB_HEADS` — the database was
    changed outside the migration job or restored from another branch: stop,
    inspect `alembic_version` and `schema_lineage`, do not force.
* Migration job exit 1 `MIGRATION_LOCK_TIMEOUT` — another migration holds the
  lock; do not start a parallel one; wait and rerun. Exit 1
  `BARRIER_NOT_ALLOWED` — planned maintenance only (`--allow-barrier`). Exit 2 —
  the migration failed and rolled back; the database is at the previous
  revision. Exit 3 — post-verify failed (lineage or grants); do not roll
  replicas.
* Policy and commands: [RELEASE-AND-MIGRATION.md](RELEASE-AND-MIGRATION.md).
