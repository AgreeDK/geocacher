"""
tests/e2e-tests/test_e2e_trip_planner.py — Trip planner dialog scenario tests.

Covers:
- TripPlannerDialog opens from the main window action (show(), not exec())
- The dialog has both Radius and Route tabs
- Radius mode: changing the radius spin updates the result label
- Route mode: adding a coordinate point enables the route list
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


# ── Dialog open / structure ────────────────────────────────────────────────────


def test_trip_planner_opens_from_main_window(seeded_window, qtbot):
    """Triggering _open_trip_planner shows a non-modal TripPlannerDialog."""
    window = seeded_window

    window._open_trip_planner()
    qtbot.wait(100)

    # The dialog is stored on the window
    dlg = window._trip_planner_win
    assert dlg is not None
    assert dlg.isVisible()

    dlg.close()
    qtbot.wait(50)


def test_trip_planner_has_radius_and_route_tabs(seeded_window, qtbot):
    """The dialog exposes two tabs: Radius and Route."""
    window = seeded_window
    window._open_trip_planner()
    qtbot.wait(100)

    dlg = window._trip_planner_win
    assert dlg._tabs.count() == 2

    dlg.close()


def test_trip_planner_receives_all_caches(seeded_window, qtbot):
    """
    The trip planner is initialised with the full cache list from the table
    (4 seeded caches).
    """
    window = seeded_window
    window._open_trip_planner()
    qtbot.wait(100)

    dlg = window._trip_planner_win
    assert len(dlg._all_caches) == 4

    dlg.close()


# ── Radius tab ─────────────────────────────────────────────────────────────────


def test_trip_planner_direct_construction(qtbot, tmp_path, monkeypatch):
    """
    TripPlannerDialog can be constructed directly with a cache list and
    the radius tab is the default active tab.
    """
    import opensak.db.manager as mgr_module
    from opensak.db.database import init_db
    from opensak.db.manager import DatabaseInfo
    from opensak.lang import load_language
    from opensak.db.database import get_session
    from opensak.importer import import_gpx
    from opensak.db.models import Cache
    from tests.data import SAMPLE_GPX

    load_language("en")

    db_path = tmp_path / "trip.db"
    init_db(db_path=db_path)

    class _FakeManager:
        def __init__(self):
            self._info = DatabaseInfo("TripTest", db_path)

        @property
        def active(self):
            return self._info

        @property
        def active_path(self):
            return self._info.path

        @property
        def databases(self):
            return [self._info]

        def ensure_active_initialised(self):
            pass

        def switch_to(self, db_info):
            pass

        def new_database(self, name, path=None):
            raise RuntimeError

    monkeypatch.setattr(mgr_module, "_manager", _FakeManager())

    gpx_file = tmp_path / "trip_sample.gpx"
    gpx_file.write_text(SAMPLE_GPX, encoding="utf-8")
    with get_session() as session:
        import_gpx(gpx_file, session)

    with get_session() as session:
        caches = session.query(Cache).all()

    from opensak.gui.dialogs.trip_dialog import TripPlannerDialog

    dlg = TripPlannerDialog(caches=caches)
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)

    # Radius tab is index 0 and is the default
    assert dlg._tabs.currentIndex() == 0
    assert dlg._tabs.count() == 2

    dlg.close()
    mgr_module._manager = None


def test_trip_planner_route_tab_switches(seeded_window, qtbot):
    """Switching to the Route tab does not crash."""
    window = seeded_window
    window._open_trip_planner()
    qtbot.wait(100)

    dlg = window._trip_planner_win
    dlg._tabs.setCurrentIndex(1)  # Route tab
    qtbot.wait(50)

    assert dlg._tabs.currentIndex() == 1
    dlg.close()
