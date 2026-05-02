"""
src/opensak/gui/dialogs/settings_dialog.py — Settings dialog.
"""

from __future__ import annotations
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QDialogButtonBox, QGroupBox, QComboBox,
    QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QTabWidget, QWidget,
    QFrame, QSizePolicy, QSpinBox, QScrollArea
)
from opensak.gui.icon import OpenSAKMessageBox as QMessageBox
from PySide6.QtGui import QPixmap, QFont
from opensak.gui.settings import get_settings, HomePoint
from opensak.lang import tr, AVAILABLE_LANGUAGES, current_language
from opensak.coords import FORMATS, format_coords
from opensak.utils.types import CoordFormat


# ── Baggrundstråd til OAuth + API-kald ───────────────────────────────────────

class _OAuthWorker(QThread):
    """Kører OAuth flow i baggrunden så GUI ikke fryser."""
    success = Signal(dict)   # token dict
    error   = Signal(str)    # fejlbesked

    def run(self):
        try:
            from opensak.api.geocaching import start_oauth_flow
            token = start_oauth_flow()
            if token:
                self.success.emit(token)
            else:
                self.error.emit(tr("gc_login_no_client_id"))
        except Exception as exc:
            self.error.emit(str(exc))


class _ProfileWorker(QThread):
    """Henter brugerprofil i baggrunden."""
    success = Signal(dict)
    error   = Signal(str)

    def run(self):
        try:
            from opensak.api.geocaching import get_user_profile
            profile = get_user_profile()
            if profile:
                self.success.emit(profile)
            else:
                self.error.emit(tr("gc_profile_error"))
        except Exception as exc:
            self.error.emit(str(exc))


# ── Hoved-dialog ──────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings_dialog_title"))
        self.setMinimumWidth(520)
        self._oauth_worker        = None
        self._profile_worker      = None
        self._editing_original_name: str | None = None   # Issue #157
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Tab-widget med tre faner
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(),   tr("settings_tab_general"))
        self._tabs.addTab(self._build_gc_tab(),         tr("settings_tab_geocaching"))
        self._tabs.addTab(self._build_advanced_tab(),   tr("settings_tab_advanced"))

        layout.addWidget(self._tabs)

        # Knapper
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Fane 1: Generelle indstillinger ──────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Hjemmepunkter ─────────────────────────────────────────────────────
        loc_group = QGroupBox(tr("settings_group_location"))
        loc_layout = QVBoxLayout(loc_group)

        self._points_table = QTableWidget(0, 3)
        self._points_table.setHorizontalHeaderLabels([
            tr("col_name"),
            tr("settings_hp_col_lat"),
            tr("settings_hp_col_lon"),
        ])
        self._points_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._points_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._points_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._points_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._points_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._points_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._points_table.verticalHeader().setVisible(False)
        self._points_table.setShowGrid(False)
        self._points_table.setAlternatingRowColors(True)
        self._points_table.verticalHeader().setDefaultSectionSize(24)
        self._points_table.setMaximumHeight(160)
        self._points_table.itemSelectionChanged.connect(self._on_point_selected)
        loc_layout.addWidget(self._points_table)

        list_btn_row = QHBoxLayout()
        self._btn_activate = QPushButton(tr("settings_hp_activate"))
        self._btn_activate.setEnabled(False)
        self._btn_activate.clicked.connect(self._activate_point)
        list_btn_row.addWidget(self._btn_activate)

        self._btn_edit = QPushButton(tr("edit"))
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._edit_point)
        list_btn_row.addWidget(self._btn_edit)

        self._btn_delete = QPushButton(tr("delete"))
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._delete_point)
        list_btn_row.addWidget(self._btn_delete)
        list_btn_row.addStretch()
        loc_layout.addLayout(list_btn_row)

        add_group = QGroupBox(tr("settings_hp_add_group"))
        add_layout = QVBoxLayout(add_group)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(tr("settings_hp_name_label")))
        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText(tr("settings_hp_name_placeholder"))
        self._new_name.setMaximumWidth(180)
        name_row.addWidget(self._new_name)
        name_row.addStretch()
        add_layout.addLayout(name_row)

        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel(tr("settings_hp_coord_label")))
        self._new_coord = QLineEdit()
        self._new_coord.setPlaceholderText(tr("coord_conv_placeholder"))
        coord_row.addWidget(self._new_coord)
        add_layout.addLayout(coord_row)

        self._coord_hint = QLabel("")
        self._coord_hint.setStyleSheet(
            "color: gray; font-size: 10px; padding-left: 2px;"
        )
        add_layout.addWidget(self._coord_hint)
        self._new_coord.textChanged.connect(self._on_coord_changed)

        add_btn_row = QHBoxLayout()
        self._btn_add = QPushButton(tr("settings_hp_add_btn"))
        self._btn_add.clicked.connect(self._add_point)
        add_btn_row.addWidget(self._btn_add)
        add_btn_row.addStretch()
        add_layout.addLayout(add_btn_row)

        loc_layout.addWidget(add_group)
        layout.addWidget(loc_group)

        # ── Visning ───────────────────────────────────────────────────────────
        disp_group = QGroupBox(tr("settings_group_display"))
        disp_layout = QVBoxLayout(disp_group)

        self._miles_cb = QCheckBox(tr("settings_use_miles"))
        disp_layout.addWidget(self._miles_cb)

        self._archived_cb = QCheckBox(tr("settings_show_archived"))
        disp_layout.addWidget(self._archived_cb)

        self._found_cb = QCheckBox(tr("settings_show_found"))
        disp_layout.addWidget(self._found_cb)

        map_row = QHBoxLayout()
        map_row.addWidget(QLabel(tr("settings_map_label")))
        self._map_provider = QComboBox()
        self._map_provider.addItem(tr("settings_map_google"), "google")
        self._map_provider.addItem(tr("settings_map_osm"), "osm")
        map_row.addWidget(self._map_provider)
        map_row.addStretch()
        disp_layout.addLayout(map_row)

        coord_fmt_row = QHBoxLayout()
        coord_fmt_row.addWidget(QLabel(tr("settings_coord_format_label")))
        self._coord_format = QComboBox()
        self._coord_format.addItem("DMM  —  N55 47.250 E012 25.000", CoordFormat.DMM)
        self._coord_format.addItem("DMS  —  N55° 47' 15\" E012° 25' 00\"", CoordFormat.DMS)
        self._coord_format.addItem("DD   —  55.78750, 12.41667", CoordFormat.DD)
        coord_fmt_row.addWidget(self._coord_format)
        coord_fmt_row.addStretch()
        disp_layout.addLayout(coord_fmt_row)

        layout.addWidget(disp_group)

        # ── Sprog ─────────────────────────────────────────────────────────────
        lang_group = QGroupBox(tr("settings_group_language"))
        lang_layout = QVBoxLayout(lang_group)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("settings_language_label")))
        self._lang_combo = QComboBox()
        for code, name in AVAILABLE_LANGUAGES.items():
            self._lang_combo.addItem(name, code)
        lang_row.addWidget(self._lang_combo)
        lang_row.addStretch()
        lang_layout.addLayout(lang_row)

        hint = QLabel(tr("settings_language_hint"))
        hint.setStyleSheet("color: gray; font-size: 10px;")
        lang_layout.addWidget(hint)

        layout.addWidget(lang_group)

        # ── Geocaching brugernavn ─────────────────────────────────────────────
        user_group = QGroupBox(tr("settings_group_user"))
        user_layout = QVBoxLayout(user_group)

        user_row = QHBoxLayout()
        user_row.addWidget(QLabel(tr("settings_gc_username_label")))
        self._gc_username = QLineEdit()
        self._gc_username.setPlaceholderText(tr("settings_gc_username_placeholder"))
        self._gc_username.setMaximumWidth(200)
        user_row.addWidget(self._gc_username)
        user_row.addStretch()
        user_layout.addLayout(user_row)

        hint = QLabel(tr("settings_gc_username_hint"))
        hint.setStyleSheet("color: gray; font-size: 10px;")
        user_layout.addWidget(hint)

        layout.addWidget(user_group)

        layout.addStretch()
        scroll.setWidget(tab)
        return scroll

    # ── Fane 3: Advanced ─────────────────────────────────────────────────────

    def _build_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ── Search behaviour ──────────────────────────────────────────────────
        search_group = QGroupBox(tr("settings_group_search"))
        search_layout = QVBoxLayout(search_group)

        min_row = QHBoxLayout()
        min_row.addWidget(QLabel(tr("settings_search_min_chars_label")))
        self._search_min_chars = QSpinBox()
        self._search_min_chars.setRange(0, 20)
        self._search_min_chars.setSpecialValueText(tr("settings_search_auto"))
        self._search_min_chars.setFixedWidth(80)
        min_row.addWidget(self._search_min_chars)
        min_row.addStretch()
        search_layout.addLayout(min_row)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel(tr("settings_search_debounce_label")))
        self._search_debounce_ms = QSpinBox()
        self._search_debounce_ms.setRange(0, 2000)
        self._search_debounce_ms.setSingleStep(50)
        self._search_debounce_ms.setSpecialValueText(tr("settings_search_auto"))
        self._search_debounce_ms.setFixedWidth(80)
        delay_row.addWidget(self._search_debounce_ms)
        delay_row.addStretch()
        search_layout.addLayout(delay_row)

        search_hint = QLabel(tr("settings_search_hint"))
        search_hint.setStyleSheet("color: gray; font-size: 10px;")
        search_hint.setWordWrap(True)
        search_layout.addWidget(search_hint)

        layout.addWidget(search_group)
        layout.addStretch()
        return tab

    # ── Fane 2: Geocaching.com ────────────────────────────────────────────────

    def _build_gc_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Status-boks (viser login-status + brugerinfo)
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_frame.setStyleSheet(
            "QFrame { border-radius: 6px; padding: 8px; }"
        )
        status_layout = QVBoxLayout(status_frame)
        status_layout.setSpacing(4)

        # Ikon + navn i samme række
        top_row = QHBoxLayout()

        name_col = QVBoxLayout()
        self._gc_username_label = QLabel(tr("gc_not_logged_in"))
        self._gc_username_label.setFont(QFont("Sans Serif", 11, QFont.Weight.Bold))
        name_col.addWidget(self._gc_username_label)

        self._gc_status_label = QLabel(tr("gc_status_offline"))
        self._gc_status_label.setStyleSheet("color: gray; font-size: 10px;")
        name_col.addWidget(self._gc_status_label)
        name_col.addStretch()

        top_row.addLayout(name_col)
        top_row.addStretch()
        status_layout.addLayout(top_row)

        # Fund-tæller
        self._gc_finds_label = QLabel("")
        self._gc_finds_label.setStyleSheet("color: gray; font-size: 10px; padding-left: 40px;")
        status_layout.addWidget(self._gc_finds_label)

        layout.addWidget(status_frame)

        # Knap-række
        btn_row = QHBoxLayout()

        self._gc_login_btn = QPushButton(tr("gc_login_btn"))
        self._gc_login_btn.setMinimumWidth(140)
        self._gc_login_btn.clicked.connect(self._on_gc_login)
        btn_row.addWidget(self._gc_login_btn)

        self._gc_logout_btn = QPushButton(tr("gc_logout_btn"))
        self._gc_logout_btn.setMinimumWidth(100)
        self._gc_logout_btn.clicked.connect(self._on_gc_logout)
        self._gc_logout_btn.setEnabled(False)
        btn_row.addWidget(self._gc_logout_btn)

        self._gc_refresh_btn = QPushButton(tr("gc_refresh_btn"))
        self._gc_refresh_btn.setMinimumWidth(100)
        self._gc_refresh_btn.clicked.connect(self._on_gc_refresh_profile)
        self._gc_refresh_btn.setEnabled(False)
        btn_row.addWidget(self._gc_refresh_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Forklaring — hvad bruges API'en til
        info_group = QGroupBox(tr("gc_info_group"))
        info_layout = QVBoxLayout(info_group)

        for text_key in [
            "gc_info_favorites",
            "gc_info_trackables",
            "gc_info_finds",
        ]:
            row = QHBoxLayout()
            bullet = QLabel("•")
            bullet.setFixedWidth(14)
            row.addWidget(bullet)
            lbl = QLabel(tr(text_key))
            lbl.setWordWrap(True)
            row.addWidget(lbl)
            info_layout.addLayout(row)

        layout.addWidget(info_group)

        # API-status note (vises kun hvis CLIENT_ID ikke er sat)
        self._gc_api_note = QLabel(tr("gc_api_not_configured"))
        self._gc_api_note.setStyleSheet(
            "color: #b07800; font-size: 10px; padding: 4px;"
            "background: #fff8e1; border-radius: 4px;"
        )
        self._gc_api_note.setWordWrap(True)
        layout.addWidget(self._gc_api_note)

        layout.addStretch()
        return tab

    # ── GC login/logout ───────────────────────────────────────────────────────

    def _on_gc_login(self) -> None:
        """Start OAuth flow i baggrundstråd."""
        from opensak.api.geocaching import GC_CLIENT_ID
        if not GC_CLIENT_ID:
            QMessageBox.information(
                self,
                tr("gc_login_unavailable_title"),
                tr("gc_login_unavailable_msg"),
            )
            return

        self._gc_login_btn.setEnabled(False)
        self._gc_login_btn.setText(tr("gc_login_waiting"))
        self._gc_status_label.setText(tr("gc_status_waiting"))

        self._oauth_worker = _OAuthWorker(self)
        self._oauth_worker.success.connect(self._on_gc_login_success)
        self._oauth_worker.error.connect(self._on_gc_login_error)
        self._oauth_worker.start()

    def _on_gc_login_success(self, token: dict) -> None:
        self._gc_login_btn.setText(tr("gc_login_btn"))
        self._gc_login_btn.setEnabled(False)
        self._gc_logout_btn.setEnabled(True)
        self._gc_refresh_btn.setEnabled(True)
        self._gc_status_label.setText(tr("gc_status_online"))
        self._gc_status_label.setStyleSheet("color: #2e7d32; font-size: 10px;")
        # Hent profil med det samme
        self._on_gc_refresh_profile()

    def _on_gc_login_error(self, msg: str) -> None:
        self._gc_login_btn.setEnabled(True)
        self._gc_login_btn.setText(tr("gc_login_btn"))
        self._gc_status_label.setText(tr("gc_status_offline"))
        QMessageBox.warning(self, tr("gc_login_error_title"), msg)

    def _on_gc_logout(self) -> None:
        reply = QMessageBox.question(
            self,
            tr("gc_logout_btn"),
            tr("gc_logout_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from opensak.api.geocaching import logout
            logout()
            self._update_gc_ui_logged_out()

    def _on_gc_refresh_profile(self) -> None:
        self._gc_refresh_btn.setEnabled(False)
        self._gc_status_label.setText(tr("gc_status_fetching"))

        self._profile_worker = _ProfileWorker(self)
        self._profile_worker.success.connect(self._on_profile_loaded)
        self._profile_worker.error.connect(self._on_profile_error)
        self._profile_worker.start()

    def _on_profile_loaded(self, profile: dict) -> None:
        username  = profile.get("username", "?")
        finds     = profile.get("findCount", "?")
        self._gc_username_label.setText(username)
        self._gc_finds_label.setText(tr("gc_find_count", count=finds))
        self._gc_status_label.setText(tr("gc_status_online"))
        self._gc_status_label.setStyleSheet("color: #2e7d32; font-size: 10px;")
        self._gc_refresh_btn.setEnabled(True)
        self._gc_login_btn.setEnabled(False)
        self._gc_logout_btn.setEnabled(True)

    def _on_profile_error(self, msg: str) -> None:
        self._gc_status_label.setText(tr("gc_status_error"))
        self._gc_status_label.setStyleSheet("color: #c62828; font-size: 10px;")
        self._gc_refresh_btn.setEnabled(True)

    def _update_gc_ui_logged_out(self) -> None:
        self._gc_username_label.setText(tr("gc_not_logged_in"))
        self._gc_finds_label.setText("")
        self._gc_status_label.setText(tr("gc_status_offline"))
        self._gc_status_label.setStyleSheet("color: gray; font-size: 10px;")
        self._gc_login_btn.setEnabled(True)
        self._gc_logout_btn.setEnabled(False)
        self._gc_refresh_btn.setEnabled(False)

    def _refresh_gc_status_on_open(self) -> None:
        """Tjek login-status når dialogen åbnes."""
        from opensak.api.geocaching import is_logged_in, GC_CLIENT_ID

        # Skjul API-note hvis CLIENT_ID er sat
        self._gc_api_note.setVisible(not bool(GC_CLIENT_ID))

        if is_logged_in():
            self._gc_login_btn.setEnabled(False)
            self._gc_logout_btn.setEnabled(True)
            self._gc_refresh_btn.setEnabled(True)
            self._gc_status_label.setText(tr("gc_status_fetching"))
            self._on_gc_refresh_profile()
        else:
            self._update_gc_ui_logged_out()

    # ── Hjemmepunkter — hjælpefunktioner ──────────────────────────────────────

    def _reload_points_table(self) -> None:
        s = get_settings()
        points = s.home_points
        active = s.active_home_name
        fmt = s.coord_format
        self._points_table.setRowCount(len(points))
        for row, p in enumerate(points):
            label = f"★  {p.name}" if p.name == active else p.name
            name_item = QTableWidgetItem(label)
            if p.name == active:
                name_item.setForeground(Qt.GlobalColor.darkGreen)

            coords_str = format_coords(p.lat, p.lon, fmt)
            if "," in coords_str:
                halves = coords_str.split(",")
                lat_str = halves[0].strip()
                lon_str = halves[1].strip() if len(halves) > 1 else ""
            else:
                parts = coords_str.split()
                mid = len(parts) // 2
                lat_str = " ".join(parts[:mid])
                lon_str = " ".join(parts[mid:])

            self._points_table.setItem(row, 0, name_item)
            self._points_table.setItem(row, 1, QTableWidgetItem(lat_str))
            self._points_table.setItem(row, 2, QTableWidgetItem(lon_str))

        self._btn_activate.setEnabled(False)
        self._btn_edit.setEnabled(False)
        self._btn_delete.setEnabled(False)

    def _selected_point(self) -> HomePoint | None:
        row = self._points_table.currentRow()
        points = get_settings().home_points
        if 0 <= row < len(points):
            return points[row]
        return None

    def _on_point_selected(self) -> None:
        has = self._points_table.currentRow() >= 0 and bool(
            self._points_table.selectedItems()
        )
        self._btn_edit.setEnabled(has)
        self._btn_delete.setEnabled(has)
        # Aktivér skal kun være aktiv hvis det valgte punkt IKKE allerede er aktivt
        if has:
            p = self._selected_point()
            already_active = p is not None and p.name == get_settings().active_home_name
            self._btn_activate.setEnabled(not already_active)
        else:
            self._btn_activate.setEnabled(False)

    def _activate_point(self) -> None:
        p = self._selected_point()
        if p:
            get_settings().set_active_home(p)
            self._reload_points_table()

    def _delete_point(self) -> None:
        p = self._selected_point()
        if not p:
            return
        reply = QMessageBox.question(
            self,
            tr("settings_hp_delete_title"),
            tr("settings_hp_delete_msg", name=p.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            get_settings().remove_home_point(p.name)
            self._reload_points_table()

    def _edit_point(self) -> None:
        p = self._selected_point()
        if not p:
            return
        fmt = get_settings().coord_format
        self._editing_original_name = p.name   # Issue #157: gem originalt navn
        self._new_name.setText(p.name)
        self._new_coord.setText(format_coords(p.lat, p.lon, fmt))
        self._btn_add.setText(tr("save"))       # Issue #157: vis at vi redigerer
        self._new_name.setFocus()

    def _on_coord_changed(self, text: str) -> None:
        if not text.strip():
            self._coord_hint.setText("")
            return
        try:
            from opensak.coords import parse_coords
            lat, lon = parse_coords(text)
            fmt = get_settings().coord_format
            self._coord_hint.setText(f"✓  {format_coords(lat, lon, fmt)}")
            self._coord_hint.setStyleSheet(
                "color: #2e7d32; font-size: 10px; padding-left: 2px;"
            )
        except Exception:
            self._coord_hint.setText(tr("settings_hp_coord_error"))
            self._coord_hint.setStyleSheet(
                "color: #c62828; font-size: 10px; padding-left: 2px;"
            )

    def _add_point(self) -> None:
        name = self._new_name.text().strip()
        coord_text = self._new_coord.text().strip()

        if not name:
            QMessageBox.warning(self, tr("warning"), tr("settings_hp_name_required"))
            return
        if not coord_text:
            QMessageBox.warning(self, tr("warning"), tr("settings_hp_coord_required"))
            return
        try:
            from opensak.coords import parse_coords
            lat, lon = parse_coords(coord_text)
        except Exception:
            QMessageBox.warning(self, tr("warning"), tr("settings_hp_coord_invalid"))
            return

        s = get_settings()
        point = HomePoint(name, lat, lon)

        # Issue #157: hvis vi redigerer og har ændret navn, fjern det gamle punkt
        if self._editing_original_name and self._editing_original_name != name:
            was_active = s.active_home_name == self._editing_original_name
            s.remove_home_point(self._editing_original_name)
            if was_active:
                s.set_active_home(point)

        s.add_or_update_home_point(point)

        if len(s.home_points) == 1 or not s.active_home_name:
            s.set_active_home(point)

        self._editing_original_name = None
        self._btn_add.setText(tr("settings_hp_add_btn"))   # Issue #157: nulstil knaptekst
        self._new_name.clear()
        self._new_coord.clear()
        self._coord_hint.setText("")
        self._reload_points_table()

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        s = get_settings()
        self._reload_points_table()
        self._miles_cb.setChecked(s.use_miles)
        self._archived_cb.setChecked(s.show_archived)
        self._found_cb.setChecked(s.show_found)
        idx = self._map_provider.findData(s.map_provider)
        self._map_provider.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self._coord_format.findData(s.coord_format)
        self._coord_format.setCurrentIndex(idx if idx >= 0 else 0)
        lang_idx = self._lang_combo.findData(current_language())
        self._lang_combo.setCurrentIndex(lang_idx if lang_idx >= 0 else 0)
        self._gc_username.setText(s.gc_username)
        self._search_min_chars.setValue(s.search_min_chars)
        self._search_debounce_ms.setValue(s.search_debounce_ms)
        # Opdater GC-status
        self._refresh_gc_status_on_open()

    def _save(self) -> None:
        s = get_settings()
        s.gc_username       = self._gc_username.text()
        s.use_miles         = self._miles_cb.isChecked()
        s.show_archived     = self._archived_cb.isChecked()
        s.show_found        = self._found_cb.isChecked()
        s.map_provider      = self._map_provider.currentData()
        s.coord_format      = self._coord_format.currentData()
        s.search_min_chars  = self._search_min_chars.value()
        s.search_debounce_ms = self._search_debounce_ms.value()
        s.sync()

        new_lang = self._lang_combo.currentData()
        if new_lang != current_language():
            from opensak.config import set_language
            set_language(new_lang)
            QMessageBox.information(
                self,
                tr("restart_required"),
                tr("restart_message"),
            )

        self.accept()
