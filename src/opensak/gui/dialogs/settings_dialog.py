"""
src/opensak/gui/dialogs/settings_dialog.py — Settings dialog.
"""

from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QDialogButtonBox, QGroupBox, QDoubleSpinBox, QComboBox
)
from opensak.gui.settings import get_settings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Indstillinger")
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Home location ─────────────────────────────────────────────────────
        loc_group = QGroupBox("Hjemkoordinat")
        loc_form = QFormLayout(loc_group)

        self._lat = QDoubleSpinBox()
        self._lat.setRange(-90.0, 90.0)
        self._lat.setDecimals(5)
        self._lat.setSingleStep(0.001)
        loc_form.addRow("Breddegrad:", self._lat)

        self._lon = QDoubleSpinBox()
        self._lon.setRange(-180.0, 180.0)
        self._lon.setDecimals(5)
        self._lon.setSingleStep(0.001)
        loc_form.addRow("Længdegrad:", self._lon)

        layout.addWidget(loc_group)

        # ── Display ───────────────────────────────────────────────────────────
        disp_group = QGroupBox("Visning")
        disp_layout = QVBoxLayout(disp_group)

        self._miles_cb = QCheckBox("Vis afstande i miles (i stedet for km)")
        disp_layout.addWidget(self._miles_cb)

        self._archived_cb = QCheckBox("Vis arkiverede caches")
        disp_layout.addWidget(self._archived_cb)

        self._found_cb = QCheckBox("Vis fundne caches")
        disp_layout.addWidget(self._found_cb)

        # Kortapp
        map_row = QHBoxLayout()
        map_row.addWidget(QLabel("Kortapp:"))
        self._map_provider = QComboBox()
        self._map_provider.addItem("Google Maps", "google")
        self._map_provider.addItem("OpenStreetMap", "osm")
        map_row.addWidget(self._map_provider)
        map_row.addStretch()
        disp_layout.addLayout(map_row)

        layout.addWidget(disp_group)

        # ── Buttons ───────────────────────────────────────────────────────────
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

    def _save(self) -> None:
        s = get_settings()
        s.home_lat = self._lat.value()
        s.home_lon = self._lon.value()
        s.use_miles = self._miles_cb.isChecked()
        s.show_archived = self._archived_cb.isChecked()
        s.show_found = self._found_cb.isChecked()
        s.map_provider = self._map_provider.currentData()
        s.sync()
        self.accept()
