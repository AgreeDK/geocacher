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
    QSizePolicy, QMessageBox, QWidgetAction
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
from opensak.lang import tr


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
        self._reload_home_combo()
        # Load caches after UI is ready
        QTimer.singleShot(100, self._refresh_cache_list)

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

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

        # Map widget
        from opensak.gui.map_widget import MapWidget
        self._map_widget = MapWidget()
        self._map_widget.cache_selected.connect(self._on_map_cache_selected)
        self._map_widget.setMinimumHeight(200)
        right_splitter.addWidget(self._map_widget)

        right_splitter.setSizes([400, 300])
        self._splitter.addWidget(right_splitter)
        self._splitter.setSizes([580, 520])

        main_layout.addWidget(self._splitter)

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        # ── Fil ───────────────────────────────────────────────────────────────
        file_menu = menubar.addMenu(tr("menu_file"))

        self._act_db_manager = QAction(tr("action_db_manager"), self)
        self._act_db_manager.setShortcut(QKeySequence("Ctrl+D"))
        self._act_db_manager.triggered.connect(self._open_db_manager)
        file_menu.addAction(self._act_db_manager)

        file_menu.addSeparator()

        self._act_import = QAction(tr("action_import"), self)
        self._act_import.setShortcut(QKeySequence("Ctrl+I"))
        self._act_import.triggered.connect(self._open_import_dialog)
        file_menu.addAction(self._act_import)

        file_menu.addSeparator()

        act_quit = QAction(tr("action_quit"), self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── Waypoint ──────────────────────────────────────────────────────────
        wp_menu = menubar.addMenu(tr("menu_waypoint"))

        act_wp_add = QAction(tr("action_wp_add"), self)
        act_wp_add.setShortcut(QKeySequence("Ctrl+N"))
        act_wp_add.triggered.connect(self._add_waypoint)
        wp_menu.addAction(act_wp_add)

        self._act_wp_edit = QAction(tr("action_wp_edit"), self)
        self._act_wp_edit.setShortcut(QKeySequence("Ctrl+E"))
        self._act_wp_edit.setEnabled(False)
        self._act_wp_edit.triggered.connect(self._edit_waypoint)
        wp_menu.addAction(self._act_wp_edit)

        self._act_wp_delete = QAction(tr("action_wp_delete"), self)
        self._act_wp_delete.setShortcut(QKeySequence("Delete"))
        self._act_wp_delete.setEnabled(False)
        self._act_wp_delete.triggered.connect(self._delete_waypoint)
        wp_menu.addAction(self._act_wp_delete)

        # ── Vis ───────────────────────────────────────────────────────────────
        view_menu = menubar.addMenu(tr("menu_view"))

        act_refresh = QAction(tr("action_refresh"), self)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self._refresh_cache_list)
        view_menu.addAction(act_refresh)

        view_menu.addSeparator()

        act_filter = QAction(tr("action_filter"), self)
        act_filter.setShortcut("Ctrl+F")
        act_filter.triggered.connect(self._open_filter_dialog)
        view_menu.addAction(act_filter)

        act_clear = QAction(tr("action_clear_filter"), self)
        act_clear.triggered.connect(self._clear_filter)
        view_menu.addAction(act_clear)

        view_menu.addSeparator()

        act_columns = QAction(tr("action_columns"), self)
        act_columns.triggered.connect(self._open_column_chooser)
        view_menu.addAction(act_columns)

        # ── Funktioner ────────────────────────────────────────────────────────
        tools_menu = menubar.addMenu(tr("menu_tools"))

        act_settings = QAction(tr("action_settings"), self)
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self._open_settings)
        tools_menu.addAction(act_settings)

        tools_menu.addSeparator()

        act_found_update = QAction(tr("action_found_update"), self)
        act_found_update.triggered.connect(self._open_found_updater)
        tools_menu.addAction(act_found_update)

        # ── GPS ───────────────────────────────────────────────────────────────
        gps_menu = menubar.addMenu("&GPS")

        self._act_gps_export = QAction(tr("action_gps_export"), self)
        self._act_gps_export.setShortcut(QKeySequence("Ctrl+G"))
        self._act_gps_export.triggered.connect(self._open_gps_export)
        gps_menu.addAction(self._act_gps_export)

        self._act_trip_planner = QAction(tr("action_trip_planner"), self)
        self._act_trip_planner.setShortcut(QKeySequence("Ctrl+T"))
        self._act_trip_planner.triggered.connect(self._open_trip_planner)
        gps_menu.addAction(self._act_trip_planner)

        # ── Geocaching Værktøjer ──────────────────────────────────────────────
        gc_tools_menu = menubar.addMenu(tr("menu_gc_tools"))

        act_coord_converter = QAction(tr("action_coord_converter"), self)
        act_coord_converter.setShortcut(QKeySequence("Ctrl+K"))
        act_coord_converter.triggered.connect(self._open_coord_converter)
        gc_tools_menu.addAction(act_coord_converter)

        act_projection = QAction(tr("action_projection"), self)
        act_projection.setShortcut(QKeySequence("Ctrl+P"))
        act_projection.triggered.connect(self._open_projection)
        gc_tools_menu.addAction(act_projection)

        gc_tools_menu.addSeparator()

        act_checksum = QAction(tr("action_checksum"), self)
        act_checksum.triggered.connect(self._open_checksum)
        gc_tools_menu.addAction(act_checksum)

        act_midpoint = QAction(tr("action_midpoint"), self)
        act_midpoint.triggered.connect(self._open_midpoint)
        gc_tools_menu.addAction(act_midpoint)

        act_dist_bearing = QAction(tr("action_dist_bearing"), self)
        act_dist_bearing.triggered.connect(self._open_dist_bearing)
        gc_tools_menu.addAction(act_dist_bearing)

        # ── Hjælp ─────────────────────────────────────────────────────────────
        help_menu = menubar.addMenu(tr("menu_help"))

        act_about = QAction(tr("action_about"), self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        # ── Søgefelt og Vis-dropdown i menulinjen ─────────────────────────────
        menubar.addSeparator()

        # Søgefelt
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText(tr("search_placeholder"))
        self._search_box.setFixedWidth(180)
        self._search_box.textChanged.connect(self._on_search_changed)
        search_action = QWidgetAction(self)
        search_action.setDefaultWidget(self._search_box)
        menubar.addAction(search_action)

        # Vis-dropdown
        self._quick_filter = QComboBox()
        self._quick_filter.setFixedWidth(140)
        self._quick_filter.addItems([
            tr("quick_all"),
            tr("quick_not_found"),
            tr("quick_found"),
            tr("quick_available"),
            tr("quick_traditional_easy"),
            tr("quick_archived"),
        ])
        self._quick_filter.currentIndexChanged.connect(self._on_quick_filter_changed)
        filter_action = QWidgetAction(self)
        filter_action.setDefaultWidget(self._quick_filter)
        menubar.addAction(filter_action)

        # Aktivt filter label
        self._filter_lbl = QLabel("")
        self._filter_lbl.setStyleSheet("color: #e65100; font-style: italic; padding: 0 4px;")
        filter_lbl_action = QWidgetAction(self)
        filter_lbl_action.setDefaultWidget(self._filter_lbl)
        menubar.addAction(filter_lbl_action)

        # Cache-tæller (højrejusteret via spacer)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer_action = QWidgetAction(self)
        spacer_action.setDefaultWidget(spacer)
        menubar.addAction(spacer_action)

        self._count_lbl = QLabel(tr("count_caches", count=0))
        self._count_lbl.setStyleSheet("color: gray; padding: 0 8px;")
        count_action = QWidgetAction(self)
        count_action.setDefaultWidget(self._count_lbl)
        menubar.addAction(count_action)

    def _setup_toolbar(self) -> None:
        tb = QToolBar("Værktøjslinje")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        # Databaser
        self._act_db_manager.setText(tr("action_db_manager"))
        self._act_db_manager.setToolTip(tr("action_db_manager") + " (Ctrl+D)")
        tb.addAction(self._act_db_manager)

        # Importer
        self._act_import.setText(tr("action_import"))
        self._act_import.setToolTip(tr("action_import") + " (Ctrl+I)")
        tb.addAction(self._act_import)

        tb.addSeparator()

        # Opdater
        refresh_act = QAction(f"⟳  {tr('toolbar_refresh')}", self)
        refresh_act.setToolTip(tr("toolbar_refresh") + " (F5)")
        refresh_act.triggered.connect(self._refresh_cache_list)
        tb.addAction(refresh_act)

        tb.addSeparator()

        # GPS
        gps_act = QAction(f"📤  {tr('toolbar_gps')}", self)
        gps_act.setToolTip(tr("toolbar_gps") + " (Ctrl+G)")
        gps_act.triggered.connect(self._open_gps_export)
        tb.addAction(gps_act)

        tb.addSeparator()

        # Turplanlægger
        trip_act = QAction(f"🗺️  {tr('toolbar_trip')}", self)
        trip_act.setToolTip(tr("toolbar_trip_tooltip") + " (Ctrl+T)")
        trip_act.triggered.connect(self._open_trip_planner)
        tb.addAction(trip_act)

        tb.addSeparator()

        # Filter
        self._act_filter = QAction(f"🔍  {tr('toolbar_filter')}", self)
        self._act_filter.setShortcut("Ctrl+F")
        self._act_filter.setToolTip(tr("toolbar_filter") + " (Ctrl+F)")
        self._act_filter.triggered.connect(self._open_filter_dialog)
        tb.addAction(self._act_filter)

        # Nulstil filter — kun ikon, ingen tekst
        self._act_clear_filter = QAction("✕", self)
        self._act_clear_filter.setToolTip(tr("toolbar_clear_filter"))
        self._act_clear_filter.setEnabled(False)
        self._act_clear_filter.triggered.connect(self._clear_filter)
        tb.addAction(self._act_clear_filter)

        tb.addSeparator()

        # Hjem-dropdown
        from PySide6.QtWidgets import QComboBox, QWidgetAction
        self._home_combo = QComboBox()
        self._home_combo.setMinimumWidth(130)
        self._home_combo.setMaximumWidth(180)
        self._home_combo.setToolTip(tr("toolbar_home_combo_tooltip"))
        self._home_combo.currentIndexChanged.connect(self._on_home_changed)
        home_combo_action = QWidgetAction(self)
        home_combo_action.setDefaultWidget(self._home_combo)
        tb.addAction(home_combo_action)

        home_act = QAction("⌂", self)
        home_act.setToolTip(tr("toolbar_home_tooltip"))
        home_act.triggered.connect(lambda: self._map_widget.pan_to_home())
        tb.addAction(home_act)

        tb.addSeparator()

        # Indstillinger — kun ikon
        settings_act = QAction("⚙", self)
        settings_act.setToolTip(tr("action_settings").replace("&", "").replace("…", ""))
        settings_act.triggered.connect(self._open_settings)
        tb.addAction(settings_act)

    def _setup_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage(tr("status_ready"))

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
        if manager.active:
            self.setWindowTitle(tr("window_title_with_db", db_name=manager.active.name))
        else:
            self.setWindowTitle(tr("window_title"))

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
            tr("status_db_name", db_name=db_info.name), 4000
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
        fs = self._build_current_filterset()
        with get_session() as session:
            caches = apply_filters(session, fs, SortSpec("name"))

        self._cache_table.load_caches(caches)
        self._map_widget.load_caches(caches)
        count = self._cache_table.row_count()
        if count == 1:
            self._count_lbl.setText(tr("count_cache_single"))
        else:
            self._count_lbl.setText(tr("count_caches", count=count))

    def _build_current_filterset(self) -> FilterSet:
        """Build a FilterSet from the current quick filter + search box."""
        fs = FilterSet(mode="AND")
        idx = self._quick_filter.currentIndex()

        if idx == 1:   # Ikke fundne / Not found
            fs.add(NotFoundFilter())
        elif idx == 2:  # Fundne / Found
            from opensak.filters.engine import FoundFilter
            fs.add(FoundFilter())
        elif idx == 3:  # Tilgængelige ikke fundne / Available not found
            fs.add(AvailableFilter())
            fs.add(NotFoundFilter())
        elif idx == 4:  # Traditional let / Traditional easy
            fs.add(CacheTypeFilter(["Traditional Cache"]))
            fs.add(DifficultyFilter(max_difficulty=2.0))
            fs.add(TerrainFilter(max_terrain=2.0))
            fs.add(AvailableFilter())
        elif idx == 5:  # Arkiverede / Archived
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
        QTimer.singleShot(300, self._refresh_cache_list)

    def _on_quick_filter_changed(self, index: int) -> None:
        self._refresh_cache_list()

    def _open_import_dialog(self) -> None:
        from opensak.gui.dialogs.import_dialog import ImportDialog
        dlg = ImportDialog(self)
        # Efter import: reload kun tabellen — ikke kortet (for mange pins ved store DB'er)
        dlg.import_completed.connect(self._refresh_table_only)
        dlg.exec()

    def _refresh_table_only(self) -> None:
        """Reload cache-tabellen uden at opdatere kortet. Bruges efter import."""
        fs = self._build_current_filterset()
        with get_session() as session:
            caches = apply_filters(session, fs, SortSpec("name"))
        self._cache_table.load_caches(caches)
        count = self._cache_table.row_count()
        if count == 1:
            self._count_lbl.setText(tr("count_cache_single"))
        else:
            self._count_lbl.setText(tr("count_caches", count=count))
        self._statusbar.showMessage(
            tr("import_table_loaded", count=count), 5000
        )

    def _open_settings(self) -> None:
        from opensak.gui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._reload_home_combo()
            self._map_widget.update_home()
            self._refresh_cache_list()

    def _reload_home_combo(self) -> None:
        """Genindlæs hjemmepunkts-dropdown fra settings."""
        s = get_settings()
        points = s.home_points
        active = s.active_home_name
        self._home_combo.blockSignals(True)
        self._home_combo.clear()
        if not points:
            self._home_combo.addItem(tr("toolbar_home_no_points"), None)
        else:
            for p in points:
                label = f"★ {p.name}" if p.name == active else p.name
                self._home_combo.addItem(label, p.name)
            # Sæt aktiv
            for i in range(self._home_combo.count()):
                if self._home_combo.itemData(i) == active:
                    self._home_combo.setCurrentIndex(i)
                    break
        self._home_combo.blockSignals(False)

    def _on_home_changed(self, index: int) -> None:
        """Skift aktivt hjemmepunkt fra dropdown."""
        name = self._home_combo.itemData(index)
        if not name:
            return
        s = get_settings()
        for p in s.home_points:
            if p.name == name:
                s.set_active_home(p)
                self._map_widget.update_home()
                self._statusbar.showMessage(
                    tr("status_home_changed", name=p.name), 3000
                )
                break

    def _add_waypoint(self) -> None:
        from opensak.gui.dialogs.waypoint_dialog import WaypointDialog
        from opensak.db.database import get_session
        from opensak.db.models import Cache
        dlg = WaypointDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            with get_session() as session:
                existing = session.query(Cache).filter_by(
                    gc_code=data["gc_code"]
                ).first()
                if existing:
                    QMessageBox.warning(
                        self,
                        tr("wp_already_exists_title"),
                        tr("wp_already_exists_msg", gc_code=data["gc_code"])
                    )
                    return
                cache = Cache(**data)
                session.add(cache)
            self._refresh_cache_list()
            self._statusbar.showMessage(
                tr("status_cache_added", gc_code=data["gc_code"]), 3000
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
                tr("status_cache_updated", gc_code=data["gc_code"]), 3000
            )

    def _delete_waypoint(self) -> None:
        cache = self._cache_table.selected_cache()
        if not cache:
            return
        from opensak.db.database import get_session
        from opensak.db.models import Cache
        reply = QMessageBox.question(
            self,
            tr("wp_delete_title"),
            tr("wp_delete_msg", gc_code=cache.gc_code, name=cache.name),
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
                tr("status_cache_deleted", gc_code=cache.gc_code), 3000
            )

    def _open_filter_dialog(self) -> None:
        from opensak.gui.dialogs.filter_dialog import FilterDialog
        dlg = FilterDialog(self, self._current_filterset)
        dlg.filter_applied.connect(self._on_filter_applied)
        dlg.exec()

    def _on_filter_applied(self, filterset, sort) -> None:
        self._current_filterset = filterset
        self._act_clear_filter.setEnabled(True)
        self._filter_lbl.setText(tr("filter_active_label"))
        self._quick_filter.setCurrentIndex(0)
        with get_session() as session:
            from opensak.filters.engine import apply_filters
            caches = apply_filters(session, filterset, sort)
        self._cache_table.load_caches(caches)
        self._map_widget.load_caches(caches)
        count = self._cache_table.row_count()
        if count == 1:
            self._count_lbl.setText(tr("count_cache_single"))
        else:
            self._count_lbl.setText(tr("count_caches", count=count))
        self._statusbar.showMessage(tr("status_filter_result", count=count), 3000)

    def _clear_filter(self) -> None:
        self._current_filterset = FilterSet()
        self._act_clear_filter.setEnabled(False)
        self._filter_lbl.setText("")
        self._refresh_cache_list()
        self._statusbar.showMessage(tr("status_filter_reset"), 3000)

    def _open_column_chooser(self) -> None:
        from opensak.gui.dialogs.column_dialog import ColumnChooserDialog
        dlg = ColumnChooserDialog(self)
        if dlg.exec():
            self._cache_table.reload_columns()

    def _open_gps_export(self) -> None:
        from opensak.gui.dialogs.gps_dialog import GpsExportDialog
        caches = [
            self._cache_table._model.cache_at(i)
            for i in range(self._cache_table.row_count())
        ]
        caches = [c for c in caches if c is not None]
        dlg = GpsExportDialog(self, caches=caches)
        dlg.exec()

    def _open_trip_planner(self) -> None:
        from opensak.gui.dialogs.trip_dialog import TripPlannerDialog
        caches = [
            self._cache_table._model.cache_at(i)
            for i in range(self._cache_table.row_count())
        ]
        caches = [c for c in caches if c is not None]
        # show() i stedet for exec() — ikke-modal så kortvinduet kan få fokus
        self._trip_planner_win = TripPlannerDialog(self, caches=caches)
        self._trip_planner_win.show()
        self._trip_planner_win.raise_()
        self._trip_planner_win.activateWindow()

    def _open_found_updater(self) -> None:
        from opensak.gui.dialogs.found_dialog import FoundUpdaterDialog
        dlg = FoundUpdaterDialog(self)
        dlg.update_completed.connect(self._refresh_cache_list)
        dlg.exec()

    def _open_coord_converter(self) -> None:
        """Åbn koordinatkonverter — præ-udfyld med valgt cache hvis mulig."""
        from opensak.gui.dialogs.coord_converter_dialog import CoordConverterDialog
        cache = self._cache_table.selected_cache()
        if cache and cache.latitude and cache.longitude:
            dlg = CoordConverterDialog(cache.latitude, cache.longitude, parent=self)
        else:
            dlg = CoordConverterDialog(parent=self)
        dlg.exec()

    def _open_projection(self) -> None:
        """Åbn koordinatprojektions-dialog — præ-udfyld med valgt cache hvis mulig."""
        from opensak.gui.dialogs.projection_dialog import ProjectionDialog
        cache = self._cache_table.selected_cache()
        if cache and cache.latitude and cache.longitude:
            dlg = ProjectionDialog(cache.latitude, cache.longitude, parent=self)
        else:
            dlg = ProjectionDialog(parent=self)
        dlg.exec()

    def _open_checksum(self) -> None:
        """Åbn tjeksum-beregner — præ-udfyld med valgt cache hvis mulig."""
        from opensak.gui.dialogs.checksum_dialog import ChecksumDialog
        cache = self._cache_table.selected_cache()
        if cache and cache.latitude and cache.longitude:
            dlg = ChecksumDialog(cache.latitude, cache.longitude, parent=self)
        else:
            dlg = ChecksumDialog(parent=self)
        dlg.exec()

    def _open_midpoint(self) -> None:
        """Åbn midtpunkt-beregner — præ-udfyld punkt A med valgt cache hvis mulig."""
        from opensak.gui.dialogs.midpoint_dialog import MidpointDialog
        cache = self._cache_table.selected_cache()
        if cache and cache.latitude and cache.longitude:
            dlg = MidpointDialog(cache.latitude, cache.longitude, parent=self)
        else:
            dlg = MidpointDialog(parent=self)
        dlg.exec()

    def _open_dist_bearing(self) -> None:
        """Åbn afstand & retning — præ-udfyld punkt A med valgt cache hvis mulig."""
        from opensak.gui.dialogs.distance_bearing_dialog import DistanceBearingDialog
        cache = self._cache_table.selected_cache()
        if cache and cache.latitude and cache.longitude:
            dlg = DistanceBearingDialog(cache.latitude, cache.longitude, parent=self)
        else:
            dlg = DistanceBearingDialog(parent=self)
        dlg.exec()

    def _show_about(self) -> None:
        from opensak import __version__
        QMessageBox.about(
            self,
            tr("about_title"),
            tr("about_text", version=__version__),
        )
