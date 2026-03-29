#!/usr/bin/env python3
"""
scripts/filter_demo.py — Demonstrates the filter engine against your imported data.

Usage:
    python scripts/filter_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opensak.db.database import init_db, get_session, db_health_check
from opensak.filters.engine import (
    FilterSet, SortSpec, FilterProfile, apply_filters,
    CacheTypeFilter, DifficultyFilter, TerrainFilter,
    NotFoundFilter, AvailableFilter, DistanceFilter,
    CountryFilter, NameFilter, ContainerFilter,
)


def print_results(label: str, caches: list, distance_from: tuple = None) -> None:
    print(f"\n{'─' * 55}")
    print(f"  {label}  ({len(caches)} results)")
    print(f"{'─' * 55}")
    if not caches:
        print("  (no results)")
        return
    for c in caches[:10]:   # show max 10
        dist = ""
        if distance_from:
            from opensak.filters.engine import _haversine_km
            km = _haversine_km(distance_from[0], distance_from[1], c.latitude, c.longitude)
            dist = f"  {km:.1f}km"
        found = "✓" if c.found else " "
        archived = " [ARCHIVED]" if c.archived else ""
        print(f"  [{found}] {c.gc_code}  D{c.difficulty}/T{c.terrain}  {c.cache_type:<20} {c.name[:35]}{dist}{archived}")
    if len(caches) > 10:
        print(f"  ... and {len(caches) - 10} more")


def main() -> None:
    print("=" * 55)
    print("  OpenSAK — Filter Engine Demo")
    print("=" * 55)

    init_db()
    stats = db_health_check()
    print(f"\nDatabase: {stats['caches']} caches, {stats['logs']} logs\n")

    if stats["caches"] == 0:
        print("No caches in database! Run import_gpx.py first.")
        sys.exit(1)

    # ── Demo 1: All caches, sorted by name ───────────────────────────────────
    with get_session() as s:
        results = apply_filters(s, sort=SortSpec("name"))
    print_results("All caches — sorted by name", results)

    # ── Demo 2: Available only ────────────────────────────────────────────────
    with get_session() as s:
        fs = FilterSet()
        fs.add(AvailableFilter())
        results = apply_filters(s, fs, SortSpec("difficulty"))
    print_results("Available caches — sorted by difficulty", results)

    # ── Demo 3: Traditional caches, D ≤ 2.0 ──────────────────────────────────
    with get_session() as s:
        fs = FilterSet()
        fs.add(CacheTypeFilter(["Traditional Cache"]))
        fs.add(DifficultyFilter(max_difficulty=2.0))
        results = apply_filters(s, fs, SortSpec("terrain"))
    print_results("Traditional, D ≤ 2.0 — sorted by terrain", results)

    # ── Demo 4: Multi and Mystery caches ─────────────────────────────────────
    with get_session() as s:
        fs = FilterSet()
        fs.add(CacheTypeFilter(["Multi-cache", "Unknown Cache"]))
        results = apply_filters(s, fs, SortSpec("difficulty", ascending=False))
    print_results("Multi + Mystery — sorted by difficulty desc", results)

    # ── Demo 5: Not found, available ─────────────────────────────────────────
    with get_session() as s:
        fs = FilterSet()
        fs.add(NotFoundFilter())
        fs.add(AvailableFilter())
        results = apply_filters(s, fs, SortSpec("name"))
    print_results("Not found + available", results)

    # ── Demo 6: Distance filter (centre of Denmark approx) ───────────────────
    home = (56.1629, 10.2039)   # Aarhus
    with get_session() as s:
        fs = FilterSet()
        fs.add(DistanceFilter(lat=home[0], lon=home[1], max_km=50.0))
        results = apply_filters(
            s, fs,
            SortSpec("name"),
            distance_from=home,
        )
    print_results(f"Within 50km of Aarhus ({home})", results, distance_from=home)

    # ── Demo 7: AND + OR nesting ──────────────────────────────────────────────
    with get_session() as s:
        # (Traditional OR Multi) AND (D ≤ 3) AND available
        type_filter = FilterSet(mode="OR")
        type_filter.add(CacheTypeFilter(["Traditional Cache"]))
        type_filter.add(CacheTypeFilter(["Multi-cache"]))

        outer = FilterSet(mode="AND")
        outer.add(type_filter)
        outer.add(DifficultyFilter(max_difficulty=3.0))
        outer.add(AvailableFilter())

        results = apply_filters(s, outer, SortSpec("difficulty"))
    print_results("(Traditional OR Multi) AND D ≤ 3 AND available", results)

    # ── Demo 8: Save and reload a filter profile ──────────────────────────────
    print(f"\n{'─' * 55}")
    print("  Saving filter profile 'easy-traditional' ...")
    fs = FilterSet()
    fs.add(CacheTypeFilter(["Traditional Cache"]))
    fs.add(DifficultyFilter(max_difficulty=2.0))
    fs.add(TerrainFilter(max_terrain=2.0))
    fs.add(AvailableFilter())

    profile = FilterProfile(
        name="easy-traditional",
        filterset=fs,
        sort=SortSpec("difficulty"),
    )
    saved_path = profile.save()
    print(f"  Saved to: {saved_path}")

    # Reload and apply
    loaded = FilterProfile.load(saved_path)
    print(f"  Reloaded: {loaded}")
    with get_session() as s:
        results = apply_filters(s, loaded.filterset, loaded.sort)
    print_results("Loaded profile 'easy-traditional'", results)

    print(f"\n{'=' * 55}")
    print("  Filter demo complete!")
    print("=" * 55)


if __name__ == "__main__":
    main()
