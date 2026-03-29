#!/usr/bin/env python3
"""
scripts/import_gpx.py — CLI tool to import a GPX or PQ zip file.

Usage:
    python scripts/import_gpx.py path/to/file.gpx
    python scripts/import_gpx.py path/to/pocketquery.zip
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opensak.db.database import init_db, get_session, db_health_check
from opensak.importer import import_gpx, import_zip


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_gpx.py <file.gpx|file.zip>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: file not found: {path}")
        sys.exit(1)

    print("=" * 55)
    print("  OpenSAK — GPX / PQ Import")
    print("=" * 55)

    init_db()

    before = db_health_check()
    print(f"\nDatabase before import: {before['caches']} caches, {before['logs']} logs\n")

    print(f"Importing: {path.name} ...")
    with get_session() as session:
        if path.suffix.lower() == ".zip":
            result = import_zip(path, session)
        else:
            result = import_gpx(path, session)

    print("\nResult:")
    print(result)

    after = db_health_check()
    print(f"\nDatabase after import: {after['caches']} caches, {after['logs']} logs, {after['waypoints']} waypoints")
    print("\n" + "=" * 55)
    print("  Import complete!")
    print("=" * 55)


if __name__ == "__main__":
    main()
