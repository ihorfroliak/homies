# Release and migration sequence (PROPOSED, not executed)

Policy: [RELEASE-AND-MIGRATION](../production/RELEASE-AND-MIGRATION.md).
Procedure: [STAGING-RUNBOOK §4–§8](../production/STAGING-RUNBOOK.md).

```mermaid
sequenceDiagram
  autonumber
  participant F as Founder
  participant CI as GitHub CI
  participant H as Host (alpha VPS)
  participant DB as PostgreSQL
  F->>CI: choose SHA on main
  CI-->>F: six checks green on exactly SHA
  F->>H: Gate D GO for this environment
  H->>H: docker build --build-arg GIT_SHA=SHA, then release manifest (build_sha = SHA)
  H->>DB: DBA bootstrap — migration_role, app_role, app_grants, passwords
  H->>DB: migrate --plan as homies_migrator (no change)
  H-->>F: plan — steps, BARRIERs
  F->>H: explicit BARRIER GO
  H->>DB: migrate --allow-barrier (lock, upgrade, lineage, grants, post-verify)
  H->>DB: migrate (no-op) and release check as homies_app
  H->>H: start worker, api, web, caddy
  H-->>F: smoke evidence (DEPLOYMENT-CHECKLIST §4)
  Note over H,DB: rollback BLOCKED — no automatic downgrade, git revert is not a schema rollback, forward repair or recreate (alpha)
```
