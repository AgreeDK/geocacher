"""
src/opensak/gui/dialogs/corrected_coords_dialog.py

Dialog til at indtaste eller redigere korrigerede koordinater for en mystery cache.
Understøtter DMM, DMS og DD format via coords-parseren.
"""

from __future__ import annotations
from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QDialogButtonBox, QFrame
)
from PySide6.QtGui import QFont

from opensak.lang import tr
from opensak.coords import format_coords, parse_coords
from opensak.gui.settings import get_settings
from opensak.utils.types import GcCode


class CorrectedCoordsDialog(QDialog):
    """
    Dialog til at indtaste korrigerede koordinater.
    Accepterer DMM, DMS eller DD format.
    """

    def __init__(
        self,
        gc_code: GcCode,
        current_lat: Optional[float] = None,
        current_lon: Optional[float] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._gc_code = gc_code
        self._lat: Optional[float] = None
        self._lon: Optional[float] = None
        self.setWindowTitle(tr("corrected_dialog_title"))
        self.setMinimumWidth(420)
        self._setup_ui(current_lat, current_lon)

    def _setup_ui(
        self, current_lat: Optional[float], current_lon: Optional[float]
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Overskrift
        title = QLabel(tr("corrected_dialog_heading", gc_code=self._gc_code))
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        layout.addWidget(title)

        # Vejledning
        hint = QLabel(tr("corrected_dialog_hint"))
        hint.setStyleSheet("color: gray; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Input felt
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.Shape.StyledPanel)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)

        input_label = QLabel(tr("corrected_dialog_input_label"))
        input_layout.addWidget(input_label)

        self._input = QLineEdit()
        self._input.setPlaceholderText(tr("corrected_dialog_placeholder"))

        if current_lat is not None and current_lon is not None:
            fmt = get_settings().coord_format
            self._input.setText(format_coords(current_lat, current_lon, fmt))

        input_layout.addWidget(self._input)

        # Parsed preview
        self._preview = QLabel("")
        self._preview.setStyleSheet("color: #2e7d32; font-size: 10px;")
        self._preview.setWordWrap(True)
        input_layout.addWidget(self._preview)

        layout.addWidget(input_frame)

        # Fejlbesked
        self._error_lbl = QLabel("")
        self._error_lbl.setStyleSheet("color: #c62828; font-size: 10px;")
        self._error_lbl.setWordWrap(True)
        layout.addWidget(self._error_lbl)

        # Knapper
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        self._ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setEnabled(False)
        layout.addWidget(btn_box)

        self._input.textChanged.connect(self._on_input_changed)
        if self._input.text():
            self._on_input_changed(self._input.text())

    def _on_input_changed(self, text: str) -> None:
        """Parse koordinat-input og vis preview."""
        text = text.strip()
        if not text:
            self._preview.setText("")
            self._error_lbl.setText("")
            self._ok_btn.setEnabled(False)
            self._lat = None
            self._lon = None
            return

        try:
            lat, lon = parse_coords(text)
            self._lat = lat
            self._lon = lon
            # Vis alle formater som preview
            dmm = format_coords(lat, lon, "dmm")
            dd  = format_coords(lat, lon, "dd")
            self._preview.setText(f"✓  {dmm}   ({dd})")
            self._preview.setStyleSheet("color: #2e7d32; font-size: 10px;")
            self._error_lbl.setText("")
            self._ok_btn.setEnabled(True)
        except (ValueError, TypeError):
            self._lat = None
            self._lon = None
            self._preview.setText("")
            self._error_lbl.setText(tr("corrected_dialog_parse_error"))
            self._ok_btn.setEnabled(False)

    def _on_accept(self) -> None:
        if self._lat is not None and self._lon is not None:
            self.accept()

    def get_coords(self) -> Tuple[Optional[float], Optional[float]]:
        """Returner de parsede koordinater."""
        return self._lat, self._lon
