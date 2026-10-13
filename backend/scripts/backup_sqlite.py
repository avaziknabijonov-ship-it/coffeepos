"""Create a verified, new SQLite backup without replacing the source database.

Usage:
    python backend/scripts/backup_sqlite.py SOURCE.db BACKUP.db

SQLite's online backup API provides a consistent snapshot while the source is
open in another process. This script never overwrites an existing backup and
never writes to the source. Backups contain sensitive business information.
"""

import argparse
import os
import sqlite3
from pathlib import Path


def backup_sqlite(source: Path, target: Path) -> None:
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()

    if not source.is_file():
        raise ValueError("Source SQLite file does not exist")
    if source == target:
        raise ValueError("The backup destination must differ from the source")
    if not target.parent.is_dir():
        raise ValueError("Backup parent directory does not exist")

    # Exclusive reservation: refuse to overwrite any existing file.
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        # mode=ro prevents an accidental write to the live source database.
        with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as live:
            with sqlite3.connect(str(target)) as backup:
                live.backup(backup)
                check = backup.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise RuntimeError("Backup failed SQLite integrity_check")
    except Exception:
        # Only delete the output that THIS invocation just reserved, never source.
        target.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a new, verified SQLite backup")
    parser.add_argument("source", type=Path, help="source SQLite .db file")
    parser.add_argument("target", type=Path, help="new backup file (must not exist)")
    args = parser.parse_args()
    try:
        backup_sqlite(args.source, args.target)
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Backup not created: {exc}\n")
    print(f"Verified backup created at {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
