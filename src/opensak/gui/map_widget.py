"""
src/opensak/gui/map_widget.py — Interaktivt OSM kort via Leaflet.js + QtWebEngine.

Viser cache pins med farvekodet ikoner efter type.
Kommunikerer med Python via QWebChannel.
"""

from __future__ import annotations
import json
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, QUrl, Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineUrlRequestInterceptor, QWebEngineProfile
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWidgets import QWidget, QVBoxLayout

from opensak.db.models import Cache
from opensak.utils.types import GcCode


# ── Tile request interceptor (sætter Referer header for OSM tiles) ───────────

class TileInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info) -> None:
        url = info.requestUrl().toString()
        if "tile.openstreetmap.org" in url:
            info.setHttpHeader(b"Referer", b"https://www.openstreetmap.org/")

# ── Cache type → Leaflet marker farve ────────────────────────────────────────

from opensak.utils.constants import CACHE_COLOURS, DEFAULT_CACHE_COLOUR


def _cache_colour(cache_type: str) -> str:
    return CACHE_COLOURS.get(cache_type, DEFAULT_CACHE_COLOUR)


# ── Python ↔ JavaScript bro ───────────────────────────────────────────────────

class MapBridge(QObject):
    """
    Eksponeres til JavaScript via QWebChannel.
    JavaScript kalder Python metoder via window.bridge.
    """
    # Signal afsendt når brugeren klikker en pin på kortet
    cache_clicked = Signal(str)   # gc_code

    @Slot(str)
    def on_cache_clicked(self, gc_code: GcCode) -> None:
        """Kaldes fra JavaScript når en pin klikkes."""
        self.cache_clicked.emit(gc_code)


# ── HTML template med Leaflet.js ──────────────────────────────────────────────

MAP_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenSAK Map</title>

<!-- Leaflet CSS -->
<link rel="stylesheet"
  href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>

<!-- Leaflet MarkerCluster CSS -->
<link rel="stylesheet"
  href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"/>
<link rel="stylesheet"
  href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"/>

<style>
  html, body, #map { height: 100%; margin: 0; padding: 0; }
  .cache-pin {
    width: 22px; height: 22px;
    border-radius: 50% 50% 50% 0;
    transform: rotate(-45deg);
    border: 2px solid #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,0.5);
  }
  .cache-pin-found { opacity: 0.45; }
  .cache-pin-corrected {
    outline: 3px solid #e65100;
    outline-offset: 2px;
    border-radius: 50% 50% 50% 0;
  }
  .home-marker {
    width: 16px; height: 16px;
    background: #e53935;
    border-radius: 50%;
    border: 3px solid #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,0.5);
  }
</style>
</head>
<body>
<div id="map"></div>

<!-- Leaflet JS -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- Leaflet MarkerCluster -->
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>

<!-- Qt WebChannel -->
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>

<script>
// ── Kort initialisering ───────────────────────────────────────────────────────
var map = L.map('map', {
    center: [56.0, 10.5],
    zoom: 7,
    zoomControl: true
});

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
    crossOrigin: true
}).addTo(map);

// ── Marker cluster gruppe ─────────────────────────────────────────────────────
var clusterGroup = L.markerClusterGroup({
    maxClusterRadius: 40,
    showCoverageOnHover: false
});
map.addLayer(clusterGroup);

// ── State ─────────────────────────────────────────────────────────────────────
var markers = {};          // gc_code → marker
var homeMarker = null;
var selectedGcCode = null;
var bridge = null;

// ── WebChannel setup ──────────────────────────────────────────────────────────
new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;
});

// ── Hjælpefunktioner ──────────────────────────────────────────────────────────
function makePinIcon(colour, found, corrected) {
    var cls = 'cache-pin' + (found ? ' cache-pin-found' : '') + (corrected ? ' cache-pin-corrected' : '');
    return L.divIcon({
        className: '',
        html: '<div class="' + cls + '" style="background:' + colour + '"></div>',
        iconSize: [22, 22],
        iconAnchor: [11, 22],
        popupAnchor: [0, -24]
    });
}

function makeHomeIcon() {
    return L.divIcon({
        className: '',
        html: '<div class="home-marker"></div>',
        iconSize: [16, 16],
        iconAnchor: [8, 8]
    });
}

// ── Public API kaldt fra Python ───────────────────────────────────────────────

function loadCaches(cachesJson) {
    var caches = JSON.parse(cachesJson);
    clusterGroup.clearLayers();
    markers = {};

    caches.forEach(function(c) {
        if (!c.lat || !c.lon) return;

        var lat = c.corrected ? c.clat : c.lat;
        var lon = c.corrected ? c.clon : c.lon;
        var marker = L.marker([lat, lon], {
            icon: makePinIcon(c.colour, c.found, c.corrected),
            title: c.name + (c.corrected ? ' 📍' : '')
        });

        var coordNote = c.corrected
            ? '<br><span style="color:#e65100;font-size:11px">📍 Korrigerede koordinater</span>'
            : '';
        marker.bindPopup(
            '<b>' + c.gc_code + '</b><br>' +
            c.name + '<br>' +
            '<span style="color:gray">' + c.cache_type + ' D' + c.difficulty + '/T' + c.terrain + '</span>' +
            coordNote
        );

        marker.on('click', function() {
            if (bridge) bridge.on_cache_clicked(c.gc_code);
            selectMarker(c.gc_code);
        });

        markers[c.gc_code] = marker;
        clusterGroup.addLayer(marker);
    });
}

function setHomeLocation(lat, lon) {
    if (homeMarker) map.removeLayer(homeMarker);
    homeMarker = L.marker([lat, lon], {
        icon: makeHomeIcon(),
        zIndexOffset: 1000,
        title: 'Hjem'
    }).addTo(map);
    homeMarker.bindPopup('<b>Hjem</b>');
}

function panToCache(gcCode) {
    var marker = markers[gcCode];
    if (marker) {
        // Unspiderfy cluster if needed
        clusterGroup.zoomToShowLayer(marker, function() {
            map.panTo(marker.getLatLng());
            marker.openPopup();
        });
        selectMarker(gcCode);
    }
}

function selectMarker(gcCode) {
    // Reset previous
    if (selectedGcCode && markers[selectedGcCode]) {
        var prev = markers[selectedGcCode];
        var prevData = prev._cacheData;
        if (prevData) {
            prev.setIcon(makePinIcon(prevData.colour, prevData.found, prevData.corrected));
        }
    }
    selectedGcCode = gcCode;
}

function fitAllMarkers() {
    if (Object.keys(markers).length > 0) {
        map.fitBounds(clusterGroup.getBounds(), {padding: [30, 30]});
    }
}

function panToHome() {
    if (homeMarker) {
        map.panTo(homeMarker.getLatLng());
        map.setZoom(12);
    }
}
</script>
</body>
</html>
"""


# ── Map widget ────────────────────────────────────────────────────────────────

class MapWidget(QWidget):
    """
    Interaktivt OSM kort.
    Sender cache_selected signal når en pin klikkes.
    """

    cache_selected = Signal(str)   # gc_code

    def __init__(self, parent=None):
        super().__init__(parent)
        self._caches: list[Cache] = []
        self._ready = False
        self._pending_caches = None
        self._pending_home = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = QWebEngineView()

        # Sæt tile interceptor på profilen
        self._interceptor = TileInterceptor()
        profile = QWebEngineProfile.defaultProfile()
        profile.setUrlRequestInterceptor(self._interceptor)

        self._page = self._view.page()

        # Sæt op WebChannel til Python ↔ JS kommunikation
        self._channel = QWebChannel()
        self._bridge = MapBridge()
        self._bridge.cache_clicked.connect(self.cache_selected)
        self._channel.registerObject("bridge", self._bridge)
        self._page.setWebChannel(self._channel)

        # Load kortet
        self._page.loadFinished.connect(self._on_load_finished)
        self._page.setHtml(MAP_HTML, QUrl("qrc:///"))

        layout.addWidget(self._view)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            return
        self._ready = True

        # Sæt hjemkoordinat
        from opensak.gui.settings import get_settings
        s = get_settings()
        self._run_js(f"setHomeLocation({s.home_lat}, {s.home_lon})")

        # Indlæs ventende caches hvis der er nogen
        if self._pending_caches is not None:
            self._do_load_caches(self._pending_caches)
            self._pending_caches = None

    def _run_js(self, js: str) -> None:
        """Kør JavaScript i kortvisningen."""
        self._page.runJavaScript(js)

    def load_caches(self, caches: list[Cache]) -> None:
        """Indlæs caches på kortet."""
        self._caches = caches
        if self._ready:
            self._do_load_caches(caches)
        else:
            self._pending_caches = caches

    def _do_load_caches(self, caches: list[Cache]) -> None:
        from opensak.gps.garmin import _effective_coords
        data = []
        for c in caches:
            if c.latitude is None or c.longitude is None:
                continue
            note = getattr(c, "user_note", None)
            has_corrected = bool(note and getattr(note, "is_corrected", False))
            eff_lat, eff_lon = _effective_coords(c)
            data.append({
                "gc_code":    c.gc_code,
                "name":       c.name or "",
                "cache_type": c.cache_type or "",
                "difficulty": c.difficulty or 0,
                "terrain":    c.terrain or 0,
                "lat":        c.latitude,
                "lon":        c.longitude,
                "clat":       eff_lat,       # korrigeret lat (samme som lat hvis ikke korrigeret)
                "clon":       eff_lon,       # korrigeret lon
                "corrected":  has_corrected,
                "colour":     _cache_colour(c.cache_type or ""),
                "found":      c.found,
            })

        json_str = json.dumps(data, ensure_ascii=False)
        # Escape backticks for JS template literal
        json_str = json_str.replace("\\", "\\\\").replace("`", "\\`")
        self._run_js(f"loadCaches(`{json_str}`)")

        # Zoom til alle markers
        if data:
            self._run_js("fitAllMarkers()")

    def pan_to_cache(self, gc_code: GcCode) -> None:
        """Centrér kortet på en bestemt cache."""
        if self._ready:
            safe = gc_code.replace("'", "\\'")
            self._run_js(f"panToCache('{safe}')")

    def update_home(self) -> None:
        """Opdatér hjemkoordinat markøren fra indstillinger."""
        from opensak.gui.settings import get_settings
        s = get_settings()
        if self._ready:
            self._run_js(f"setHomeLocation({s.home_lat}, {s.home_lon})")

    def fit_all(self) -> None:
        if self._ready:
            self._run_js("fitAllMarkers()")

    def pan_to_home(self) -> None:
        if self._ready:
            self._run_js("panToHome()")
