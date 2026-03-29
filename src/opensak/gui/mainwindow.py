"""
src/opensak/gui/mainwindow.py — Main application window.
"""

from __future__ import annotations
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QStatusBar,
    QToolBar, QPushButton, QComboBox, QFrame,
    QSizePolicy, QMessageBox
)

from opensak.db.database import get_session, db_health_check
from opensak.db.models import Cache
from opensak.filters.engine import (
    FilterSet, SortSpec, apply_filters,
    AvailableFilter, NotFoundFilter, CacheTypeFilter,
    DifficultyFilter, TerrainFilter
)
from opensak.gui.cache_table import CacheTableView
from opensak.gui.cache_detail import CacheDetailPanel
from opensak.gui.settings import get_settings


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(1100, 680)
        self._current_filterset = FilterSet()
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._restore_state()
        self._update_title()
        # Load caches after UI is ready
        QTimer.singleShot(100, self._refresh_cache_list)

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # ── Quick filter bar ──────────────────────────────────────────────────
        filter_bar = self._build_filter_bar()
        main_layout.addWidget(filter_bar)

        # ── Main splitter: list | detail ──────────────────────────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: cache list
        self._cache_table = CacheTableView()
        self._cache_table.cache_selected.connect(self._on_cache_selected)
        self._splitter.addWidget(self._cache_table)

        # Right: detail + map placeholder stacked vertically
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self._detail_panel = CacheDetailPanel()
        right_splitter.addWidget(self._detail_panel)

        # Map widget (Stage 5)
        from opensak.gui.map_widget import MapWidget
        self._map_widget = MapWidget()
        self._map_widget.cache_selected.connect(self._on_map_cache_selected)
        self._map_widget.setMinimumHeight(200)
        right_splitter.addWidget(self._map_widget)

        right_splitter.setSizes([400, 300])
        self._splitter.addWidget(right_splitter)
        self._splitter.setSizes([580, 520])

        main_layout.addWidget(self._splitter)

    def _build_filter_bar(self) -> QWidget:
        """Quick filter bar above the cache list."""
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.StyledPanel)
        bar.setMaximumHeight(44)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Search box
        layout.addWidget(QLabel("Søg:"))
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Navn eller GC kode…")
        self._search_box.setMaximumWidth(200)
        self._search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_box)

        # Quick filters
        layout.addWidget(QLabel("Vis:"))
        self._quick_filter = QComboBox()
        self._quick_filter.addItems([
            "Alle caches",
            "Ikke fundne",
            "Fundne",
            "Tilgængelige (ikke fundne)",
            "Traditional — let (D≤2, T≤2)",
            "Arkiverede",
        ])
        self._quick_filter.currentIndexChanged.connect(self._on_quick_filter_changed)
        layout.addWidget(self._quick_filter)

        # Aktivt filter label
        self._filter_lbl = QLabel("")
        self._filter_lbl.setStyleSheet("color: #e65100; font-style: italic;")
        layout.addWidget(self._filter_lbl)

        layout.addStretch()

        # Cache count label
        self._count_lbl = QLabel("0 caches")
        self._count_lbl.setStyleSheet("color: gray;")
        layout.addWidget(self._count_lbl)

        return bar

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        # ── Fil ───────────────────────────────────────────────────────────────
        file_menu = menubar.addMenu("&Fil")

        # Database
        self._act_db_manager = QAction("&Administrer databaser…", self)
        self._act_db_manager.setShortcut(QKeySequence("Ctrl+D"))
        self._act_db_manager.triggered.connect(self._open_db_manager)
        file_menu.addAction(self._act_db_manager)

        file_menu.addSeparator()

        self._act_import = QAction("&Importer GPX / PQ zip…", self)
        self._act_import.setShortcut(QKeySequence("Ctrl+I"))
        self._act_import.triggered.connect(self._open_import_dialog)
        file_menu.addAction(self._act_import)

        file_menu.addSeparator()

        act_quit = QAction("&Afslut", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── Waypoint ──────────────────────────────────────────────────────────
        wp_menu = menubar.addMenu("&Waypoint")

        act_wp_add = QAction("&Tilføj cache…", self)
        act_wp_add.setShortcut(QKeySequence("Ctrl+N"))
        act_wp_add.triggered.connect(self._add_waypoint)
        wp_menu.addAction(act_wp_add)

        self._act_wp_edit = QAction("&Rediger cache…", self)
        self._act_wp_edit.setShortcut(QKeySequence("Ctrl+E"))
        self._act_wp_edit.setEnabled(False)
        self._act_wp_edit.triggered.connect(self._edit_waypoint)
        wp_menu.addAction(self._act_wp_edit)

        self._act_wp_delete = QAction("&Slet cache…", self)
        self._act_wp_delete.setShortcut(QKeySequence("Delete"))
        self._act_wp_delete.setEnabled(False)
        self._act_wp_delete.triggered.connect(self._delete_waypoint)
        wp_menu.addAction(self._act_wp_delete)

        # ── Vis ───────────────────────────────────────────────────────────────
        view_menu = menubar.addMenu("&Vis")

        act_refresh = QAction("&Opdater liste", self)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self._refresh_cache_list)
        view_menu.addAction(act_refresh)

        view_menu.addSeparator()

        act_filter = QAction("🔍  &Sæt filter…", self)
        act_filter.setShortcut("Ctrl+F")
        act_filter.triggered.connect(self._open_filter_dialog)
        view_menu.addAction(act_filter)

        act_clear = QAction("❌  &Nulstil filter", self)
        act_clear.triggered.connect(self._clear_filter)
        view_menu.addAction(act_clear)

        view_menu.addSeparator()

        act_columns = QAction("&Vælg kolonner…", self)
        act_columns.triggered.connect(self._open_column_chooser)
        view_menu.addAction(act_columns)

        # ── Funktioner ────────────────────────────────────────────────────────
        tools_menu = menubar.addMenu("F&unktioner")

        act_settings = QAction("&Indstillinger…", self)
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self._open_settings)
        tools_menu.addAction(act_settings)

        tools_menu.addSeparator()

        act_found_update = QAction("⟳  Opdater fund fra reference database…", self)
        act_found_update.triggered.connect(self._open_found_updater)
        tools_menu.addAction(act_found_update)

        # ── Hjælp ─────────────────────────────────────────────────────────────
        help_menu = menubar.addMenu("&Hjælp")

        act_about = QAction("&Om OpenSAK…", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _setup_toolbar(self) -> None:
        tb = QToolBar("Værktøjslinje")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction(self._act_db_manager)
        tb.addAction(self._act_import)

        tb.addSeparator()

        refresh_act = QAction("⟳  Opdater", self)
        refresh_act.triggered.connect(self._refresh_cache_list)
        tb.addAction(refresh_act)

        tb.addSeparator()

        self._act_filter = QAction("🔍  Filter", self)
        self._act_filter.setToolTip("Åbn filter dialog (Ctrl+F)")
        self._act_filter.setShortcut("Ctrl+F")
        self._act_filter.triggered.connect(self._open_filter_dialog)
        tb.addAction(self._act_filter)

        self._act_clear_filter = QAction("❌  Slet filter", self)
        self._act_clear_filter.setToolTip("Nulstil alle filtre")
        self._act_clear_filter.setEnabled(False)
        self._act_clear_filter.triggered.connect(self._clear_filter)
        tb.addAction(self._act_clear_filter)

        tb.addSeparator()

        fit_act = QAction("⊞  Vis alle", self)
        fit_act.setToolTip("Zoom kortet til alle caches")
        fit_act.triggered.connect(lambda: self._map_widget.fit_all())
        tb.addAction(fit_act)

        home_act = QAction("⌂  Hjem", self)
        home_act.setToolTip("Gå til hjemkoordinat")
        home_act.triggered.connect(lambda: self._map_widget.pan_to_home())
        tb.addAction(home_act)

        tb.addSeparator()

        settings_act = QAction("⚙  Indstillinger", self)
        settings_act.triggered.connect(self._open_settings)
        tb.addAction(settings_act)

    def _setup_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Klar")

    # ── State save/restore ────────────────────────────────────────────────────

    def _restore_state(self) -> None:
        s = get_settings()
        if s.window_geometry:
            self.restoreGeometry(s.window_geometry)
        if s.window_state:
            self.restoreState(s.window_state)
        if s.splitter_state:
            self._splitter.restoreState(s.splitter_state)

    def _update_title(self) -> None:
        """Opdatér vinduestitel med aktiv database navn."""
        from opensak.db.manager import get_db_manager
        manager = get_db_manager()
        db_name = manager.active.name if manager.active else "Ingen database"
        self.setWindowTitle(f"OpenSAK — {db_name}")

    def _open_db_manager(self) -> None:
        from opensak.gui.dialogs.database_dialog import DatabaseManagerDialog
        dlg = DatabaseManagerDialog(self)
        dlg.database_switched.connect(self._on_database_switched)
        dlg.exec()

    def _on_database_switched(self, db_info) -> None:
        """Kaldes når brugeren skifter aktiv database."""
        self._update_title()
        self._detail_panel.clear()
        self._refresh_cache_list()
        self._statusbar.showMessage(
            f"Skiftede til database: {db_info.name}", 4000
        )

    def closeEvent(self, event) -> None:
        s = get_settings()
        s.window_geometry = self.saveGeometry()
        s.window_state    = self.saveState()
        s.splitter_state  = self._splitter.saveState()
        s.sync()
        super().closeEvent(event)

    # ── Cache list ────────────────────────────────────────────────────────────

    def _refresh_cache_list(self) -> None:
        """Reload caches from DB applying current filters."""
        self._statusbar.showMessage("Henter caches…")

        fs = self._build_current_filterset()
        with get_session() as session:
            caches = apply_filters(session, fs, SortSpec("name"))

        self._cache_table.load_caches(caches)
        self._map_widget.load_caches(caches)
        count = self._cache_table.row_count()
        self._count_lbl.setText(f"{count} cache{'r' if count != 1 else ''}")
        self._statusbar.showMessage(f"{count} caches indlæst", 3000)

    def _build_current_filterset(self) -> FilterSet:
        """Build a FilterSet from the current quick filter + search box."""
        fs = FilterSet(mode="AND")
        idx = self._quick_filter.currentIndex()

        if idx == 1:   # Ikke fundne
            fs.add(NotFoundFilter())
        elif idx == 2:  # Fundne
            from opensak.filters.engine import FoundFilter
            fs.add(FoundFilter())
        elif idx == 3:  # Tilgængelige ikke fundne
            fs.add(AvailableFilter())
            fs.add(NotFoundFilter())
        elif idx == 4:  # Traditional let
            fs.add(CacheTypeFilter(["Traditional Cache"]))
            fs.add(DifficultyFilter(max_difficulty=2.0))
            fs.add(TerrainFilter(max_terrain=2.0))
            fs.add(AvailableFilter())
        elif idx == 5:  # Arkiverede
            from opensak.filters.engine import ArchivedFilter
            fs.add(ArchivedFilter())

        # Search box
        search = self._search_box.text().strip()
        if search:
            from opensak.filters.engine import NameFilter, GcCodeFilter, FilterSet as FS
            search_or = FS(mode="OR")
            search_or.add(NameFilter(search))
            search_or.add(GcCodeFilter(search))
            fs.add(search_or)

        return fs

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_cache_selected(self, cache: Cache) -> None:
        self._detail_panel.show_cache(cache)
        self._map_widget.pan_to_cache(cache.gc_code)
        self._act_wp_edit.setEnabled(True)
        self._act_wp_delete.setEnabled(True)
        if cache.latitude and cache.longitude:
            self._statusbar.showMessage(
                f"{cache.gc_code} — {cache.name} "
                f"({cache.latitude:.5f}, {cache.longitude:.5f})"
            )

    def _on_map_cache_selected(self, gc_code: str) -> None:
        """Called when a pin is clicked on the map."""
        # Find cache in table and select it
        from opensak.db.database import get_session
        from opensak.db.models import Cache as CacheModel
        with get_session() as session:
            cache = session.query(CacheModel).filter_by(gc_code=gc_code).first()
            if cache:
                self._detail_panel.show_cache(cache)
                self._statusbar.showMessage(
                    f"{cache.gc_code} — {cache.name}"
                )

    def _on_search_changed(self, text: str) -> None:
        # Small delay so we don't query on every keypress
        QTimer.singleShot(300, self._refresh_cache_list)

    def _on_quick_filter_changed(self, index: int) -> None:
        self._refresh_cache_list()

    def _open_import_dialog(self) -> None:
        from opensak.gui.dialogs.import_dialog import ImportDialog
        dlg = ImportDialog(self)
        dlg.import_completed.connect(self._refresh_cache_list)
        dlg.exec()

    def _open_settings(self) -> None:
        from opensak.gui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._map_widget.update_home()   # update home marker
            self._refresh_cache_list()       # distances may have changed

    def _add_waypoint(self) -> None:
        from opensak.gui.dialogs.waypoint_dialog import WaypointDialog
        from opensak.db.database import get_session
        from opensak.db.models import Cache
        dlg = WaypointDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            with get_session() as session:
                # Tjek om GC koden allerede eksisterer
                existing = session.query(Cache).filter_by(
                    gc_code=data["gc_code"]
                ).first()
                if existing:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self, "Allerede eksisterer",
                        f"{data['gc_code']} findes allerede i databasen."
                    )
                    return
                cache = Cache(**data)
                session.add(cache)
            self._refresh_cache_list()
            self._statusbar.showMessage(
                f"Cache {data['gc_code']} tilføjet", 3000
            )

    def _edit_waypoint(self) -> None:
        cache = self._cache_table.selected_cache()
        if not cache:
            return
        from opensak.gui.dialogs.waypoint_dialog import WaypointDialog
        from opensak.db.database import get_session
        from opensak.db.models import Cache
        dlg = WaypointDialog(self, cache=cache)
        if dlg.exec():
            data = dlg.get_data()
            with get_session() as session:
                c = session.query(Cache).filter_by(
                    gc_code=data["gc_code"]
                ).first()
                if c:
                    for field, value in data.items():
                        if field != "gc_code":
                            setattr(c, field, value)
            self._refresh_cache_list()
            self._statusbar.showMessage(
                f"Cache {data['gc_code']} opdateret", 3000
            )

    def _delete_waypoint(self) -> None:
        cache = self._cache_table.selected_cache()
        if not cache:
            return
        from PySide6.QtWidgets import QMessageBox
        from opensak.db.database import get_session
        from opensak.db.models import Cache
        msg = f"Er du sikker på at du vil slette:\n{cache.gc_code} — {cache.name}?"
        reply = QMessageBox.question(
            self, "Slet cache", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            with get_session() as session:
                c = session.query(Cache).filter_by(
                    gc_code=cache.gc_code
                ).first()
                if c:
                    session.delete(c)
            self._detail_panel.clear()
            self._act_wp_edit.setEnabled(False)
            self._act_wp_delete.setEnabled(False)
            self._refresh_cache_list()
            self._statusbar.showMessage(
                f"Cache {cache.gc_code} slettet", 3000
            )

    def _open_filter_dialog(self) -> None:
        from opensak.gui.dialogs.filter_dialog import FilterDialog
        dlg = FilterDialog(self, self._current_filterset)
        dlg.filter_applied.connect(self._on_filter_applied)
        dlg.exec()

    def _on_filter_applied(self, filterset, sort) -> None:
        self._current_filterset = filterset
        self._act_clear_filter.setEnabled(True)
        self._filter_lbl.setText("🔍 Filter aktivt")
        self._quick_filter.setCurrentIndex(0)
        with get_session() as session:
            from opensak.filters.engine import apply_filters
            caches = apply_filters(session, filterset, sort)
        self._cache_table.load_caches(caches)
        self._map_widget.load_caches(caches)
        count = self._cache_table.row_count()
        self._count_lbl.setText(f"{count} cache{'r' if count != 1 else ''}")
        self._statusbar.showMessage(f"Filter: {count} caches", 3000)

    def _clear_filter(self) -> None:
        self._current_filterset = FilterSet()
        self._act_clear_filter.setEnabled(False)
        self._filter_lbl.setText("")
        self._refresh_cache_list()
        self._statusbar.showMessage("Filter nulstillet", 3000)

    def _open_column_chooser(self) -> None:
        from opensak.gui.dialogs.column_dialog import ColumnChooserDialog
        dlg = ColumnChooserDialog(self)
        if dlg.exec():
            self._cache_table.reload_columns()

    def _open_found_updater(self) -> None:
        from opensak.gui.dialogs.found_dialog import FoundUpdaterDialog
        dlg = FoundUpdaterDialog(self)
        dlg.update_completed.connect(self._refresh_cache_list)
        dlg.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "Om OpenSAK",
            "<h3>OpenSAK 0.1.0</h3>"
            "<p>Et open source geocaching-styringsværktøj "
            "til Linux og Windows.</p>"
            "<p>Bygget med Python og PySide6.</p>"
            "<p><a href='https://github.com/AgreeDK/opensak'>"
            "github.com/AgreeDK/opensak</a></p>"
        )
