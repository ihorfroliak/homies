#!/usr/bin/env bash
# D9 disaster-recovery drill. Executes real recovery and prints evidence +
# metrics. Nothing here is assumed — every step runs.
#
# Drills:
#   A. clean restore into a fresh DB + financial verification
#   B. accidental DROP TABLE -> restore -> re-verify (data returns)
#   C. RTO measurement (wall-clock of restore)
set -euo pipefail
cd "$(dirname "$0")"
export BACKUP_KEY="${BACKUP_KEY:-dev-backup-key-change-me}"
CONTAINER=homies-db-1
SRC=homies
DR=homies_dr
PY="../../.venv/Scripts/python"
URL="postgresql+psycopg://homies:homies@localhost:5433/${DR}"

echo "=================== D9 DR DRILL ==================="

echo "[0] source fingerprint"
docker exec "$CONTAINER" psql -U homies -d "$SRC" -t -c \
  "SELECT 'bookings='||count(*) FROM bookings UNION ALL SELECT 'journal_lines='||count(*) FROM journal_lines;" | sed 's/^/    /'

echo "[1] BACKUP"
ART=$(./backup.sh "$CONTAINER" "$SRC" backups | tail -1)
echo "    artifact: $ART"

echo "[2] DRILL A — clean restore + financial verify"
t0=$(date +%s)
BACKUP_KEY="$BACKUP_KEY" ./restore.sh "$ART" "$DR" "$CONTAINER" >/tmp/dr_restore.log 2>&1 || { cat /tmp/dr_restore.log; exit 1; }
t1=$(date +%s)
echo "    RTO (restore wall-clock) = $((t1 - t0))s"
"$PY" verify_restore.py "$URL"

echo "[3] verify append-only triggers survived restore"
docker exec "$CONTAINER" psql -U homies -d "$DR" -t -c \
  "SELECT count(*) FROM pg_trigger WHERE tgname LIKE '%append_only%';" | sed 's/^/    triggers=/'
docker exec "$CONTAINER" psql -U homies -d "$DR" -t -c \
  "SELECT conname FROM pg_constraint WHERE conname='excl_booking_overlap';" | sed 's/^/    /'

echo "[4] DRILL B — simulate accidental DROP TABLE, then recover"
docker exec "$CONTAINER" psql -U homies -d "$DR" -c "DROP TABLE journal_lines CASCADE;" >/dev/null
echo "    dropped journal_lines from $DR (disaster)"
BACKUP_KEY="$BACKUP_KEY" ./restore.sh "$ART" "$DR" "$CONTAINER" >/tmp/dr_restore2.log 2>&1 || { cat /tmp/dr_restore2.log; exit 1; }
echo "    restored; re-verifying"
"$PY" verify_restore.py "$URL"

echo "[5] cleanup drill DB"
docker exec "$CONTAINER" psql -U homies -d postgres -c "DROP DATABASE IF EXISTS ${DR};" >/dev/null
echo "=================== DRILL COMPLETE ==================="
