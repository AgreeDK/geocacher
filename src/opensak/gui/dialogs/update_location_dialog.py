"""
src/opensak/gui/dialogs/update_location_dialog.py — Update county/state/country dialog.

Runs a background reverse-geocode pass over caches using Nominatim (OSM),
which is the same boundary data source as project-gc.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import NamedTuple

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit,
    QGroupBox, QRadioButton, QCheckBox,
)

from opensak.lang import tr


# ── Data types ────────────────────────────────────────────────────────────────

class _CacheRow(NamedTuple):
    gc_code: str
    lat: float
    lon: float


@dataclass
class UpdateLocationResult:
    updated: int = 0
    skipped: int = 0
    errors:  int = 0
    error_msgs: list[str] = field(default_factory=list)


# ── Worker ────────────────────────────────────────────────────────────────────

class ReverseGeocodeWorker(QThread):
    """
    Background thread: iterates caches, calls Nominatim, writes results to DB.

    Rate-limited to 1 req/sec (Nominatim ToS).
    """

    progress    = Signal(int, int)          # (current, total)
    row_done    = Signal(str, str)          # (gc_code, log_line)
    all_done    = Signal(object)            # UpdateLocationResult
    cancelled   = Signal(object)            # UpdateLocationResult

    def __init__(self, rows: list[_CacheRow], *, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        from opensak.geocoder import reverse_geocode
        from opensak.db.database import get_session
        from opensak.db.models import Cache

        result = UpdateLocationResult()
        total = len(self._rows)

        for i, row in enumerate(self._rows):
            if self._cancel:
                self.cancelled.emit(result)
                return

            self.progress.emit(i + 1, total)

            loc = reverse_geocode(row.lat, row.lon)
            if loc is None:
                result.errors += 1
                line = tr("update_loc_row_error", gc_code=row.gc_code, msg="network/parse error")
                self.row_done.emit(row.gc_code, line)
            else:
                try:
                    with get_session() as session:
                        cache = session.query(Cache).filter_by(gc_code=row.gc_code).first()
                        if cache:
                            cache.country = loc.country
                            cache.state   = loc.state
                            cache.county  = loc.county
                    result.updated += 1
                    line = tr(
                        "update_loc_row",
                        gc_code=row.gc_code,
                        country=loc.country or "–",
                        state=loc.state or "–",
                        county=loc.county or "–",
                    )
                    self.row_done.emit(row.gc_code, line)
                except Exception as exc:
                    result.errors += 1
                    line = tr("update_loc_row_error", gc_code=row.gc_code, msg=str(exc))
                    self.row_done.emit(row.gc_code, line)

            # Nominatim ToS: max 1 request/second
            if not self._cancel:
                time.sleep(1.0)

        self.all_done.emit(result)


# ── Dialog ────────────────────────────────────────────────────────────────────

class UpdateLocationDialog(QDialog):
    """
    Dialog to update county/state/country via Nominatim reverse geocoding.

    Options:
    - Scope: all caches / only those with missing location data
    - Use corrected coordinates when available
    """

    location_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("update_loc_title"))
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)
        self._worker: ReverseGeocodeWorker | None = None
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Info label
        info = QLabel(tr("update_loc_info"))
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(mid);")
        layout.addWidget(info)

        # ── Scope ─────────────────────────────────────────────────────────────
        scope_box = QGroupBox(tr("update_loc_scope_group"))
        scope_layout = QVBoxLayout(scope_box)

        self._rb_all = QRadioButton(tr("update_loc_scope_all"))
        self._rb_missing = QRadioButton(tr("update_loc_scope_missing"))
        self._rb_missing.setChecked(True)
        scope_layout.addWidget(self._rb_all)
        scope_layout.addWidget(self._rb_missing)

        layout.addWidget(scope_box)

        # ── Options ───────────────────────────────────────────────────────────
        self._cb_corrected = QCheckBox(tr("update_loc_use_corrected"))
        self._cb_corrected.setChecked(True)
        layout.addWidget(self._cb_corrected)

        # ── Progress ──────────────────────────────────────────────────────────
        self._progress_label = QLabel("")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Log ───────────────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText(tr("update_loc_log_placeholder"))
        layout.addWidget(self._log)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._start_btn = QPushButton(tr("update_loc_start_btn"))
        self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton(tr("cancel"))
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._request_cancel)
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch()

        self._close_btn = QPushButton(tr("close"))
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

    # ── Slot helpers ──────────────────────────────────────────────────────────

    def _build_rows(self) -> list[_CacheRow]:
        """Load cache rows from the active DB, applying scope and coord options."""
        from opensak.db.database import get_session
        from opensak.db.models import Cache, UserNote
        from sqlalchemy.orm import joinedload

        use_corrected = self._cb_corrected.isChecked()
        only_missing  = self._rb_missing.isChecked()

        rows: list[_CacheRow] = []
        with get_session() as session:
            query = session.query(Cache)
            if use_corrected:
                query = query.options(joinedload(Cache.user_note))
            if only_missing:
                query = query.filter(
                    (Cache.country == None) | (Cache.country == "") |
                    (Cache.state   == None) | (Cache.state   == "") |
                    (Cache.county  == None) | (Cache.county  == "")
                )
            for cache in query.all():
                # resolve coordinates
                lat, lon = cache.latitude, cache.longitude
                if use_corrected and cache.user_note and cache.user_note.is_corrected:
                    clat = cache.user_note.corrected_lat
                    clon = cache.user_note.corrected_lon
                    if clat is not None and clon is not None:
                        lat, lon = clat, clon

                if lat is None or lon is None:
                    continue
                rows.append(_CacheRow(gc_code=cache.gc_code, lat=lat, lon=lon))

        return rows

    def _start(self) -> None:
        rows = self._build_rows()
        if not rows:
            self._log.setPlainText(tr("update_loc_nothing_to_do"))
            return

        self._start_btn.setEnabled(False)
        self._rb_all.setEnabled(False)
        self._rb_missing.setEnabled(False)
        self._cb_corrected.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._close_btn.setEnabled(False)

        self._progress.setRange(0, len(rows))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._log.clear()
        self._progress_label.setText(tr("update_loc_progress", current=0, total=len(rows)))

        self._worker = ReverseGeocodeWorker(rows)
        self._worker.progress.connect(self._on_progress)
        self._worker.row_done.connect(self._on_row_done)
        self._worker.all_done.connect(self._on_done)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.start()

    def _request_cancel(self) -> None:
        if self._worker:
            self._worker.request_cancel()
        self._cancel_btn.setEnabled(False)

    # ── Worker signals ────────────────────────────────────────────────────────

    def _on_progress(self, current: int, total: int) -> None:
        self._progress.setValue(current)
        self._progress_label.setText(tr("update_loc_progress", current=current, total=total))

    def _on_row_done(self, _gc_code: str, line: str) -> None:
        self._log.append(line)

    def _on_done(self, result: UpdateLocationResult) -> None:
        self._finalize()
        summary = tr(
            "update_loc_done",
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
        )
        self._progress_label.setText(summary)
        self.location_updated.emit()

    def _on_cancelled(self, result: UpdateLocationResult) -> None:
        self._finalize()
        summary = tr("update_loc_cancelled", updated=result.updated)
        self._progress_label.setText(summary)
        if result.updated > 0:
            self.location_updated.emit()

    def _finalize(self) -> None:
        self._start_btn.setEnabled(True)
        self._rb_all.setEnabled(True)
        self._rb_missing.setEnabled(True)
        self._cb_corrected.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._close_btn.setEnabled(True)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
