#!/usr/bin/env bash
# CoffeePOS PostgreSQL backup: dump -> verify -> gzip -> (optional) GPG encrypt -> (optional) offsite copy.
#
# Settings (env or deploy/backup.env):
#   BACKUP_DIR            local folder (default: ~/coffeepos-backups)
#   BACKUP_KEEP_DAYS      local retention in days (default: 14)
#   BACKUP_GPG_RECIPIENT  GPG key id/email; when set, only the encrypted .gpg file is kept
#   BACKUP_RCLONE_REMOTE  rclone destination, e.g. "b2:coffeepos-backups" (offsite copy)
#   BACKUP_HEALTHCHECK_URL optional URL pinged after success (e.g. healthchecks.io)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f deploy/backup.env ] && . deploy/backup.env
BACKUP_DIR="${BACKUP_DIR:-$HOME/coffeepos-backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
COMPOSE="${COMPOSE:-docker compose}"
umask 077
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp="$BACKUP_DIR/.coffeepos-$stamp.sql.tmp"
final="$BACKUP_DIR/coffeepos-$stamp.sql.gz"
trap 'rm -f "$tmp" "$tmp.gz"' EXIT

$COMPOSE exec -T db pg_dump -U coffeepos --no-owner coffeepos > "$tmp"
test -s "$tmp"
grep -q 'PostgreSQL database dump complete' "$tmp"
gzip -9 "$tmp"
mv "$tmp.gz" "$final"

if [ -n "${BACKUP_GPG_RECIPIENT:-}" ]; then
  gpg --batch --yes --trust-model always --recipient "$BACKUP_GPG_RECIPIENT" --output "$final.gpg" --encrypt "$final"
  rm -f "$final"
  final="$final.gpg"
fi
trap - EXIT

if [ -n "${BACKUP_RCLONE_REMOTE:-}" ]; then
  rclone copy --no-traverse "$final" "$BACKUP_RCLONE_REMOTE/"
  echo "Offsite copy: $BACKUP_RCLONE_REMOTE/$(basename "$final")"
fi

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'coffeepos-*.sql*' -mtime +"$KEEP_DAYS" -delete
date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_DIR/LAST_SUCCESS"
[ -n "${BACKUP_HEALTHCHECK_URL:-}" ] && curl -fsS -m 10 "$BACKUP_HEALTHCHECK_URL" >/dev/null || true
echo "Backup saved: $final"
