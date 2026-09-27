# Migration rollout — operational gate before any production database

Status: **required before the first production migration run** (TASK-002 §52,
from TASK-001 audit §10). Nothing has been deployed; no production database
exists. This note does not rewrite any historical migration — it states what a
rollout of the current chain must plan for.

## What the chain does, operationally

| Revision | Cycle | Operational character |
|---|---|---|
| `a1c6d2e8b407` | C1 | 11 money columns int4 → int8: **table rewrite under ACCESS EXCLUSIVE**; five separate ALTERs on `classified_offers` rewrite it repeatedly. Downgrade refuses if values exceed int4. |
| `b7e4f19a2c60` | C2 | Legal parties + authorities backfill: `fetchall` + per-row INSERT, **unchunked**, one transaction. Downgrade destroys authority/legal-identity history. |
| `c9d3a5e71f28` | C3 | Spaces backfill, per-property INSERT + mass UPDATE of offers; constraint/index scans. Downgrade loses room/space semantics. |
| `d4e8b2c61a95` | C4 | Price components backfill, per-offer inserts; drops flat price columns. Downgrade restores current flat values only, history lost. |
| `f1a7c3d9e2b4` | C5 | STORED geography computed for all rows; GiST builds (plain `CREATE INDEX` — **blocks writes**); per-offer public-point update. |
| `a8b2c4d6e1f3` … `d5e7f9a1b3c4` | C6–C8 | New tables and indexes; downgrades delete their data (C8 does not clean stored files). |
| `a7c9e1f3b5d2` | TASK-002 R2 | Coordinate preflight (**refuses** invalid positions), edge public-point recompute, six CHECKs (each scans its table under ACCESS EXCLUSIVE). |
| `b8d0f2a4c6e1` | TASK-002 R2 | Min-term preflight (refuses < 1), one CHECK. |
| `c1e3a5b7d9f2` | TASK-002 R3 | Adds `file_objects.processing_version`; **quarantines** every existing PROPERTY_MEDIA file (UPDATE). Downgrade leaves them quarantined by design. |
| `e4f6a8b0c2d4` | TASK-010 | Geography tables, one UNSTRUCTURED address per property (per-row backfill), `address_id` NOT NULL + UNIQUE. |
| `a7c9e1f3b5d7` | TASK-010R | Converts stored public EXACT offers to APPROXIMATE (grid recomputed in SQL); CHECK re-created. |
| `b8d0f2a4c6e8` | TASK-012 | Status preflight (**refuses** unknown statuses), adds `last_confirmed_available_at` backfilled from `published_at`, status CHECK, index. **Changes no status.** |
| `d3f5b7a9c1e4` | TASK-002 R4 | Preflights (refuses duplicate active threads / incoherent viewings), partial UNIQUE index (blocks writes on `conversations` while building), one CHECK on `viewings`. |

`alembic/env.py` runs an upgrade in one transaction, so every lock taken by an
early revision is held until the whole `upgrade head` commits.

## Before running against a database with real data

1. **Representative-volume rehearsal** on a restored copy of the target
   (use the DR restore drill, `docs/design/d9-disaster-recovery.md`): measure
   duration, lock waits, WAL volume and migrator memory for the full chain.
2. **Backup immediately before**, verified by a restore test — the B2 drill,
   not an unrestored dump.
3. **Maintenance window or expand–contract plan.** For large tables, split
   the rewrite-heavy revisions (C1, C5, the TASK-002 CHECKs) into
   expand–contract steps: add nullable/new columns, backfill in chunks
   outside the DDL transaction, `ADD CONSTRAINT … NOT VALID` then
   `VALIDATE CONSTRAINT` in a separate transaction, `CREATE INDEX
   CONCURRENTLY` outside a transaction. This is a planned change to how the
   chain is run, recorded as its own task — not an edit of history.
4. **Lock timeouts.** Run with `SET lock_timeout` (e.g. 5 s) and
   `statement_timeout` so a migration queued behind a long transaction fails
   fast instead of stalling every request behind its lock request.
5. **Forward repair, not downgrade.** Several downgrades are destructive
   (C2–C8). The recovery path for a failed rollout is restore-from-backup or a
   forward fix migration; downgrades are for development databases.
6. **Preflight failures are expected outcomes.** The TASK-002 migrations stop
   and name rows (invalid coordinates, sub-month terms, duplicate threads,
   incoherent viewings) instead of guessing. Plan the manual correction
   before the window, by running the same SELECTs read-only in advance.
7. **After R3:** run `python -m app.scripts.reprocess_media` so quarantined
   photos are re-encoded; until then they are not served.
8. **Before TASK-012 (`b8d0f2a4c6e8`) reaches real inventory:** run
   `python -m app.scripts.listing_freshness preflight` against the target
   (after the migration, before traffic) and record the count and list in the
   release notes. Every active listing whose last publication/confirmation is
   older than 21 days leaves the public board the moment the new code serves
   (the visibility rule is evaluated on read, D-59/D-62); owners see those
   listings as needing confirmation in `GET /v1/me/classifieds`. Decide
   explicitly whether to notify owners or to run the release with a
   temporary longer policy — do not let supply disappear unnoticed. Then run
   `python -m app.scripts.listing_freshness sweep` (or enable
   `listing_freshness_worker_enabled`) so statuses and reminder events follow.
