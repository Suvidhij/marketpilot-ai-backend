"""Consistent, owner-readable SQLite backup. Usage: python -m app.utils.backup path.sqlite3"""

import argparse
import os
from pathlib import Path
import sqlite3
from sqlalchemy.engine import make_url
from app.core.config import get_settings


def backup(target: Path):
    url = make_url(get_settings().database_url)
    if (
        not url.drivername.startswith("sqlite")
        or not url.database
        or url.database == ":memory:"
    ):
        raise ValueError("This command requires a file-backed SQLite database")
    source = Path(url.database).resolve()
    target = target.resolve()
    if not source.exists() or source == target:
        raise ValueError("Source must exist and backup must have a different path")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with (
            sqlite3.connect(f"file:{source}?mode=ro", uri=True) as original,
            sqlite3.connect(target) as copy,
        ):
            original.backup(copy)
            if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity check failed")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    print("Backup created:", backup(parser.parse_args().destination))
