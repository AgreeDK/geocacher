"""
src/opensak/gui/dialogs/update_location_dialog.py — Update county/state/country dialog.

Two-phase reverse geocoding:
  Phase 1 (always): offline KD-tree (GeoNames), instant, no network.
  Phase 2 (opt-in): online OpenStreetMap lookup, 1 req/sec.

Can be opened two ways:
  - Bulk (no gc_codes): shows scope options, user picks all vs. missing-only.
  - Single/selection (gc_codes list): compact mode, scope group hidden.
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_eta(remaining_seconds: int) -> str:
    if remaining_seconds < 60:
        return tr("update_loc_eta_sec", n=remaining_seconds)
    elif remaining_seconds < 3600:
        m, s = divmod(remaining_seconds, 60)
        return tr("update_loc_eta_min", m=m, s=s)
    else:
        h, rem = divmod(remaining_seconds, 3600)
        m = rem // 60
        return tr("update_loc_eta_hr", h=h, m=m)


# ── Workers ───────────────────────────────────────────────────────────────────

class ReverseGeocodeWorker(QThread):
    """
    Phase 1: offline geocoding using the reverse_geocoder KD-tree (GeoNames).

    Fills country + state + county for all rows in a single batch call.
    No network, no rate limit — runs in under a second for any database size.
    """

    row_done  = Signal(str, str)  # (gc_code, log_line)
    all_done  = Signal(object)    # UpdateLocationResult
    cancelled = Signal(object)    # UpdateLocationResult

    def __init__(self, rows: list[_CacheRow], *, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        from opensak.geocoder import fast_batch_geocode
        from opensak.db.database import get_session
        from opensak.db.models import Cache

        result = UpdateLocationResult()

        if self._cancel:
            self.cancelled.emit(result)
            return

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

        self.all_done.emit(result)


class OnlineLookupWorker(QThread):
    """
    Phase 2: online lookup via OpenStreetMap at 1 request/second.

    Refines county/state/country for each cache using OSM polygon boundaries.
    Requires internet. Only non-None fields are written back, so Phase 1 data
    is never erased by a failed or empty online response.
    """

    row_done  = Signal(str, str)   # (gc_code, log_line)
    progress  = Signal(int, int)   # (done, total)
    all_done  = Signal(object)     # UpdateLocationResult
    cancelled = Signal(object)     # UpdateLocationResult

    def __init__(self, rows: list[_CacheRow], *, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        from opensak.geocoder import nominatim_reverse
        from opensak.db.database import get_session
        from opensak.db.models import Cache

        result = UpdateLocationResult()
        total = len(self._rows)

        for i, row in enumerate(self._rows):
            if self._cancel:
                self.cancelled.emit(result)
                return

            t0 = time.monotonic()
            loc = nominatim_reverse(row.lat, row.lon)
            elapsed = time.monotonic() - t0

            if loc.country is None and loc.state is None and loc.county is None:
                result.skipped += 1
                self.row_done.emit(
                    row.gc_code,
                    tr("update_loc_online_skip", gc_code=row.gc_code),
                )
            else:
                try:
                    with get_session() as session:
                        cache = session.query(Cache).filter_by(gc_code=row.gc_code).first()
                        if cache:
                            if loc.country is not None:
                                cache.country = loc.country
                            if loc.state is not None:
                                cache.state = loc.state
                            if loc.county is not None:
                                cache.county = loc.county
                            result.updated += 1
                            self.row_done.emit(
                                row.gc_code,
                                tr(
                                    "update_loc_online_row",
                                    gc_code=row.gc_code,
                                    county=loc.county or "–",
                                ),
                            )
                except Exception as exc:
                    result.errors += 1
                    self.row_done.emit(
                        "",
                        tr("update_loc_row_error", gc_code=row.gc_code, msg=str(exc)),
                    )

            self.progress.emit(i + 1, total)

            # Maintain 1 req/sec; sleep in small steps to allow cancellation
            if i < total - 1:
                deadline = t0 + 1.0
                while time.monotonic() < deadline:
                    if self._cancel:
                        self.cancelled.emit(result)
                        return
                    time.sleep(0.05)

        self.all_done.emit(result)


# ── Dialog ────────────────────────────────────────────────────────────────────

class UpdateLocationDialog(QDialog):
    """
    Dialog to update county/state/country via reverse geocoding.

    Phase 1 (always active): offline GeoNames KD-tree — instant.
    Phase 2 (opt-in): online OpenStreetMap lookup — 1 req/sec.

    Bulk mode (gc_codes=None): full dialog with scope options and log.
    Single/selection mode (gc_codes list): compact dialog, no log.
    """

    location_updated = Signal()

    def __init__(self, parent=None, *, gc_codes: list[str] | None = None):
        super().__init__(parent)
        self._gc_codes = gc_codes
        self._is_single = gc_codes is not None
        self.setWindowTitle(tr("update_loc_title"))
        self.setMinimumWidth(460)
        self._worker: ReverseGeocodeWorker | OnlineLookupWorker | None = None
        self._pending_rows: list[_CacheRow] = []
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        from opensak.utils import flags
        from opensak.gui.settings import get_settings

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Info label — text changes when the online checkbox is toggled
        self._info_label = QLabel(tr("update_loc_info"))
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: palette(mid);")
        layout.addWidget(self._info_label)

        # ── Scope (bulk mode only) ────────────────────────────────────────────
        self._scope_box = QGroupBox(tr("update_loc_scope_group"))
        scope_layout = QVBoxLayout(self._scope_box)
        self._rb_all = QRadioButton(tr("update_loc_scope_all"))
        self._rb_missing = QRadioButton(tr("update_loc_scope_missing"))
        self._rb_missing.setChecked(True)
        scope_layout.addWidget(self._rb_all)
        scope_layout.addWidget(self._rb_missing)
        layout.addWidget(self._scope_box)

        if self._is_single:
            self._scope_box.setVisible(False)

        # ── Options ───────────────────────────────────────────────────────────
        self._cb_corrected = QCheckBox(tr("update_loc_use_corrected"))
        self._cb_corrected.setChecked(True)
        layout.addWidget(self._cb_corrected)

        # Online lookup checkbox — always visible when flag is on;
        # initial state comes from the Advanced Settings default.
        if flags.update_location:
            self._cb_online = QCheckBox(tr("update_loc_online_cb"))
            self._cb_online.setChecked(get_settings().nominatim_enabled)
            self._cb_online.setToolTip(tr("update_loc_online_tooltip"))
            self._cb_online.stateChanged.connect(self._on_online_toggled)
            layout.addWidget(self._cb_online)
            # Sync info text with initial checkbox state
            self._on_online_toggled()
        else:
            self._cb_online = None

        # ── Progress ──────────────────────────────────────────────────────────
        self._progress_label = QLabel("")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Log (bulk mode only — hidden for single-cache to reduce verbosity) ─
        if not self._is_single:
            self._log = QTextEdit()
            self._log.setReadOnly(True)
            self._log.setPlaceholderText(tr("update_loc_log_placeholder"))
            layout.addWidget(self._log)
            self.setMinimumHeight(420)
        else:
            self._log = None

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

    # ── Dynamic info text ─────────────────────────────────────────────────────

    def _on_online_toggled(self) -> None:
        if self._cb_online and self._cb_online.isChecked():
            self._info_label.setText(tr("update_loc_info_online"))
        else:
            self._info_label.setText(tr("update_loc_info"))

    # ── Row building ──────────────────────────────────────────────────────────

    def _build_rows(self) -> list[_CacheRow]:
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
            self._progress_label.setText(tr("update_loc_nothing_to_do"))
            return

        self._pending_rows = rows
        self._set_controls_enabled(False)

        self._progress.setRange(0, 0)
        self._progress.setVisible(True)
        if self._log:
            self._log.clear()
        self._progress_label.setText(tr("update_loc_running", total=len(rows)))

        self._worker = ReverseGeocodeWorker(rows)
        self._worker.row_done.connect(self._on_row_done)
        self._worker.all_done.connect(self._on_phase1_done)
        self._worker.cancelled.connect(self._on_phase1_cancelled)
        self._worker.start()

    def _start_online_phase(self, rows: list[_CacheRow]) -> None:
        self._progress.setRange(0, len(rows))
        self._progress.setValue(0)
        self._cancel_btn.setEnabled(True)

        self._worker = OnlineLookupWorker(rows)
        self._worker.row_done.connect(self._on_row_done)
        self._worker.progress.connect(self._on_online_progress)
        self._worker.all_done.connect(self._on_online_done)
        self._worker.cancelled.connect(self._on_online_cancelled)
        self._worker.start()

    def _request_cancel(self) -> None:
        if self._worker:
            self._worker.request_cancel()
        self._cancel_btn.setEnabled(False)

    # ── Worker signals — Phase 1 ──────────────────────────────────────────────

    def _on_row_done(self, _gc_code: str, line: str) -> None:
        if self._log:
            self._log.append(line)

    def _on_phase1_done(self, result: UpdateLocationResult) -> None:
        self.location_updated.emit()

        online_requested = self._cb_online is not None and self._cb_online.isChecked()
        if online_requested and self._pending_rows:
            self._progress_label.setText(tr(
                "update_loc_offline_done",
                updated=result.updated,
            ))
            self._start_online_phase(self._pending_rows)
        else:
            self._finalize()
            self._progress_label.setText(tr(
                "update_loc_done",
                updated=result.updated,
                skipped=result.skipped,
                errors=result.errors,
            ))

    def _on_phase1_cancelled(self, result: UpdateLocationResult) -> None:
        self._finalize()
        self._progress_label.setText(tr("update_loc_cancelled", updated=result.updated))
        if result.updated > 0:
            self.location_updated.emit()

    # ── Worker signals — Phase 2 ──────────────────────────────────────────────

    def _on_online_progress(self, done: int, total: int) -> None:
        self._progress.setValue(done)
        eta = _format_eta(total - done)
        self._progress_label.setText(tr(
            "update_loc_online_running",
            done=done,
            total=total,
            eta=eta,
        ))

    def _on_online_done(self, result: UpdateLocationResult) -> None:
        self._finalize()
        self._progress_label.setText(tr(
            "update_loc_online_done",
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
        ))
        self.location_updated.emit()

    def _on_online_cancelled(self, result: UpdateLocationResult) -> None:
        self._finalize()
        self._progress_label.setText(tr(
            "update_loc_online_cancelled",
            updated=result.updated,
        ))
        if result.updated > 0:
            self.location_updated.emit()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._start_btn.setEnabled(enabled)
        self._scope_box.setEnabled(enabled)
        self._cb_corrected.setEnabled(enabled)
        if self._cb_online is not None:
            self._cb_online.setEnabled(enabled)
        self._cancel_btn.setEnabled(not enabled)
        self._close_btn.setEnabled(enabled)

    def _finalize(self) -> None:
        self._progress.setVisible(False)
        self._set_controls_enabled(True)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
