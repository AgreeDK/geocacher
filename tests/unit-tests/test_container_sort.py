"""
tests/unit-tests/test_container_sort.py — Tests for issue #90.

Verifies that the Container column sorts by logical size, not alphabetically.

Sort order (group):
  1  Virtual / EarthCache / Lab    (no physical container — by cache_type,
                                    sorted alphabetically within the group)
  2  Nano
  3  Micro
  4  Small
  5  Regular
  6  Large
  7  Other                          (unknown size)
  8  Not chosen / empty             (incomplete data, sorts last)

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
        groups = [
            _container_sort_key("Nano")[0],
            _container_sort_key("Micro")[0],
            _container_sort_key("Small")[0],
            _container_sort_key("Regular")[0],
            _container_sort_key("Large")[0],
        ]
        assert groups == sorted(groups)
        assert len(set(groups)) == 5  # all distinct

    def test_virtual_cache_sorts_first(self):
        """Virtual caches should sort before any physical container."""
        virtual_key = _container_sort_key("Other", "Virtual Cache")
        nano_key = _container_sort_key("Nano")
        assert virtual_key < nano_key

    def test_earthcache_sorts_first(self):
        """EarthCaches should sort before any physical container."""
        earth_key = _container_sort_key("", "EarthCache")
        nano_key = _container_sort_key("Nano")
        assert earth_key < nano_key

    def test_lab_cache_sorts_first(self):
        """Lab caches should sort before any physical container."""
        lab_key = _container_sort_key("Other", "Lab Cache")
        nano_key = _container_sort_key("Nano")
        assert lab_key < nano_key

    def test_other_sorts_after_large(self):
        """'Other' is unknown size but exists — sorts after Large."""
        assert _container_sort_key("Other") > _container_sort_key("Large")

    def test_not_chosen_sorts_last(self):
        """'Not chosen' indicates incomplete data — sorts at the end."""
        not_chosen = _container_sort_key("Not chosen")
        for size in ("Nano", "Micro", "Small", "Regular", "Large", "Other"):
            assert _container_sort_key(size) < not_chosen

    def test_empty_sorts_last(self):
        """Empty string sorts last (same as 'Not chosen')."""
        assert _container_sort_key("") == _container_sort_key("Not chosen")

    def test_none_sorts_last(self):
        """None container value sorts last."""
        assert _container_sort_key(None) == _container_sort_key("Not chosen")

    def test_case_insensitive(self):
        """Container values should be matched case-insensitively."""
        assert _container_sort_key("MICRO") == _container_sort_key("micro")
        assert _container_sort_key("Micro") == _container_sort_key("micro")

    def test_whitespace_tolerated(self):
        """Leading/trailing whitespace should be ignored."""
        assert _container_sort_key("  Small  ") == _container_sort_key("Small")

    def test_unknown_value_falls_back_to_other(self):
        """Unknown container values fall back to 'Other' group, not lost."""
        # Made-up value should sort with Other (group 7), not at the end
        assert (_container_sort_key("XYZ")[0]
                == _container_sort_key("Other")[0])


# ─────────────────────────────────────────────────────────────────────────────
# Alphabetic sub-ordering within group 1 (non-physical types)
# ─────────────────────────────────────────────────────────────────────────────

class TestNonPhysicalAlphabeticOrder:
    """Within group 1, Virtual/Earth/Lab sort alphabetically by cache_type
    so they stay grouped together visually (and future types slot in)."""

    def test_earthcache_before_lab(self):
        """E < L → EarthCache sorts before Lab Cache."""
        earth = _container_sort_key("Other", "EarthCache")
        lab = _container_sort_key("Other", "Lab Cache")
        assert earth < lab

    def test_lab_before_virtual(self):
        """L < V → Lab Cache sorts before Virtual Cache."""
        lab = _container_sort_key("Other", "Lab Cache")
        virtual = _container_sort_key("Other", "Virtual Cache")
        assert lab < virtual

    def test_full_alphabetic_order_in_group_1(self):
        """All three non-physical types should be in alphabetic order."""
        caches = [
            FakeCache("GC_VIRT1",  "Other", "Virtual Cache"),
            FakeCache("GC_EARTH1", "",      "EarthCache"),
            FakeCache("GC_LAB1",   "Other", "Lab Cache"),
            FakeCache("GC_VIRT2",  "Other", "Virtual Cache"),
            FakeCache("GC_EARTH2", "",      "EarthCache"),
        ]
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        types_in_order = [c.cache_type for c in caches]
        assert types_in_order == [
            "EarthCache",
            "EarthCache",
            "Lab Cache",
            "Virtual Cache",
            "Virtual Cache",
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Stability — secondary sorts should be preserved within container groups
# ─────────────────────────────────────────────────────────────────────────────

class TestSortStability:
    """Within each container size group, the existing order must be preserved.

    This is critical: if a user sorts by Distance first, then by Container,
    they expect caches within each container group to still be ordered by
    Distance. Python's sort() is stable, but only if our key function gives
    equal keys to caches in the same group.
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
        # Small (group 4) caches first, then Large (group 6)
        # Within each group: distance order preserved (CLOSE before MID before FAR)
        assert [c.gc_code for c in caches] == [
            "CLOSE_SMALL",
            "MID_SMALL",
            "CLOSE_LARGE",
            "MID_LARGE",
            "FAR_LARGE",
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Integration: sorting a list of caches end-to-end
# ─────────────────────────────────────────────────────────────────────────────

class TestContainerSorting:
    """Verify that sorting a list of caches produces the expected order."""

    def test_ascending_sort_full_set(self):
        """Mixed list should produce: Earth → Lab → Virtual → Nano → … → Not chosen."""
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
        # Group 1 sorted alphabetically by cache_type:
        # EarthCache → Lab Cache → Virtual Cache
        assert order == [
            "GC_EARTH",
            "GC_LAB",
            "GC_VIRTUAL",
            "GC_NANO",
            "GC_MICRO",
            "GC_SMALL",
            "GC_REGULAR",
            "GC_LARGE",
            "GC_OTHER",
            "GC_NOTCHOSEN",
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
        """Real GPX data: Virtual Cache with no container value should still sort first."""
        caches = [
            FakeCache("GC_NANO", "Nano"),
            FakeCache("GC_VIRT", None, cache_type="Virtual Cache"),
        ]
        caches.sort(key=lambda c: _container_sort_key(c.container, c.cache_type))
        assert caches[0].gc_code == "GC_VIRT"

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
