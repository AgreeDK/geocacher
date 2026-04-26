"""
tests/e2e-tests/test_sort_persistence.py — E2E tests for sort persistence (feature #63).

Covers:
  1. Sort saved to settings when the user clicks a column header.
  2. Sort restored from settings when a MainWindow is (re-)created.
  3. Sort is per-database: switching databases loads the correct saved sort.
  4. Sort from the filter dialog is saved to settings.

Requires pytest-qt; skipped automatically when unavailable.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from unittest.mock import patch

from PySide6.QtCore import Qt

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_fake_manager(db_path, name="TestDB"):
    """Return a minimal DatabaseManager stand-in for a single database."""
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
            self._info = db_info

        def new_database(self, name, path=None):
            raise RuntimeError("new_database called during sort test")

    return _FakeManager()


class _StubSettings:
    """Minimal AppSettings stand-in backed by an in-process dict."""

    def __init__(self, store: dict):
        self._store = store
        self.show_archived = False
        self.show_found = True
        self.window_geometry = None
        self.window_state = None
        self.home_points = []
        self.active_home_name = ""

    @property
    def sort_spec(self) -> dict:
        return self._store.get("sort_spec", {"field": "name", "ascending": True})

    @sort_spec.setter
    def sort_spec(self, value: dict) -> None:
        self._store["sort_spec"] = value

    def sync(self) -> None:
        pass


def _build_window(qtbot, monkeypatch, db_path, mgr_module, fake_manager, settings_store):
    """
    Create and show a MainWindow backed by *db_path*.

    *settings_store* is a plain dict used as backing storage for the stub
    AppSettings so each test can inspect / pre-populate sort_spec without
    touching real QSettings.
    """
    from opensak.gui.mainwindow import MainWindow

    monkeypatch.setattr(mgr_module, "_manager", fake_manager)
    stub = _StubSettings(settings_store)

    with patch("opensak.gui.mainwindow.get_settings", return_value=stub):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        qtbot.waitExposed(window)
        qtbot.wait(300)
        yield window, stub


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sort_window(qtbot, tmp_path, monkeypatch):
    """MainWindow with a seeded DB and an isolated settings store."""
    import opensak.db.manager as mgr_module
    from opensak.db.database import init_db, get_session
    from opensak.importer import import_gpx
    from opensak.lang import load_language
    from tests.data import SAMPLE_GPX

    load_language("en")

    db_path = tmp_path / "sort_test.db"
    init_db(db_path=db_path)

    gpx_file = tmp_path / "sample.gpx"
    gpx_file.write_text(SAMPLE_GPX, encoding="utf-8")
    with get_session() as session:
        import_gpx(gpx_file, session)

    fake_manager = _make_fake_manager(db_path)
    settings_store: dict = {}

    yield from _build_window(qtbot, monkeypatch, db_path, mgr_module, fake_manager, settings_store)

    mgr_module._manager = None


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSortSavedOnColumnClick:
    """Sort settings are persisted when the user clicks a column header."""

    def test_sort_by_difficulty_saved(self, sort_window, qtbot):
        window, mock_settings = sort_window
        table = window._cache_table

        columns = table._model._columns
        if "difficulty" not in columns:
            pytest.skip("difficulty column not visible")

        col_idx = columns.index("difficulty")
        table.sortByColumn(col_idx, Qt.SortOrder.AscendingOrder)
        qtbot.wait(50)

        saved = mock_settings.sort_spec
        assert saved["field"] == "difficulty"
        assert saved["ascending"] is True

    def test_sort_descending_saved(self, sort_window, qtbot):
        window, mock_settings = sort_window
        table = window._cache_table

        columns = table._model._columns
        if "name" not in columns:
            pytest.skip("name column not visible")

        col_idx = columns.index("name")
        table.sortByColumn(col_idx, Qt.SortOrder.DescendingOrder)
        qtbot.wait(50)

        saved = mock_settings.sort_spec
        assert saved["field"] == "name"
        assert saved["ascending"] is False

    def test_sort_changes_on_second_click(self, sort_window, qtbot):
        window, mock_settings = sort_window
        table = window._cache_table
        columns = table._model._columns

        if "difficulty" not in columns or "terrain" not in columns:
            pytest.skip("required columns not visible")

        table.sortByColumn(columns.index("difficulty"), Qt.SortOrder.AscendingOrder)
        qtbot.wait(50)
        assert mock_settings.sort_spec["field"] == "difficulty"

        table.sortByColumn(columns.index("terrain"), Qt.SortOrder.DescendingOrder)
        qtbot.wait(50)
        saved = mock_settings.sort_spec
        assert saved["field"] == "terrain"
        assert saved["ascending"] is False


class TestSortRestoredOnStartup:
    """The last saved sort is applied when a MainWindow is created."""

    def test_difficulty_descending_restored(self, qtbot, tmp_path, monkeypatch):
        import opensak.db.manager as mgr_module
        from opensak.db.database import init_db, get_session
        from opensak.importer import import_gpx
        from opensak.lang import load_language
        from tests.data import SAMPLE_GPX

        load_language("en")

        db_path = tmp_path / "restore_test.db"
        init_db(db_path=db_path)
        gpx_file = tmp_path / "sample.gpx"
        gpx_file.write_text(SAMPLE_GPX, encoding="utf-8")
        with get_session() as session:
            import_gpx(gpx_file, session)

        fake_manager = _make_fake_manager(db_path)
        # Pre-populate settings with a non-default sort
        settings_store = {"sort_spec": {"field": "difficulty", "ascending": False}}

        gen = _build_window(qtbot, monkeypatch, db_path, mgr_module, fake_manager, settings_store)
        window, _ = next(gen)
        try:
            table = window._cache_table
            columns = table._model._columns
            if "difficulty" not in columns:
                pytest.skip("difficulty column not visible")

            col_idx = columns.index("difficulty")
            header = table.horizontalHeader()
            assert header.sortIndicatorSection() == col_idx
            assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
        finally:
            try:
                next(gen)
            except StopIteration:
                pass
            mgr_module._manager = None

    def test_default_sort_applied_when_no_saved_spec(self, qtbot, tmp_path, monkeypatch):
        import opensak.db.manager as mgr_module
        from opensak.db.database import init_db, get_session
        from opensak.importer import import_gpx
        from opensak.lang import load_language
        from tests.data import SAMPLE_GPX

        load_language("en")

        db_path = tmp_path / "default_sort.db"
        init_db(db_path=db_path)
        gpx_file = tmp_path / "sample.gpx"
        gpx_file.write_text(SAMPLE_GPX, encoding="utf-8")
        with get_session() as session:
            import_gpx(gpx_file, session)

        fake_manager = _make_fake_manager(db_path)
        settings_store: dict = {}  # no saved sort → default to "name" ascending

        gen = _build_window(qtbot, monkeypatch, db_path, mgr_module, fake_manager, settings_store)
        window, _ = next(gen)
        try:
            table = window._cache_table
            columns = table._model._columns
            if "name" not in columns:
                pytest.skip("name column not visible")

            col_idx = columns.index("name")
            header = table.horizontalHeader()
            assert header.sortIndicatorSection() == col_idx
            assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        finally:
            try:
                next(gen)
            except StopIteration:
                pass
            mgr_module._manager = None


class TestSortPerDatabase:
    """Each database has its own sort setting."""

    def test_switching_database_loads_correct_sort(self, qtbot, tmp_path, monkeypatch):
        import opensak.db.manager as mgr_module
        from opensak.db.database import init_db, get_session
        from opensak.importer import import_gpx
        from opensak.lang import load_language
        from opensak.db.manager import DatabaseInfo
        from tests.data import SAMPLE_GPX

        load_language("en")

        db_a = tmp_path / "db_a.db"
        db_b = tmp_path / "db_b.db"
        for path in (db_a, db_b):
            init_db(db_path=path)
            gpx = tmp_path / f"{path.stem}.gpx"
            gpx.write_text(SAMPLE_GPX, encoding="utf-8")
            with get_session() as session:
                import_gpx(gpx, session)

        info_a = DatabaseInfo("DB_A", db_a)
        info_b = DatabaseInfo("DB_B", db_b)

        # Per-database sort store: keyed by safe path
        def _safe(p):
            return str(p).replace("/", "_").replace("\\", "_")

        per_db: dict[str, dict] = {
            _safe(db_a): {"field": "difficulty", "ascending": True},
            _safe(db_b): {"field": "terrain", "ascending": False},
        }

        fake_manager = _make_fake_manager(db_a, name="DB_A")

        class _PerDbSettings:
            show_archived = False
            show_found = True
            window_geometry = None
            window_state = None
            home_points = []
            active_home_name = ""

            @property
            def sort_spec(self):
                key = _safe(fake_manager.active.path)
                return per_db.get(key, {"field": "name", "ascending": True})

            @sort_spec.setter
            def sort_spec(self, v):
                key = _safe(fake_manager.active.path)
                per_db[key] = v

            def sync(self):
                pass

        stub = _PerDbSettings()
        monkeypatch.setattr(mgr_module, "_manager", fake_manager)

        from opensak.gui.mainwindow import MainWindow

        with patch("opensak.gui.mainwindow.get_settings", return_value=stub):
            window = MainWindow()
            qtbot.addWidget(window)
            window.show()
            qtbot.waitExposed(window)
            qtbot.wait(300)

            try:
                table = window._cache_table
                columns = table._model._columns
                header = table.horizontalHeader()

                # Check initial sort (DB_A → difficulty ascending)
                if "difficulty" in columns:
                    assert header.sortIndicatorSection() == columns.index("difficulty")
                    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder

                # Simulate switching to DB_B
                fake_manager.switch_to(info_b)
                window._on_database_switched(info_b)
                qtbot.wait(200)

                # Check sort after switch (DB_B → terrain descending)
                if "terrain" in columns:
                    assert header.sortIndicatorSection() == columns.index("terrain")
                    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
            finally:
                mgr_module._manager = None


class TestFilterDialogSortSaved:
    """Sort emitted from the filter dialog is persisted."""

    def test_filter_sort_saved_to_settings(self, sort_window, qtbot):
        window, mock_settings = sort_window
        from opensak.filters.engine import FilterSet, SortSpec

        sort = SortSpec(field="difficulty", ascending=False)
        window._on_filter_applied(FilterSet(), sort)
        qtbot.wait(50)

        saved = mock_settings.sort_spec
        assert saved["field"] == "difficulty"
        assert saved["ascending"] is False

    def test_filter_sort_reflected_in_table_indicator(self, sort_window, qtbot):
        window, _ = sort_window
        from opensak.filters.engine import FilterSet, SortSpec

        table = window._cache_table
        columns = table._model._columns
        if "terrain" not in columns:
            pytest.skip("terrain column not visible")

        sort = SortSpec(field="terrain", ascending=True)
        window._on_filter_applied(FilterSet(), sort)
        qtbot.wait(50)

        header = table.horizontalHeader()
        assert header.sortIndicatorSection() == columns.index("terrain")
        assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
