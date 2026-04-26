"""
tests/e2e-tests/conftest.py — Shared fixtures for e2e GUI tests.
"""

from __future__ import annotations
import pytest

pytest.importorskip("pytestqt")


def _make_fake_manager(db_path, name="E2ETest"):
    from opensak.db.manager import DatabaseInfo

    class _FakeManager:
        def __init__(self):
            self._info = DatabaseInfo(name, db_path)

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
            raise RuntimeError("new_database called during e2e test")

    return _FakeManager()


@pytest.fixture
def seeded_window(qtbot, tmp_path, monkeypatch):
    """MainWindow backed by a throwaway database pre-seeded with 4 test caches."""
    import opensak.db.manager as mgr_module
    from opensak.db.database import init_db, get_session
    from opensak.lang import load_language
    from opensak.importer import import_gpx
    from tests.data import SAMPLE_GPX, SAMPLE_WPTS_GPX, make_variant_gpx

    load_language("en")

    db_path = tmp_path / "e2e.db"
    init_db(db_path=db_path)

    gpx_file = tmp_path / "sample.gpx"
    gpx_file.write_text(SAMPLE_GPX, encoding="utf-8")
    wpts_file = tmp_path / "sample-wpts.gpx"
    wpts_file.write_text(SAMPLE_WPTS_GPX, encoding="utf-8")

    with get_session() as session:
        import_gpx(gpx_file, session, wpts_path=wpts_file)

    variant_file = tmp_path / "variant.gpx"
    variant_file.write_text(make_variant_gpx("GCAAA01", "GCAAA02"), encoding="utf-8")
    with get_session() as session:
        import_gpx(variant_file, session)

    monkeypatch.setattr(mgr_module, "_manager", _make_fake_manager(db_path))

    from opensak.gui.mainwindow import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    qtbot.wait(300)

    yield window

    mgr_module._manager = None


@pytest.fixture
def empty_window(qtbot, tmp_path, monkeypatch):
    """MainWindow backed by a fresh empty database (0 caches)."""
    import opensak.db.manager as mgr_module
    from opensak.db.database import init_db
    from opensak.lang import load_language

    load_language("en")

    db_path = tmp_path / "empty.db"
    init_db(db_path=db_path)

    monkeypatch.setattr(mgr_module, "_manager", _make_fake_manager(db_path, name="E2EEmpty"))

    from opensak.gui.mainwindow import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    qtbot.wait(300)

    yield window

    mgr_module._manager = None
