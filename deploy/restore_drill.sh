#!/usr/bin/env bash
# Restore drill: decrypt a backup into a throwaway PostgreSQL container and verify it.
# Never point this at production. Usage: BACKUP_PASSPHRASE_FILE=... deploy/restore_drill.sh <file.sql.enc>
set -euo pipefail
file="${1:?backup file required}"
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE is required}"
name="coffeepos-restore-drill-$$"
umask 077
plain="$(mktemp)"
trap 'rm -f "$plain"; docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$BACKUP_PASSPHRASE_FILE" -in "$file" -out "$plain"
if [ -f "$file.sha256" ]; then
  test "$(sha256sum "$plain" | cut -d' ' -f1)" = "$(cat "$file.sha256")"
fi
docker run -d --name "$name" -e POSTGRES_PASSWORD=drill -e POSTGRES_USER=coffeepos -e POSTGRES_DB=coffeepos \
  postgres:16 >/dev/null
for _ in $(seq 1 30); do docker exec "$name" pg_isready -U coffeepos >/dev/null 2>&1 && break; sleep 1; done
sleep 2
docker exec -i "$name" psql -q -v ON_ERROR_STOP=1 -U coffeepos coffeepos < "$plain" >/dev/null
for table in companies orders order_payments audit_events schema_migrations; do
  count="$(docker exec "$name" psql -tA -U coffeepos coffeepos -c "SELECT count(*) FROM $table")"
  echo "$table: $count"
done
echo "Restore drill OK: $file"
