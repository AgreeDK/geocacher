"""
src/opensak/gui/dialogs/gps_dialog.py — GPS export dialog.

Finder automatisk tilsluttede Garmin enheder og eksporterer
valgte/filtrerede caches som GPX fil direkte til enheden.
"""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from opensak.lang import tr
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTextEdit,
    QProgressBar, QGroupBox, QRadioButton,
    QFileDialog, QButtonGroup, QSpinBox,
    QCheckBox, QMessageBox
)


from opensak.gui.icon import OpenSAKMessageBox as QMessageBox
class DeleteWorker(QThread):
    """Kører sletning af GPX filer i baggrundstråd."""
    finished = Signal(object)
    error    = Signal(str)

    def __init__(self, device_path: Path):
        super().__init__()
        self.device_path = device_path

    def run(self) -> None:
        try:
            from opensak.gps.garmin import delete_gpx_files
            result = delete_gpx_files(self.device_path)
            self.finished.emit(result)
        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())


class ExportWorker(QThread):
    """Kører eksporten i baggrundstråd."""
    finished = Signal(object)
    error    = Signal(str)

    def __init__(self, caches, device_path, filename, max_caches):
        super().__init__()
        self.caches      = caches
        self.device_path = device_path
        self.filename    = filename
        self.max_caches  = max_caches

    def run(self) -> None:
        try:
            from opensak.gps.garmin import export_to_device, export_to_file
            caches = self.caches[:self.max_caches] if self.max_caches > 0 else self.caches

            if self.device_path.is_dir() and (self.device_path / "Garmin").exists():
                result = export_to_device(caches, self.device_path, self.filename)
            else:
                result = export_to_file(caches, self.device_path / f"{self.filename}.gpx")

            self.finished.emit(result)
        except Exception as e:
            import traceback
            self.error.emit(traceback.format_exc())


class GpsExportDialog(QDialog):
    """Dialog til at eksportere caches til GPS enhed."""

    def __init__(self, parent=None, caches=None):
        super().__init__(parent)
        self.setWindowTitle(tr("gps_dialog_title"))
        self.setMinimumWidth(520)
        self._caches = caches or []
        self._worker = None
        self._delete_worker = None
        self._setup_ui()
        self._scan_devices()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Info ──────────────────────────────────────────────────────────────
        count_lbl = QLabel(tr("gps_caches_ready", count=len(self._caches)))
        layout.addWidget(count_lbl)

        # ── Destination ───────────────────────────────────────────────────────
        dest_group = QGroupBox(tr("gps_dest_group"))
        dest_layout = QVBoxLayout(dest_group)

        # Auto-detekterede enheder
        self._rb_device = QRadioButton(tr("gps_rb_device"))
        self._rb_device.setChecked(True)
        dest_layout.addWidget(self._rb_device)

        device_row = QHBoxLayout()
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(300)
        device_row.addWidget(self._device_combo)

        self._scan_btn = QPushButton(tr("gps_scan_btn"))
        self._scan_btn.setMaximumWidth(80)
        self._scan_btn.clicked.connect(self._scan_devices)
        device_row.addWidget(self._scan_btn)
        dest_layout.addLayout(device_row)

        self._device_info = QLabel("")
        self._device_info.setWordWrap(True)
        self._device_info.setStyleSheet("color: gray; font-size: 10px;")
        dest_layout.addWidget(self._device_info)

        # Gem som fil
        self._rb_file = QRadioButton(tr("gps_rb_file"))
        dest_layout.addWidget(self._rb_file)

        file_row = QHBoxLayout()
        self._file_path = QLineEdit()
        self._file_path.setPlaceholderText(tr("gps_file_placeholder"))
        self._file_path.setReadOnly(True)
        file_row.addWidget(self._file_path)
        browse_btn = QPushButton(tr("gps_browse"))
        browse_btn.setMaximumWidth(80)
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        dest_layout.addLayout(file_row)

        # Radioknap gruppe
        self._btn_group = QButtonGroup()
        self._btn_group.addButton(self._rb_device, 0)
        self._btn_group.addButton(self._rb_file, 1)
        self._rb_device.toggled.connect(self._on_mode_changed)

        layout.addWidget(dest_group)

        # ── Indstillinger ─────────────────────────────────────────────────────
        opt_group = QGroupBox(tr("gps_opt_group"))
        opt_layout = QVBoxLayout(opt_group)

        # Filnavn
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(tr("gps_filename_label")))
        self._filename = QLineEdit("opensak")
        self._filename.setMaximumWidth(200)
        name_row.addWidget(self._filename)
        name_row.addWidget(QLabel(".gpx"))
        name_row.addStretch()
        opt_layout.addLayout(name_row)

        # Max antal caches
        max_row = QHBoxLayout()
        max_row.addWidget(QLabel(tr("gps_max_label")))
        self._max_caches = QSpinBox()
        self._max_caches.setRange(0, 5000)
        self._max_caches.setValue(500)
        self._max_caches.setSpecialValueText(tr("gps_max_all"))
        self._max_caches.setMaximumWidth(100)
        max_row.addWidget(self._max_caches)
        max_row.addWidget(QLabel(tr("gps_max_hint")))
        max_row.addStretch()
        opt_layout.addLayout(max_row)

        # Slet eksisterende GPX filer
        self._cb_delete_gpx = QCheckBox(
            tr("gps_delete_cb")
        )
        self._cb_delete_gpx.setToolTip(
            "Sletter alle .gpx filer i Garmin/GPX mappen på enheden\n"
            "inden den nye fil uploades. Virker kun ved direkte GPS-upload."
        )
        opt_layout.addWidget(self._cb_delete_gpx)

        layout.addWidget(opt_group)

        # ── Progress og resultat ──────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setPlaceholderText(tr("gps_log_placeholder"))
        layout.addWidget(self._log)

        # ── Knapper ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._export_btn = QPushButton(tr("gps_export_btn"))
        self._export_btn.setStyleSheet("font-weight: bold;")
        self._export_btn.clicked.connect(self._start_export)
        btn_row.addWidget(self._export_btn)

        close_btn = QPushButton(tr("close"))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._selected_file_path: Path | None = None

    def _scan_devices(self) -> None:
        """Scan for tilsluttede Garmin enheder."""
        from opensak.gps.garmin import find_garmin_devices
        self._device_combo.clear()

        self._scan_btn.setText(tr("gps_scan_scanning"))
        self._scan_btn.setEnabled(False)

        devices = find_garmin_devices()

        if devices:
            for dev in devices:
                self._device_combo.addItem(str(dev), dev)
            self._device_info.setText(
                tr("gps_devices_found", count=len(devices))
            )
            self._device_info.setStyleSheet("color: #2e7d32; font-size: 10px;")
            self._export_btn.setEnabled(True)
        else:
            self._device_combo.addItem(tr("gps_no_device"))
            self._device_info.setText(tr("gps_no_device_hint"))
            self._device_info.setStyleSheet("color: #c62828; font-size: 10px;")
            self._rb_file.setChecked(True)

        self._scan_btn.setText(tr("gps_scan_btn"))
        self._scan_btn.setEnabled(True)

    def _on_mode_changed(self, device_checked: bool) -> None:
        self._device_combo.setEnabled(device_checked)
        self._scan_btn.setEnabled(device_checked)
        self._cb_delete_gpx.setEnabled(device_checked)
        if not device_checked:
            self._cb_delete_gpx.setChecked(False)

    def _browse_file(self) -> None:
        from opensak.config import get_app_data_dir
        path, _ = QFileDialog.getSaveFileName(
            self, "Gem GPX fil",
            str(Path.home()),
            "GPX filer (*.gpx)"
        )
        if path:
            p = Path(path)
            self._selected_file_path = p.parent
            self._file_path.setText(str(p))
            self._filename.setText(p.stem)
            self._rb_file.setChecked(True)

    def _get_destination(self) -> Path | None:
        if self._rb_device.isChecked():
            data = self._device_combo.currentData()
            return Path(data) if data else None
        else:
            if self._selected_file_path:
                return self._selected_file_path
            return Path.home()

    def _start_export(self) -> None:
        dest = self._get_destination()
        if not dest:
            self._log.setPlainText(tr("gps_no_dest"))
            return

        filename  = self._filename.text().strip() or "opensak"
        max_caches = self._max_caches.value()
        do_delete  = (
            self._cb_delete_gpx.isChecked()
            and self._rb_device.isChecked()
        )

        # ── Bekræft sletning ──────────────────────────────────────────────────
        if do_delete:
            from opensak.gps.garmin import get_garmin_gpx_path
            gpx_dir = get_garmin_gpx_path(dest)
            existing = list(gpx_dir.glob("*.gpx")) if gpx_dir.exists() else []
            count    = len(existing)

            msg = QMessageBox(self)
            msg.setWindowTitle(tr("gps_confirm_delete_title"))
            msg.setIcon(QMessageBox.Icon.Warning)
            if count > 0:
                msg.setText(
                    tr("gps_confirm_delete_msg", count=count)
                )
                details = "\n".join(f.name for f in existing)
                msg.setDetailedText(tr("gps_delete_file_list", files=details))
            else:
                msg.setText(
                    tr("gps_confirm_no_files_msg")
                )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if msg.exec() != QMessageBox.StandardButton.Ok:
                return

        self._export_btn.setEnabled(False)
        self._progress.setVisible(True)

        if do_delete:
            self._log.setPlainText(tr("gps_deleting"))
            self._delete_worker = DeleteWorker(dest)
            self._delete_worker.finished.connect(
                lambda res: self._on_delete_finished(res, dest, filename, max_caches)
            )
            self._delete_worker.error.connect(self._on_error)
            self._delete_worker.start()
        else:
            self._run_export(dest, filename, max_caches)

    def _on_delete_finished(
        self,
        delete_result,
        dest: Path,
        filename: str,
        max_caches: int,
    ) -> None:
        """Kaldt når sletning er færdig — fortsæt med export."""
        self._log.setPlainText(
            str(delete_result) + "\n\nEksporterer caches…"
        )
        self._run_export(dest, filename, max_caches)

    def _run_export(self, dest: Path, filename: str, max_caches: int) -> None:
        """Start selve export-arbejderen."""
        self._log.append(tr("gps_exporting", count=len(self._caches)))
        self._worker = ExportWorker(self._caches, dest, filename, max_caches)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, result) -> None:
        self._progress.setVisible(False)
        self._export_btn.setEnabled(True)
        self._log.setPlainText(str(result))

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._export_btn.setEnabled(True)
        self._log.setPlainText(f"✗ Fejl:\n{msg}")
