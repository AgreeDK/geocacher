"""
src/opensak/gui/cache_table.py — Sortable cache list table widget.
Understøtter dynamiske kolonner valgt af brugeren.
"""

from __future__ import annotations
import webbrowser
from typing import Optional
from datetime import datetime

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, QPoint
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView, QMenu

from opensak.db.models import Cache
from opensak.filters.engine import _haversine_km
from opensak.gui.settings import get_settings
from opensak.coords import format_coords
from opensak.lang import tr
from opensak.utils.types import GcCode


# ── Alle mulige kolonner ──────────────────────────────────────────────────────

def get_column_defs() -> dict:
    """Returner kolonnenavne oversat til det aktive sprog."""
    return {
        "status":       ("",                          22),
        "gc_code":      (tr("col_gc_code"),           80),
        "name":         (tr("col_name"),             260),
        "cache_type":   (tr("col_type"),             130),
        "difficulty":   (tr("col_difficulty"),        50),
        "terrain":      (tr("col_terrain"),           50),
        "container":    (tr("col_container"),         80),
        "country":      (tr("col_country"),           80),
        "state":        (tr("col_state"),            120),
        "county":       (tr("col_county"),           100),
        "distance":     (tr("col_distance"),          75),
        "found":        (tr("col_found"),             55),
        "placed_by":    (tr("col_placed_by"),        120),
        "hidden_date":  (tr("col_hidden_date"),       90),
        "last_log":     (tr("col_last_log"),          90),
        "log_count":    (tr("col_log_count"),         70),
        "dnf":          (tr("col_dnf"),               45),
        "premium_only": (tr("col_premium"),           65),
        "archived":     (tr("col_archived"),          70),
        "favorite":     (tr("col_favorite"),          60),
        "corrected":    (tr("col_corrected"),         40),
    }


def _get_active_columns() -> list[str]:
    from opensak.gui.dialogs.column_dialog import get_visible_columns
    return get_visible_columns()


def _gc_sort_key(gc_code: GcCode) -> str:
    """Return a zero-padded sort key so GC codes sort numerically.

    GC codes are alphanumeric (base-31), so pure alphabetical sorting gives
    wrong order, e.g. GC1DCA before GC1D.  Zero-padding the suffix to a fixed
    width produces correct ordering without needing a base-31 conversion.

    Examples:
        GC1D   → GC000000001D
        GC1DCA → GC0000001DCA   (correctly sorts after GC1D)
    """
    if not gc_code:
        return ""
    upper = gc_code.upper()
    suffix = upper[2:] if upper.startswith("GC") else upper
    return "GC" + suffix.zfill(10)


class CacheTableModel(QAbstractTableModel):
    """Qt table model backed by a list of Cache objects."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._caches: list[Cache] = []
        self._distances: dict[int, float] = {}
        self._columns: list[str] = _get_active_columns()

    def reload_columns(self) -> None:
        """Genindlæs kolonnedefinitioner fra indstillinger."""
        self.beginResetModel()
        self._columns = _get_active_columns()
        self.endResetModel()

    def load(self, caches: list[Cache]) -> None:
        self.beginResetModel()
        self._caches = caches
        self._update_distances()
        self.endResetModel()

    def _update_distances(self) -> None:
        settings = get_settings()
        self._distances = {}
        for c in self._caches:
            if c.latitude is not None and c.longitude is not None:
                self._distances[c.id] = _haversine_km(
                    settings.home_lat, settings.home_lon,
                    c.latitude, c.longitude
                )

    def cache_at(self, row: int) -> Optional[Cache]:
        if 0 <= row < len(self._caches):
            return self._caches[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._caches)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._columns)

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                col_id = self._columns[section]
                return get_column_defs().get(col_id, (col_id, 80))[0]
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        cache = self._caches[index.row()]
        col = self._columns[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(cache, col)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in ("difficulty", "terrain", "distance", "found",
                       "dnf", "premium_only", "archived", "log_count",
                       "corrected"):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.ForegroundRole:
            if cache.archived:
                return QColor("#999999")
            if cache.found:
                return QColor("#2e7d32")

        if role == Qt.ItemDataRole.FontRole:
            if cache.found:
                font = QFont()
                font.setItalic(True)
                return font

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == "corrected":
                note = cache.user_note
                if note and note.is_corrected:
                    fmt = get_settings().coord_format
                    coords = format_coords(note.corrected_lat, note.corrected_lon, fmt)
                    return tr("col_corrected_tooltip", coords=coords)

        if role == Qt.ItemDataRole.UserRole:
            return cache

        return None

    def _display_value(self, cache: Cache, col: str) -> str:
        if col == "status":
            if cache.archived:
                return "🔒"
            if cache.found:
                return "✅"
            if cache.dnf:
                return "❌"
            if not cache.available:
                return "⚠️"
            return ""
        if col == "gc_code":
            return cache.gc_code or ""
        if col == "name":
            return cache.name or ""
        if col == "cache_type":
            t = cache.cache_type or ""
            return t.replace(" Cache", "").replace("Unknown", "Mystery")
        if col == "difficulty":
            return f"{cache.difficulty:.1f}" if cache.difficulty else "?"
        if col == "terrain":
            return f"{cache.terrain:.1f}" if cache.terrain else "?"
        if col == "container":
            return cache.container or ""
        if col == "country":
            return cache.country or ""
        if col == "state":
            return cache.state or ""
        if col == "county":
            return cache.county or ""
        if col == "distance":
            dist = self._distances.get(cache.id)
            if dist is None:
                return "?"
            if get_settings().use_miles:
                return f"{dist * 0.621371:.1f} mi"
            return f"{dist:.1f} km"
        if col == "found":
            return "✓" if cache.found else ""
        if col == "placed_by":
            return cache.placed_by or ""
        if col == "hidden_date":
            return cache.hidden_date.strftime("%d.%m.%Y") if cache.hidden_date else ""
        if col == "last_log":
            if cache.logs:
                latest = max(
                    (l for l in cache.logs if l.log_date),
                    key=lambda l: l.log_date,
                    default=None
                )
                if latest:
                    return latest.log_date.strftime("%d.%m.%Y")
            return ""
        if col == "log_count":
            return str(len(cache.logs)) if cache.logs is not None else "0"
        if col == "dnf":
            return "DNF" if cache.dnf else ""
        if col == "premium_only":
            return "P" if cache.premium_only else ""
        if col == "archived":
            return "✓" if cache.archived else ""
        if col == "favorite":
            return "★" if cache.favorite_point else ""
        if col == "corrected":
            note = cache.user_note
            return "📍" if (note and note.is_corrected) else ""
        return ""

    def sort(self, column: int, order=Qt.SortOrder.AscendingOrder) -> None:
        if column >= len(self._columns):
            return
        col = self._columns[column]
        reverse = (order == Qt.SortOrder.DescendingOrder)
        self.beginResetModel()
        if col == "difficulty":
            self._caches.sort(key=lambda c: c.difficulty or 0, reverse=reverse)
        elif col == "terrain":
            self._caches.sort(key=lambda c: c.terrain or 0, reverse=reverse)
        elif col == "distance":
            self._caches.sort(
                key=lambda c: self._distances.get(c.id, 99999), reverse=reverse
            )
        elif col == "found":
            self._caches.sort(key=lambda c: int(c.found), reverse=reverse)
        elif col == "corrected":
            self._caches.sort(
                key=lambda c: int(
                    bool(c.user_note and c.user_note.is_corrected)
                ),
                reverse=reverse,
            )
        elif col == "log_count":
            self._caches.sort(
                key=lambda c: len(c.logs) if c.logs else 0, reverse=reverse
            )
        elif col == "hidden_date":
            self._caches.sort(
                key=lambda c: c.hidden_date or datetime.min, reverse=reverse
            )
        elif col == "name":
            self._caches.sort(
                key=lambda c: (c.name or "").lower(), reverse=reverse
            )
        elif col == "gc_code":
            self._caches.sort(key=lambda c: _gc_sort_key(c.gc_code or ""), reverse=reverse)
        else:
            self._caches.sort(
                key=lambda c: (getattr(c, col, "") or "").lower()
                if isinstance(getattr(c, col, ""), str) else getattr(c, col, 0) or 0,
                reverse=reverse
            )
        self.endResetModel()


class CacheTableView(QTableView):
    """The main cache list widget."""

    cache_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = CacheTableModel()
        self.setModel(self._model)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.setWordWrap(False)
        self.verticalHeader().setDefaultSectionSize(24)
        self._apply_column_widths()
        self.horizontalHeader().setSortIndicatorShown(True)
        self.selectionModel().currentRowChanged.connect(self._on_row_changed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _apply_column_widths(self) -> None:
        header = self.horizontalHeader()
        columns = self._model._columns
        for i, col_id in enumerate(columns):
            width = get_column_defs().get(col_id, (col_id, 80))[1]
            self.setColumnWidth(i, width)
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        if "name" in columns:
            name_idx = columns.index("name")
            header.setSectionResizeMode(
                name_idx, QHeaderView.ResizeMode.Stretch
            )

    def reload_columns(self) -> None:
        """Opdatér kolonner fra indstillinger."""
        self._model.reload_columns()
        self._apply_column_widths()

    def load_caches(self, caches: list[Cache]) -> None:
        self._model.load(caches)

    def _on_row_changed(self, current, previous) -> None:
        cache = self._model.cache_at(current.row())
        if cache:
            self.cache_selected.emit(cache)

    def _show_context_menu(self, pos: QPoint) -> None:
        """Vis højreklik kontekstmenu for den valgte cache."""
        cache = self._model.cache_at(self.indexAt(pos).row())
        if not cache:
            return

        menu = QMenu(self)

        # Åbn på geocaching.com
        act_open = menu.addAction(tr("ctx_open_geocaching"))
        act_open.triggered.connect(
            lambda: webbrowser.open(f"https://coord.info/{cache.gc_code}")
        )

        # Åbn i kortapp
        if cache.latitude and cache.longitude:
            from opensak.gui.settings import get_settings
            s = get_settings()
            map_name = "OpenStreetMap" if s.map_provider == "osm" else "Google Maps"
            act_maps = menu.addAction(tr("ctx_open_maps", map_name=map_name))
            lat, lon = cache.latitude, cache.longitude
            act_maps.triggered.connect(
                lambda checked=False, la=lat, lo=lon: webbrowser.open(
                    get_settings().get_maps_url(la, lo)
                )
            )

        menu.addSeparator()

        # Kopiér GC kode
        act_copy_gc = menu.addAction(tr("ctx_copy_gc"))
        act_copy_gc.triggered.connect(lambda: self._copy_to_clipboard(cache.gc_code))

        # Kopiér koordinater — i det valgte format
        if cache.latitude and cache.longitude:
            fmt = get_settings().coord_format
            coords = format_coords(cache.latitude, cache.longitude, fmt)
            act_copy_coords = menu.addAction(tr("ctx_copy_coords"))
            act_copy_coords.triggered.connect(
                lambda: self._copy_to_clipboard(coords)
            )

            # Åbn koordinatkonverter
            act_converter = menu.addAction(tr("ctx_coord_converter"))
            lat, lon = cache.latitude, cache.longitude
            act_converter.triggered.connect(
                lambda checked=False, la=lat, lo=lon: self._open_converter(la, lo)
            )

        menu.addSeparator()

        # Korrigerede koordinater
        note = cache.user_note
        has_corrected = note and note.is_corrected
        if has_corrected:
            act_edit_corrected = menu.addAction(tr("ctx_edit_corrected"))
        else:
            act_edit_corrected = menu.addAction(tr("ctx_add_corrected"))
        act_edit_corrected.triggered.connect(
            lambda checked=False, c=cache: self._edit_corrected(c)
        )
        if has_corrected:
            act_clear_corrected = menu.addAction(tr("ctx_clear_corrected"))
            act_clear_corrected.triggered.connect(
                lambda checked=False, c=cache: self._clear_corrected(c)
            )

        menu.addSeparator()

        # Marker som fundet / ikke fundet
        if cache.found:
            act_found = menu.addAction(tr("ctx_mark_not_found"))
            act_found.triggered.connect(lambda: self._toggle_found(cache, False))
        else:
            act_found = menu.addAction(tr("ctx_mark_found"))
            act_found.triggered.connect(lambda: self._toggle_found(cache, True))

        menu.exec(self.viewport().mapToGlobal(pos))

    def _edit_corrected(self, cache: Cache) -> None:
        """Åbn dialog til at sætte/redigere korrigerede koordinater."""
        from opensak.gui.dialogs.corrected_coords_dialog import CorrectedCoordsDialog
        note = cache.user_note
        cur_lat = note.corrected_lat if (note and note.is_corrected) else None
        cur_lon = note.corrected_lon if (note and note.is_corrected) else None
        dlg = CorrectedCoordsDialog(
            gc_code=cache.gc_code,
            current_lat=cur_lat,
            current_lon=cur_lon,
            parent=self,
        )
        if dlg.exec():
            lat, lon = dlg.get_coords()
            self._save_corrected(cache, lat, lon)

    def _clear_corrected(self, cache: Cache) -> None:
        """Slet korrigerede koordinater."""
        self._save_corrected(cache, None, None)

    def _save_corrected(self, cache: Cache, lat, lon) -> None:
        from opensak.db.database import get_session
        from opensak.db.models import UserNote, Cache as CacheModel
        with get_session() as session:
            cache_row = session.query(CacheModel).filter_by(
                gc_code=cache.gc_code
            ).first()
            if not cache_row:
                return
            note = cache_row.user_note
            if note is None:
                note = UserNote(cache_id=cache_row.id)
                session.add(note)
            note.corrected_lat = lat
            note.corrected_lon = lon
            note.is_corrected = (lat is not None and lon is not None)
        # Opdatér lokal cache-objekt og refresh
        if cache.user_note is None:
            from opensak.db.models import UserNote as UN
            cache.user_note = UN.__new__(UN)
        cache.user_note.corrected_lat = lat
        cache.user_note.corrected_lon = lon
        cache.user_note.is_corrected = (lat is not None and lon is not None)
        self._model.beginResetModel()
        self._model.endResetModel()

    def _open_converter(self, lat: float, lon: float) -> None:
        """Åbn koordinatkonverter popup."""
        from opensak.gui.dialogs.coord_converter_dialog import CoordConverterDialog
        dlg = CoordConverterDialog(lat, lon, parent=self)
        dlg.exec()

    def _copy_to_clipboard(self, text: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _toggle_found(self, cache, found: bool) -> None:
        from opensak.db.database import get_session
        from opensak.db.models import Cache as CacheModel
        with get_session() as session:
            c = session.query(CacheModel).filter_by(gc_code=cache.gc_code).first()
            if c:
                c.found = found
        cache.found = found
        self._model.beginResetModel()
        self._model.endResetModel()

    def selected_cache(self) -> Optional[Cache]:
        indexes = self.selectedIndexes()
        if indexes:
            return self._model.cache_at(indexes[0].row())
        return None

    def select_by_gc_code(self, gc_code: str) -> None:
        """Vælg og scroll til rækken med det givne gc_code. Bruges når
        brugeren klikker på en pin på kortet, så listen synkroniseres."""
        for row in range(self._model.rowCount()):
            cache = self._model.cache_at(row)
            if cache and cache.gc_code == gc_code:
                index = self._model.index(row, 0)
                self.setCurrentIndex(index)
                self.scrollTo(index, self.ScrollHint.PositionAtCenter)
                return

    def row_count(self) -> int:
        return self._model.rowCount()
