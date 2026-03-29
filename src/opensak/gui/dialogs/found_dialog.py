"""
src/opensak/gui/dialogs/found_dialog.py — Dialog til at opdatere
'fundet' status baseret på en reference database (Mine Fund).
"""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit,
    QProgressBar, QGroupBox, QRadioButton,
    QFileDialog, QDialogButtonBox, QButtonGroup
)

from opensak.db.manager import get_db_manager


class UpdateWorker(QThread):
    """Kører opdateringen i baggrundstråd."""
    finished = Signal(object)   # UpdateResult
    error    = Signal(str)

    def __init__(self, reference_path: Path):
        super().__init__()
        self.reference_path = reference_path

    def run(self) -> None:
        try:
            from opensak.db.found_updater import update_found_from_reference
            result = update_found_from_reference(self.reference_path)
            self.finished.emit(result)
        except Exception as e:
            import traceback
            self.error.emit(traceback.format_exc())


class FoundUpdaterDialog(QDialog):
    """
    Dialog der lader brugeren opdatere 'fundet' status i den aktive
    database baseret på en reference database (f.eks. Mine Fund).
    """

    update_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opdater fund fra reference database")
        self.setMinimumWidth(520)
        self._worker: UpdateWorker | None = None
        self._reference_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Forklaring ────────────────────────────────────────────────────────
        info = QLabel(
            "Denne funktion markerer caches som <b>fundet</b> i den aktive database,\n"
            "baseret på GC koder fra en reference database (f.eks. 'Mine Fund').\n\n"
            "Typisk workflow:\n"
            "1. Importer din 'My Finds' Pocket Query i en separat database\n"
            "2. Skift til den database du vil opdatere (f.eks. 'Sjælland')\n"
            "3. Vælg 'Mine Fund' som reference og klik Opdater"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #444; font-size: 11px;")
        layout.addWidget(info)

        # ── Aktiv database ────────────────────────────────────────────────────
        manager = get_db_manager()
        active_name = manager.active.name if manager.active else "Ingen"
        active_lbl = QLabel(f"<b>Aktiv database (opdateres):</b> {active_name}")
        active_lbl.setStyleSheet("color: #1565c0;")
        layout.addWidget(active_lbl)

        # ── Vælg reference database ───────────────────────────────────────────
        ref_group = QGroupBox("Reference database (Mine Fund)")
        ref_layout = QVBoxLayout(ref_group)

        # Radio: vælg fra kendte databaser
        self._rb_known = QRadioButton("Vælg fra kendte databaser:")
        self._rb_known.setChecked(True)
        ref_layout.addWidget(self._rb_known)

        self._db_combo = QComboBox()
        other_dbs = [
            db for db in manager.databases
            if db != manager.active and db.exists
        ]
        for db in other_dbs:
            self._db_combo.addItem(db.name, db.path)
        if not other_dbs:
            self._db_combo.addItem("(Ingen andre databaser)")
            self._db_combo.setEnabled(False)
        ref_layout.addWidget(self._db_combo)

        # Radio: vælg fil
        self._rb_file = QRadioButton("Vælg en .db fil:")
        ref_layout.addWidget(self._rb_file)

        file_row = QHBoxLayout()
        self._file_lbl = QLabel("(ingen fil valgt)")
        self._file_lbl.setStyleSheet("color: gray;")
        file_row.addWidget(self._file_lbl, stretch=1)
        browse_btn = QPushButton("Vælg…")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        ref_layout.addLayout(file_row)

        # Radioknap gruppe
        self._btn_group = QButtonGroup()
        self._btn_group.addButton(self._rb_known, 0)
        self._btn_group.addButton(self._rb_file, 1)
        self._rb_known.toggled.connect(self._on_source_changed)

        layout.addWidget(ref_group)

        # ── Progress og resultat ──────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(130)
        self._log.setPlaceholderText("Resultat vises her efter opdatering…")
        layout.addWidget(self._log)

        # ── Knapper ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._update_btn = QPushButton("⟳  Opdater fund")
        self._update_btn.setStyleSheet("font-weight: bold;")
        self._update_btn.clicked.connect(self._start_update)
        btn_row.addWidget(self._update_btn)

        close_btn = QPushButton("Luk")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _on_source_changed(self, checked: bool) -> None:
        self._db_combo.setEnabled(self._rb_known.isChecked())

    def _browse_file(self) -> None:
        from opensak.config import get_app_data_dir
        path, _ = QFileDialog.getOpenFileName(
            self, "Vælg reference database",
            str(get_app_data_dir()),
            "SQLite database (*.db)"
        )
        if path:
            self._reference_path = Path(path)
            self._file_lbl.setText(self._reference_path.name)
            self._file_lbl.setStyleSheet("")
            self._rb_file.setChecked(True)

    def _get_reference_path(self) -> Path | None:
        if self._rb_file.isChecked():
            return self._reference_path
        else:
            data = self._db_combo.currentData()
            return Path(data) if data else None

    def _start_update(self) -> None:
        ref_path = self._get_reference_path()
        if not ref_path:
            self._log.setPlainText("Vælg en reference database først.")
            return

        manager = get_db_manager()
        if manager.active and ref_path == manager.active.path:
            self._log.setPlainText(
                "Reference databasen må ikke være den samme som den aktive database."
            )
            return

        self._update_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log.setPlainText(f"Opdaterer fra: {ref_path.name}…")

        self._worker = UpdateWorker(ref_path)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, result) -> None:
        self._progress.setVisible(False)
        self._update_btn.setEnabled(True)

        lines = [
            "✓ Opdatering fuldført!\n",
            str(result),
        ]
        if result.errors:
            lines.append(f"\nFejl:")
            for e in result.errors:
                lines.append(f"  - {e}")

        self._log.setPlainText("\n".join(lines))

        if result.updated > 0:
            self.update_completed.emit()

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._update_btn.setEnabled(True)
        self._log.setPlainText(f"✗ Fejl:\n{msg}")
