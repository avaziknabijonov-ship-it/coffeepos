#!/usr/bin/env bash
# Read-only PostgreSQL backup of the current Docker Compose database.
# It never restores, overwrites an existing backup, or modifies source data.
set -euo pipefail
umask 077

BACKUP_DIR="${1:-./backups}"
mkdir -p -- "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/coffeepos-$STAMP.dump"
TEMP="$OUT.partial"

if [ -e "$OUT" ] || [ -e "$TEMP" ]; then
  echo "Backup already exists; refusing to overwrite: $OUT" >&2
  exit 1
fi
trap 'rm -f -- "$TEMP"' EXIT

# Requires a running PostgreSQL service named 'db' in docker-compose.yml.
docker compose exec -T db pg_dump -U coffeepos --format=custom --no-owner --no-acl coffeepos > "$TEMP"
# Validate the dump archive before exposing it as a completed backup.
docker compose exec -T db pg_restore --list < "$TEMP" > /dev/null
mv -- "$TEMP" "$OUT"
trap - EXIT
printf 'Verified PostgreSQL backup: %s\n' "$OUT"
