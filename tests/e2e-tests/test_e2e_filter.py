"""
tests/e2e-tests/test_e2e_filter.py — Filter scenario tests.

The seeded DB has 4 caches:
  GC12345  — Traditional Cache, D=2.0 T=3.0, found=False, available=True
  GC99999  — Unknown Cache,     D=4.0 T=2.5, found=False, available=True
  GCAAA01  — Traditional Cache, D=2.0 T=3.0, found=False, available=True (variant)
  GCAAA02  — Unknown Cache,     D=4.0 T=2.5, found=False, available=True (variant)

Covers:
- Quick-filter "Found" returns 0 rows (none are marked found)
- Quick-filter "Not Found" returns all 4 rows
- Name search narrows the table and clear restores it
- GC-code search field filters to a single exact match
- FilterDialog type filter reduces the visible set
"""

import pytest

pytest.importorskip("pytestqt")


TOTAL = 4  # caches seeded into the test DB


# ── Quick-filter ───────────────────────────────────────────────────────────────


def test_quick_filter_found_returns_zero(seeded_window, qtbot):
    """Selecting the 'Found' quick-filter hides all caches (none are marked found)."""
    window = seeded_window
    assert window._cache_table.row_count() == TOTAL

    window._quick_filter.setCurrentIndex(2)  # index 2 = Found
    qtbot.wait(50)

    assert window._cache_table.row_count() == 0


def test_quick_filter_not_found_returns_all(seeded_window, qtbot):
    """Selecting 'Not Found' keeps all 4 caches visible."""
    window = seeded_window

    window._quick_filter.setCurrentIndex(2)  # Found → 0 rows
    qtbot.wait(50)
    assert window._cache_table.row_count() == 0

    window._quick_filter.setCurrentIndex(1)  # Not Found → all rows
    qtbot.wait(50)

    assert window._cache_table.row_count() == TOTAL


def test_quick_filter_reset_to_all_restores_count(seeded_window, qtbot):
    """Switching back to 'All' (index 0) after a filter restores full count."""
    window = seeded_window

    window._quick_filter.setCurrentIndex(2)  # Found → 0
    qtbot.wait(50)
    window._quick_filter.setCurrentIndex(0)  # All
    qtbot.wait(50)

    assert window._cache_table.row_count() == TOTAL


# ── Name search ────────────────────────────────────────────────────────────────


def test_name_search_filters_to_matching_rows(seeded_window, qtbot):
    """Typing in the name field narrows the table to caches whose name matches."""
    window = seeded_window

    # "Test Traditional" matches GC12345 and GCAAA01 (both share that name)
    window._search_box.setText("Test Traditional")
    qtbot.waitUntil(lambda: window._cache_table.row_count() == 2, timeout=1_000)

    assert window._cache_table.row_count() == 2


def test_name_search_clear_restores_all(seeded_window, qtbot):
    """Clearing the name search field restores the full cache list."""
    window = seeded_window

    window._search_box.setText("Mystery Cache")
    qtbot.waitUntil(lambda: window._cache_table.row_count() == 2, timeout=1_000)

    window._search_box.setText("")
    qtbot.waitUntil(lambda: window._cache_table.row_count() == TOTAL, timeout=1_000)

    assert window._cache_table.row_count() == TOTAL


def test_name_search_no_match_returns_zero(seeded_window, qtbot):
    """A search term that matches nothing yields an empty table."""
    window = seeded_window

    window._search_box.setText("zzz_no_match_zzz")
    qtbot.waitUntil(lambda: window._cache_table.row_count() == 0, timeout=1_000)

    assert window._cache_table.row_count() == 0


# ── GC-code search ─────────────────────────────────────────────────────────────


def test_gc_search_finds_exact_code(seeded_window, qtbot):
    """Typing a GC code in the GC field returns exactly that one cache."""
    window = seeded_window

    window._search_gc.setText("GC12345")
    qtbot.waitUntil(lambda: window._cache_table.row_count() == 1, timeout=1_000)

    assert window._cache_table.row_count() == 1


def test_gc_search_prefix_finds_multiple(seeded_window, qtbot):
    """A partial GC prefix matches all caches whose code starts with it."""
    window = seeded_window

    window._search_gc.setText("GCAAA")
    qtbot.waitUntil(lambda: window._cache_table.row_count() == 2, timeout=1_000)

    assert window._cache_table.row_count() == 2


# ── FilterDialog (Ctrl+F path) ─────────────────────────────────────────────────


def test_filter_applied_signal_updates_table(seeded_window, qtbot):
    """
    Simulating what happens when FilterDialog emits filter_applied:
    the main window reloads the table with the new FilterSet.
    """
    from opensak.filters.engine import FilterSet, SortSpec, CacheTypeFilter

    window = seeded_window
    assert window._cache_table.row_count() == TOTAL

    # Only Traditional caches → 2 rows (GC12345 + GCAAA01)
    fs = FilterSet(mode="AND")
    fs.add(CacheTypeFilter(["Traditional Cache"]))
    sort = SortSpec("name", ascending=True)

    window._on_filter_applied(fs, sort, "Traditional only")
    qtbot.wait(50)

    assert window._cache_table.row_count() == 2
    assert window._filter_lbl.text() != ""  # label shows active filter name


def test_clear_filter_removes_advanced_filter(seeded_window, qtbot):
    """After _clear_filter the full row count is restored and label is gone."""
    from opensak.filters.engine import FilterSet, SortSpec, CacheTypeFilter

    window = seeded_window

    fs = FilterSet(mode="AND")
    fs.add(CacheTypeFilter(["Traditional Cache"]))
    window._on_filter_applied(fs, SortSpec("name", ascending=True), "Traditional only")
    qtbot.wait(50)
    assert window._cache_table.row_count() == 2

    window._clear_filter()
    qtbot.wait(50)

    assert window._cache_table.row_count() == TOTAL
    assert window._filter_lbl.text() == ""
