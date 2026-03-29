"""
src/opensak/gui/dialogs/database_dialog.py — Database manager dialog.
"""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QDialogButtonBox,
    QSizePolicy
)

from opensak.db.manager import DatabaseManager, DatabaseInfo, get_db_manager


class NewDatabaseDialog(QDialog):
    """Dialog til at oprette en ny database."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ny database")
        self.setMinimumWidth(380)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("f.eks. Sjælland, Bornholm 2026…")
        form.addRow("Navn:", self._name_edit)

        layout.addLayout(form)
        layout.addWidget(QLabel(
            "<small style='color:gray'>Databasen gemmes automatisk i app-mappen.<br>"
            "Du kan ændre placeringen nedenfor (valgfrit).</small>"
        ))

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("(standard placering)")
        self._path_edit.setReadOnly(True)
        path_row.addWidget(self._path_edit)
        browse_btn = QPushButton("Vælg…")
        browse_btn.setMaximumWidth(70)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._custom_path: Path | None = None

    def _browse(self) -> None:
        from opensak.config import get_app_data_dir
        path, _ = QFileDialog.getSaveFileName(
            self, "Vælg placering",
            str(get_app_data_dir()),
            "SQLite database (*.db)"
        )
        if path:
            self._custom_path = Path(path)
            self._path_edit.setText(str(self._custom_path))

    def _validate(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Mangler navn", "Indtast et navn til databasen.")
            return
        self.accept()

    @property
    def name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def custom_path(self) -> Path | None:
        return self._custom_path


class DatabaseManagerDialog(QDialog):
    """
    Fuld database manager dialog.
    Viser alle kendte databaser og lader brugeren skifte, oprette,
    omdøbe, kopiere og slette databaser.
    """

    database_switched = Signal(object)   # emits DatabaseInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Administrer databaser")
        self.setMinimumSize(560, 400)
        self._manager = get_db_manager()
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)

        # ── Venstre: database liste ───────────────────────────────────────────
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Databaser:</b>"))

        self._list = QListWidget()
        self._list.setMinimumWidth(220)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._switch_to_selected)
        left.addWidget(self._list)
        layout.addLayout(left)

        # ── Højre: detaljer + knapper ─────────────────────────────────────────
        right = QVBoxLayout()

        # Detaljer
        info_group = QGroupBox("Detaljer")
        info_form = QFormLayout(info_group)
        self._info_name  = QLabel("—")
        self._info_path  = QLabel("—")
        self._info_path.setWordWrap(True)
        self._info_size  = QLabel("—")
        self._info_mod   = QLabel("—")
        info_form.addRow("Navn:",     self._info_name)
        info_form.addRow("Sti:",      self._info_path)
        info_form.addRow("Størrelse:", self._info_size)
        info_form.addRow("Ændret:",   self._info_mod)
        right.addWidget(info_group)

        # Knapper
        btn_layout = QVBoxLayout()

        self._btn_switch = QPushButton("⟵  Skift til denne")
        self._btn_switch.setEnabled(False)
        self._btn_switch.clicked.connect(self._switch_to_selected)
        btn_layout.addWidget(self._btn_switch)

        btn_layout.addSpacing(8)

        self._btn_new = QPushButton("＋  Ny database…")
        self._btn_new.clicked.connect(self._new_database)
        btn_layout.addWidget(self._btn_new)

        self._btn_open = QPushButton("📂  Åbn eksisterende…")
        self._btn_open.clicked.connect(self._open_database)
        btn_layout.addWidget(self._btn_open)

        self._btn_copy = QPushButton("⎘  Kopiér…")
        self._btn_copy.setEnabled(False)
        self._btn_copy.clicked.connect(self._copy_database)
        btn_layout.addWidget(self._btn_copy)

        self._btn_rename = QPushButton("✎  Omdøb…")
        self._btn_rename.setEnabled(False)
        self._btn_rename.clicked.connect(self._rename_database)
        btn_layout.addWidget(self._btn_rename)

        btn_layout.addSpacing(8)

        self._btn_remove = QPushButton("✕  Fjern fra liste")
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_from_list)
        btn_layout.addWidget(self._btn_remove)

        self._btn_delete = QPushButton("🗑  Slet permanent…")
        self._btn_delete.setEnabled(False)
        self._btn_delete.setStyleSheet("color: #c62828;")
        self._btn_delete.clicked.connect(self._delete_database)
        btn_layout.addWidget(self._btn_delete)

        btn_layout.addStretch()

        close_btn = QPushButton("Luk")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        right.addLayout(btn_layout)
        layout.addLayout(right)

    def _refresh_list(self) -> None:
        self._list.clear()
        active = self._manager.active
        for db in self._manager.databases:
            item = QListWidgetItem(db.name)
            item.setData(Qt.ItemDataRole.UserRole, db)
            if db == active:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setText(f"{db.name}  ✓")
            if not db.exists:
                item.setForeground(Qt.GlobalColor.gray)
                item.setToolTip("Filen blev ikke fundet")
            self._list.addItem(item)

    def _selected_db(self) -> DatabaseInfo | None:
        item = self._list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_selection_changed(self) -> None:
        db = self._selected_db()
        is_active = db == self._manager.active if db else False

        if db:
            self._info_name.setText(db.name)
            self._info_path.setText(str(db.path))
            self._info_size.setText(f"{db.size_mb:.2f} MB" if db.exists else "Ikke fundet")
            self._info_mod.setText(
                db.modified.strftime("%d.%m.%Y %H:%M") if db.modified else "—"
            )
        else:
            for lbl in (self._info_name, self._info_path,
                        self._info_size, self._info_mod):
                lbl.setText("—")

        self._btn_switch.setEnabled(db is not None and not is_active and db.exists)
        self._btn_copy.setEnabled(db is not None and db.exists)
        self._btn_rename.setEnabled(db is not None)
        self._btn_remove.setEnabled(db is not None and not is_active)
        self._btn_delete.setEnabled(db is not None and not is_active)

    def _switch_to_selected(self, *_) -> None:
        db = self._selected_db()
        if not db or db == self._manager.active:
            return
        self._manager.switch_to(db)
        self._refresh_list()
        self.database_switched.emit(db)
        QMessageBox.information(
            self, "Database skiftet",
            f"Aktiv database er nu:\n{db.name}"
        )

    def _new_database(self) -> None:
        dlg = NewDatabaseDialog(self)
        if dlg.exec():
            try:
                db = self._manager.new_database(dlg.name, dlg.custom_path)
                self._refresh_list()
                QMessageBox.information(
                    self, "Database oprettet",
                    f"'{db.name}' er oprettet.\n\nBrug 'Skift til denne' for at aktivere den."
                )
            except ValueError as e:
                QMessageBox.warning(self, "Fejl", str(e))

    def _open_database(self) -> None:
        from opensak.config import get_app_data_dir
        path, _ = QFileDialog.getOpenFileName(
            self, "Åbn database",
            str(get_app_data_dir()),
            "SQLite database (*.db)"
        )
        if path:
            try:
                db = self._manager.open_database(Path(path))
                self._refresh_list()
                QMessageBox.information(
                    self, "Database åbnet",
                    f"'{db.name}' er tilføjet til listen."
                )
            except Exception as e:
                QMessageBox.warning(self, "Fejl", str(e))

    def _copy_database(self) -> None:
        db = self._selected_db()
        if not db:
            return
        name, ok = self._simple_input(
            "Kopiér database",
            "Navn på kopien:",
            f"{db.name} (kopi)"
        )
        if ok and name:
            try:
                new_db = self._manager.copy_database(db, name)
                self._refresh_list()
                QMessageBox.information(
                    self, "Kopi oprettet",
                    f"'{new_db.name}' er oprettet som kopi af '{db.name}'."
                )
            except Exception as e:
                QMessageBox.warning(self, "Fejl", str(e))

    def _rename_database(self) -> None:
        db = self._selected_db()
        if not db:
            return
        name, ok = self._simple_input("Omdøb database", "Nyt navn:", db.name)
        if ok and name and name != db.name:
            try:
                self._manager.rename(db, name)
                self._refresh_list()
            except ValueError as e:
                QMessageBox.warning(self, "Fejl", str(e))

    def _remove_from_list(self) -> None:
        db = self._selected_db()
        if not db:
            return
        reply = QMessageBox.question(
            self, "Fjern fra liste",
            f"Fjern '{db.name}' fra listen?\n\nFilen slettes IKKE.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._manager.remove_from_list(db)
                self._refresh_list()
            except ValueError as e:
                QMessageBox.warning(self, "Fejl", str(e))

    def _delete_database(self) -> None:
        db = self._selected_db()
        if not db:
            return
        reply = QMessageBox.warning(
            self, "Slet database permanent",
            f"Er du sikker på at du vil slette '{db.name}' permanent?\n\n"
            f"Filen {db.path} vil blive slettet og kan ikke gendannes!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._manager.delete_database(db)
                self._refresh_list()
            except ValueError as e:
                QMessageBox.warning(self, "Fejl", str(e))

    def _simple_input(self, title: str, label: str,
                      default: str = "") -> tuple[str, bool]:
        """Simpel tekst-input dialog."""
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, title, label, text=default)
        return text.strip(), ok
