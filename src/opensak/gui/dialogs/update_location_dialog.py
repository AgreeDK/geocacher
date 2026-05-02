"""
src/opensak/gui/dialogs/update_location_dialog.py — Update county/state/country dialog.

Runs a background reverse-geocode pass over caches using Nominatim (OSM),
which is the same boundary data source as project-gc.

Can be opened two ways:
  - Bulk (no gc_codes): shows scope options, user picks all vs. missing-only.
  - Single/selection (gc_codes list): hides scope group, targets only those caches.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit,
    QGroupBox, QRadioButton, QCheckBox,
)

from opensak.lang import tr


# ── Data types ────────────────────────────────────────────────────────────────

class _CacheRow:
    __slots__ = ("gc_code", "lat", "lon")

    def __init__(self, gc_code: str, lat: float, lon: float) -> None:
        self.gc_code = gc_code
        self.lat = lat
        self.lon = lon


@dataclass
class UpdateLocationResult:
    updated: int = 0
    skipped: int = 0
    errors:  int = 0
    error_msgs: list[str] = field(default_factory=list)


# ── Worker ────────────────────────────────────────────────────────────────────

class ReverseGeocodeWorker(QThread):
    """
    Two-phase hybrid geocoding worker.

    Phase 1 — fast (offline, instant):
        Uses reverse_geocoder KD-tree to fill country + state + county
        for ALL rows in a single batch call. No network, no rate limit.

    Phase 2 — refinement (online, 1 req/sec):
        Uses Nominatim to replace the county field with a more accurate
        polygon-based result. User can cancel between phases.
    """

    phase_changed = Signal(int, int)  # (phase_number, total_phases)
    progress      = Signal(int, int)  # (current, total)  — phase 2 only
    row_done      = Signal(str, str)  # (gc_code, log_line)
    all_done      = Signal(object)    # UpdateLocationResult
    cancelled     = Signal(object)    # UpdateLocationResult

    def __init__(self, rows: list[_CacheRow], *, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        from opensak.geocoder import fast_batch_geocode, nominatim_county
        from opensak.db.database import get_session
        from opensak.db.models import Cache

        result = UpdateLocationResult()
        total = len(self._rows)

        # ── Phase 1: fast offline batch ───────────────────────────────────────
        self.phase_changed.emit(1, 2)

        coords = [(row.lat, row.lon) for row in self._rows]
        locations = fast_batch_geocode(coords)

        try:
            with get_session() as session:
                for row, loc in zip(self._rows, locations):
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
            self.row_done.emit("", tr("update_loc_row_error", gc_code="batch", msg=str(exc)))

        if self._cancel:
            self.cancelled.emit(result)
            return

        # ── Phase 2: Nominatim county refinement ──────────────────────────────
        self.phase_changed.emit(2, 2)

        for i, row in enumerate(self._rows):
            if self._cancel:
                self.cancelled.emit(result)
                return

            self.progress.emit(i + 1, total)

            county = nominatim_county(row.lat, row.lon)
            if county is not None:
                try:
                    with get_session() as session:
                        cache = session.query(Cache).filter_by(gc_code=row.gc_code).first()
                        if cache:
                            cache.county = county
                    line = tr(
                        "update_loc_county_refined",
                        gc_code=row.gc_code,
                        county=county,
                    )
                    self.row_done.emit(row.gc_code, line)
                except Exception as exc:
                    result.errors += 1
                    self.row_done.emit(
                        row.gc_code,
                        tr("update_loc_row_error", gc_code=row.gc_code, msg=str(exc)),
                    )

            # Nominatim ToS: max 1 request/second
            if not self._cancel:
                time.sleep(1.0)

        self.all_done.emit(result)


# ── Dialog ────────────────────────────────────────────────────────────────────

class UpdateLocationDialog(QDialog):
    """
    Dialog to update county/state/country via Nominatim reverse geocoding.

    When gc_codes is None: full bulk mode — scope options are shown.
    When gc_codes is a list: targeted mode — scope group is hidden and only
    those specific caches are processed.
    """

    location_updated = Signal()

    def __init__(self, parent=None, *, gc_codes: list[str] | None = None):
        super().__init__(parent)
        self._gc_codes = gc_codes
        self.setWindowTitle(tr("update_loc_title"))
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)
        self._worker: ReverseGeocodeWorker | None = None
        self._setup_ui()

        # In targeted mode, hide the scope controls — they don't apply.
        if gc_codes is not None:
            self._scope_box.setVisible(False)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Info label
        info = QLabel(tr("update_loc_info"))
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(mid);")
        layout.addWidget(info)

        # ── Scope (bulk mode only) ─────────────────────────────────────────────
        self._scope_box = QGroupBox(tr("update_loc_scope_group"))
        scope_layout = QVBoxLayout(self._scope_box)

        self._rb_all = QRadioButton(tr("update_loc_scope_all"))
        self._rb_missing = QRadioButton(tr("update_loc_scope_missing"))
        self._rb_missing.setChecked(True)
        scope_layout.addWidget(self._rb_all)
        scope_layout.addWidget(self._rb_missing)

        layout.addWidget(self._scope_box)

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

    # ── Row building ──────────────────────────────────────────────────────────

    def _build_rows(self) -> list[_CacheRow]:
        """Load cache rows from the active DB, applying scope and coord options."""
        from opensak.db.database import get_session
        from opensak.db.models import Cache
        from sqlalchemy.orm import joinedload

        use_corrected = self._cb_corrected.isChecked()
        only_missing  = self._rb_missing.isChecked()

        rows: list[_CacheRow] = []
        with get_session() as session:
            query = session.query(Cache)
            if use_corrected:
                query = query.options(joinedload(Cache.user_note))

            if self._gc_codes is not None:
                # Targeted mode: restrict to the given gc_codes.
                query = query.filter(Cache.gc_code.in_(self._gc_codes))
            elif only_missing:
                query = query.filter(
                    (Cache.country == None) | (Cache.country == "") |
                    (Cache.state   == None) | (Cache.state   == "") |
                    (Cache.county  == None) | (Cache.county  == "")
                )

            for cache in query.all():
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

    # ── Actions ───────────────────────────────────────────────────────────────

    def _start(self) -> None:
        rows = self._build_rows()
        if not rows:
            self._log.setPlainText(tr("update_loc_nothing_to_do"))
            return

        self._start_btn.setEnabled(False)
        self._scope_box.setEnabled(False)
        self._cb_corrected.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._close_btn.setEnabled(False)

        self._progress.setRange(0, len(rows))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._log.clear()
        self._progress_label.setText(tr("update_loc_progress", current=0, total=len(rows)))

        self._worker = ReverseGeocodeWorker(rows)
        self._worker.phase_changed.connect(self._on_phase_changed)
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

    def _on_phase_changed(self, phase: int, total: int) -> None:
        self._progress_label.setText(tr("update_loc_phase", phase=phase, total=total))
        if phase == 1:
            self._progress.setRange(0, 0)  # indeterminate during fast batch
        else:
            self._progress.setRange(0, len(self._worker._rows))
            self._progress.setValue(0)

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
        self._progress_label.setText(tr("update_loc_cancelled", updated=result.updated))
        if result.updated > 0:
            self.location_updated.emit()

    def _finalize(self) -> None:
        self._start_btn.setEnabled(True)
        self._scope_box.setEnabled(True)
        self._cb_corrected.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._close_btn.setEnabled(True)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
