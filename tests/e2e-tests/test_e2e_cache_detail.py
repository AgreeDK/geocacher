"""
tests/e2e-tests/test_e2e_cache_detail.py — Cache detail panel scenario tests.

Covers:
- Selecting a cache in the table populates the detail panel (title, GC code, D/T)
- The hint tab contains the raw encoded hint text
- Clicking the decode button ROT13-decodes the hint; clicking again re-encodes it
- Log search highlights matching text (content test via toPlainText)
- Selecting a different cache updates the detail panel
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView


def _select_row(window, qtbot, row: int = 0) -> None:
    """Select *row* in the cache table and wait for the detail panel to populate."""
    view = window._cache_table
    model = view.model()
    view.setCurrentIndex(model.index(row, 0))
    qtbot.wait(100)


# ── Detail panel population ────────────────────────────────────────────────────


def test_selecting_cache_shows_name_in_title(seeded_window, qtbot):
    """Clicking the first row sets the detail panel title to that cache's name."""
    window = seeded_window
    _select_row(window, qtbot, 0)

    title = window._detail_panel._title.text()
    assert title != ""
    # Title is one of the seeded names (not the placeholder)
    assert title not in ("Select a cache", "Vælg en cache")


def test_detail_panel_shows_gc_code(seeded_window, qtbot):
    """After selecting GC12345 the detail panel GC-code label reads 'GC12345'."""
    window = seeded_window

    # Locate the row for GC12345
    table = window._cache_table
    model = table.model()
    target_row = None
    for row in range(model.rowCount()):
        cache = model.cache_at(row)
        if cache and cache.gc_code == "GC12345":
            target_row = row
            break
    assert target_row is not None, "GC12345 not found in table"

    table.setCurrentIndex(model.index(target_row, 0))
    qtbot.wait(100)

    assert window._detail_panel._gc_code_lbl.text() == "GC12345"


def test_detail_panel_shows_difficulty_terrain(seeded_window, qtbot):
    """The D/T label is populated after a cache is selected."""
    window = seeded_window
    _select_row(window, qtbot, 0)

    dt = window._detail_panel._dt_lbl.text()
    assert "/" in dt, f"Expected 'D / T' format, got: {dt!r}"
    assert dt != "— / —"


def test_detail_panel_clears_between_caches(seeded_window, qtbot):
    """Selecting a second cache replaces the detail panel content."""
    window = seeded_window
    table = window._cache_table
    model = table.model()

    table.setCurrentIndex(model.index(0, 0))
    qtbot.wait(100)
    gc_first = window._detail_panel._gc_code_lbl.text()

    table.setCurrentIndex(model.index(1, 0))
    qtbot.wait(100)
    gc_second = window._detail_panel._gc_code_lbl.text()

    assert gc_first != gc_second, "Detail panel GC code did not update on row change"


# ── Hint tab ───────────────────────────────────────────────────────────────────


def _select_gc12345(window, qtbot):
    table = window._cache_table
    model = table.model()
    for row in range(model.rowCount()):
        cache = model.cache_at(row)
        if cache and cache.gc_code == "GC12345":
            table.setCurrentIndex(model.index(row, 0))
            qtbot.wait(100)
            return
    pytest.fail("GC12345 not found in table")


def test_hint_tab_shows_raw_encoded_text(seeded_window, qtbot):
    """The hint browser initially shows the raw (ROT13-encoded) hint text."""
    window = seeded_window
    _select_gc12345(window, qtbot)

    raw = window._detail_panel._hint_browser.toPlainText()
    assert raw == "Under a rock."


def test_decode_button_rot13_decodes_hint(seeded_window, qtbot):
    """
    Clicking 'Decode' translates 'Under a rock.' via ROT13 to 'Haqre n ebpx.'
    and updates the button label.
    """
    window = seeded_window
    _select_gc12345(window, qtbot)

    panel = window._detail_panel
    assert not panel._hint_decoded

    panel._decode_btn.click()
    qtbot.wait(50)

    assert panel._hint_decoded
    decoded = panel._hint_browser.toPlainText()
    assert decoded == "Haqre n ebpx."


def test_encode_button_restores_raw_hint(seeded_window, qtbot):
    """Clicking 'Encode' after 'Decode' restores the original hint text."""
    window = seeded_window
    _select_gc12345(window, qtbot)

    panel = window._detail_panel
    panel._decode_btn.click()  # decode
    qtbot.wait(30)
    panel._decode_btn.click()  # encode back
    qtbot.wait(30)

    assert not panel._hint_decoded
    assert panel._hint_browser.toPlainText() == "Under a rock."


# ── Log search ─────────────────────────────────────────────────────────────────


def test_log_search_filters_visible_log_entries(seeded_window, qtbot):
    """
    Typing in the log search field re-renders logs; content with the search term
    should be present while unrelated log text should not appear.
    """
    window = seeded_window
    _select_gc12345(window, qtbot)

    panel = window._detail_panel
    # GC12345 has two logs: 'TFTC! Great hide.' and 'Could not find it.'
    panel._log_search.setText("TFTC")
    qtbot.wait(50)

    html = panel._log_browser.toHtml()
    assert "TFTC" in html
    assert "Could not find it" not in html


def test_log_search_clear_restores_all_logs(seeded_window, qtbot):
    """Clearing the log search field shows all log entries again."""
    window = seeded_window
    _select_gc12345(window, qtbot)

    panel = window._detail_panel
    panel._log_search.setText("TFTC")
    qtbot.wait(50)
    panel._log_search.setText("")
    qtbot.wait(50)

    html = panel._log_browser.toHtml()
    assert "TFTC" in html
    assert "Could not find it" in html
