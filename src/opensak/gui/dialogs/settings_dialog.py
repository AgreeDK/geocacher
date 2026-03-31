"""
src/opensak/gui/dialogs/settings_dialog.py — Settings dialog.
"""

from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QDialogButtonBox, QGroupBox, QDoubleSpinBox, QComboBox,
    QMessageBox
)
from opensak.gui.settings import get_settings
from opensak.lang import tr, AVAILABLE_LANGUAGES, current_language
from opensak.coords import FORMATS, FORMAT_DMM, FORMAT_DMS, FORMAT_DD


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings_dialog_title"))
        self.setMinimumWidth(420)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Hjemkoordinat ─────────────────────────────────────────────────────
        loc_group = QGroupBox(tr("settings_group_location"))
        loc_form = QFormLayout(loc_group)

        self._lat = QDoubleSpinBox()
        self._lat.setRange(-90.0, 90.0)
        self._lat.setDecimals(5)
        self._lat.setSingleStep(0.001)
        loc_form.addRow(tr("settings_lat_label"), self._lat)

        self._lon = QDoubleSpinBox()
        self._lon.setRange(-180.0, 180.0)
        self._lon.setDecimals(5)
        self._lon.setSingleStep(0.001)
        loc_form.addRow(tr("settings_lon_label"), self._lon)

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

        # Kortapp
        map_row = QHBoxLayout()
        map_row.addWidget(QLabel(tr("settings_map_label")))
        self._map_provider = QComboBox()
        self._map_provider.addItem(tr("settings_map_google"), "google")
        self._map_provider.addItem(tr("settings_map_osm"), "osm")
        map_row.addWidget(self._map_provider)
        map_row.addStretch()
        disp_layout.addLayout(map_row)

        # Koordinatformat
        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel(tr("settings_coord_format_label")))
        self._coord_format = QComboBox()
        self._coord_format.addItem("DMM  —  N55 47.250 E012 25.000", FORMAT_DMM)
        self._coord_format.addItem("DMS  —  N55° 47' 15\" E012° 25' 00\"", FORMAT_DMS)
        self._coord_format.addItem("DD   —  55.78750, 12.41667", FORMAT_DD)
        coord_row.addWidget(self._coord_format)
        coord_row.addStretch()
        disp_layout.addLayout(coord_row)

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

    def _load(self) -> None:
        s = get_settings()
        self._lat.setValue(s.home_lat)
        self._lon.setValue(s.home_lon)
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
        s.home_lat      = self._lat.value()
        s.home_lon      = self._lon.value()
        s.use_miles     = self._miles_cb.isChecked()
        s.show_archived = self._archived_cb.isChecked()
        s.show_found    = self._found_cb.isChecked()
        s.map_provider  = self._map_provider.currentData()
        s.coord_format  = self._coord_format.currentData()
        s.sync()

        # Gem sprog hvis det er ændret
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
