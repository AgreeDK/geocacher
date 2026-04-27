"""
tests/unit-tests/test_container_sort.py — Tests for issue #90.

Verifies that the Container column sorts by visual grouping:

  Group 1: Physical containers (smallest → largest)
           Nano → Micro → Small → Regular → Large

  Group 2: Empty bars + letter (alphabetic by the letter)
           EarthCache  → 'E'
           Lab Cache   → 'L'
           Other       → 'O'
           Virtual     → 'V'

  Group 3: Empty bars, no letter
           Not chosen / empty

Within each group, Python's stable sort preserves the existing order
so a previous sort (e.g. distance) is retained as a secondary order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from opensak.gui.cache_table import _container_sort_key


@dataclass
class FakeCache:
    """Minimal Cache stand-in for sort testing — no DB required."""
    gc_code: str
    container: Optional[str]
    cache_type: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Direct sort key tests
# ─────────────────────────────────────────────────────────────────────────────

class TestContainerSortKey:
    """Verify the sort key function returns the expected (group, sub_key) tuples."""

    def test_returns_tuple(self):
        """Sort key must always be a tuple for stable composite ordering."""
        result = _container_sort_key("Nano")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_physical_containers_in_size_order(self):
        """Physical containers must be ordered from smallest to largest."""
        order = [
            _container_sort_key("Nano"),
            _container_sort_key("Micro"),
            _container_sort_key("Small"),
            _container_sort_key("Regular"),
            _container_sort_key("Large"),
        ]
        assert order == sorted(order)
        assert len(set(order)) == 5  # all distinct

    def test_physical_containers_in_group_1(self):
        """All physical containers should be in group 1."""
        for size in ("Nano", "Micro", "Small", "Regular", "Large"):
            assert _container_sort_key(size)[0] == 1

    def test_letter_types_in_group_2(self):
        """All letter-display types should be in group 2."""
        assert _container_sort_key("Other")[0] == 2
        assert _container_sort_key("Other", "EarthCache")[0] == 2
        assert _container_sort_key("Other", "Lab Cache")[0] == 2
        assert _container_sort_key("Other", "Virtual Cache")[0] == 2

    def test_empty_in_group_3(self):
        """Empty / not chosen values should be in group 3."""
        assert _container_sort_key("")[0] == 3
        assert _container_sort_key("Not chosen")[0] == 3
        assert _container_sort_key(None)[0] == 3

    def test_letters_are_alphabetic(self):
        """Within group 2, sub_key should be the displayed letter."""
        assert _container_sort_key("Other", "EarthCache")[1] == "E"
        assert _container_sort_key("Other", "Lab Cache")[1] == "L"
        assert _container_sort_key("Other")[1] == "O"
        assert _container_sort_key("Other", "Virtual Cache")[1] == "V"

    def test_physical_sorts_before_letters(self):
        """Group 1 (physical) sorts before group 2 (letters)."""
        large = _container_sort_key("Large")
        earth = _container_sort_key("Other", "EarthCache")
        virtual = _container_sort_key("Other", "Virtual Cache")
        assert large < earth < virtual

    def test_letters_sort_before_empty(self):
        """Group 2 (letters) sorts before group 3 (empty)."""
        virtual = _container_sort_key("Other", "Virtual Cache")
        not_chosen = _container_sort_key("Not chosen")
        empty = _container_sort_key("")
        assert virtual < not_chosen
        assert virtual < empty

    def test_case_insensitive(self):
        """Container values should be matched case-insensitively."""
        assert _container_sort_key("MICRO") == _container_sort_key("micro")
        assert _container_sort_key("Micro") == _container_sort_key("micro")

    def test_whitespace_tolerated(self):
        """Leading/trailing whitespace should be ignored."""
        assert _container_sort_key("  Small  ") == _container_sort_key("Small")

    def test_unknown_container_falls_back_to_other(self):
        """Unknown container values fall back to 'O' (group 2)."""
        # Made-up value should sort as 'Other' ('O' in group 2)
        assert _container_sort_key("XYZ") == _container_sort_key("Other")


# ─────────────────────────────────────────────────────────────────────────────
# Alphabetic sub-ordering within group 2 (letter types)
# ─────────────────────────────────────────────────────────────────────────────

class TestLetterAlphabeticOrder:
    """Within group 2, types sort alphabetically by their displayed letter:
    EarthCache 'E' → Lab Cache 'L' → Other 'O' → Virtual 'V'."""

    def test_earth_before_lab(self):
        """E < L → EarthCache sorts before Lab Cache."""
        earth = _container_sort_key("Other", "EarthCache")
        lab = _container_sort_key("Other", "Lab Cache")
        assert earth < lab

    def test_lab_before_other(self):
        """L < O → Lab Cache sorts before Other."""
        lab = _container_sort_key("Other", "Lab Cache")
        other = _container_sort_key("Other")
        assert lab < other

    def test_other_before_virtual(self):
        """O < V → Other sorts before Virtual."""
        other = _container_sort_key("Other")
        virtual = _container_sort_key("Other", "Virtual Cache")
        assert other < virtual

    def test_full_alphabetic_order(self):
        """All four letter-types sort: E → L → O → V."""
        caches = [
            FakeCache("GC_VIRT",  "Other", "Virtual Cache"),
            FakeCache("GC_EARTH", "",      "EarthCache"),
            FakeCache("GC_OTHER", "Other"),
            FakeCache("GC_LAB",   "Other", "Lab Cache"),
        ]
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        assert [c.gc_code for c in caches] == [
            "GC_EARTH",  # E
            "GC_LAB",    # L
            "GC_OTHER",  # O
            "GC_VIRT",   # V
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Stability — secondary sorts should be preserved within container groups
# ─────────────────────────────────────────────────────────────────────────────

class TestSortStability:
    """Within each container size group, the existing order must be preserved.

    This is critical: if a user sorts by Distance first, then by Container,
    they expect caches within each container group to still be ordered by
    Distance. Python's sort() is stable, but only if our key function gives
    equal keys to caches that should be considered the same.
    """

    def test_same_size_caches_keep_input_order(self):
        """Two Small caches in input order A, B should stay in order A, B after sort."""
        caches = [
            FakeCache("GC_SMALL_A", "Small"),
            FakeCache("GC_SMALL_B", "Small"),
            FakeCache("GC_SMALL_C", "Small"),
        ]
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        assert [c.gc_code for c in caches] == ["GC_SMALL_A", "GC_SMALL_B", "GC_SMALL_C"]

    def test_distance_pre_sort_preserved_within_groups(self):
        """If caches are pre-sorted by distance, container sort keeps that within groups."""
        # Pre-sorted by simulated distance (closest first)
        caches = [
            FakeCache("CLOSE_LARGE",  "Large"),    # 1km
            FakeCache("CLOSE_SMALL",  "Small"),    # 2km
            FakeCache("MID_LARGE",    "Large"),    # 5km
            FakeCache("MID_SMALL",    "Small"),    # 6km
            FakeCache("FAR_LARGE",    "Large"),    # 10km
        ]
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        # Small (sub_key 3) caches first, then Large (sub_key 5) — both group 1
        # Within each: distance order preserved (CLOSE before MID before FAR)
        assert [c.gc_code for c in caches] == [
            "CLOSE_SMALL",
            "MID_SMALL",
            "CLOSE_LARGE",
            "MID_LARGE",
            "FAR_LARGE",
        ]

    def test_same_letter_caches_keep_input_order(self):
        """Two Virtual caches stay in input order (same sub_key 'V')."""
        caches = [
            FakeCache("GC_VIRT_A", "Other", "Virtual Cache"),
            FakeCache("GC_VIRT_B", "Other", "Virtual Cache"),
            FakeCache("GC_VIRT_C", "Other", "Virtual Cache"),
        ]
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        assert [c.gc_code for c in caches] == ["GC_VIRT_A", "GC_VIRT_B", "GC_VIRT_C"]


# ─────────────────────────────────────────────────────────────────────────────
# Integration: sorting a list of caches end-to-end
# ─────────────────────────────────────────────────────────────────────────────

class TestContainerSorting:
    """Verify that sorting a list of caches produces the expected order."""

    def test_ascending_sort_full_set(self):
        """Mixed list produces: Nano → … → Large → E → L → O → V → Not chosen."""
        caches = [
            FakeCache("GC_LARGE",       "Large"),
            FakeCache("GC_MICRO",       "Micro"),
            FakeCache("GC_NOTCHOSEN",   "Not chosen"),
            FakeCache("GC_VIRTUAL",     "Other",  cache_type="Virtual Cache"),
            FakeCache("GC_REGULAR",     "Regular"),
            FakeCache("GC_OTHER",       "Other"),
            FakeCache("GC_NANO",        "Nano"),
            FakeCache("GC_EARTH",       "",       cache_type="EarthCache"),
            FakeCache("GC_LAB",         "Other",  cache_type="Lab Cache"),
            FakeCache("GC_SMALL",       "Small"),
        ]
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        order = [c.gc_code for c in caches]
        # Group 1 (physical, smallest first), then group 2 (letters
        # alphabetically: E, L, O, V), then group 3 (empty/not chosen)
        assert order == [
            "GC_NANO",       # group 1, sub 1
            "GC_MICRO",      # group 1, sub 2
            "GC_SMALL",      # group 1, sub 3
            "GC_REGULAR",    # group 1, sub 4
            "GC_LARGE",      # group 1, sub 5
            "GC_EARTH",      # group 2, 'E'
            "GC_LAB",        # group 2, 'L'
            "GC_OTHER",      # group 2, 'O'
            "GC_VIRTUAL",    # group 2, 'V'
            "GC_NOTCHOSEN",  # group 3
        ]

    def test_descending_sort_reverses(self):
        """Descending sort should produce the exact reverse order."""
        caches = [
            FakeCache("GC_NANO",   "Nano"),
            FakeCache("GC_MICRO",  "Micro"),
            FakeCache("GC_LARGE",  "Large"),
        ]
        caches.sort(
            key=lambda c: _container_sort_key(c.container, c.cache_type),
            reverse=True,
        )
        assert [c.gc_code for c in caches] == ["GC_LARGE", "GC_MICRO", "GC_NANO"]

    def test_string_sort_was_wrong(self):
        """Demonstrate why we needed this fix.

        Pure alphabetical sorting puts Large before Micro, which is wrong:
        Large is the BIGGEST physical container, not smaller than Micro.
        """
        sizes = ["Large", "Micro", "Nano", "Regular", "Small"]
        # Old (wrong) behaviour — alphabetical
        assert sorted(sizes) == ["Large", "Micro", "Nano", "Regular", "Small"]
        # New (correct) behaviour — by physical size
        new_order = sorted(sizes, key=lambda s: _container_sort_key(s))
        assert new_order == ["Nano", "Micro", "Small", "Regular", "Large"]


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestContainerSortEdgeCases:
    """Verify edge cases don't break sorting."""

    def test_virtual_cache_with_empty_container(self):
        """Real GPX data: Virtual Cache with no container value still sorts as 'V'."""
        caches = [
            FakeCache("GC_NANO", "Nano"),
            FakeCache("GC_VIRT", None, cache_type="Virtual Cache"),
        ]
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        # Nano (group 1) comes before Virtual (group 2 'V')
        assert [c.gc_code for c in caches] == ["GC_NANO", "GC_VIRT"]

    def test_only_not_chosen_caches(self):
        """List of only 'Not chosen' caches shouldn't crash."""
        caches = [
            FakeCache("GC_A", "Not chosen"),
            FakeCache("GC_B", "Not chosen"),
            FakeCache("GC_C", ""),
            FakeCache("GC_D", None),
        ]
        # Should not raise — all keys equal, order preserved (stable sort)
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        assert len(caches) == 4

    @pytest.mark.parametrize("container,cache_type", [
        ("Nano", None),
        ("Micro", "Traditional Cache"),
        ("Other", "Mystery Cache"),
        ("", "Virtual Cache"),
        (None, "EarthCache"),
    ])
    def test_returns_tuple_always(self, container, cache_type):
        """Sort key must always be a tuple for stable, comparable sorting."""
        result = _container_sort_key(container, cache_type)
        assert isinstance(result, tuple)
        assert len(result) == 2
