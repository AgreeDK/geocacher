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
from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView, QMenu, QApplication

from opensak.db.models import Cache
from opensak.filters.engine import _haversine_km
import math


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Beregn azimut (kompasretning) fra punkt 1 til punkt 2 i grader (0-360)."""
    r = math.pi / 180
    dlon = (lon2 - lon1) * r
    la1, la2 = lat1 * r, lat2 * r
    x = math.sin(dlon) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _bearing_compass(deg: float) -> str:
    """Returner kompasretning på dansk (8 verdenshjørner) + grader."""
    dirs = ["N", "NØ", "Ø", "SØ", "S", "SV", "V", "NV"]
    idx = round(deg / 45) % 8
    return f"{dirs[idx]} {int(round(deg))}°"
from opensak.gui.settings import get_settings
from opensak.coords import format_coords
from opensak.lang import tr
from opensak.utils.types import GcCode
from opensak.gui.icon_provider import get_cache_type_icon, get_cache_size_icon


# ── Alle mulige kolonner ──────────────────────────────────────────────────────

def get_column_defs() -> dict:
    """Returner kolonnenavne oversat til det aktive sprog."""
    return {
        "gc_code":      (tr("col_gc_code"),           80),
        "name":         (tr("col_name"),             260),
        "cache_type":   (tr("col_type"),              28),
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
        # ── Issue #33: GSAK-compatible fields ─────────────────────────────
        "found_date":      (tr("col_found_date"),      90),
        "dnf_date":        (tr("col_dnf_date"),        90),
        "first_to_find":   (tr("col_first_to_find"),   45),
        "favorite_points": (tr("col_favorite_points"), 55),
        "user_flag":       (tr("col_user_flag"),    30),
        "bearing":         (tr("col_bearing"),           55),
        "user_sort":       (tr("col_user_sort"),       55),
        "user_data_1":     (tr("col_user_data_1"),    100),
        "user_data_2":     (tr("col_user_data_2"),    100),
        "user_data_3":     (tr("col_user_data_3"),    100),
        "user_data_4":     (tr("col_user_data_4"),    100),
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


from PySide6.QtWidgets import QStyledItemDelegate, QApplication
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import QRect


class SizeBarDelegate(QStyledItemDelegate):
    """Tegner en vandret fyldt bar (GSAK-stil) for container-kolonnen."""

    # Bredde i procent for hvert størrelsesstrin (0.0–1.0)
    _BAR_WIDTHS = {
        "nano":       0.10,
        "micro":      0.25,
        "small":      0.45,
        "regular":    0.65,
        "large":      0.90,
        "other":      0.50,
        "not chosen": 0.00,
        "virtual":    0.00,
        "":           0.00,
    }
    _BAR_COLOR   = QColor("#5b8dd9")   # GSAK-blå
    _EMPTY_COLOR = QColor("#dde3ee")   # lys grå baggrund

    def paint(self, painter: QPainter, option, index) -> None:
        size_key = index.data(Qt.ItemDataRole.UserRole + 10) or ""
        ratio = self._BAR_WIDTHS.get(size_key.lower(), 0.30)

        painter.save()

        # Baggrund
        bg = option.rect.adjusted(4, 3, -4, -3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._EMPTY_COLOR)
        painter.drawRoundedRect(bg, 2, 2)

        # Fyldt del
        if ratio > 0:
            filled = QRect(bg.x(), bg.y(), int(bg.width() * ratio), bg.height())
            painter.setBrush(self._BAR_COLOR)
            painter.drawRoundedRect(filled, 2, 2)

        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        sh.setHeight(max(sh.height(), 20))
        return sh


class CacheTableModel(QAbstractTableModel):
    """Qt table model backed by a list of Cache objects."""

    flags_changed = Signal()   # emitteres når user_flag toggler

    def __init__(self, parent=None):
        super().__init__(parent)
        self._caches: list[Cache] = []
        self._distances: dict[int, float] = {}
        self._bearings: dict[int, float] = {}
        self._columns: list[str] = _get_active_columns()

    def flags(self, index: QModelIndex):
        base = super().flags(index)
        if index.isValid() and self._columns[index.column()] == "user_flag":
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        """Toggle user_flag når brugeren klikker på Flag-kolonnen."""
        if not index.isValid():
            return False
        col = self._columns[index.column()]
        if col != "user_flag":
            return False
        cache = self._caches[index.row()]
        new_flag = not bool(cache.user_flag)
        from opensak.db.database import get_session
        from opensak.db.models import Cache as CacheModel
        with get_session() as session:
            c = session.query(CacheModel).filter_by(gc_code=cache.gc_code).first()
            if c:
                c.user_flag = new_flag
        cache.user_flag = new_flag
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
        self.flags_changed.emit()
        return True

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
                self._bearings[c.id] = _bearing_deg(
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
                       "corrected", "first_to_find", "user_flag", "bearing",
                       "user_sort", "favorite_points"):
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
            if col == "cache_type":
                t = cache.cache_type or ""
                return t.replace("Unknown", "Mystery")
            if col == "corrected":
                note = cache.user_note
                if note and note.is_corrected:
                    fmt = get_settings().coord_format
                    coords = format_coords(note.corrected_lat, note.corrected_lon, fmt)
                    return tr("col_corrected_tooltip", coords=coords)

        if role == Qt.ItemDataRole.DecorationRole:
            return self._decoration_value(cache, col)

        if role == Qt.ItemDataRole.UserRole + 10:
            # Size key til SizeBarDelegate
            return (cache.container or "").lower()

        if role == Qt.ItemDataRole.UserRole:
            return cache

        return None

    # ── Cache-type string → icon key ──────────────────────────────────────────

    @staticmethod
    def _type_icon_key(cache: Cache) -> str:
        """Map a Cache object to an icon_provider key (cache type only, ikke status)."""
        if cache.archived:
            return "archived"
        if not cache.available:
            return "disabled"
        t = (cache.cache_type or "").lower()
        mapping = {
            "traditional cache":            "traditional",
            "multi-cache":                  "multi",
            "mystery cache":                "mystery",
            "unknown cache":                "mystery",
            "letterbox hybrid":             "letterbox",
            "whereigo cache":               "whereigo",
            "earthcache":                   "earthcache",
            "virtual cache":                "virtual",
            "webcam cache":                 "webcam",
            "event cache":                  "event",
            "cache in trash out event":     "cito",
            "mega-event cache":             "mega_event",
            "giga-event cache":             "giga_event",
            "lab cache":                    "lab_cache",
            "community celebration event":  "community_celebration",
            "gps adventures maze":          "gps_adventures",
            "locationless (reverse) cache": "locationless",
            "project a.p.e. cache":         "project_ape",
            "groundspeak hq":               "geocaching_hq",
        }
        return mapping.get(t, "unknown")

    @staticmethod
    def _size_icon_key(cache: Cache) -> str:
        """Map container string to icon_provider size key."""
        mapping = {
            "nano":       "nano",
            "micro":      "micro",
            "small":      "small",
            "regular":    "regular",
            "large":      "large",
            "other":      "other",
            "not chosen": "not_chosen",
            "virtual":    "not_chosen",
        }
        return mapping.get((cache.container or "").lower(), "other")

    def _decoration_value(self, cache: Cache, col: str):
        """Return QIcon for columns that show icons."""
        if col == "cache_type":
            return get_cache_type_icon(
                self._type_icon_key(cache),
                size=24,
            )
        if col == "container":
            return get_cache_size_icon(self._size_icon_key(cache), size=20)
        return None

    def _display_value(self, cache: Cache, col: str) -> str:
        if col == "gc_code":
            return cache.gc_code or ""
        if col == "name":
            return cache.name or ""
        if col == "cache_type":
            return ""   # ikon vises via DecorationRole — fuldt navn i tooltip
        if col == "difficulty":
            return f"{cache.difficulty:.1f}" if cache.difficulty else "?"
        if col == "terrain":
            return f"{cache.terrain:.1f}" if cache.terrain else "?"
        if col == "container":
            return ""   # ikon vises via DecorationRole
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
        if col == "bearing":
            deg = self._bearings.get(cache.id)
            if deg is None:
                return "?"
            return _bearing_compass(deg)
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
        # ── Issue #33: GSAK-compatible fields ─────────────────────────────────
        if col == "found_date":
            return cache.found_date.strftime("%d.%m.%Y") if cache.found_date else ""
        if col == "dnf_date":
            return cache.dnf_date.strftime("%d.%m.%Y") if cache.dnf_date else ""
        if col == "first_to_find":
            return "FTF" if cache.first_to_find else ""
        if col == "favorite_points":
            return str(cache.favorite_points) if cache.favorite_points is not None else ""
        if col == "user_flag":
            return "🚩" if cache.user_flag else ""
        if col == "user_sort":
            return str(cache.user_sort) if cache.user_sort is not None else ""
        if col == "user_data_1":
            return cache.user_data_1 or ""
        if col == "user_data_2":
            return cache.user_data_2 or ""
        if col == "user_data_3":
            return cache.user_data_3 or ""
        if col == "user_data_4":
            return cache.user_data_4 or ""
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
        elif col == "bearing":
            self._caches.sort(
                key=lambda c: self._bearings.get(c.id, 999), reverse=reverse
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
        elif col == "found_date":
            self._caches.sort(
                key=lambda c: c.found_date or datetime.min, reverse=reverse
            )
        elif col == "dnf_date":
            self._caches.sort(
                key=lambda c: c.dnf_date or datetime.min, reverse=reverse
            )
        elif col == "first_to_find":
            self._caches.sort(key=lambda c: int(c.first_to_find or False), reverse=reverse)
        elif col == "user_flag":
            self._caches.sort(key=lambda c: int(c.user_flag or False), reverse=reverse)
        elif col == "user_sort":
            self._caches.sort(key=lambda c: c.user_sort if c.user_sort is not None else 999999, reverse=reverse)
        elif col == "favorite_points":
            self._caches.sort(key=lambda c: c.favorite_points or 0, reverse=reverse)
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
    flags_changed = Signal()   # videresendes fra model

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = CacheTableModel()
        self.setModel(self._model)
        self._model.flags_changed.connect(self.flags_changed)
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

    def mousePressEvent(self, event) -> None:
        """Klik på user_flag-kolonnen toggler flaget direkte."""
        index = self.indexAt(event.pos())
        if index.isValid():
            col = self._model._columns[index.column()]
            if col == "user_flag" and event.button() == Qt.MouseButton.LeftButton:
                self._model.setData(index, None)
                return
        super().mousePressEvent(event)

    def _apply_column_widths(self) -> None:
        header = self.horizontalHeader()
        columns = self._model._columns
        for i, col_id in enumerate(columns):
            width = get_column_defs().get(col_id, (col_id, 80))[1]
            self.setColumnWidth(i, width)
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            if col_id == "container":
                self._size_bar_delegate = SizeBarDelegate(self)
                self.setItemDelegateForColumn(i, self._size_bar_delegate)
            else:
                self.setItemDelegateForColumn(i, None)
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

    def get_all_caches(self) -> list[Cache]:
        """Returner alle caches i det aktive filter (som vist i tabellen)."""
        return [
            self._model.cache_at(i)
            for i in range(self._model.rowCount())
            if self._model.cache_at(i) is not None
        ]

    def get_flagged_caches(self) -> list[Cache]:
        """Returner alle flaggede caches i det aktive filter."""
        return [c for c in self.get_all_caches() if c.user_flag]
