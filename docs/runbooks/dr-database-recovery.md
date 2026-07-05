# Runbook — Database Disaster Recovery

Executable procedures. Every step is a real command in
`backend/scripts/backup/`. Rehearsed in the D9 drill
(`docs/design/d9-disaster-recovery.md`).

Prereq: `export BACKUP_KEY=<the real key>` (never the dev default in prod).

## R1 — Take a backup
```
cd backend/scripts/backup
BACKUP_KEY=$KEY ./backup.sh homies-db-1 homies backups
# -> backups/homies_homies_<ts>.dump.gz.enc (+ .sha256)
```

## R2 — Restore into a target database
```
BACKUP_KEY=$KEY ./restore.sh backups/homies_homies_<ts>.dump.gz.enc homies_restored homies-db-1
python ../../.venv/Scripts/python verify_restore.py \
  postgresql+psycopg://homies:homies@localhost:5433/homies_restored
# expect: FINANCIAL RECOVERY: PASS
```

## R3 — Accidental DROP / DELETE recovery
1. Stop writes (scale API to 0 / maintenance flag).
2. Restore latest good artifact into a NEW db (R2) — never overwrite the
   live db blindly.
3. Run `verify_restore.py` → must PASS.
4. Repoint the app `DATABASE_URL` at the restored db, or rename dbs.
5. Reconcile against Stripe (once real Stripe is wired): compare ledger
   `provider_cash`/payouts to Stripe Balance for the window.

## R4 — Broken migration recovery
1. `alembic downgrade -1` if the migration is reversible (D8 migrations are).
2. If data was mangled, restore latest pre-migration backup (R2).
3. Fix the migration, re-run `alembic upgrade head` on a clone first.

## R5 — Full disaster drill (rehearsal)
```
cd backend/scripts/backup && ./dr_drill.sh
# runs backup -> clean restore + verify -> DROP TABLE -> restore + verify
```

## R6 — Payment provider outage (degraded mode)
- New bookings: keep in `pending` (payment intent fails cleanly, no phantom
  confirmation — proven in D6). Show honest banner.
- Do NOT retry-storm the provider; back off.
- When provider returns: pending bookings retry payment; unpaid past TTL
  are auto-voided (once auto-void lands, P1).

## R7 — Manual booking / payout continuation
- Booking: admin can inspect state via `/admin/bookings`; manual confirm
  is NOT exposed by design (money must go through the ledger). Wait for
  provider recovery instead of hand-editing.
- Payout: `/hosts/{id}/payouts/run` is idempotent (D6: 10x -> 1). Safe to
  re-run after any outage.

## R8 — Incident escalation
1. Detect (reconciliation break / failed backup / P1 booking).
2. Freeze payouts if financial integrity is in doubt.
3. Take a fresh backup BEFORE any repair.
4. Repair on a restored clone, verify, then cut over.
5. Post-mortem: what broke, TTD, TTR, fix, prevention.
