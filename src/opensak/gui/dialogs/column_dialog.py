"""
src/opensak/gui/dialogs/column_dialog.py — Vælg synlige kolonner i cachelisten.
"""

from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QDialogButtonBox
)
from PySide6.QtCore import QSettings

# Alle tilgængelige kolonner: (felt_id, visningsnavn, bredde, standard_synlig)
ALL_COLUMNS = [
    ("status",       "Status ikon",      22,  True),
    ("gc_code",      "GC Kode",         80,  True),
    ("name",         "Navn",            260,  True),
    ("cache_type",   "Type",            130,  True),
    ("difficulty",   "Sværhedsgrad",     50,  True),
    ("terrain",      "Terræn",           50,  True),
    ("container",    "Container",        80,  True),
    ("country",      "Land",             80,  True),
    ("state",        "Region",           120, False),
    ("distance",     "Afstand",          75,  True),
    ("found",        "Fundet",           55,  True),
    ("placed_by",    "Udlagt af",        120, False),
    ("hidden_date",  "Udlagt dato",      90,  False),
    ("last_log",     "Seneste log",      90,  False),
    ("log_count",    "Antal logs",       70,  False),
    ("dnf",          "DNF",              45,  False),
    ("premium_only", "Premium",          65,  False),
    ("archived",     "Arkiveret",        70,  False),
    ("favorite",     "Favorit ★",        60,  True),
]

# Kolonner der altid skal være synlige
ALWAYS_VISIBLE = {"gc_code", "name"}


def get_visible_columns() -> list[str]:
    """Returner liste over synlige kolonne-id'er fra QSettings."""
    s = QSettings("OpenSAK Project", "OpenSAK")
    saved = s.value("columns/visible")
    if saved:
        return list(saved)
    # Standard: vis de kolonner der er markeret som standard
    return [col[0] for col in ALL_COLUMNS if col[3]]


def set_visible_columns(col_ids: list[str]) -> None:
    """Gem liste over synlige kolonne-id'er til QSettings."""
    s = QSettings("OpenSAK Project", "OpenSAK")
    s.setValue("columns/visible", col_ids)
    s.sync()


class ColumnChooserDialog(QDialog):
    """Dialog til at vælge hvilke kolonner der vises i cachelisten."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vælg kolonner")
        self.setMinimumSize(360, 460)
        self._visible = set(get_visible_columns())
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Vælg hvilke kolonner der skal vises i cachelisten.\n"
            "GC Kode og Navn kan ikke skjules."
        ))

        self._list = QListWidget()
        for col_id, col_name, _, _ in ALL_COLUMNS:
            item = QListWidgetItem(col_name)
            item.setData(Qt.ItemDataRole.UserRole, col_id)
            item.setCheckState(
                Qt.CheckState.Checked
                if col_id in self._visible
                else Qt.CheckState.Unchecked
            )
            if col_id in ALWAYS_VISIBLE:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setForeground(Qt.GlobalColor.gray)
            self._list.addItem(item)
        layout.addWidget(self._list)

        # Vælg alle / Fravælg alle
        btn_row = QHBoxLayout()
        select_all = QPushButton("Vælg alle")
        select_all.clicked.connect(self._select_all)
        btn_row.addWidget(select_all)

        select_default = QPushButton("Standard")
        select_default.clicked.connect(self._select_default)
        btn_row.addWidget(select_default)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_all(self) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setCheckState(Qt.CheckState.Checked)

    def _select_default(self) -> None:
        defaults = {col[0] for col in ALL_COLUMNS if col[3]}
        for i in range(self._list.count()):
            item = self._list.item(i)
            col_id = item.data(Qt.ItemDataRole.UserRole)
            if col_id not in ALWAYS_VISIBLE:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if col_id in defaults
                    else Qt.CheckState.Unchecked
                )

    def _save_and_accept(self) -> None:
        visible = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                visible.append(item.data(Qt.ItemDataRole.UserRole))
        # Sørg for at altid-synlige er med
        for col_id in ALWAYS_VISIBLE:
            if col_id not in visible:
                visible.insert(0, col_id)
        set_visible_columns(visible)
        self.accept()
