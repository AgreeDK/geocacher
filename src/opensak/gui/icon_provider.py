"""
icon_provider.py — OpenSAK cache icon provider

Leverer QIcon og QPixmap for cache-typer, størrelser og kort-pins.
Alle ikoner er bundlet som SVG-strenge direkte i modulet (ingen løse filer),
så der ikke er afhængighed af filsystemet ved kørsel.

Brug:
    from opensak.gui.icon_provider import (
        get_cache_type_icon,
        get_cache_size_icon,
        get_cache_type_pixmap,
        get_map_pin_html,
    )

    icon = get_cache_type_icon("traditional")   # QIcon 32x32
    icon = get_cache_type_icon("found")         # status-variant
    size = get_cache_size_icon("micro")         # QIcon 32x32
    pin  = get_map_pin_html("mystery")          # HTML til Leaflet divIcon
"""

from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvg import QSvgRenderer


# ── Internal helpers (defined first) ─────────────────────────────────────────

def _size_circle(label: str, fill: str = "#3498db", stroke: str = "#2980b9") -> str:
    """Generate a circular size-badge SVG."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        f'<circle cx="16" cy="16" r="13" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        f'<text x="16" y="21" text-anchor="middle" font-size="11" font-weight="700" '
        f'fill="white" font-family="sans-serif">{label}</text>'
        f'</svg>'
    )


def _box(fill: str, stroke: str, inner: str = "") -> str:
    """Standard cache box with lid SVG."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        f'<rect x="4" y="8" width="24" height="7" rx="2" fill="{stroke}" stroke="{stroke}" stroke-width="0.5"/>'
        f'<rect x="6" y="14" width="20" height="13" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        f'<rect x="13" y="17" width="6" height="4" rx="1" fill="white" opacity="0.75"/>'
        f'{inner}'
        f'</svg>'
    )


def _box_text(fill: str, stroke: str, text: str) -> str:
    """Box with text label over clasp."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        f'<rect x="4" y="8" width="24" height="7" rx="2" fill="{stroke}" stroke="{stroke}" stroke-width="0.5"/>'
        f'<rect x="6" y="14" width="20" height="13" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        f'<text x="16" y="24" text-anchor="middle" font-size="9" font-weight="700" '
        f'fill="white" font-family="sans-serif">{text}</text>'
        f'</svg>'
    )


def _calendar(badge: str, extra: str = "") -> str:
    """Red event calendar SVG with badge text and optional extra SVG elements."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        f'<rect x="4" y="9" width="24" height="19" rx="2" fill="#e74c3c" stroke="#c0392b" stroke-width="1"/>'
        f'<rect x="4" y="9" width="24" height="8" rx="2" fill="#c0392b"/>'
        f'<circle cx="11" cy="9" r="2.5" fill="#7f8c8d"/>'
        f'<circle cx="21" cy="9" r="2.5" fill="#7f8c8d"/>'
        f'<text x="16" y="24" text-anchor="middle" font-size="9" font-weight="700" '
        f'fill="white" font-family="sans-serif">{badge}</text>'
        f'{extra}'
        f'</svg>'
    )


# ── SVG data ──────────────────────────────────────────────────────────────────

_CACHE_TYPE_SVGS: dict[str, str] = {

    # ── Standard box types ────────────────────────────────────────────────────

    "traditional": _box("#2ecc71", "#27ae60"),

    "multi": _box_text("#e67e22", "#ca6f1e", "2+"),

    "mystery": _box_text("#3498db", "#2980b9", "?"),

    "letterbox": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="4" y="8" width="24" height="7" rx="2" fill="#7b3f00" stroke="#7b3f00" stroke-width="0.5"/>'
        '<rect x="6" y="14" width="20" height="13" rx="2" fill="#a0522d" stroke="#7b3f00" stroke-width="1"/>'
        '<circle cx="12" cy="21" r="3.5" fill="#d4a76a" opacity="0.9"/>'
        '<circle cx="20" cy="21" r="3.5" fill="#d4a76a" opacity="0.9"/>'
        '</svg>'
    ),

    "whereigo": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="4" y="8" width="24" height="7" rx="2" fill="#17a589" stroke="#17a589" stroke-width="0.5"/>'
        '<rect x="6" y="14" width="20" height="13" rx="2" fill="#1abc9c" stroke="#17a589" stroke-width="1"/>'
        '<polygon points="16,16 21,26 16,23 11,26" fill="white" opacity="0.9"/>'
        '</svg>'
    ),

    # ── Special types ─────────────────────────────────────────────────────────

    "earthcache": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<circle cx="16" cy="18" r="12" fill="#27ae60" stroke="#1e8449" stroke-width="1"/>'
        '<ellipse cx="12" cy="15" rx="5" ry="7" fill="#f0e68c" opacity="0.85"/>'
        '<ellipse cx="20" cy="20" rx="4" ry="5" fill="#f0e68c" opacity="0.85"/>'
        '</svg>'
    ),

    "virtual": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="4" y="8" width="24" height="7" rx="2" fill="none" stroke="#8e44ad" '
        'stroke-width="2" stroke-dasharray="3,2"/>'
        '<rect x="6" y="14" width="20" height="13" rx="2" fill="none" stroke="#8e44ad" '
        'stroke-width="1.5" stroke-dasharray="3,2"/>'
        '<text x="16" y="24" text-anchor="middle" font-size="10" font-weight="700" '
        'fill="#8e44ad" font-family="sans-serif">V</text>'
        '</svg>'
    ),

    "webcam": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="3" y="11" width="20" height="14" rx="3" fill="#7f8c8d" stroke="#616a6b" stroke-width="1"/>'
        '<rect x="23" y="14" width="7" height="5" rx="1" fill="#95a5a6" stroke="#616a6b" stroke-width="0.8"/>'
        '<circle cx="13" cy="18" r="5" fill="#95a5a6" stroke="#616a6b" stroke-width="0.8"/>'
        '<circle cx="13" cy="18" r="3" fill="#2c3e50"/>'
        '<circle cx="13" cy="18" r="1.5" fill="#3498db"/>'
        '</svg>'
    ),

    "lab_cache": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="12" y="3" width="8" height="7" rx="1.5" fill="#9b59b6" stroke="#7d3c98" stroke-width="1"/>'
        '<path d="M12,9 L6,24 Q6,29 16,29 Q26,29 26,24 L20,9 Z" '
        'fill="#d7bde2" stroke="#9b59b6" stroke-width="1.2"/>'
        '<path d="M8,20 Q8,29 16,29 Q24,29 24,20 Z" fill="#9b59b6" opacity="0.8"/>'
        '<circle cx="13" cy="17" r="2" fill="white" opacity="0.7"/>'
        '<circle cx="19" cy="22" r="1.5" fill="white" opacity="0.7"/>'
        '</svg>'
    ),

    "gps_adventures": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="3" y="3" width="26" height="26" rx="3" fill="#16a085" stroke="#0e6655" stroke-width="1"/>'
        '<polyline points="7,7 7,16 13,16 13,10 19,10 19,20 25,20 25,25 16,25" '
        'fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="7" cy="7" r="2.5" fill="#f1c40f"/>'
        '<circle cx="16" cy="25" r="2.5" fill="#e74c3c"/>'
        '</svg>'
    ),

    # ── Event types (calendar base) ───────────────────────────────────────────

    "event": _calendar("E"),

    "cito": _calendar("C"),

    "mega_event": _calendar("M"),

    "giga_event": _calendar(
        "G",
        '<polygon points="16,2 17.2,6 21,6 18,8.5 19.2,12.5 16,10 12.8,12.5 14,8.5 11,6 14.8,6" '
        'fill="#f1c40f" stroke="#e67e22" stroke-width="0.5"/>',
    ),

    "community_celebration": _calendar(
        "CC",
        '<circle cx="5" cy="7" r="2" fill="#f1c40f"/>'
        '<circle cx="27" cy="7" r="2" fill="#2ecc71"/>'
        '<circle cx="3" cy="19" r="2" fill="#3498db"/>'
        '<circle cx="29" cy="19" r="2" fill="#9b59b6"/>',
    ),

    # ── Status variants ───────────────────────────────────────────────────────

    "found": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="4" y="8" width="24" height="7" rx="2" fill="#27ae60" stroke="#27ae60" stroke-width="0.5"/>'
        '<rect x="6" y="14" width="20" height="13" rx="2" fill="#2ecc71" stroke="#27ae60" stroke-width="1"/>'
        '<rect x="13" y="17" width="6" height="4" rx="1" fill="white" opacity="0.75"/>'
        '<circle cx="25" cy="9" r="7" fill="#f39c12" stroke="white" stroke-width="1.5"/>'
        '<polyline points="21,9 24,12 30,5" fill="none" stroke="white" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),

    "dnf": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="4" y="8" width="24" height="7" rx="2" fill="#27ae60" stroke="#27ae60" stroke-width="0.5"/>'
        '<rect x="6" y="14" width="20" height="13" rx="2" fill="#2ecc71" stroke="#27ae60" stroke-width="1"/>'
        '<rect x="13" y="17" width="6" height="4" rx="1" fill="white" opacity="0.75"/>'
        '<circle cx="25" cy="9" r="7" fill="#e74c3c" stroke="white" stroke-width="1.5"/>'
        '<line x1="21" y1="5" x2="29" y2="13" stroke="white" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="29" y1="5" x2="21" y2="13" stroke="white" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),

    "disabled": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="4" y="8" width="24" height="7" rx="2" fill="#7f8c8d" stroke="#616a6b" stroke-width="0.5"/>'
        '<rect x="6" y="14" width="20" height="13" rx="2" fill="#95a5a6" stroke="#7f8c8d" stroke-width="1"/>'
        '<line x1="4" y1="6" x2="28" y2="30" stroke="#e74c3c" stroke-width="2.5" stroke-linecap="round"/>'
        '</svg>'
    ),

    "archived": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="4" y="8" width="24" height="7" rx="2" fill="#616a6b" stroke="#4a4a4a" stroke-width="0.5"/>'
        '<rect x="6" y="14" width="20" height="13" rx="2" fill="#7f8c8d" stroke="#616a6b" stroke-width="1"/>'
        '<line x1="10" y1="18" x2="22" y2="18" stroke="white" stroke-width="1.5" opacity="0.8"/>'
        '<line x1="10" y1="21" x2="22" y2="21" stroke="white" stroke-width="1.5" opacity="0.8"/>'
        '<line x1="10" y1="24" x2="22" y2="24" stroke="white" stroke-width="1.5" opacity="0.8"/>'
        '</svg>'
    ),

    "unknown": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        '<rect x="4" y="8" width="24" height="7" rx="2" fill="#95a5a6" stroke="#7f8c8d" stroke-width="0.5"/>'
        '<rect x="6" y="14" width="20" height="13" rx="2" fill="#bdc3c7" stroke="#95a5a6" stroke-width="1"/>'
        '<text x="16" y="24" text-anchor="middle" font-size="10" font-weight="700" '
        'fill="#7f8c8d" font-family="sans-serif">?</text>'
        '</svg>'
    ),
}

_CACHE_SIZE_SVGS: dict[str, str] = {
    "nano":       _size_circle("N"),
    "micro":      _size_circle("Mi"),
    "small":      _size_circle("S"),
    "regular":    _size_circle("R"),
    "large":      _size_circle("L"),
    "other":      _size_circle("?",  "#95a5a6", "#7f8c8d"),
    "not_chosen": _size_circle("—",  "#bdc3c7", "#95a5a6"),
}

# ── Map pin data ──────────────────────────────────────────────────────────────

_PIN_COLORS: dict[str, str] = {
    "traditional":           "#2ecc71",
    "multi":                 "#e67e22",
    "mystery":               "#3498db",
    "letterbox":             "#a0522d",
    "whereigo":              "#1abc9c",
    "earthcache":            "#27ae60",
    "virtual":               "#8e44ad",
    "webcam":                "#7f8c8d",
    "event":                 "#e74c3c",
    "cito":                  "#e74c3c",
    "mega_event":            "#e74c3c",
    "giga_event":            "#e74c3c",
    "lab_cache":             "#9b59b6",
    "gps_adventures":        "#16a085",
    "community_celebration": "#e74c3c",
    "found":                 "#f39c12",
    "dnf":                   "#c0392b",
    "disabled":              "#95a5a6",
    "archived":              "#616a6b",
    "unknown":               "#bdc3c7",
}

_PIN_LABELS: dict[str, str] = {
    "traditional":           "",
    "multi":                 "2+",
    "mystery":               "?",
    "letterbox":             "LB",
    "whereigo":              "W",
    "earthcache":            "E",
    "virtual":               "V",
    "webcam":                "",
    "event":                 "E",
    "cito":                  "C",
    "mega_event":            "M",
    "giga_event":            "G",
    "lab_cache":             "L",
    "gps_adventures":        "GPS",
    "community_celebration": "CC",
    "found":                 "✓",
    "dnf":                   "✗",
    "disabled":              "—",
    "archived":              "A",
    "unknown":               "?",
}

# ── Qt rendering ──────────────────────────────────────────────────────────────

def _svg_to_pixmap(svg_data: str, size: int = 32) -> QPixmap:
    """Render SVG string to QPixmap at given pixel size."""
    renderer = QSvgRenderer(QByteArray(svg_data.encode()))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def _normalize_key(raw: str) -> str:
    return (raw or "").lower().replace(" ", "_").replace("-", "_")


# ── Public API ────────────────────────────────────────────────────────────────

def get_cache_type_icon(cache_type: str, size: int = 32) -> QIcon:
    """
    Return QIcon for a cache type key.

    Known keys: traditional, multi, mystery, letterbox, whereigo,
                earthcache, virtual, webcam, event, cito, mega_event,
                giga_event, lab_cache, gps_adventures, community_celebration,
                found, dnf, disabled, archived, unknown.

    Falls back to "unknown" for unrecognised types.
    """
    svg = _CACHE_TYPE_SVGS.get(_normalize_key(cache_type), _CACHE_TYPE_SVGS["unknown"])
    return QIcon(_svg_to_pixmap(svg, size))


def get_cache_size_icon(cache_size: str, size: int = 32) -> QIcon:
    """
    Return QIcon for a cache container size.

    Known keys: nano, micro, small, regular, large, other, not_chosen.
    Falls back to "other" for unrecognised sizes.
    """
    svg = _CACHE_SIZE_SVGS.get(_normalize_key(cache_size), _CACHE_SIZE_SVGS["other"])
    return QIcon(_svg_to_pixmap(svg, size))


def get_cache_type_pixmap(cache_type: str, size: int = 32) -> QPixmap:
    """Return QPixmap for a cache type — useful for composite map overlays."""
    svg = _CACHE_TYPE_SVGS.get(_normalize_key(cache_type), _CACHE_TYPE_SVGS["unknown"])
    return _svg_to_pixmap(svg, size)


def get_map_pin_html(cache_type: str) -> str:
    """
    Return HTML string for a Leaflet divIcon map pin.

    Usage in map_widget.py JavaScript:
        L.marker([lat, lng], {
            icon: L.divIcon({
                html: '<pin_html_here>',
                iconSize: [24, 32],
                iconAnchor: [12, 32],
                popupAnchor: [0, -32],
                className: ''
            })
        })
    """
    key = _normalize_key(cache_type)
    color = _PIN_COLORS.get(key, "#bdc3c7")
    label = _PIN_LABELS.get(key, "")

    label_span = (
        f'<span style="position:absolute;top:4px;left:0;right:0;text-align:center;'
        f'font-size:7px;font-weight:700;color:white;font-family:sans-serif;'
        f'line-height:1;">{label}</span>'
    ) if label else ""

    return (
        f'<div style="position:relative;width:24px;height:32px;">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 32" '
        f'width="24" height="32" style="display:block;">'
        f'<path d="M12 2 C5 2 2 8 2 13 C2 21 12 30 12 30 C12 30 22 21 22 13 C22 8 19 2 12 2Z" '
        f'fill="{color}" stroke="rgba(0,0,0,0.3)" stroke-width="1"/>'
        f'<circle cx="12" cy="12" r="6" fill="white" opacity="0.25"/>'
        f'</svg>'
        f'{label_span}'
        f'</div>'
    )


def get_all_type_keys() -> list[str]:
    """Return sorted list of all known cache type keys."""
    return sorted(_CACHE_TYPE_SVGS.keys())


def get_all_size_keys() -> list[str]:
    """Return sorted list of all known cache size keys."""
    return sorted(_CACHE_SIZE_SVGS.keys())
