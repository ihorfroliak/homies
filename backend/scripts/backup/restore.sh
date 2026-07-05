#!/usr/bin/env bash
# Homies DB restore (D9 §4). Decrypt -> gunzip -> pg_restore into a target DB.
# Verifies checksum before trusting the artifact.
#
# Usage: BACKUP_KEY=... ./restore.sh <artifact.enc> [target_db] [db_container]
set -euo pipefail

ART="$1"
TARGET="${2:-homies_dr}"
CONTAINER="${3:-homies-db-1}"
KEY="${BACKUP_KEY:-dev-backup-key-change-me}"

echo "[restore] verifying checksum"
sha256sum -c "${ART}.sha256"

TMP="$(mktemp -d)"
openssl enc -d -aes-256-cbc -pbkdf2 -pass "pass:${KEY}" -in "$ART" -out "${TMP}/b.gz"
gunzip -c "${TMP}/b.gz" > "${TMP}/b.dump"

echo "[restore] (re)creating target DB $TARGET"
docker exec "$CONTAINER" psql -U homies -d postgres -c "DROP DATABASE IF EXISTS ${TARGET};" >/dev/null
docker exec "$CONTAINER" psql -U homies -d postgres -c "CREATE DATABASE ${TARGET};" >/dev/null

echo "[restore] pg_restore into $TARGET"
docker exec -i "$CONTAINER" pg_restore -U homies -d "$TARGET" --no-owner < "${TMP}/b.dump"
rm -rf "$TMP"
echo "[restore] done -> $TARGET"
