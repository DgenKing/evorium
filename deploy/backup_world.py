"""Safe nightly copy of the Evorium world, using SQLite's backup API (safe while the server is running).

    .venv/bin/python deploy/backup_world.py            # writes backups/evorium-YYYYmmdd-HHMM.sqlite3, keeps 14
    .venv/bin/python deploy/backup_world.py --keep 30

The world file is EVORIUM_DB_PATH if set, otherwise evorium.sqlite3 in the project folder.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description="Back up the Evorium world file.")
    parser.add_argument("--keep", type=int, default=14, help="how many backups to keep (default 14)")
    parser.add_argument("--dest", default=str(PROJECT / "backups"), help="backup folder")
    args = parser.parse_args(argv)

    source = Path(os.environ.get("EVORIUM_DB_PATH") or PROJECT / "evorium.sqlite3")
    if not source.is_file():
        print(f"No world file at {source}; nothing to back up.")
        return 1
    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"evorium-{datetime.now():%Y%m%d-%H%M}.sqlite3"

    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    os.chmod(target, 0o600)

    backups = sorted(dest_dir.glob("evorium-*.sqlite3"))
    for old in backups[:-max(1, args.keep)]:
        old.unlink()
    print(f"Backed up to {target} ({target.stat().st_size // 1024} KB); keeping {min(len(backups), args.keep)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
