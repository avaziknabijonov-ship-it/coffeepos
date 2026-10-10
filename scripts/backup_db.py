"""Create a consistent SQLite backup without stopping CoffeePOS.

Run from the project directory:
    py -3.12 scripts/backup_db.py
Schedule with Windows Task Scheduler after verifying manually.
"""
from datetime import datetime
from pathlib import Path
import os
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("COFFEEPOS_DB", str(ROOT / "coffeepos.db")))
DEST_DIR = Path(os.environ.get("COFFEEPOS_BACKUP_DIR", str(ROOT.parent / "zaxira")))


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Database not found: {SOURCE}")
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    destination = DEST_DIR / f"coffeepos-{datetime.now():%Y%m%d-%H%M%S}.db"
    if destination.exists():
        raise SystemExit(f"Backup exists: {destination}")
    with sqlite3.connect(f"file:{SOURCE.as_posix()}?mode=ro", uri=True) as source:
        with sqlite3.connect(destination) as backup:
            source.backup(backup)
            result = backup.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                destination.unlink(missing_ok=True)
                raise SystemExit("Backup integrity check failed")
    print(f"Backup created: {destination}")


if __name__ == "__main__":
    main()
