"""
src/opensak/gui/cache_detail.py — Cache detail panel (right side).
Shows name, type, D/T, description, hints and recent logs.
"""

from __future__ import annotations
import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QTabWidget, QFrame, QSizePolicy,
    QPushButton
)
from PySide6.QtGui import QFont

from opensak.db.models import Cache


class CacheDetailPanel(QWidget):
    """Displays full details for a single selected cache."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.clear()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)

        # ── Header ────────────────────────────────────────────────────────────
        self._title = QLabel("Vælg en cache")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self._title.setFont(font)
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        # ── Meta row (GC code | Type | D/T | Container | Country) ────────────
        meta_frame = QFrame()
        meta_frame.setFrameShape(QFrame.Shape.StyledPanel)
        meta_layout = QHBoxLayout(meta_frame)
        meta_layout.setContentsMargins(6, 4, 6, 4)
        meta_layout.setSpacing(16)

        self._gc_code_lbl  = self._meta_label("—")
        self._gc_code_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gc_code_lbl.setToolTip("Klik for at åbne på geocaching.com")
        self._gc_code_lbl.mousePressEvent = self._open_on_geocaching
        self._type_lbl     = self._meta_label("—")
        self._dt_lbl       = self._meta_label("—")
        self._container_lbl = self._meta_label("—")
        self._country_lbl  = self._meta_label("—")
        self._coords_lbl   = self._meta_label("—")
        self._coords_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._coords_lbl.setToolTip("Klik for at åbne i Google Maps")
        self._coords_lbl.mousePressEvent = self._open_in_maps

        for lbl, caption in [
            (self._gc_code_lbl,   "GC Kode"),
            (self._type_lbl,      "Type"),
            (self._dt_lbl,        "D / T"),
            (self._container_lbl, "Container"),
            (self._country_lbl,   "Land"),
            (self._coords_lbl,    "Koordinater"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(1)
            cap = QLabel(caption)
            cap.setStyleSheet("color: gray; font-size: 10px;")
            col.addWidget(cap)
            col.addWidget(lbl)
            meta_layout.addLayout(col)

        meta_layout.addStretch()
        layout.addWidget(meta_frame)

        # ── Placed by / hidden date ───────────────────────────────────────────
        self._placed_lbl = QLabel("")
        self._placed_lbl.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._placed_lbl)

        # ── Tabs: Description | Hint | Logs ───────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._desc_browser = QTextBrowser()
        self._desc_browser.setOpenExternalLinks(True)
        self._tabs.addTab(self._desc_browser, "Beskrivelse")

        hint_widget = QWidget()
        hint_layout = QVBoxLayout(hint_widget)
        hint_layout.setContentsMargins(0, 4, 0, 0)
        hint_layout.setSpacing(4)

        hint_btn_row = QHBoxLayout()
        self._decode_btn = QPushButton("🔓  Dekod hint (ROT13)")
        self._decode_btn.setMaximumWidth(200)
        self._decode_btn.clicked.connect(self._toggle_hint_decode)
        self._hint_decoded = False
        hint_btn_row.addWidget(self._decode_btn)
        hint_btn_row.addStretch()
        hint_layout.addLayout(hint_btn_row)

        self._hint_browser = QTextBrowser()
        hint_layout.addWidget(self._hint_browser)
        self._tabs.addTab(hint_widget, "Hint")

        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.setSpacing(4)

        # Søgefelt til logs
        from PySide6.QtWidgets import QLineEdit
        log_search_row = QHBoxLayout()
        self._log_search = QLineEdit()
        self._log_search.setPlaceholderText("Søg i logs…")
        self._log_search.setMaximumWidth(250)
        self._log_search.textChanged.connect(self._filter_logs)
        log_search_row.addWidget(self._log_search)
        log_search_row.addStretch()
        log_layout.addLayout(log_search_row)

        self._log_browser = QTextBrowser()
        log_layout.addWidget(self._log_browser)
        self._tabs.addTab(log_widget, "Logs")

        layout.addWidget(self._tabs)

    def _meta_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        lbl.setFont(font)
        return lbl

    def _filter_logs(self, text: str) -> None:
        """Filtrer logs baseret på søgetekst."""
        if hasattr(self, '_cached_logs'):
            self._render_log_html(self._cached_logs, filter_text=text.lower())

    def _toggle_hint_decode(self) -> None:
        self._hint_decoded = not self._hint_decoded
        if self._hint_decoded:
            decoded = self._raw_hint.translate(
                str.maketrans(
                    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                    'NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm'
                )
            ) if self._raw_hint else ""
            self._hint_browser.setPlainText(decoded)
            self._decode_btn.setText("🔒  Skjul hint")
        else:
            self._hint_browser.setPlainText(self._raw_hint or "(Intet hint)")
            self._decode_btn.setText("🔓  Dekod hint (ROT13)")

    def _open_in_maps(self, event=None) -> None:
        """Åbn koordinater i kortapp i standard browseren."""
        if hasattr(self, '_current_lat') and self._current_lat is not None:
            from opensak.gui.settings import get_settings
            url = get_settings().get_maps_url(self._current_lat, self._current_lon)
            webbrowser.open(url)

    def _open_on_geocaching(self, event=None) -> None:
        """Åbn cache-siden på geocaching.com i standard browseren."""
        if hasattr(self, '_current_gc_code') and self._current_gc_code:
            url = f"https://coord.info/{self._current_gc_code}"
            webbrowser.open(url)

    def clear(self) -> None:
        self._current_gc_code = None
        self._current_lat = None
        self._current_lon = None
        self._coords_lbl.setStyleSheet("")
        self._title.setText("Vælg en cache fra listen")
        self._gc_code_lbl.setText("—")
        self._gc_code_lbl.setStyleSheet("")
        self._current_gc_code = None
        self._current_lat = None
        self._current_lon = None
        self._coords_lbl.setStyleSheet("")
        self._type_lbl.setText("—")
        self._dt_lbl.setText("—")
        self._container_lbl.setText("—")
        self._country_lbl.setText("—")
        self._coords_lbl.setText("—")
        self._placed_lbl.setText("")
        self._desc_browser.setHtml("")
        self._hint_browser.setPlainText("")
        self._log_browser.setHtml("")
        self._raw_hint = ""
        self._hint_decoded = False
        self._decode_btn.setText("🔓  Dekod hint (ROT13)")
        self._log_search.setText("")
        self._cached_logs = []

    def show_cache(self, cache: Cache) -> None:
        """Populate the panel with data from *cache*."""
        # Title
        found_mark = " ✓" if cache.found else ""
        archived_mark = " [ARKIVERET]" if cache.archived else ""
        self._title.setText(f"{cache.name}{found_mark}{archived_mark}")

        # Meta — GC kode som klikbart link
        gc = cache.gc_code or "—"
        self._gc_code_lbl.setText(gc)
        self._gc_code_lbl.setStyleSheet(
            "color: #1565c0; text-decoration: underline; font-weight: bold;"
            if cache.gc_code else ""
        )
        self._current_gc_code = cache.gc_code
        self._type_lbl.setText(
            (cache.cache_type or "—")
            .replace(" Cache", "")
            .replace("Unknown", "Mystery")
        )
        d = f"{cache.difficulty:.1f}" if cache.difficulty else "?"
        t = f"{cache.terrain:.1f}" if cache.terrain else "?"
        self._dt_lbl.setText(f"{d} / {t}")
        self._container_lbl.setText(cache.container or "—")
        self._country_lbl.setText(
            f"{cache.country or '—'}"
            + (f" / {cache.state}" if cache.state else "")
        )
        if cache.latitude and cache.longitude:
            self._coords_lbl.setText(f"{cache.latitude:.5f}, {cache.longitude:.5f}")
            self._coords_lbl.setStyleSheet(
                "color: #1565c0; text-decoration: underline; font-weight: bold;"
            )
            self._current_lat = cache.latitude
            self._current_lon = cache.longitude
        else:
            self._coords_lbl.setText("—")
            self._coords_lbl.setStyleSheet("")
            self._current_lat = None
            self._current_lon = None

        # Placed by / date
        parts = []
        if cache.placed_by:
            parts.append(f"Udlagt af: {cache.placed_by}")
        if cache.hidden_date:
            parts.append(f"Dato: {cache.hidden_date.strftime('%d.%m.%Y')}")
        self._placed_lbl.setText("   |   ".join(parts))

        # Description
        if cache.long_description:
            if cache.long_desc_html:
                self._desc_browser.setHtml(cache.long_description)
            else:
                self._desc_browser.setPlainText(cache.long_description)
        elif cache.short_description:
            if cache.short_desc_html:
                self._desc_browser.setHtml(cache.short_description)
            else:
                self._desc_browser.setPlainText(cache.short_description)
        else:
            self._desc_browser.setPlainText("(Ingen beskrivelse)")

        # Hint — gem rå hint og nulstil decode state
        self._raw_hint = cache.encoded_hints or ""
        self._hint_decoded = False
        self._decode_btn.setText("🔓  Dekod hint (ROT13)")
        self._hint_browser.setPlainText(
            self._raw_hint if self._raw_hint else "(Intet hint)"
        )

        # Logs — show up to 10 most recent
        self._render_logs(cache)

    def _render_logs(self, cache: Cache) -> None:
        logs = sorted(
            cache.logs,
            key=lambda l: l.log_date or 0,
            reverse=True
        )
        # Gem alle logs til søgning
        self._cached_logs = logs
        self._log_search.setText("")
        self._tabs.setTabText(2, f"Logs ({len(logs)})" if logs else "Logs")
        self._render_log_html(logs)

    def _render_log_html(self, logs: list, filter_text: str = "") -> None:
        """Render logs som HTML, evt. filtreret."""
        if not logs:
            self._log_browser.setPlainText("(Ingen logs)")
            return

        colours = {
            "Found it":          "#2e7d32",
            "Didn't find it":    "#c62828",
            "Write note":        "#1565c0",
            "Owner Maintenance": "#6a1b9a",
        }

        filtered = logs
        if filter_text:
            filtered = [
                l for l in logs
                if filter_text in (l.text or "").lower()
                or filter_text in (l.finder or "").lower()
                or filter_text in (l.log_type or "").lower()
            ]

        if not filtered:
            self._log_browser.setPlainText(
                f"(Ingen logs matcher '{filter_text}')"
            )
            return

        html = []
        for log in filtered[:20]:   # max 20 ad gangen
            colour = colours.get(log.log_type, "#555555")
            date_str = log.log_date.strftime("%d.%m.%Y") if log.log_date else "?"
            text = log.text or ""
            if len(text) > 500:
                text = text[:500] + "…"
            # Fremhæv søgetekst
            if filter_text and filter_text in text.lower():
                idx = text.lower().find(filter_text)
                text = (
                    text[:idx]
                    + f'<mark>{text[idx:idx+len(filter_text)]}</mark>'
                    + text[idx+len(filter_text):]
                )
            html.append(
                f'<p><b style="color:{colour}">{log.log_type}</b> '
                f'— {log.finder or "?"} '
                f'<span style="color:gray">({date_str})</span><br>'
                f'{text}</p><hr>'
            )

        self._log_browser.setHtml("".join(html))
