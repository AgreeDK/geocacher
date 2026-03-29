#!/usr/bin/env python3
"""
scripts/init_db.py

Quick CLI script to initialise the OpenSAK database and verify it works.
Run this after installing dependencies to confirm your setup is correct.

Usage:
    python scripts/init_db.py
"""

import sys
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opensak.config import print_config, get_db_path
from opensak.db.database import init_db, db_health_check, get_session
from opensak.db.models import Cache, Waypoint, Log, Attribute, UserNote


def main() -> None:
    print("=" * 55)
    print("  OpenSAK — Stage 1 Database Initialisation")
    print("=" * 55)

    # Show where everything lives
    print("\nConfiguration paths:")
    print_config()

    # Initialise (creates the SQLite file and all tables)
    print(f"\nInitialising database at: {get_db_path()}")
    init_db()
    print("  ✓ Tables created successfully")

    # Health check — should all be zero on a fresh install
    stats = db_health_check()
    print("\nDatabase stats (should all be 0 on first run):")
    for key, val in stats.items():
        print(f"  {key:<12}: {val}")

    # Insert a sample cache so we can verify round-trip read/write
    print("\nInserting a test cache record ...")
    with get_session() as session:
        test_cache = Cache(
            gc_code="GC00001",
            name="Test Cache — Stage 1 Verification",
            cache_type="Traditional Cache",
            container="Small",
            latitude=55.6761,
            longitude=12.5683,
            difficulty=1.5,
            terrain=2.0,
            placed_by="OpenSAK Dev",
            country="Denmark",
            state="Zealand",
            short_description="A synthetic cache used to verify the DB setup.",
            encoded_hints="Look under the rock.",
        )
        # Attach a waypoint
        parking = Waypoint(
            prefix="PK",
            wp_type="Parking Area",
            name="Parking",
            latitude=55.6762,
            longitude=12.5680,
        )
        test_cache.waypoints.append(parking)

        # Attach a log
        log = Log(
            log_type="Found it",
            finder="Tester",
            text="TFTC! Found it right away.",
        )
        test_cache.logs.append(log)

        # Attach a user note
        note = UserNote(note="Remember to bring a pen next time.")
        test_cache.user_note = note

        session.add(test_cache)

    print("  ✓ Test cache written")

    # Read it back
    with get_session() as session:
        cache = session.query(Cache).filter_by(gc_code="GC00001").one()
        print(f"\nRead back: {cache}")
        print(f"  Waypoints : {cache.waypoints}")
        print(f"  Logs      : {cache.logs}")
        print(f"  User note : {cache.user_note}")

    # Final stats
    stats = db_health_check()
    print("\nDatabase stats after test insert:")
    for key, val in stats.items():
        print(f"  {key:<12}: {val}")

    # Clean up the test record so the DB stays empty for real use
    with get_session() as session:
        cache = session.query(Cache).filter_by(gc_code="GC00001").one()
        session.delete(cache)
    print("\n  ✓ Test record cleaned up")

    print("\n" + "=" * 55)
    print("  Stage 1 complete — database is ready!")
    print("  Next step: Stage 2 (GPX importer)")
    print("=" * 55)


if __name__ == "__main__":
    main()
