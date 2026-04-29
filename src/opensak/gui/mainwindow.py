"""
src/opensak/gui/mainwindow.py — Main application window.
"""

from __future__ import annotations
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QStatusBar,
    QToolBar, QPushButton, QComboBox,
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
from opensak.coords import format_coords
from opensak.gui.settings import get_settings
from opensak.lang import tr
from opensak.utils.types import GcCode
from opensak.updater import UpdateCheckWorker, RELEASES_PAGE


class InfoBar(QFrame):
    """GSAK-style info bar between cache list and detail/map panel (issue #116).

    Shows (left to right):
      Filter name | Total caches in DB | Flagged count | Center point
      ... spacer ...
      Count label:  Found (yellow)  All-in-filter (white)  Inactive (red)  Owned (green)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setFixedHeight(24)
        self.setStyleSheet(
            "InfoBar {"
            "  background-color: palette(window);"
            "  border: 1px solid palette(mid);"
            "  padding: 0 2px;"
            "}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(0)

        small = "font-size: 11px;"

        # ── Left side ─────────────────────────────────────────────────────────
        self._filter_lbl = QLabel("")
        self._filter_lbl.setStyleSheet(f"{small} color: palette(text);")
        row.addWidget(self._filter_lbl)

        row.addWidget(self._sep())

        self._total_lbl = QLabel("")
        self._total_lbl.setStyleSheet(small)
        row.addWidget(self._total_lbl)

        row.addWidget(self._sep())

        self._flag_lbl = QLabel("")
        self._flag_lbl.setStyleSheet(small)
        row.addWidget(self._flag_lbl)

        row.addWidget(self._sep())

        self._center_lbl = QLabel("")
        self._center_lbl.setStyleSheet(f"{small} color: palette(text);")
        row.addWidget(self._center_lbl)

        # ── Spacer ────────────────────────────────────────────────────────────
        row.addStretch()

        # ── Right side: color-coded counts ────────────────────────────────────
        count_style = f"{small} font-weight: bold; padding: 0 3px;"

        lbl_prefix = QLabel(tr("infobar_count_label"))
        lbl_prefix.setStyleSheet(f"{small} padding: 0 4px;")
        row.addWidget(lbl_prefix)

        self._found_lbl = QLabel("0")
        self._found_lbl.setStyleSheet(f"{count_style} color: #b8860b;")
        self._found_lbl.setToolTip(tr("infobar_found_tooltip"))
        row.addWidget(self._found_lbl)

        self._all_lbl = QLabel("0")
        self._all_lbl.setStyleSheet(f"{count_style} color: palette(text);")
        self._all_lbl.setToolTip(tr("infobar_all_tooltip"))
        row.addWidget(self._all_lbl)

        self._inactive_lbl = QLabel("0")
        self._inactive_lbl.setStyleSheet(f"{count_style} color: #c62828;")
        self._inactive_lbl.setToolTip(tr("infobar_inactive_tooltip"))
        row.addWidget(self._inactive_lbl)

        self._owned_lbl = QLabel("0")
        self._owned_lbl.setStyleSheet(f"{count_style} color: #2e7d32;")
        self._owned_lbl.setToolTip(tr("infobar_owned_tooltip"))
        row.addWidget(self._owned_lbl)

    @staticmethod
    def _sep() -> QFrame:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setFrameShadow(QFrame.Shadow.Sunken)
        s.setFixedWidth(16)
        return s

    def update_counts(
        self,
        filter_name: str,
        total_in_db: int,
        flagged: int,
        center_name: str,
        found: int,
        all_in_filter: int,
        inactive: int,
        owned: int,
    ) -> None:
        self._filter_lbl.setText(
            f"{tr('infobar_filter')}: {filter_name}" if filter_name
            else f"{tr('infobar_filter')}: {tr('infobar_filter_none')}"
        )
        self._total_lbl.setText(f"{total_in_db} {tr('infobar_total')}")
        self._flag_lbl.setText(f"🚩 = {flagged}")
        self._center_lbl.setText(
            f"{tr('infobar_center')}: {center_name}" if center_name
            else f"{tr('infobar_center')}: —"
        )
        self._found_lbl.setText(str(found))
        self._all_lbl.setText(str(all_in_filter))
        self._inactive_lbl.setText(str(inactive))
        self._owned_lbl.setText(str(owned))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 500)
        self._current_filterset = FilterSet()
        self._current_sort = SortSpec("name", ascending=True)
        self._active_filter_name = ""
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_search_bar()
        self._setup_statusbar()
        self._restore_state()
        self._update_title()
        self._reload_home_combo()
        # Load caches after UI is ready
        QTimer.singleShot(100, self._refresh_cache_list)
        # Tjek for opdateringer i baggrunden (5 sek forsinkelse — GUI er klar)
        QTimer.singleShot(5000, self._check_update_background)

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # ── Main splitter: cache list (top) | info bar + bottom panel (below) ─
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setObjectName("main_splitter")

        # Top: cache list — fuld bredde
        self._cache_table = CacheTableView()
        self._cache_table.cache_selected.connect(self._on_cache_selected)
        self._cache_table.flags_changed.connect(self._on_flags_changed)
        self._cache_table.sort_changed.connect(self._on_sort_changed)
        self._splitter.addWidget(self._cache_table)

        # Bottom container: info bar (fixed) + horisontal splitter (resizable)
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        # Info bar (GSAK-style, issue #116)
        self._info_bar = InfoBar()
        bottom_layout.addWidget(self._info_bar)

        # Horisontal splitter — detaljer til venstre, kort til højre
        self._bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._bottom_splitter.setObjectName("bottom_splitter")

        self._detail_panel = CacheDetailPanel()
        self._detail_panel.corrected_coords_changed.connect(self._on_corrected_coords_changed)
        self._bottom_splitter.addWidget(self._detail_panel)

        # Map widget
        from opensak.gui.map_widget import MapWidget
        self._map_widget = MapWidget()
        self._map_widget.cache_selected.connect(self._on_map_cache_selected)
        self._map_widget.setMinimumWidth(300)
        self._bottom_splitter.addWidget(self._map_widget)

        self._bottom_splitter.setSizes([560, 540])
        bottom_layout.addWidget(self._bottom_splitter)

        self._splitter.addWidget(bottom_container)
        self._splitter.setSizes([380, 400])

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

        wp_menu.addSeparator()

        act_delete_flagged = QAction(tr("action_delete_flagged"), self)
        act_delete_flagged.triggered.connect(self._delete_flagged_caches)
        wp_menu.addAction(act_delete_flagged)

        act_delete_filtered = QAction(tr("action_delete_filtered"), self)
        act_delete_filtered.triggered.connect(self._delete_filtered_caches)
        wp_menu.addAction(act_delete_filtered)

        wp_menu.addSeparator()

        act_clear_flags = QAction(tr("action_clear_flags"), self)
        act_clear_flags.triggered.connect(self._clear_all_flags)
        wp_menu.addAction(act_clear_flags)

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

        act_check_update = QAction(tr("action_check_update"), self)
        act_check_update.triggered.connect(self._check_update_manual)
        help_menu.addAction(act_check_update)

        # ── Vis-dropdown i menulinjen ─────────────────────────────────────────
        menubar.addSeparator()

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

    def _setup_search_bar(self) -> None:
        """Søgelinje på linje 3 under primær toolbar — højrejusteret via HBoxLayout.

        Søgelinjen tvinges altid synlig fordi:
        - Den indeholder essentielle søgefelter (GC code, Name)
        - Qt gemmer toolbar-synlighed i QSettings, så et utilsigtet højreklik-
          uncheck ville skjule den permanent for brugeren
        - Den er planlagt til at indeholde flere felter (status, hurtig-nav)
        """
        from PySide6.QtWidgets import (
            QToolBar, QLabel, QLineEdit, QWidgetAction, QWidget, QSizePolicy, QHBoxLayout
        )
        sb = QToolBar(tr("search"))
        sb.setObjectName("search_toolbar")
        sb.setMovable(False)
        # Issue #86 follow-up: forhindre at brugeren skjuler søgelinjen via
        # højreklik-menu på toolbar-området. toggleViewAction() er den action
        # Qt bruger i toolbar-kontekstmenuen — ved at deaktivere den fjerner
        # vi muligheden for at skjule søgelinjen utilsigtet.
        sb.toggleViewAction().setEnabled(False)
        sb.toggleViewAction().setVisible(False)
        self.addToolBarBreak()
        self.addToolBar(sb)
        # Tving synlig — overskriver evt. gemt QSettings-state hvor en bruger
        # tidligere har skjult toolbar'en
        sb.setVisible(True)

        # Container-widget med HBoxLayout — spacer skubber felterne til højre
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 8, 0)
        row.setSpacing(4)

        # GC-nummer label + felt
        gc_lbl = QLabel(tr("search_gc_label") + ":")
        gc_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        row.addWidget(gc_lbl)

        self._search_gc = QLineEdit()
        self._search_gc.setPlaceholderText("GC12345")
        self._search_gc.setFixedWidth(110)
        self._search_gc.setClearButtonEnabled(True)
        self._search_gc.textChanged.connect(self._on_search_changed)
        row.addWidget(self._search_gc)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        row.addWidget(sep)

        # Navn label + felt
        name_lbl = QLabel(tr("col_name") + ":")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        row.addWidget(name_lbl)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText(tr("search_placeholder"))
        self._search_box.setFixedWidth(220)
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._on_search_changed)
        row.addWidget(self._search_box)

        # Spacer — skubber felterne til venstre (issue #125)
        row.addStretch()

        container_action = QWidgetAction(self)
        container_action.setDefaultWidget(container)
        sb.addAction(container_action)

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
        self._load_sort_for_active_db()

        # Gendan splitter-størrelser som procentandele af vinduets størrelse.
        # Vi gemmer ratios (0.0–1.0) i stedet for absolutte pixels, så
        # layoutet ser fornuftigt ud uanset skærmopløsning (issue #62).
        QTimer.singleShot(0, self._restore_splitter_ratios)

    def _update_title(self) -> None:
        """Opdatér vinduestitel med aktiv database navn og versionsnummer."""
        from opensak import __version__
        from opensak.db.manager import get_db_manager
        manager = get_db_manager()
        if manager.active:
            self.setWindowTitle(
                tr("window_title_with_db", db_name=manager.active.name) + f"  v{__version__}"
            )
        else:
            self.setWindowTitle(tr("window_title") + f"  v{__version__}")

    def _open_db_manager(self) -> None:
        from opensak.gui.dialogs.database_dialog import DatabaseManagerDialog
        dlg = DatabaseManagerDialog(self)
        dlg.database_switched.connect(self._on_database_switched)
        dlg.exec()

    def _on_database_switched(self, db_info) -> None:
        """Kaldes når brugeren skifter aktiv database."""
        self._update_title()
        self._detail_panel.clear()
        self._load_sort_for_active_db()
        self._refresh_cache_list()
        self._statusbar.showMessage(
            tr("status_db_name", db_name=db_info.name), 4000
        )

    def _restore_splitter_ratios(self) -> None:
        """Gendan splitter-størrelser fra gemte procentandele (issue #62).

        Ratios gemmes som floats (0.0–1.0) så layoutet skalerer korrekt
        på tværs af skærmopløsninger og platforme.
        """
        s = get_settings()
        total_v = self._splitter.height()
        ratio_v = getattr(s, "splitter_ratio_top", 0.49)
        if total_v > 10:
            top = int(total_v * ratio_v)
            self._splitter.setSizes([top, total_v - top])
        else:
            self._splitter.setSizes([380, 400])

        total_h = self._bottom_splitter.width()
        ratio_h = getattr(s, "bottom_splitter_ratio_left", 0.51)
        if total_h > 10:
            left = int(total_h * ratio_h)
            self._bottom_splitter.setSizes([left, total_h - left])
        else:
            self._bottom_splitter.setSizes([560, 540])

    def _save_splitter_ratios(self) -> None:
        """Gem splitter-størrelser som procentandele (issue #62)."""
        s = get_settings()
        sizes_v = self._splitter.sizes()
        total_v = sum(sizes_v)
        if total_v > 0:
            s.splitter_ratio_top = sizes_v[0] / total_v

        sizes_h = self._bottom_splitter.sizes()
        total_h = sum(sizes_h)
        if total_h > 0:
            s.bottom_splitter_ratio_left = sizes_h[0] / total_h

    def closeEvent(self, event) -> None:
        s = get_settings()
        s.window_geometry = self.saveGeometry()
        s.window_state    = self.saveState()
        self._save_splitter_ratios()
        s.sync()
        super().closeEvent(event)

    # ── Cache list ────────────────────────────────────────────────────────────

    def _refresh_cache_list(self) -> None:
        """Reload caches from DB applying current filters.

        Combines the advanced filter (self._current_filterset, set via the
        filter dialog) with the quick-filter / search-box filters so that
        returning from Settings or any other dialog never discards the active
        filter (fixes #128).
        """
        quick_fs = self._build_current_filterset()

        # Wrap both filtersets in a top-level AND so they work together.
        # If _current_filterset is empty it has no effect (FilterSet.matches()
        # returns True for an empty set), so this is safe in all cases.
        if len(self._current_filterset) > 0 or len(quick_fs) > 0:
            from opensak.filters.engine import FilterSet as _FS
            combined = _FS(mode="AND")
            if len(self._current_filterset) > 0:
                combined.add(self._current_filterset)
            if len(quick_fs) > 0:
                combined.add(quick_fs)
            fs = combined
        else:
            fs = quick_fs

        with get_session() as session:
            caches = apply_filters(session, fs, self._current_sort)

        self._cache_table.load_caches(caches)
        self._map_widget.load_caches(caches)
        count = self._cache_table.row_count()
        if count == 1:
            self._count_lbl.setText(tr("count_cache_single"))
        else:
            self._count_lbl.setText(tr("count_caches", count=count))
        self._update_info_bar()

    def _update_info_bar(self) -> None:
        """Recalculate and update the GSAK-style info bar (issue #116)."""
        s = get_settings()
        caches = self._cache_table.get_all_caches()

        # Total caches in database (not just filtered)
        with get_session() as session:
            total_in_db = session.query(Cache).count()

        # Filter name
        filter_name = self._active_filter_name

        # Flagged count
        flagged = sum(1 for c in caches if c.user_flag)

        # Center point name
        center_name = s.active_home_name or ""

        # Color-coded counts (from filtered caches)
        found = sum(1 for c in caches if c.found)
        all_in_filter = len(caches)
        inactive = sum(1 for c in caches if c.archived or not c.available)

        # Owned: match placed_by against stored GC username
        gc_user = s.gc_username.strip().lower() if s.gc_username else ""
        if gc_user:
            owned = sum(
                1 for c in caches
                if c.placed_by and c.placed_by.strip().lower() == gc_user
            )
        else:
            owned = 0

        self._info_bar.update_counts(
            filter_name=filter_name,
            total_in_db=total_in_db,
            flagged=flagged,
            center_name=center_name,
            found=found,
            all_in_filter=all_in_filter,
            inactive=inactive,
            owned=owned,
        )

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

        # GC-nummer søgefelt (søger kun i GC kode)
        gc_search = self._search_gc.text().strip()
        if gc_search:
            from opensak.filters.engine import GcCodeFilter
            fs.add(GcCodeFilter(gc_search))

        # Navn-søgefelt — matcher kun på navn (GSAK-style, issue #86)
        # Issue #80 introduced a combined Name+GC code search here, but
        # users prefer the GSAK convention of separate search fields with
        # clear, single purposes. GC code search lives in its own field.
        name_search = self._search_box.text().strip()
        if name_search:
            from opensak.filters.engine import NameFilter
            fs.add(NameFilter(name_search))

        return fs

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_full_cache(self, gc_code: GcCode):
        """
        Indlæs en enkelt cache fra DB med alle relationer eager-loaded.

        apply_filters() bruger noload() på logs/waypoints/user_note for
        performance ved store databaser. Denne hjælper bruges når brugeren
        vælger en cache, så detaljepanelet altid får komplette data.
        """
        from opensak.db.models import Cache as CacheModel
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            return session.query(CacheModel).options(
                joinedload(CacheModel.logs),
                joinedload(CacheModel.attributes),
                joinedload(CacheModel.waypoints),
                joinedload(CacheModel.user_note),
            ).filter_by(gc_code=gc_code).first()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_cache_selected(self, cache: Cache) -> None:
        """Kaldes når brugeren klikker på en cache i tabellen."""
        # Genindlæs cachen med alle relationer (logs, waypoints osv.)
        # da apply_filters() bruger noload() på disse for performance.
        full = self._load_full_cache(cache.gc_code)
        if not full:
            return
        self._detail_panel.show_cache(full)
        self._map_widget.pan_to_cache(full.gc_code)
        self._act_wp_edit.setEnabled(True)
        self._act_wp_delete.setEnabled(True)
        if full.latitude and full.longitude:
            coords = format_coords(full.latitude, full.longitude, get_settings().coord_format)
            self._statusbar.showMessage(
                f"{full.gc_code} — {full.name} ({coords})"
            )

    def _on_map_cache_selected(self, gc_code: GcCode) -> None:
        """Kaldes når brugeren klikker på en pin på kortet."""
        full = self._load_full_cache(gc_code)
        if full:
            self._cache_table.select_by_gc_code(gc_code)
            self._detail_panel.show_cache(full)
            self._statusbar.showMessage(
                f"{full.gc_code} — {full.name}"
            )

    def _on_corrected_coords_changed(self, gc_code: GcCode) -> None:
        """Update the map pin for a single cache after corrected coordinates change."""
        full = self._load_full_cache(gc_code)
        if full:
            self._map_widget.update_cache(full)

    def _on_search_changed(self, text: str) -> None:
        QTimer.singleShot(300, self._refresh_cache_list)

    def _on_quick_filter_changed(self, index: int) -> None:
        self._refresh_cache_list()

    def _open_import_dialog(self) -> None:
        from opensak.gui.dialogs.import_dialog import ImportDialog
        dlg = ImportDialog(self)
        dlg.import_completed.connect(self._refresh_after_import)
        dlg.exec()

    def _refresh_after_import(self) -> None:
        """Reload both cache table and map after a successful import."""
        self._refresh_cache_list()
        count = self._cache_table.row_count()
        self._statusbar.showMessage(
            tr("import_table_loaded", count=count), 5000
        )

    def _refresh_table_only(self) -> None:
        """Reload cache-tabellen uden at opdatere kortet. Bruges efter import."""
        fs = self._build_current_filterset()
        with get_session() as session:
            caches = apply_filters(session, fs, self._current_sort)
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

    def _delete_flagged_caches(self) -> None:
        """Slet alle caches med Flag=True i det aktive filter."""
        caches = self._cache_table.get_flagged_caches()
        if not caches:
            QMessageBox.information(
                self,
                tr("delete_flagged_title"),
                tr("delete_flagged_none"),
            )
            return
        reply = QMessageBox.question(
            self,
            tr("delete_flagged_title"),
            tr("delete_flagged_msg", count=len(caches)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            gc_codes = [c.gc_code for c in caches]
            self._bulk_delete_caches(gc_codes)
            self._detail_panel.clear()
            self._act_wp_edit.setEnabled(False)
            self._act_wp_delete.setEnabled(False)
            self._refresh_cache_list()
            self._statusbar.showMessage(
                tr("status_deleted_count", count=len(gc_codes)), 3000
            )

    def _delete_filtered_caches(self) -> None:
        """Slet alle caches i det aktive filter (uanset flag)."""
        caches = self._cache_table.get_all_caches()
        if not caches:
            QMessageBox.information(
                self,
                tr("delete_filtered_title"),
                tr("delete_filtered_none"),
            )
            return
        reply = QMessageBox.question(
            self,
            tr("delete_filtered_title"),
            tr("delete_filtered_msg", count=len(caches)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            gc_codes = [c.gc_code for c in caches]
            self._bulk_delete_caches(gc_codes)
            self._detail_panel.clear()
            self._act_wp_edit.setEnabled(False)
            self._act_wp_delete.setEnabled(False)
            self._refresh_cache_list()
            self._statusbar.showMessage(
                tr("status_deleted_count", count=len(gc_codes)), 3000
            )

    def _bulk_delete_caches(self, gc_codes: list[str]) -> None:
        """Delete caches and all child records by GC codes (bulk SQL)."""
        from opensak.db.models import (
            Cache as CacheModel, Log, Attribute, Trackable, Waypoint, UserNote,
        )
        with get_session() as session:
            cache_ids = [
                row[0] for row in
                session.query(CacheModel.id).filter(
                    CacheModel.gc_code.in_(gc_codes)
                ).all()
            ]
            if cache_ids:
                session.query(Log).filter(Log.cache_id.in_(cache_ids)).delete(synchronize_session=False)
                session.query(Attribute).filter(Attribute.cache_id.in_(cache_ids)).delete(synchronize_session=False)
                session.query(Trackable).filter(Trackable.cache_id.in_(cache_ids)).delete(synchronize_session=False)
                session.query(Waypoint).filter(Waypoint.cache_id.in_(cache_ids)).delete(synchronize_session=False)
                session.query(UserNote).filter(UserNote.cache_id.in_(cache_ids)).delete(synchronize_session=False)
                session.query(CacheModel).filter(CacheModel.id.in_(cache_ids)).delete(synchronize_session=False)

    def _clear_all_flags(self) -> None:
        """Fjern alle flag (user_flag=False) på alle caches i aktiv database."""
        reply = QMessageBox.question(
            self,
            tr("clear_flags_title"),
            tr("clear_flags_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from opensak.db.models import Cache as CacheModel
            with get_session() as session:
                session.query(CacheModel).filter(
                    CacheModel.user_flag == True  # noqa: E712
                ).update({CacheModel.user_flag: False}, synchronize_session=False)
            self._refresh_cache_list()
            self._statusbar.showMessage(tr("status_flags_cleared"), 3000)

    def _on_flags_changed(self) -> None:
        """Opdatér statuslinjen når et flag toggler."""
        flagged = len(self._cache_table.get_flagged_caches())
        total = self._cache_table.row_count()
        if flagged:
            self._statusbar.showMessage(
                tr("status_flagged_count", flagged=flagged, total=total), 3000
            )
        self._update_info_bar()

    def _on_sort_changed(self, col_id: str, ascending: bool) -> None:
        """Kaldes når brugeren klikker en kolonneheader i tabellen."""
        self._current_sort = SortSpec(col_id, ascending=ascending)
        self._save_sort_for_active_db()

    def _save_sort_for_active_db(self) -> None:
        """Gem aktuel sortering per database i QSettings."""
        from opensak.db.manager import get_db_manager
        from PySide6.QtCore import QSettings
        manager = get_db_manager()
        if not manager.active:
            return
        s = QSettings("OpenSAK Project", "OpenSAK")
        key = f"sort/{manager.active.path}"
        s.setValue(f"{key}/field", self._current_sort.field)
        s.setValue(f"{key}/ascending", self._current_sort.ascending)
        s.sync()

    def _load_sort_for_active_db(self) -> None:
        """Indlaes gemt sortering for den aktive database fra QSettings."""
        from opensak.db.manager import get_db_manager
        from PySide6.QtCore import QSettings
        manager = get_db_manager()
        if not manager.active:
            return
        s = QSettings("OpenSAK Project", "OpenSAK")
        key = f"sort/{manager.active.path}"
        field = s.value(f"{key}/field", "name")
        ascending = s.value(f"{key}/ascending", True, type=bool)
        self._current_sort = SortSpec(field, ascending=ascending)
        # Genanvend sort-indikatoren i tabellen hvis den allerede er loaded
        if hasattr(self, "_cache_table"):
            self._cache_table.apply_sort(field, ascending)

    def _open_filter_dialog(self) -> None:
        from opensak.gui.dialogs.filter_dialog import FilterDialog
        dlg = FilterDialog(self, self._current_filterset, self._active_filter_name)
        dlg.filter_applied.connect(self._on_filter_applied)
        dlg.exec()

    def _on_filter_applied(self, filterset, sort, profile_name: str) -> None:
        self._current_filterset = filterset
        self._current_sort = sort
        self._active_filter_name = profile_name
        self._save_sort_for_active_db()
        self._act_clear_filter.setEnabled(True)
        label = profile_name if profile_name else tr("filter_active_label")
        self._filter_lbl.setText(f"🔍 {label}")
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
        self._update_info_bar()

    def _clear_filter(self) -> None:
        self._current_filterset = FilterSet()
        self._active_filter_name = ""
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

    # ── Opdateringsstjek ───────────────────────────────────────────────────────

    def _check_update_background(self) -> None:
        """Kald ved opstart — tjekker lydløst i baggrunden."""
        from opensak import __version__
        self._update_worker = UpdateCheckWorker(__version__, parent=self)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.start()

    def _check_update_manual(self) -> None:
        """Kald fra menuen — viser resultat uanset om der er opdatering."""
        from opensak import __version__
        self._manual_update_worker = UpdateCheckWorker(__version__, parent=self)
        self._manual_update_worker.update_available.connect(
            lambda tag, url: self._on_update_available(tag, url, manual=True)
        )
        self._manual_update_worker.check_done.connect(
            self._on_manual_check_done
        )
        self._manual_update_worker.start()
        self._manual_found_update = False

    def _on_manual_check_done(self) -> None:
        """Vises kun ved manuel tjek — hvis ingen opdatering fundet."""
        if not getattr(self, "_manual_found_update", False):
            QMessageBox.information(
                self,
                tr("update_uptodate_title"),
                tr("update_uptodate_msg"),
            )

    def _on_update_available(
        self, latest_tag: str, url: str, *, manual: bool = False
    ) -> None:
        """Vis notifikationsdialog om ny version."""
        self._manual_found_update = True
        from opensak import __version__
        msg = QMessageBox(self)
        msg.setWindowTitle(tr("update_available_title"))
        msg.setText(tr("update_available_msg", latest=latest_tag, current=__version__))
        msg.setInformativeText(tr("update_available_info"))
        btn_open = msg.addButton(tr("update_open_releases"), QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(tr("update_later"), QMessageBox.ButtonRole.RejectRole)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        if msg.clickedButton() == btn_open:
            import webbrowser
            webbrowser.open(url)

