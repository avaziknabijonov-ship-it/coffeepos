"""Backup utility is tested using a disposable SQLite DB, never live cafe data."""
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_safe_sqlite_backup_and_integrity(tmp_path):
    source = tmp_path / "test-cafe.db"
    backups = tmp_path / "backups"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE testing (id INTEGER PRIMARY KEY, cafe TEXT NOT NULL)")
        db.execute("INSERT INTO testing (cafe) VALUES (?)", ("CI test cafe",))

    script = Path(__file__).resolve().parents[2] / "scripts" / "backup-sqlite.py"
    result = subprocess.run(
        [sys.executable, str(script), str(source), str(backups)],
        text=True, capture_output=True, check=True,
    )
    backup_files = list(backups.glob("test-cafe-*.db"))
    assert len(backup_files) == 1, result.stdout
    with sqlite3.connect(source) as db:
        assert db.execute("SELECT cafe FROM testing").fetchone() == ("CI test cafe",)
    with sqlite3.connect(backup_files[0]) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT cafe FROM testing").fetchone() == ("CI test cafe",)
