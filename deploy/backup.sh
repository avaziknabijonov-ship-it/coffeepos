#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-$HOME/coffeepos-backups}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp="$BACKUP_DIR/coffeepos-$stamp.sql.tmp"
final="$BACKUP_DIR/coffeepos-$stamp.sql"
umask 077
trap 'rm -f "$tmp"' EXIT
docker compose exec -T db pg_dump -U coffeepos coffeepos > "$tmp"
test -s "$tmp"
grep -q 'PostgreSQL database dump complete' "$tmp"
mv "$tmp" "$final"
trap - EXIT
find "$BACKUP_DIR" -type f -name 'coffeepos-*.sql' -mtime +14 -delete
echo "Backup saved: $final"
