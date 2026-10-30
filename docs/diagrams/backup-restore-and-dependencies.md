# Backup, restore and operational dependencies

What exists versus what a production-like environment would still need.
Facts: [BACKUP-RESTORE](../production/BACKUP-RESTORE.md),
[PRODUCTION-READINESS](../production/PRODUCTION-READINESS.md).

```mermaid
flowchart TB
  subgraph exists["Exists in the repository (scripts and CI drills)"]
    BK["backup.sh: pg_dump custom, gzip, AES-256, sha256"]
    RS["restore.sh: verify checksum, pg_restore into a target"]
    DR["CI restore drills on every build (disposable databases)"]
  end
  subgraph missing["Missing (founder decisions)"]
    SCH["schedule"]
    OFF["offsite, encrypted storage and retention"]
    KEY["BACKUP_KEY custody"]
    MED["media backup — pg_dump has no photo bytes"]
    PITR["PITR for RPO at most 15 min (proposed, not accepted)"]
    ALR["real alert destination"]
  end
  DB[("PostgreSQL")] --> BK --> OFF
  OFF --> RS --> T[("separate restore database")]
  MV[("MEDIA_ROOT")] --> MED
  SCH -.-> BK
  KEY -.-> BK
  KEY -.-> RS
  PROM["Prometheus rules"] --> AM["Alertmanager — local sink only today"] -.-> ALR
```

Private alpha: synthetic data, so recovery means recreate
([STAGING-RUNBOOK §9](../production/STAGING-RUNBOOK.md#9-reset-and-recreate-alpha)).
No RPO or RTO is claimed for it.
