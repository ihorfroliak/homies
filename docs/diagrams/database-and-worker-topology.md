# Database and worker topology (private alpha, PROPOSED)

The workers run inside the API process through the FastAPI lifespan
([composition.py](../../backend/app/composition.py)); "worker" below is a second
instance of the same image with the worker flags on and no ingress.

```mermaid
flowchart LR
  subgraph edge["edge network"]
    API["api — HTTP; all worker flags false"]
  end
  subgraph data["data network (internal)"]
    WK["worker — same image and SHA; notification + saved-search on, freshness optional; no ingress"]
    DB[("PostgreSQL 16 + PostGIS 3.4, database ending _e2e")]
    MJ["migrate job — homies_migrator"]
    SJ["seed job — ENV=test, synthetic only"]
  end
  API -->|"homies_app"| DB
  WK -->|"homies_app, FOR UPDATE SKIP LOCKED claims"| DB
  MJ -->|"DDL, alembic_version, schema_lineage, grants"| DB
  SJ -->|"synthetic fixtures"| DB
  API --- MV[("media volume, api only")]
```

| Role | Who connects | Can | Cannot |
|---|---|---|---|
| bootstrap superuser | DBA, once | run the role scripts | — (never used by the app) |
| `homies_migrator` | migrate job | own and change the schema; write lineage | serve requests |
| `homies_app` | api, worker, seed | DML on application tables | DDL, writing the schema record, UPDATE/DELETE append-only tables |

Source: [RELEASE-AND-MIGRATION §7](../production/RELEASE-AND-MIGRATION.md#7-roles).
