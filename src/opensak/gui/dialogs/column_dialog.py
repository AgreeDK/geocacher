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
from opensak.lang import tr

# Alle tilgængelige kolonner: (felt_id, visningsnavn, bredde, standard_synlig)
# Kolonnestruktur: (felt_id, tr_nøgle, bredde, standard_synlig)
_ALL_COLUMNS_DEF = [
    # Standard synlige kolonner — i GSAK-rækkefølge
    ("user_flag",    "col_user_flag",    30,  True),
    ("gc_code",      "col_gc_code",      80,  True),
    ("name",         "col_name",        260,  True),
    ("cache_type",   "col_type",          28,  True),   # ikon + tooltip, ingen tekst
    ("container",    "col_container",    80,  True),   # størrelses-bar
    ("difficulty",   "col_difficulty",   36,  True),
    ("terrain",      "col_terrain",      36,  True),
    ("distance",     "col_distance",     75,  True),
    ("bearing",      "col_bearing",      70,  True),
    ("found",        "col_found",        36,  True),
    ("favorite",     "col_favorite",     36,  True),
    ("corrected",    "col_corrected",    36, False),
    # Ekstra kolonner (fra)
    ("country",      "col_country",      80, False),
    ("state",        "col_state",       120, False),
    ("county",       "col_county",      100, False),
    ("placed_by",    "col_placed_by",   120, False),
    ("hidden_date",  "col_hidden_date",  90, False),
    ("last_log",     "col_last_log",     90, False),
    ("log_count",    "col_log_count",    70, False),
    ("dnf",          "col_dnf",          36, False),
    ("premium_only", "col_premium",      36, False),
    ("archived",     "col_archived",     36, False),
    # ── Issue #33: GSAK-compatible fields ─────────────────────────────────────
    ("found_date",     "col_found_date",    90, False),
    ("dnf_date",       "col_dnf_date",      90, False),
    ("first_to_find",  "col_first_to_find", 36, False),
    ("favorite_points","col_favorite_points",55, False),
    ("user_sort",      "col_user_sort",     55, False),
    ("user_data_1",    "col_user_data_1",  100, False),
    ("user_data_2",    "col_user_data_2",  100, False),
    ("user_data_3",    "col_user_data_3",  100, False),
    ("user_data_4",    "col_user_data_4",  100, False),
]

def get_all_columns():
    """Returner kolonner med oversatte navne."""
    from opensak.lang import tr
    return [(fid, tr(key), w, default) for fid, key, w, default in _ALL_COLUMNS_DEF]

# Bagudkompatibel alias — bruges af column_dialog internt
ALL_COLUMNS = property(lambda self: get_all_columns()) if False else None  # se get_all_columns()

# Kolonner der altid skal være synlige
ALWAYS_VISIBLE = {"gc_code", "name"}


def get_visible_columns() -> list[str]:
    """Returner liste over synlige kolonne-id'er fra QSettings."""
    s = QSettings("OpenSAK Project", "OpenSAK")
    saved = s.value("columns/visible")
    if saved:
        return list(saved)
    # Standard: vis de kolonner der er markeret som standard
    return [col[0] for col in get_all_columns() if col[3]]


def set_visible_columns(col_ids: list[str]) -> None:
    """Gem liste over synlige kolonne-id'er til QSettings."""
    s = QSettings("OpenSAK Project", "OpenSAK")
    s.setValue("columns/visible", col_ids)
    s.sync()


class ColumnChooserDialog(QDialog):
    """Dialog til at vælge hvilke kolonner der vises i cachelisten."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("column_dialog_title"))
        self.setMinimumSize(360, 460)
        self._visible = set(get_visible_columns())
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(tr("column_dialog_hint")))

        self._list = QListWidget()
        for col_id, col_name, _, _ in get_all_columns():
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
        select_all = QPushButton(tr("column_select_all"))
        select_all.clicked.connect(self._select_all)
        btn_row.addWidget(select_all)

        select_default = QPushButton(tr("column_select_default"))
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
        defaults = {col[0] for col in get_all_columns() if col[3]}
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
