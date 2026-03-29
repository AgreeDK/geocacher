"""
src/opensak/gui/dialogs/import_dialog.py — GPX / PQ zip import dialog.
"""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QProgressBar,
    QTextEdit, QDialogButtonBox
)

from opensak.gui.settings import get_settings


class ImportWorker(QThread):
    """Runs the import in a background thread so the UI stays responsive."""
    finished = Signal(object)   # emits ImportResult
    error    = Signal(str)

    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def run(self) -> None:
        try:
            from opensak.db.database import init_db, get_session
            from opensak.importer import import_gpx, import_zip

            # Ensure DB is initialised in this thread too
            init_db()

            with get_session() as session:
                if self.path.suffix.lower() == ".zip":
                    result = import_zip(self.path, session)
                else:
                    result = import_gpx(self.path, session)

            self.finished.emit(result)
        except Exception as e:
            import traceback
            self.error.emit(traceback.format_exc())


class ImportDialog(QDialog):
    """Dialog for importing GPX or PQ zip files."""

    import_completed = Signal()   # emitted when import finishes successfully

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importer GPX / Pocket Query")
        self.setMinimumWidth(500)
        self._worker: ImportWorker | None = None
        self._selected_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── File selection ────────────────────────────────────────────────────
        file_lbl = QLabel("Vælg en GPX fil eller Pocket Query ZIP fil:")
        layout.addWidget(file_lbl)

        file_row = QHBoxLayout()
        self._path_lbl = QLabel("(ingen fil valgt)")
        self._path_lbl.setStyleSheet("color: gray;")
        file_row.addWidget(self._path_lbl, stretch=1)

        self._browse_btn = QPushButton("Vælg fil…")
        self._browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self._browse_btn)
        layout.addLayout(file_row)

        # ── Progress ──────────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Result log ────────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(180)
        self._log.setPlaceholderText("Importresultat vises her…")
        layout.addWidget(self._log)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._import_btn = QPushButton("Importer")
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._start_import)
        btn_row.addWidget(self._import_btn)

        self._close_btn = QPushButton("Luk")
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

    def _browse(self) -> None:
        settings = get_settings()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vælg GPX eller ZIP fil",
            settings.last_import_dir,
            "Geocaching filer (*.gpx *.zip);;GPX filer (*.gpx);;ZIP filer (*.zip)"
        )
        if path:
            self._selected_path = Path(path)
            self._path_lbl.setText(self._selected_path.name)
            self._path_lbl.setStyleSheet("")
            self._import_btn.setEnabled(True)
            settings.last_import_dir = str(self._selected_path.parent)

    def _start_import(self) -> None:
        if not self._selected_path:
            return

        self._import_btn.setEnabled(False)
        self._browse_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._log.setPlainText(f"Importerer {self._selected_path.name}…")

        self._worker = ImportWorker(self._selected_path)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, result) -> None:
        self._progress.setVisible(False)
        self._browse_btn.setEnabled(True)

        lines = [
            f"✓ Import fuldført: {self._selected_path.name}",
            f"",
            f"  Nye caches:      {result.created}",
            f"  Opdaterede:      {result.updated}",
            f"  Waypoints:       {result.waypoints}",
            f"  Sprunget over:   {result.skipped}",
        ]
        if result.errors:
            lines.append(f"\n  Fejl ({len(result.errors)}):")
            for e in result.errors[:10]:
                lines.append(f"    - {e}")

        self._log.setPlainText("\n".join(lines))
        self._import_btn.setText("Importer igen")
        self._import_btn.setEnabled(True)

        if result.created > 0 or result.updated > 0:
            self.import_completed.emit()

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._browse_btn.setEnabled(True)
        self._import_btn.setEnabled(True)
        self._log.setPlainText(f"✗ Fejl under import:\n{msg}")
