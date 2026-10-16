# CoffeePOS — backup and recovery checklist

**Do not use live MasterCoffee data for release testing.** These commands are a
disaster-recovery runbook. Always confirm the database source and destination
before running them. A backup is not considered usable until a restore has been
verified on an **isolated** test database.

## SQLite (local Windows test installations)

1. Find the SQLite source file in the **TEST** project's `DATABASE_URL` or the
   test directory. Never assume it is the same as the live cafe database.
2. Stop the test app or keep it running: Python's SQLite online backup API
   supports a consistent snapshot from an active database.
3. Choose an entirely **new** destination path (do not overwrite an existing
   backup).

From the project root, for a disposable *test* DB:

```cmd
py -3.12 backend\scripts\backup_sqlite.py "C:\path\to\TEST_ONLY.db" "C:\path\to\new-test-backup.db"
```

The script opens the source read-only, refuses to overwrite the target,
checks `PRAGMA integrity_check`, and deletes only a newly created partial
output when verification fails. Treat backup files as sensitive: they may
contain sales history, staff names and password/PIN hashes. Store them in a
restricted location, never post them publicly.

**Restore rehearsal (test environment only):** Copy the backup to a new,
unused test folder and point an isolated test process at the copied file via
`DATABASE_URL=sqlite:///...`; check menu, order count, balances, and `PRAGMA
integrity_check`. Do not replace the source or point the isolated server to
the production path.

Automated proof is in `backend/tests/test_backup_sqlite.py`: an open SQLite
database is backed up, the restored snapshot is read and integrity-checked,
the backup is protected against overwrite, and the source remains unchanged.

## PostgreSQL (Docker or hosted production)

PostgreSQL requires `pg_dump` / `pg_restore`, **not** the SQLite utility.
Example backup command for an authorized operator whose connection and
database names have been verified:

```sh
pg_dump --format=custom --no-owner --file=coffeepos-YYYYMMDD.dump "$DATABASE_URL"
```

Do not commit backups to Git and do not expose DB credentials in logs or
screenshots. For rehearsal, provision a *separate, disposable PostgreSQL
instance*, create an empty database there, and run
`pg_restore --no-owner --dbname=<TEST_DATABASE_URL> coffeepos-YYYYMMDD.dump`
with that test instance's credentials.

Review restored tenant data integrity, order/shift counts, and access
control. **PostgreSQL restoration remains a manual unverified release gate**;
the GitHub CI only tests SQLite.

## Release safety

- Never copy `coffeepos.db`, `.env`, auth keys or private backups from
  `C:\CoffeePoss\yangi-versiya` into the TEST checkout.
- Keep release deployment and database migration separate from the new APK.
- Before production deployment, take a fresh verified backup and prepare a
  rollback with matching app/database schema versions.
- Check changes on TEST COFFEE first, especially salary, inventory, cash guard,
  loans, and Android LAN login.
