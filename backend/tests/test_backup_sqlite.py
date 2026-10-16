"""Online backup regression tests use only disposable, temporary SQLite files."""

import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_sqlite.py"


def run_backup(source: Path, destination: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), str(destination)],
        check=False, capture_output=True, text=True,
    )


def test_backup_is_consistent_and_never_overwrites(tmp_path):
    source = tmp_path / "test-source.db"
    target = tmp_path / "backups" / "backup-1.db"
    target.parent.mkdir()

    # Keep the database open, as CoffeePOS does during operation.
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE test_sales (id INTEGER PRIMARY KEY, amount INTEGER)")
        connection.execute("INSERT INTO test_sales (amount) VALUES (28000)")
        connection.commit()
        result = run_backup(source, target)
        assert result.returncode == 0, result.stderr

        with sqlite3.connect(target) as restored:
            assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert restored.execute("SELECT amount FROM test_sales").fetchall() == [(28000,)]

        # Further writes to the live source do not modify the existing snapshot.
        connection.execute("INSERT INTO test_sales (amount) VALUES (20000)")
        connection.commit()

        second = run_backup(source, target)
        assert second.returncode != 0, "Must refuse to overwrite an existing backup"
        with sqlite3.connect(target) as restored:
            assert restored.execute("SELECT amount FROM test_sales").fetchall() == [(28000,)]

        assert run_backup(source, source).returncode != 0
        assert connection.execute("SELECT amount FROM test_sales").fetchall() == [(28000,), (20000,)]


def test_backup_does_not_create_or_overwrite_source_when_missing(tmp_path):
    source = tmp_path / "missing.db"
    target = tmp_path / "snapshot.db"
    result = run_backup(source, target)
    assert result.returncode != 0
    assert not source.exists()
    assert not target.exists()
