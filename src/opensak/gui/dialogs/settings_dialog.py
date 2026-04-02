"""
src/opensak/gui/dialogs/settings_dialog.py — Settings dialog.
"""

from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QDialogButtonBox, QGroupBox, QComboBox,
    QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from opensak.gui.settings import get_settings, HomePoint
from opensak.lang import tr, AVAILABLE_LANGUAGES, current_language
from opensak.coords import FORMATS, FORMAT_DMM, FORMAT_DMS, FORMAT_DD, format_coords


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings_dialog_title"))
        self.setMinimumWidth(480)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Hjemmepunkter ─────────────────────────────────────────────────────
        loc_group = QGroupBox(tr("settings_group_location"))
        loc_layout = QVBoxLayout(loc_group)

        # Tabel over gemte punkter
        self._points_table = QTableWidget(0, 3)
        self._points_table.setHorizontalHeaderLabels([
            tr("settings_hp_col_name"),
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

        # Knapper til liste-håndtering
        list_btn_row = QHBoxLayout()
        self._btn_activate = QPushButton(tr("settings_hp_activate"))
        self._btn_activate.setEnabled(False)
        self._btn_activate.clicked.connect(self._activate_point)
        list_btn_row.addWidget(self._btn_activate)

        self._btn_edit = QPushButton(tr("settings_hp_edit"))
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._edit_point)
        list_btn_row.addWidget(self._btn_edit)

        self._btn_delete = QPushButton(tr("settings_hp_delete"))
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._delete_point)
        list_btn_row.addWidget(self._btn_delete)

        list_btn_row.addStretch()
        loc_layout.addLayout(list_btn_row)

        # Tilføj / rediger punkt
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
        self._new_coord.setPlaceholderText(tr("settings_hp_coord_placeholder"))
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
        self._coord_format.addItem("DMM  —  N55 47.250 E012 25.000", FORMAT_DMM)
        self._coord_format.addItem("DMS  —  N55° 47' 15\" E012° 25' 00\"", FORMAT_DMS)
        self._coord_format.addItem("DD   —  55.78750, 12.41667", FORMAT_DD)
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

        # ── Knapper ───────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Hjemmepunkter — hjælpefunktioner ──────────────────────────────────────

    def _reload_points_table(self) -> None:
        s = get_settings()
        points = s.home_points
        active = s.active_home_name
        fmt = s.coord_format
        self._points_table.setRowCount(len(points))
        for row, p in enumerate(points):
            # Navn — marker aktiv med stjerne
            label = f"★  {p.name}" if p.name == active else p.name
            name_item = QTableWidgetItem(label)
            if p.name == active:
                name_item.setForeground(Qt.GlobalColor.darkGreen)

            # Koordinater i valgt format
            coords_str = format_coords(p.lat, p.lon, fmt)
            parts = coords_str.split()
            # DMM: "N55 47.250 E012 25.000" -> lat=parts[0:2], lon=parts[2:4]
            # DD:  "55.78750, 12.41667"      -> split on comma
            if "," in coords_str:
                halves = coords_str.split(",")
                lat_str = halves[0].strip()
                lon_str = halves[1].strip() if len(halves) > 1 else ""
            else:
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
        self._btn_activate.setEnabled(has)
        self._btn_edit.setEnabled(has)
        self._btn_delete.setEnabled(has)

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
        """Udfyld input-felterne med det valgte punkt til redigering."""
        p = self._selected_point()
        if not p:
            return
        fmt = get_settings().coord_format
        self._new_name.setText(p.name)
        self._new_coord.setText(format_coords(p.lat, p.lon, fmt))
        self._new_name.setFocus()

    def _on_coord_changed(self, text: str) -> None:
        """Live validering — vis koordinat i valgt format ved gyldig input."""
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
        """Tilføj eller opdatér hjemmepunkt fra input-felterne."""
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
        s.add_or_update_home_point(point)

        # Første punkt aktiveres automatisk
        if len(s.home_points) == 1 or not s.active_home_name:
            s.set_active_home(point)

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

    def _save(self) -> None:
        s = get_settings()
        s.use_miles     = self._miles_cb.isChecked()
        s.show_archived = self._archived_cb.isChecked()
        s.show_found    = self._found_cb.isChecked()
        s.map_provider  = self._map_provider.currentData()
        s.coord_format  = self._coord_format.currentData()
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
