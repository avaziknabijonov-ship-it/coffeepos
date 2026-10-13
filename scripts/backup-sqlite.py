"""Safe copy-only SQLite backup for Windows/local CoffeePOS installations.

Usage:
    py -3.12 scripts/backup-sqlite.py SOURCE_COFFEEPOS_DB BACKUP_DIRECTORY

Never closes, replaces, migrates, or changes the source database.
The output is a NEW independent snapshot; restore is intentionally manual.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile


def back_up_sqlite(source: Path, destination_dir: Path) -> Path:
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError("Source SQLite database is not a file")
    destination_dir = destination_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    name = f"{source.stem}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.db"
    final = destination_dir / name
    if final.exists():
        raise FileExistsError(f"Backup already exists: {final}")
    # Temporary snapshot must be on the same drive for atomic rename.
    fd, temp_name = tempfile.mkstemp(prefix=".coffeepos-snapshot-", suffix=".tmp", dir=destination_dir)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=30) as src:
            with sqlite3.connect(str(temp), timeout=30) as dst:
                src.backup(dst, pages=200, sleep=0.1)
                verdict = dst.execute("PRAGMA integrity_check").fetchone()[0]
                if verdict != "ok":
                    raise RuntimeError(f"SQLite snapshot integrity check failed: {verdict}")
        if final.exists():
            raise FileExistsError(f"Backup already exists: {final}")
        temp.rename(final)
        return final
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Create a new verified SQLite backup without touching the source")
    parser.add_argument("source_db", type=Path)
    parser.add_argument("backup_directory", type=Path)
    args = parser.parse_args()
    result = back_up_sqlite(args.source_db, args.backup_directory)
    print(f"Verified SQLite snapshot: {result}")


if __name__ == "__main__":
    main()
