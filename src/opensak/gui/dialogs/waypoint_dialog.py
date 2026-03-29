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


# ── Konstanter ────────────────────────────────────────────────────────────────

CACHE_TYPES = [
    "Traditional Cache",
    "Multi-cache",
    "Unknown Cache",
    "Letterbox Hybrid",
    "Wherigo Cache",
    "Event Cache",
    "Mega-Event Cache",
    "Earthcache",
    "Virtual Cache",
    "Webcam Cache",
]

CONTAINER_SIZES = [
    "Nano",
    "Micro",
    "Small",
    "Regular",
    "Large",
    "Other",
    "Not chosen",
]


class WaypointDialog(QDialog):
    """
    Dialog til at tilføje eller redigere en cache manuelt.
    """

    def __init__(self, parent=None, cache: Optional[Cache] = None):
        super().__init__(parent)
        self._cache = cache
        self._is_edit = cache is not None
        self.setWindowTitle("Rediger cache" if self._is_edit else "Tilføj cache")
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
        self._gc_code.setPlaceholderText("f.eks. GC12345")
        if self._is_edit:
            self._gc_code.setReadOnly(True)
            self._gc_code.setStyleSheet("color: gray;")
        basic_layout.addRow("GC Kode *:", self._gc_code)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Navn på cachen")
        basic_layout.addRow("Navn *:", self._name)

        self._cache_type = QComboBox()
        self._cache_type.addItems(CACHE_TYPES)
        basic_layout.addRow("Type *:", self._cache_type)

        self._container = QComboBox()
        self._container.addItems(CONTAINER_SIZES)
        basic_layout.addRow("Container:", self._container)

        # Koordinater
        coord_group = QGroupBox("Koordinater")
        coord_layout = QFormLayout(coord_group)

        self._lat = QDoubleSpinBox()
        self._lat.setRange(-90.0, 90.0)
        self._lat.setDecimals(6)
        self._lat.setSingleStep(0.0001)
        coord_layout.addRow("Breddegrad *:", self._lat)

        self._lon = QDoubleSpinBox()
        self._lon.setRange(-180.0, 180.0)
        self._lon.setDecimals(6)
        self._lon.setSingleStep(0.0001)
        coord_layout.addRow("Længdegrad *:", self._lon)

        basic_layout.addRow(coord_group)

        # D/T
        dt_layout = QHBoxLayout()
        self._difficulty = QDoubleSpinBox()
        self._difficulty.setRange(1.0, 5.0)
        self._difficulty.setSingleStep(0.5)
        self._difficulty.setDecimals(1)
        self._difficulty.setValue(1.5)
        dt_layout.addWidget(QLabel("Sværhedsgrad:"))
        dt_layout.addWidget(self._difficulty)
        dt_layout.addSpacing(16)

        self._terrain = QDoubleSpinBox()
        self._terrain.setRange(1.0, 5.0)
        self._terrain.setSingleStep(0.5)
        self._terrain.setDecimals(1)
        self._terrain.setValue(1.5)
        dt_layout.addWidget(QLabel("Terræn:"))
        dt_layout.addWidget(self._terrain)
        dt_layout.addStretch()
        basic_layout.addRow("D / T:", dt_layout)

        tabs.addTab(basic, "Grundlæggende")

        # ── Fane 2: Detaljer ──────────────────────────────────────────────────
        details = QWidget()
        details_layout = QFormLayout(details)
        details_layout.setSpacing(8)

        self._placed_by = QLineEdit()
        self._placed_by.setPlaceholderText("Udlæggerens brugernavn")
        details_layout.addRow("Udlagt af:", self._placed_by)

        self._country = QLineEdit()
        self._country.setPlaceholderText("f.eks. Denmark")
        details_layout.addRow("Land:", self._country)

        self._state = QLineEdit()
        self._state.setPlaceholderText("f.eks. Zealand")
        details_layout.addRow("Region/stat:", self._state)

        self._short_desc = QTextEdit()
        self._short_desc.setMaximumHeight(80)
        self._short_desc.setPlaceholderText("Kort beskrivelse...")
        details_layout.addRow("Kort beskr.:", self._short_desc)

        self._long_desc = QTextEdit()
        self._long_desc.setMaximumHeight(120)
        self._long_desc.setPlaceholderText("Lang beskrivelse...")
        details_layout.addRow("Lang beskr.:", self._long_desc)

        self._hints = QLineEdit()
        self._hints.setPlaceholderText("Hint til cachen")
        details_layout.addRow("Hint:", self._hints)

        tabs.addTab(details, "Detaljer")

        # ── Fane 3: Status ────────────────────────────────────────────────────
        status = QWidget()
        status_layout = QFormLayout(status)
        status_layout.setSpacing(8)

        self._available = QCheckBox("Tilgængelig")
        self._available.setChecked(True)
        status_layout.addRow("Status:", self._available)

        self._archived = QCheckBox("Arkiveret")
        status_layout.addRow("", self._archived)

        self._premium = QCheckBox("Kun premium medlemmer")
        status_layout.addRow("", self._premium)

        self._found = QCheckBox("Fundet af mig")
        status_layout.addRow("Personligt:", self._found)

        self._dnf = QCheckBox("DNF (Did Not Find)")
        status_layout.addRow("", self._dnf)

        self._favorite = QCheckBox("Favorit ★")
        status_layout.addRow("", self._favorite)

        tabs.addTab(status, "Status")

        layout.addWidget(tabs)

        # ── Knapper ───────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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

        if cache.latitude:
            self._lat.setValue(cache.latitude)
        if cache.longitude:
            self._lon.setValue(cache.longitude)
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
            QMessageBox.warning(self, "Mangler data", "GC Kode er påkrævet.")
            return
        if not gc_code.startswith("GC"):
            QMessageBox.warning(self, "Ugyldig GC Kode", "GC Kode skal starte med 'GC'.")
            return
        if not name:
            QMessageBox.warning(self, "Mangler data", "Navn er påkrævet.")
            return

        self.accept()

    def get_data(self) -> dict:
        """Returner formulardata som dict klar til at oprette/opdatere en Cache."""
        return {
            "gc_code":           self._gc_code.text().strip().upper(),
            "name":              self._name.text().strip(),
            "cache_type":        self._cache_type.currentText(),
            "container":         self._container.currentText(),
            "latitude":          self._lat.value(),
            "longitude":         self._lon.value(),
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
