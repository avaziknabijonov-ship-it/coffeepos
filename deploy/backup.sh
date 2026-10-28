#!/usr/bin/env bash
# Encrypted PostgreSQL backup with retention, optional offsite copy and a status file for monitoring.
#   BACKUP_PASSPHRASE_FILE  file with the encryption passphrase (required; keep it outside the repo)
#   BACKUP_DIR              local directory (default ~/coffeepos-backups)
#   BACKUP_RETENTION_DAYS   local retention (default 14)
#   BACKUP_RCLONE_REMOTE    optional rclone target, e.g. "s3:coffeepos-backups" (offsite)
#   PG_DUMP_CMD             override dump command (default: docker compose exec -T db pg_dump ...)
set -euo pipefail
cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-$HOME/coffeepos-backups}"
RETENTION="${BACKUP_RETENTION_DAYS:-14}"
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE is required (encryption is mandatory)}"
test -r "$BACKUP_PASSPHRASE_FILE"
PG_DUMP_CMD="${PG_DUMP_CMD:-docker compose exec -T db pg_dump --no-owner --no-privileges -U coffeepos coffeepos}"
umask 077
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
plain="$BACKUP_DIR/.coffeepos-$stamp.sql.tmp"
final="$BACKUP_DIR/coffeepos-$stamp.sql.enc"
status="$BACKUP_DIR/last-status.json"
fail() { printf '{"status":"failed","at":"%s","step":"%s"}\n' "$stamp" "$1" > "$status"; exit 1; }
trap 'rm -f "$plain" "$final.tmp"' EXIT
$PG_DUMP_CMD > "$plain" || fail dump
test -s "$plain" || fail empty
grep -q 'PostgreSQL database dump complete' "$plain" || fail incomplete
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$BACKUP_PASSPHRASE_FILE" \
  -in "$plain" -out "$final.tmp" || fail encrypt
sha256sum "$plain" | cut -d' ' -f1 > "$final.sha256"
mv "$final.tmp" "$final"
rm -f "$plain"
if [ -n "${BACKUP_RCLONE_REMOTE:-}" ]; then
  rclone copy "$final" "$BACKUP_RCLONE_REMOTE" && rclone copy "$final.sha256" "$BACKUP_RCLONE_REMOTE" || fail offsite
fi
find "$BACKUP_DIR" -type f \( -name 'coffeepos-*.sql.enc' -o -name 'coffeepos-*.sql.enc.sha256' \) \
  -mtime +"$RETENTION" -delete
printf '{"status":"ok","at":"%s","file":"%s","bytes":%s,"offsite":%s}\n' "$stamp" "$(basename "$final")" \
  "$(stat -c %s "$final")" "$([ -n "${BACKUP_RCLONE_REMOTE:-}" ] && echo true || echo false)" > "$status"
trap - EXIT
echo "Encrypted backup saved: $final"
