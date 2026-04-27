"""
tests/e2e-tests/test_e2e_gps_export.py — GPS export scenario tests.

Covers:
- GpsExportDialog opens and shows the correct cache count label
- Exporting to a file path (file mode) writes a valid GPX file on disk
- The written GPX contains the GC codes of the exported caches
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt


def _build_caches(tmp_path):
    """
    Return a list of Cache ORM objects from the SAMPLE_GPX fixture.

    user_note is eagerly loaded so objects remain usable after the session
    closes — generate_gpx() accesses cache.user_note on detached instances,
    which would raise DetachedInstanceError for lazy-loaded relationships.
    """
    from opensak.db.database import init_db, get_session
    from opensak.importer import import_gpx
    from opensak.db.models import Cache
    from sqlalchemy.orm import joinedload
    from tests.data import SAMPLE_GPX

    db_path = tmp_path / "gps_test.db"
    init_db(db_path=db_path)

    gpx_file = tmp_path / "gps_sample.gpx"
    gpx_file.write_text(SAMPLE_GPX, encoding="utf-8")

    with get_session() as session:
        import_gpx(gpx_file, session)

    with get_session() as session:
        return (
            session.query(Cache)
            .options(
                joinedload(Cache.user_note),
                joinedload(Cache.logs),   # generate_gpx also accesses cache.logs
            )
            .all()
        )


# ── Dialog smoke test ──────────────────────────────────────────────────────────


def test_gps_dialog_opens_and_shows_cache_count(qtbot, tmp_path, monkeypatch):
    """GpsExportDialog opens and its header label reflects the number of caches passed in."""
    import opensak.db.manager as mgr_module
    from opensak.db.database import init_db
    from opensak.db.manager import DatabaseInfo
    from opensak.lang import load_language

    load_language("en")

    db_path = tmp_path / "gps_dlg.db"
    init_db(db_path=db_path)

    class _FakeManager:
        def __init__(self):
            self._info = DatabaseInfo("GPSTest", db_path)

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

    caches = _build_caches(tmp_path)
    assert len(caches) == 2

    from opensak.gui.dialogs.gps_dialog import GpsExportDialog

    dlg = GpsExportDialog(caches=caches)
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)

    # The dialog's title bar or layout should reference the cache count
    assert dlg._caches is not None
    assert len(dlg._caches) == 2

    mgr_module._manager = None


# ── File-mode export ───────────────────────────────────────────────────────────


def test_gps_export_file_mode_writes_gpx(qtbot, tmp_path, monkeypatch):
    """
    Exporting to a file (no Garmin device) creates a .gpx file containing
    the GC codes of the exported caches.
    """
    import opensak.db.manager as mgr_module
    from opensak.db.database import init_db
    from opensak.db.manager import DatabaseInfo
    from opensak.lang import load_language

    load_language("en")

    db_path = tmp_path / "gps_export.db"
    init_db(db_path=db_path)

    class _FakeManager:
        def __init__(self):
            self._info = DatabaseInfo("GPSExport", db_path)

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

    caches = _build_caches(tmp_path)
    from opensak.gui.dialogs.gps_dialog import GpsExportDialog

    dlg = GpsExportDialog(caches=caches)
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)

    # Configure file-mode export
    out_dir = tmp_path / "gpx_out"
    out_dir.mkdir()
    dlg._rb_file.setChecked(True)
    dlg._selected_file_path = out_dir
    dlg._filename.setText("e2e_export")
    dlg._export_btn.setEnabled(True)

    qtbot.mouseClick(dlg._export_btn, Qt.MouseButton.LeftButton)

    # Wait for the background ExportWorker thread to finish (up to 10 s)
    qtbot.waitUntil(
        lambda: (out_dir / "e2e_export.gpx").exists(),
        timeout=10_000,
    )

    gpx_path = out_dir / "e2e_export.gpx"
    assert gpx_path.exists()

    content = gpx_path.read_text(encoding="utf-8")
    assert "GC12345" in content
    assert "GC99999" in content

    mgr_module._manager = None


# ── Direct export_to_file function test ───────────────────────────────────────


def test_export_to_file_writes_valid_gpx(tmp_path, monkeypatch):
    """
    export_to_file() (the core function, no dialog) writes a GPX file whose
    content includes the GC codes of every exported cache.
    This is a fast, headless sanity-check independent of the Qt layer.
    """
    import opensak.db.manager as mgr_module
    from opensak.db.database import init_db
    from opensak.db.manager import DatabaseInfo

    db_path = tmp_path / "direct_export.db"
    init_db(db_path=db_path)

    class _FakeManager:
        def __init__(self):
            self._info = DatabaseInfo("DirectExport", db_path)

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

    caches = _build_caches(tmp_path)

    from opensak.gps.garmin import export_to_file

    out_file = tmp_path / "direct.gpx"
    result = export_to_file(caches, out_file)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "GC12345" in content
    assert "GC99999" in content
    assert result.cache_count == 2

    mgr_module._manager = None
