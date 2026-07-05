#!/usr/bin/env bash
# Homies DB backup (D9 §3). Custom-format pg_dump -> gzip -> AES-256 encrypt.
# Produces an encrypted, checksummed, timestamped artifact.
#
# Usage: BACKUP_KEY=... ./backup.sh [db_container] [db_name] [out_dir]
# RPO note: RPO = the interval this script is scheduled at (e.g. cron hourly
#           => RPO 1h). Sub-minute RPO needs WAL archiving / managed PITR.
set -euo pipefail

CONTAINER="${1:-homies-db-1}"
DB="${2:-homies}"
OUT="${3:-backups}"
KEY="${BACKUP_KEY:-dev-backup-key-change-me}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
BASE="$OUT/homies_${DB}_${TS}"

echo "[backup] pg_dump $DB @ $CONTAINER"
docker exec "$CONTAINER" pg_dump -U homies -Fc "$DB" > "${BASE}.dump"
gzip -c "${BASE}.dump" > "${BASE}.dump.gz"
openssl enc -aes-256-cbc -pbkdf2 -salt -pass "pass:${KEY}" \
    -in "${BASE}.dump.gz" -out "${BASE}.dump.gz.enc"
sha256sum "${BASE}.dump.gz.enc" > "${BASE}.dump.gz.enc.sha256"
rm -f "${BASE}.dump" "${BASE}.dump.gz"   # keep only the encrypted artifact

SIZE=$(wc -c < "${BASE}.dump.gz.enc")
echo "[backup] wrote ${BASE}.dump.gz.enc (${SIZE} bytes)"
echo "[backup] checksum: $(cat "${BASE}.dump.gz.enc.sha256")"
echo "${BASE}.dump.gz.enc"
