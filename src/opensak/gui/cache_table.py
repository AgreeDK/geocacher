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
from opensak.gui.settings import get_settings
from opensak.coords import format_coords, format_lat, format_lon, format_lat, format_lon
from opensak.lang import tr
from opensak.utils.types import GcCode
from opensak.gui.icon_provider import get_cache_type_icon, get_cache_size_icon
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
    dirs = tr("bearing_dirs").split()
    idx = round(deg / 45) % 8
    return f"{dirs[idx]} {int(round(deg))}°"


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
        # ── Issue #84: Latitude og Longitude ──────────────────────────────
        "latitude":     (tr("col_latitude"),         110),
        "longitude":    (tr("col_longitude"),        110),
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


# ── Issue #90: Container size sort order ─────────────────────────────────────
#
# Container values are sorted by logical "size" rather than alphabetically.
# Non-physical container types (Virtual, EarthCache, Lab) are placed first
# because they have no physical size — these are detected via cache_type, not
# container, since Groundspeak GPX files set container="Other" or "Not chosen"
# for these types.
#
# Sort order:
#   1  Virtual / EarthCache / Lab    (no physical container — by cache_type)
#   2  Nano
#   3  Micro
#   4  Small
#   5  Regular
#   6  Large
#   7  Other                          (unknown size)
#   8  Not chosen / empty             (incomplete data, sorts last)
#
_CONTAINER_SORT_ORDER = {
    "nano":        2,
    "micro":       3,
    "small":       4,
    "regular":     5,
    "large":       6,
    "other":       7,
    "not chosen":  8,
    "":            8,
}

# Cache types that have no physical container — these sort first (group 1)
_NON_PHYSICAL_TYPES = {
    "virtual cache",
    "earthcache",
    "lab cache",
    "locationless (reverse) cache",
}


def _container_sort_key(container: str | None, cache_type: str | None = None) -> tuple:
    """Return sort key tuple for the Container column.

    Returns a (group, sub_key) tuple so:
    - Primary sort is by logical container size group (1-8)
    - Within group 1 (non-physical types), secondary sort is alphabetic
      on cache_type so 'EarthCache' → 'Lab Cache' → 'Virtual Cache' stay
      grouped together (and any future non-physical type slots in
      alphabetically without code changes).
    - Within other groups, sub_key is empty so Python's stable sort
      preserves the existing order (e.g. distance sort).

    Used by the Container column to sort by logical size instead of
    alphabetically. Non-physical cache types (Virtual, EarthCache, Lab)
    are detected by cache_type since they typically have container='Other'
    or empty in GPX data.

    Unknown values fall back to the same group as 'Other' so they don't
    disappear at the very end.
    """
    # Non-physical types come first (group 1), sorted alphabetically by type
    if cache_type:
        ct = cache_type.strip().lower()
        if ct in _NON_PHYSICAL_TYPES:
            return (1, ct)
    # Physical containers — sub_key empty so stable sort preserves order
    if container is None:
        return (_CONTAINER_SORT_ORDER[""], "")
    key = container.strip().lower()
    return (_CONTAINER_SORT_ORDER.get(key, 7), "")  # unknown → group 7


from PySide6.QtWidgets import QStyledItemDelegate, QApplication
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import QRect


class SizeBarDelegate(QStyledItemDelegate):
    """Tegner GSAK-stil segmenteret størrelsesindikator for container-kolonnen.

    5 firkantede segmenter fylder op fra venstre:
      Nano=1, Micro=2, Small=3, Regular=4, Large=5
    Special visning (tomme segmenter + bogstav i sidste segment):
      Other        → 'O'   (ukendt fysisk størrelse)
      Virtual Cache → 'V'  (ingen fysisk container — by cache_type)
      EarthCache   → 'E'   (ingen fysisk container — by cache_type)
    Not chosen og tom → 5 tomme segmenter, intet bogstav
    """

    # Antal fyldte segmenter per størrelse (ud af 5)
    _SEGMENTS = {
        "nano":       1,
        "micro":      2,
        "small":      3,
        "regular":    4,
        "large":      5,
        "other":      0,    # tom — bogstav vises i stedet (issue #90)
        "not chosen": 0,
        "":           0,
    }
    # Bogstaver vist i sidste segment for size-værdier (issue #90)
    _SIZE_LABELS = {
        "other": "O",
    }
    # Cache-typer der vises med tomt felt + bogstav (uanset container value)
    _LABEL_TYPES = {
        "virtual cache": "V",
        "earthcache":    "E",
    }

    _SEG_COUNT   = 5
    _SEG_GAP     = 2
    _BAR_COLOR   = QColor("#5b8dd9")   # GSAK-blå
    _EMPTY_COLOR = QColor("#c8d4ea")   # lys grå baggrund
    _LABEL_COLOR = QColor("#4a72b0")   # bogstav-farve (mørkere blå)

    def paint(self, painter: QPainter, option, index) -> None:
        data = index.data(Qt.ItemDataRole.UserRole + 10) or {}
        size_key  = data.get("size", "").lower()  if isinstance(data, dict) else ""
        cache_type = data.get("type", "").lower() if isinstance(data, dict) else ""

        filled = self._SEGMENTS.get(size_key, 0)
        # cache_type label tager førsteret over size label (Virtual/Earth → V/E)
        # ellers fall back til size-baseret label (Other → O)
        label = self._LABEL_TYPES.get(cache_type, "") or self._SIZE_LABELS.get(size_key, "")

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect
        margin_x, margin_y = 4, 3
        total_w = rect.width()  - 2 * margin_x
        total_h = rect.height() - 2 * margin_y
        x0 = rect.x() + margin_x
        y0 = rect.y() + margin_y

        seg_w = max(4, (total_w - self._SEG_GAP * (self._SEG_COUNT - 1)) // self._SEG_COUNT)

        for i in range(self._SEG_COUNT):
            sx = x0 + i * (seg_w + self._SEG_GAP)
            seg_rect = QRect(sx, y0, seg_w, total_h)

            is_filled = (i < filled) and not label
            is_last   = (i == self._SEG_COUNT - 1)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._BAR_COLOR if is_filled else self._EMPTY_COLOR)
            painter.drawRoundedRect(seg_rect, 1, 1)

            # Bogstav i det sidste segment for Virtual/Earth/Other
            if label and is_last:
                painter.setPen(self._LABEL_COLOR)
                font = painter.font()
                font.setPointSize(7)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(seg_rect, Qt.AlignmentFlag.AlignCenter, label)
                painter.setPen(Qt.PenStyle.NoPen)

        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        sh.setHeight(max(sh.height(), 20))
        return sh


class CacheTableModel(QAbstractTableModel):
    """Qt table model backed by a list of Cache objects."""

    flags_changed = Signal()          # emitteres når user_flag toggler
    sort_changed = Signal(str, bool)  # (col_id, ascending) når brugeren sorterer

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
                       "user_sort", "favorite_points",
                       "latitude", "longitude"):
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
            if col in ("latitude", "longitude"):
                # Vis tooltip der angiver om koordinaterne er korrigerede
                note = cache.user_note
                if note and note.is_corrected:
                    return tr("col_coord_tooltip_corrected")
                return tr("col_coord_tooltip_original")

        if role == Qt.ItemDataRole.DecorationRole:
            return self._decoration_value(cache, col)

        if role == Qt.ItemDataRole.UserRole + 10:
            # Dict med size + type til SizeBarDelegate
            return {
                "size": (cache.container or "").lower(),
                "type": (cache.cache_type or "").lower(),
            }

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
            "wherigo cache":                "wherigo",
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
            "gps adventures maze exhibit":  "gps_adventures",
            "gps adventures exhibit":       "gps_adventures",
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

    @staticmethod
    def _effective_coords(cache: Cache) -> tuple[float | None, float | None]:
        """Returnér de effektive koordinater (corrected hvis sat, ellers original).

        Bruges af latitude/longitude-kolonnerne så visningen matcher kortet,
        som også viser corrected hvis tilgængelige.
        """
        note = cache.user_note
        if (note and note.is_corrected
                and note.corrected_lat is not None
                and note.corrected_lon is not None):
            return note.corrected_lat, note.corrected_lon
        return cache.latitude, cache.longitude

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
            # Issue #87: use cached log_count column instead of len(cache.logs)
            # because logs are noload'ed for performance and would always be
            # an empty list here. log_count is maintained on import.
            return str(cache.log_count or 0)
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
        # ── Issue #84: Latitude og Longitude (i brugerens valgte format) ──────
        if col == "latitude":
            lat, _ = self._effective_coords(cache)
            if lat is None:
                return ""
            fmt = get_settings().coord_format
            return format_lat(lat, fmt)
        if col == "longitude":
            _, lon = self._effective_coords(cache)
            if lon is None:
                return ""
            fmt = get_settings().coord_format
            return format_lon(lon, fmt)
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
            # Issue #87: sort on cached log_count column (logs are noload'ed)
            self._caches.sort(
                key=lambda c: c.log_count or 0, reverse=reverse
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
        elif col == "container":
            # Issue #90: Sort by logical container size, not alphabetically
            self._caches.sort(
                key=lambda c: _container_sort_key(c.container, c.cache_type),
                reverse=reverse,
            )
        elif col == "latitude":
            # Numerisk sortering på rå float — ikke formateret tekst
            # Bruger effektive koordinater (corrected hvis sat)
            self._caches.sort(
                key=lambda c: (self._effective_coords(c)[0]
                               if self._effective_coords(c)[0] is not None
                               else -999.0),
                reverse=reverse,
            )
        elif col == "longitude":
            self._caches.sort(
                key=lambda c: (self._effective_coords(c)[1]
                               if self._effective_coords(c)[1] is not None
                               else -999.0),
                reverse=reverse,
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
        self.sort_changed.emit(col, not reverse)


class CacheTableView(QTableView):
    """The main cache list widget."""

    cache_selected = Signal(object)
    flags_changed = Signal()          # videresendes fra model
    sort_changed = Signal(str, bool)  # (col_id, ascending) videresendes fra model

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = CacheTableModel()
        self.setModel(self._model)
        self._model.flags_changed.connect(self.flags_changed)
        self._model.sort_changed.connect(self._on_model_sort_changed)
        self._last_sort_col: Optional[int] = None
        self._last_sort_asc: bool = True
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
                name_idx, QHeaderView.ResizeMode.Interactive
            )

    def reload_columns(self) -> None:
        """Opdatér kolonner fra indstillinger."""
        self._model.reload_columns()
        self._apply_column_widths()

    def _on_model_sort_changed(self, col_id: str, ascending: bool) -> None:
        """Store last sort so we can re-apply after reload."""
        cols = self._model._columns
        if col_id in cols:
            self._last_sort_col = cols.index(col_id)
            self._last_sort_asc = ascending
        self.sort_changed.emit(col_id, ascending)

    def apply_sort(self, col_id: str, ascending: bool) -> None:
        """Genanvend sortering - kaldes fra mainwindow ved opstart/db-skift."""
        cols = self._model._columns
        if col_id not in cols:
            return
        col_idx = cols.index(col_id)
        order = (Qt.SortOrder.AscendingOrder if ascending
                 else Qt.SortOrder.DescendingOrder)
        self._last_sort_col = col_idx
        self._last_sort_asc = ascending
        self._model.sort(col_idx, order)
        self.horizontalHeader().setSortIndicator(col_idx, order)

    def load_caches(self, caches: list[Cache]) -> None:
        self._model.load(caches)
        # Genanvend sortering - beginResetModel() nulstiller Qt sort-indikatoren
        if self._last_sort_col is not None:
            order = (Qt.SortOrder.AscendingOrder if self._last_sort_asc
                     else Qt.SortOrder.DescendingOrder)
            self._model.sort(self._last_sort_col, order)
            self.horizontalHeader().setSortIndicator(self._last_sort_col, order)

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
            corrected_lat=cur_lat,
            corrected_lon=cur_lon,
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
