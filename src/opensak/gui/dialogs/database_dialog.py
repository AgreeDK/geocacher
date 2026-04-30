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
from opensak.lang import tr


class NewDatabaseDialog(QDialog):
    """Dialog til at oprette en ny database."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("db_new_title"))
        self.setMinimumWidth(380)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("f.eks. Sjælland, Bornholm 2026…")
        self._name_edit.textChanged.connect(self._update_path_preview)
        form.addRow(tr("db_name_label"), self._name_edit)

        layout.addLayout(form)
        info_text = tr("db_new_info").replace("\n", "<br>")
        layout.addWidget(QLabel(f"<small style='color:gray'>{info_text}</small>"))

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(tr("db_default_path"))
        self._path_edit.setReadOnly(True)
        path_row.addWidget(self._path_edit)
        browse_btn = QPushButton(tr("gps_browse"))
        browse_btn.setMaximumWidth(80)
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
        folder = QFileDialog.getExistingDirectory(
            self, tr("db_browse_title"),
            str(get_app_data_dir()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self._custom_path = Path(folder)
            self._update_path_preview()

    def _update_path_preview(self) -> None:
        """Vis fuld filsti (mappe + navn + .db) i sti-feltet."""
        name = self._name_edit.text().strip()
        if self._custom_path:
            filename = f"{name}.db" if name else "(<navn>.db)"
            self._path_edit.setText(str(self._custom_path / filename))

    def _validate(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("warning"), tr("db_name_required"))
            return
        self.accept()

    @property
    def name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def custom_path(self) -> Path | None:
        """Returner fuld filsti (mappe + navn.db), eller None for default placering."""
        if self._custom_path is None:
            return None
        name = self._name_edit.text().strip()
        if not name:
            return self._custom_path  # _validate() fanger dette
        safe_name = "".join(
            c if c.isalnum() or c in "-_ " else "_" for c in name
        ).strip()
        return self._custom_path / f"{safe_name}.db"


class DatabaseManagerDialog(QDialog):
    """
    Fuld database manager dialog.
    Viser alle kendte databaser og lader brugeren skifte, oprette,
    omdøbe, kopiere og slette databaser.
    """

    database_switched = Signal(object)   # emits DatabaseInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("db_dialog_title"))
        self.setMinimumSize(560, 400)
        self._manager = get_db_manager()
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)

        # ── Venstre: database liste ───────────────────────────────────────────
        left = QVBoxLayout()
        left.addWidget(QLabel(f"<b>{tr('db_list_label')}</b>"))

        self._list = QListWidget()
        self._list.setMinimumWidth(220)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._switch_to_selected)
        left.addWidget(self._list)
        layout.addLayout(left)

        # ── Højre: detaljer + knapper ─────────────────────────────────────────
        right = QVBoxLayout()

        # Detaljer
        info_group = QGroupBox(tr("wp_tab_details"))
        info_form = QFormLayout(info_group)
        self._info_name  = QLabel("—")
        self._info_path  = QLabel("—")
        self._info_path.setWordWrap(True)
        self._info_size  = QLabel("—")
        self._info_mod   = QLabel("—")
        info_form.addRow(tr("db_name_label"),     self._info_name)
        info_form.addRow(tr("db_path_label"),      self._info_path)
        info_form.addRow(tr("db_size_label"), self._info_size)
        info_form.addRow(tr("db_modified_label"),   self._info_mod)
        right.addWidget(info_group)

        # Knapper
        btn_layout = QVBoxLayout()

        self._btn_switch = QPushButton(tr("db_switch_btn"))
        self._btn_switch.setEnabled(False)
        self._btn_switch.clicked.connect(self._switch_to_selected)
        btn_layout.addWidget(self._btn_switch)

        btn_layout.addSpacing(8)

        self._btn_new = QPushButton(tr("db_new_btn"))
        self._btn_new.clicked.connect(self._new_database)
        btn_layout.addWidget(self._btn_new)

        self._btn_open = QPushButton(tr("db_open_btn"))
        self._btn_open.clicked.connect(self._open_database)
        btn_layout.addWidget(self._btn_open)

        self._btn_copy = QPushButton(tr("db_copy_btn"))
        self._btn_copy.setEnabled(False)
        self._btn_copy.clicked.connect(self._copy_database)
        btn_layout.addWidget(self._btn_copy)

        self._btn_rename = QPushButton(tr("db_rename_btn"))
        self._btn_rename.setEnabled(False)
        self._btn_rename.clicked.connect(self._rename_database)
        btn_layout.addWidget(self._btn_rename)

        btn_layout.addSpacing(8)

        self._btn_remove = QPushButton(tr("db_remove_btn"))
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_from_list)
        btn_layout.addWidget(self._btn_remove)

        self._btn_delete = QPushButton(tr("db_delete_btn"))
        self._btn_delete.setEnabled(False)
        self._btn_delete.setStyleSheet("color: #c62828;")
        self._btn_delete.clicked.connect(self._delete_database)
        btn_layout.addWidget(self._btn_delete)

        btn_layout.addStretch()

        close_btn = QPushButton(tr("close"))
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
                item.setToolTip(tr("db_file_not_found"))
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
            self._info_size.setText(f"{db.size_mb:.2f} MB" if db.exists else tr("db_not_found"))
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
        # Delete requires: something selected, not active, and file exists on disk
        self._btn_delete.setEnabled(db is not None and not is_active and db.exists)

    def _switch_to_selected(self, *_) -> None:
        db = self._selected_db()
        if not db or db == self._manager.active:
            return
        self._manager.switch_to(db)
        self._refresh_list()
        self.database_switched.emit(db)
        QMessageBox.information(
            self, tr("db_switched_title"),
            tr("db_switched_msg", name=db.name)
        )

    def _new_database(self) -> None:
        dlg = NewDatabaseDialog(self)
        if dlg.exec():
            try:
                db = self._manager.new_database(dlg.name, dlg.custom_path)
                self._refresh_list()
                QMessageBox.information(
                    self, tr("db_created_title"),
                    tr("db_created_msg", name=db.name)
                )
            except ValueError as e:
                QMessageBox.warning(self, tr("warning"), str(e))

    def _open_database(self) -> None:
        from opensak.config import get_app_data_dir
        path, _ = QFileDialog.getOpenFileName(
            self, tr("db_open_browse_title"),
            str(get_app_data_dir()),
            tr("db_file_filter")
        )
        if path:
            try:
                db = self._manager.open_database(Path(path))
                self._refresh_list()
                QMessageBox.information(
                    self, tr("db_opened_title"),
                    tr("db_opened_msg", name=db.name)
                )
            except Exception as e:
                QMessageBox.warning(self, tr("warning"), str(e))

    def _copy_database(self) -> None:
        db = self._selected_db()
        if not db:
            return
        name, ok = self._simple_input(
            tr("db_copy_title"),
            tr("db_copy_name_label"),
            f"{db.name} ({tr('db_copy_suffix')})"
        )
        if ok and name:
            try:
                new_db = self._manager.copy_database(db, name)
                self._refresh_list()
                QMessageBox.information(
                    self, tr("db_copied_title"),
                    tr("db_copied_msg", new_name=new_db.name, orig_name=db.name)
                )
            except Exception as e:
                QMessageBox.warning(self, tr("warning"), str(e))

    def _rename_database(self) -> None:
        db = self._selected_db()
        if not db:
            return
        name, ok = self._simple_input(tr("db_rename_title"), tr("db_rename_label"), db.name)
        if ok and name and name != db.name:
            try:
                self._manager.rename(db, name)
                self._refresh_list()
            except ValueError as e:
                QMessageBox.warning(self, tr("warning"), str(e))

    def _remove_from_list(self) -> None:
        db = self._selected_db()
        if not db:
            return
        reply = QMessageBox.question(
            self, tr("db_remove_title"),
            tr("db_remove_msg", name=db.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._manager.remove_from_list(db)
                self._refresh_list()
            except ValueError as e:
                QMessageBox.warning(self, tr("warning"), str(e))

    def _delete_database(self) -> None:
        db = self._selected_db()
        if not db:
            return

        # Safety guard: active database must never be deleted
        if db == self._manager.active:
            QMessageBox.warning(
                self,
                tr("db_delete_confirm_title"),
                tr("db_delete_active_error", name=db.name),
            )
            return

        reply = QMessageBox.warning(
            self, tr("db_delete_confirm_title"),
            tr("db_delete_confirm_msg", name=db.name, path=db.path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._manager.delete_database(db)
                self._refresh_list()
            except OSError as e:
                # Filer kunne ikke slettes, men db er fjernet fra listen
                self._refresh_list()
                QMessageBox.warning(self, tr("warning"), str(e))
            except ValueError as e:
                QMessageBox.warning(self, tr("warning"), str(e))

    def _simple_input(self, title: str, label: str,
                      default: str = "") -> tuple[str, bool]:
        """Simpel tekst-input dialog."""
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, title, label, text=default)
        return text.strip(), ok
