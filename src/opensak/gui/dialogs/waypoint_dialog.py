"""
src/opensak/gui/dialogs/waypoint_dialog.py — Tilføj/Rediger cache dialog.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox,
    QDoubleSpinBox, QSpinBox, QCheckBox,
    QPushButton, QDialogButtonBox, QTabWidget,
    QWidget, QGroupBox, QMessageBox
)

from opensak.db.models import Cache
from opensak.lang import tr
from opensak.coords import format_coords, parse_coords
from opensak.gui.settings import get_settings


# ── Konstanter ────────────────────────────────────────────────────────────────

from opensak.utils.constants import CACHE_TYPES, CONTAINER_SIZES


class WaypointDialog(QDialog):
    """
    Dialog til at tilføje eller redigere en cache manuelt.
    """

    def __init__(self, parent=None, cache: Optional[Cache] = None):
        super().__init__(parent)
        self._cache = cache
        self._is_edit = cache is not None
        # Parsed koordinater gemmes her
        self._parsed_lat: Optional[float] = None
        self._parsed_lon: Optional[float] = None
        self.setWindowTitle(tr("wp_dialog_title_edit") if self._is_edit else tr("wp_dialog_title_add"))
        self.setMinimumSize(520, 580)
        self._setup_ui()
        if self._is_edit:
            self._populate(cache)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # ── Fane 1: Grundlæggende ─────────────────────────────────────────────
        basic = QWidget()
        basic_layout = QFormLayout(basic)
        basic_layout.setSpacing(8)

        self._gc_code = QLineEdit()
        self._gc_code.setPlaceholderText(tr("wp_ph_gc_code"))
        if self._is_edit:
            self._gc_code.setReadOnly(True)
            self._gc_code.setStyleSheet("color: gray;")
        basic_layout.addRow(tr("wp_label_gc_code"), self._gc_code)

        self._name = QLineEdit()
        self._name.setPlaceholderText(tr("wp_ph_name"))
        basic_layout.addRow(tr("wp_label_name"), self._name)

        self._cache_type = QComboBox()
        self._cache_type.addItems(CACHE_TYPES)
        basic_layout.addRow(tr("wp_label_type"), self._cache_type)

        self._container = QComboBox()
        self._container.addItems(CONTAINER_SIZES)
        basic_layout.addRow(tr("wp_label_container"), self._container)

        # Koordinater — tekstfelt med parse-feedback (samme mønster som corrected_coords_dialog)
        coord_group = QGroupBox(tr("detail_coords"))
        coord_layout = QVBoxLayout(coord_group)
        coord_layout.setSpacing(4)

        fmt = get_settings().coord_format
        placeholder = {
            "dmm": "N55 47.250 E012 25.000",
            "dms": "N55° 47' 15\" E012° 25' 00\"",
            "dd":  "55.78750, 12.41667",
        }.get(fmt, "N55 47.250 E012 25.000")

        self._coord_input = QLineEdit()
        self._coord_input.setPlaceholderText(placeholder)
        self._coord_input.textChanged.connect(self._on_coord_changed)
        coord_layout.addWidget(self._coord_input)

        self._coord_feedback = QLabel("")
        self._coord_feedback.setStyleSheet("font-size: 10px;")
        self._coord_feedback.setWordWrap(True)
        coord_layout.addWidget(self._coord_feedback)

        basic_layout.addRow(coord_group)

        # D/T
        dt_layout = QHBoxLayout()
        self._difficulty = QDoubleSpinBox()
        self._difficulty.setRange(1.0, 5.0)
        self._difficulty.setSingleStep(0.5)
        self._difficulty.setDecimals(1)
        self._difficulty.setValue(1.5)
        dt_layout.addWidget(QLabel(tr("wp_label_difficulty")))
        dt_layout.addWidget(self._difficulty)
        dt_layout.addSpacing(16)

        self._terrain = QDoubleSpinBox()
        self._terrain.setRange(1.0, 5.0)
        self._terrain.setSingleStep(0.5)
        self._terrain.setDecimals(1)
        self._terrain.setValue(1.5)
        dt_layout.addWidget(QLabel(tr("wp_label_terrain")))
        dt_layout.addWidget(self._terrain)
        dt_layout.addStretch()
        basic_layout.addRow(tr("wp_label_dt"), dt_layout)

        tabs.addTab(basic, tr("wp_tab_basic"))

        # ── Fane 2: Detaljer ──────────────────────────────────────────────────
        details = QWidget()
        details_layout = QFormLayout(details)
        details_layout.setSpacing(8)

        self._placed_by = QLineEdit()
        self._placed_by.setPlaceholderText(tr("wp_ph_placed_by"))
        details_layout.addRow(tr("wp_label_placed_by"), self._placed_by)

        self._country = QLineEdit()
        self._country.setPlaceholderText(tr("wp_ph_country"))
        details_layout.addRow(tr("wp_label_country"), self._country)

        self._state = QLineEdit()
        self._state.setPlaceholderText(tr("wp_ph_state"))
        details_layout.addRow(tr("wp_label_state"), self._state)

        self._short_desc = QTextEdit()
        self._short_desc.setMaximumHeight(80)
        self._short_desc.setPlaceholderText(tr("wp_ph_short_desc"))
        details_layout.addRow(tr("wp_label_short_desc"), self._short_desc)

        self._long_desc = QTextEdit()
        self._long_desc.setMaximumHeight(120)
        self._long_desc.setPlaceholderText(tr("wp_ph_long_desc"))
        details_layout.addRow(tr("wp_label_long_desc"), self._long_desc)

        self._hints = QLineEdit()
        self._hints.setPlaceholderText(tr("wp_ph_hint"))
        details_layout.addRow(tr("wp_label_hint"), self._hints)

        tabs.addTab(details, tr("wp_tab_details"))

        # ── Fane 3: Status ────────────────────────────────────────────────────
        status = QWidget()
        status_layout = QFormLayout(status)
        status_layout.setSpacing(8)

        self._available = QCheckBox(tr("wp_cb_available"))
        self._available.setChecked(True)
        status_layout.addRow(tr("wp_label_status"), self._available)

        self._archived = QCheckBox(tr("wp_cb_archived"))
        status_layout.addRow("", self._archived)

        self._premium = QCheckBox(tr("wp_cb_premium"))
        status_layout.addRow("", self._premium)

        self._found = QCheckBox(tr("wp_cb_found"))
        status_layout.addRow(tr("wp_label_personal"), self._found)

        self._dnf = QCheckBox(tr("wp_cb_dnf"))
        status_layout.addRow("", self._dnf)

        self._favorite = QCheckBox(tr("wp_cb_favorite"))
        status_layout.addRow("", self._favorite)

        tabs.addTab(status, tr("wp_tab_status"))

        layout.addWidget(tabs)

        # ── Knapper ───────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_coord_changed(self, text: str) -> None:
        """Parse koordinat-input og vis feedback i brugerens format."""
        text = text.strip()
        if not text:
            self._coord_feedback.setText("")
            self._parsed_lat = None
            self._parsed_lon = None
            return

        result = parse_coords(text)
        if result is not None:
            lat, lon = result
            self._parsed_lat = lat
            self._parsed_lon = lon
            fmt = get_settings().coord_format
            display = format_coords(lat, lon, fmt)
            self._coord_feedback.setText(f"✓  {display}")
            self._coord_feedback.setStyleSheet("color: #2e7d32; font-size: 10px;")
        else:
            self._parsed_lat = None
            self._parsed_lon = None
            self._coord_feedback.setText(tr("coord_conv_parse_error"))
            self._coord_feedback.setStyleSheet("color: #c62828; font-size: 10px;")

    def _populate(self, cache: Cache) -> None:
        """Udfyld felterne med data fra en eksisterende cache."""
        self._gc_code.setText(cache.gc_code or "")
        self._name.setText(cache.name or "")

        idx = self._cache_type.findText(cache.cache_type or "")
        if idx >= 0:
            self._cache_type.setCurrentIndex(idx)

        idx = self._container.findText(cache.container or "")
        if idx >= 0:
            self._container.setCurrentIndex(idx)

        # Vis koordinater i brugerens valgte format
        if cache.latitude is not None and cache.longitude is not None:
            fmt = get_settings().coord_format
            self._coord_input.setText(format_coords(cache.latitude, cache.longitude, fmt))
            self._parsed_lat = cache.latitude
            self._parsed_lon = cache.longitude

        if cache.difficulty:
            self._difficulty.setValue(cache.difficulty)
        if cache.terrain:
            self._terrain.setValue(cache.terrain)

        self._placed_by.setText(cache.placed_by or "")
        self._country.setText(cache.country or "")
        self._state.setText(cache.state or "")
        self._short_desc.setPlainText(cache.short_description or "")
        self._long_desc.setPlainText(cache.long_description or "")
        self._hints.setText(cache.encoded_hints or "")

        self._available.setChecked(cache.available if cache.available is not None else True)
        self._archived.setChecked(cache.archived if cache.archived is not None else False)
        self._premium.setChecked(cache.premium_only if cache.premium_only is not None else False)
        self._found.setChecked(cache.found if cache.found is not None else False)
        self._dnf.setChecked(cache.dnf if cache.dnf is not None else False)
        self._favorite.setChecked(cache.favorite_point if cache.favorite_point is not None else False)

    def _validate_and_accept(self) -> None:
        """Validér og gem."""
        gc_code = self._gc_code.text().strip().upper()
        name = self._name.text().strip()

        if not gc_code:
            QMessageBox.warning(self, tr("warning"), tr("wp_val_gc_required"))
            return
        if not gc_code.startswith("GC"):
            QMessageBox.warning(self, tr("warning"), tr("wp_val_gc_invalid"))
            return
        if not name:
            QMessageBox.warning(self, tr("warning"), tr("wp_val_name_required"))
            return

        # Koordinat-feltet er udfyldt men ikke parset korrekt
        coord_text = self._coord_input.text().strip()
        if coord_text and self._parsed_lat is None:
            QMessageBox.warning(self, tr("warning"), tr("coord_conv_parse_error"))
            return

        self.accept()

    def get_data(self) -> dict:
        """Returner formulardata som dict klar til at oprette/opdatere en Cache."""
        return {
            "gc_code":           self._gc_code.text().strip().upper(),
            "name":              self._name.text().strip(),
            "cache_type":        self._cache_type.currentText(),
            "container":         self._container.currentText(),
            "latitude":          self._parsed_lat,
            "longitude":         self._parsed_lon,
            "difficulty":        self._difficulty.value(),
            "terrain":           self._terrain.value(),
            "placed_by":         self._placed_by.text().strip() or None,
            "country":           self._country.text().strip() or None,
            "state":             self._state.text().strip() or None,
            "short_description": self._short_desc.toPlainText().strip() or None,
            "long_description":  self._long_desc.toPlainText().strip() or None,
            "encoded_hints":     self._hints.text().strip() or None,
            "available":         self._available.isChecked(),
            "archived":          self._archived.isChecked(),
            "premium_only":      self._premium.isChecked(),
            "found":             self._found.isChecked(),
            "dnf":               self._dnf.isChecked(),
            "favorite_point":    self._favorite.isChecked(),
        }
