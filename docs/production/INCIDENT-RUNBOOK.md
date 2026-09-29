# Incident runbook — outline (PR-001)

Not rehearsed. No production, no on-call, no alert destination exists yet;
this is the outline staging must exercise. Database recovery details:
`docs/runbooks/dr-database-recovery.md` and `BACKUP-RESTORE.md`.

## First five minutes (any incident)

1. Open an incident record (time, reporter, symptom).
2. Check `/readyz` on each instance and the Prometheus alerts page. A frozen
   database answers 503 after a few seconds, but a hung query can hold a probe
   for up to ~13 s, and under heavy traffic probes queue behind hung business
   requests (PR-003 debt) — set orchestrator probe timeouts accordingly.
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
| Freshness sweep stopped | — | — | (off by default; visibility never depends on it) | ticket | **no** metric |
| Notification worker stopped | — | the queue gauge is refreshed by the worker itself, so a stopped worker freezes or drops it | needs a worker heartbeat | ticket | **no** (observability track) |
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
