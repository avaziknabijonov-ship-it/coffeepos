#!/usr/bin/env bash
# Restore a CoffeePOS backup (.sql, .sql.gz or .sql.gz.gpg).
#
#   deploy/restore.sh FILE              restore drill: load into a scratch DB, check, drop it (safe)
#   deploy/restore.sh FILE --production replace the live "coffeepos" DB (stops the API first)
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE="${COMPOSE:-docker compose}"
file="${1:?usage: deploy/restore.sh BACKUP_FILE [--production]}"
mode="${2:-drill}"
[ -f "$file" ] || { echo "No such file: $file" >&2; exit 1; }

dump() {
  case "$file" in
    *.gpg) gpg --batch --decrypt "$file" | gunzip ;;
    *.gz) gunzip -c "$file" ;;
    *) cat "$file" ;;
  esac
}
psql_db() { $COMPOSE exec -T db psql -v ON_ERROR_STOP=1 -q -o /dev/null -c "SET client_min_messages=warning" -f -  -U coffeepos -d "$1"; }

if [ "$mode" = "--production" ]; then
  read -r -p "Live 'coffeepos' database will be REPLACED from $file. Type RESTORE to continue: " answer
  [ "$answer" = "RESTORE" ] || { echo "Cancelled"; exit 1; }
  deploy/backup.sh  # safety copy of the current state first
  $COMPOSE stop api
  echo "DROP DATABASE IF EXISTS coffeepos_old;" | psql_db postgres
  echo "ALTER DATABASE coffeepos RENAME TO coffeepos_old;" | psql_db postgres
  echo "CREATE DATABASE coffeepos;" | psql_db postgres
  dump | psql_db coffeepos >/dev/null
  $COMPOSE start api
  echo "Restored. Previous data kept as database coffeepos_old (drop it after checking)."
  exit 0
fi

db="coffeepos_restore_drill"
echo "DROP DATABASE IF EXISTS $db;" | psql_db postgres
echo "CREATE DATABASE $db;" | psql_db postgres
trap 'echo "DROP DATABASE IF EXISTS $db;" | psql_db postgres' EXIT
dump | psql_db "$db" >/dev/null
counts="$(echo "SELECT 'companies=' || count(*) FROM companies UNION ALL SELECT 'orders=' || count(*) FROM orders UNION ALL SELECT 'staff=' || count(*) FROM staff;" \
  | $COMPOSE exec -T db psql -At -U coffeepos -d "$db")"
echo "$counts"
echo "$counts" | grep -q '^companies=[1-9]' || { echo "Restore drill FAILED: no companies in backup" >&2; exit 1; }
echo "Restore drill OK: $file"
