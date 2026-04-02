"""
src/opensak/gui/settings.py — Application settings using QSettings.

Settings are stored in:
  Linux:   ~/.config/OpenSAK Project/OpenSAK.ini
  Windows: Registry or %APPDATA%/OpenSAK Project/OpenSAK.ini
"""

from __future__ import annotations
import json
from PySide6.QtCore import QSettings


# ── Hjemmepunkt dataklasse ────────────────────────────────────────────────────

class HomePoint:
    """Et navngivet hjemmepunkt."""

    def __init__(self, name: str, lat: float, lon: float):
        self.name = name
        self.lat  = lat
        self.lon  = lon

    def to_dict(self) -> dict:
        return {"name": self.name, "lat": self.lat, "lon": self.lon}

    @staticmethod
    def from_dict(d: dict) -> "HomePoint":
        return HomePoint(d["name"], float(d["lat"]), float(d["lon"]))

    def __repr__(self) -> str:
        return f"HomePoint({self.name!r}, {self.lat}, {self.lon})"


class AppSettings:
    """Thin wrapper around QSettings with typed getters/setters."""

    def __init__(self):
        self._s = QSettings("OpenSAK Project", "OpenSAK")

    # ── Home location (per database) ──────────────────────────────────────────

    def _db_key(self, key: str) -> str:
        """Returner en QSettings nøgle der er unik per aktiv database."""
        try:
            from opensak.db.manager import get_db_manager
            manager = get_db_manager()
            if manager.active:
                safe = str(manager.active.path).replace("/", "_").replace("\\", "_")
                return f"db_{safe}/{key}"
        except Exception:
            pass
        return f"location/{key}"

    @property
    def home_lat(self) -> float:
        return float(self._s.value(self._db_key("home_lat"), 55.6761))

    @home_lat.setter
    def home_lat(self, value: float) -> None:
        self._s.setValue(self._db_key("home_lat"), value)

    @property
    def home_lon(self) -> float:
        return float(self._s.value(self._db_key("home_lon"), 12.5683))

    @home_lon.setter
    def home_lon(self, value: float) -> None:
        self._s.setValue(self._db_key("home_lon"), value)

    # ── Globale hjemmepunkter (liste) ─────────────────────────────────────────

    @property
    def home_points(self) -> list[HomePoint]:
        """Global liste af navngivne hjemmepunkter."""
        raw = self._s.value("homepoints/list", None)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return [HomePoint.from_dict(d) for d in data]
        except Exception:
            return []

    @home_points.setter
    def home_points(self, points: list[HomePoint]) -> None:
        self._s.setValue(
            "homepoints/list",
            json.dumps([p.to_dict() for p in points])
        )

    @property
    def active_home_name(self) -> str:
        """Navn på det aktive hjemmepunkt (globalt)."""
        return self._s.value("homepoints/active_name", "")

    @active_home_name.setter
    def active_home_name(self, value: str) -> None:
        self._s.setValue("homepoints/active_name", value)

    def set_active_home(self, point: HomePoint) -> None:
        """Sæt aktivt hjemmepunkt — opdaterer både global navn og per-db koordinater."""
        self.active_home_name = point.name
        self.home_lat = point.lat
        self.home_lon = point.lon
        self._s.sync()

    def get_active_home(self) -> HomePoint | None:
        """Returner det aktive hjemmepunkt fra listen, eller None."""
        name = self.active_home_name
        for p in self.home_points:
            if p.name == name:
                return p
        return None

    def add_or_update_home_point(self, point: HomePoint) -> None:
        """Tilføj nyt hjemmepunkt eller opdatér eksisterende med samme navn."""
        points = self.home_points
        for i, p in enumerate(points):
            if p.name == point.name:
                points[i] = point
                self.home_points = points
                return
        points.append(point)
        self.home_points = points

    def remove_home_point(self, name: str) -> None:
        """Fjern hjemmepunkt med det givne navn."""
        self.home_points = [p for p in self.home_points if p.name != name]
        if self.active_home_name == name:
            self.active_home_name = ""

    # ── Units ─────────────────────────────────────────────────────────────────

    @property
    def use_miles(self) -> bool:
        return self._s.value("display/use_miles", False, type=bool)

    @use_miles.setter
    def use_miles(self, value: bool) -> None:
        self._s.setValue("display/use_miles", value)

    # ── Koordinatformat ───────────────────────────────────────────────────────

    @property
    def coord_format(self) -> str:
        """Coordinate display format: 'dmm' (default), 'dms', or 'dd'."""
        return self._s.value("display/coord_format", "dmm")

    @coord_format.setter
    def coord_format(self, value: str) -> None:
        self._s.setValue("display/coord_format", value)

    # ── Kort udbyder ──────────────────────────────────────────────────────────

    @property
    def map_provider(self) -> str:
        return self._s.value("display/map_provider", "google")

    @map_provider.setter
    def map_provider(self, value: str) -> None:
        self._s.setValue("display/map_provider", value)

    def get_maps_url(self, lat: float, lon: float) -> str:
        if self.map_provider == "osm":
            return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=16"
        else:
            return f"https://www.google.com/maps?q={lat},{lon}"

    # ── Display ───────────────────────────────────────────────────────────────

    @property
    def show_archived(self) -> bool:
        return self._s.value("display/show_archived", False, type=bool)

    @show_archived.setter
    def show_archived(self, value: bool) -> None:
        self._s.setValue("display/show_archived", value)

    @property
    def show_found(self) -> bool:
        return self._s.value("display/show_found", True, type=bool)

    @show_found.setter
    def show_found(self, value: bool) -> None:
        self._s.setValue("display/show_found", value)

    # ── Window state ──────────────────────────────────────────────────────────

    @property
    def window_geometry(self):
        return self._s.value("window/geometry")

    @window_geometry.setter
    def window_geometry(self, value) -> None:
        self._s.setValue("window/geometry", value)

    @property
    def window_state(self):
        return self._s.value("window/state")

    @window_state.setter
    def window_state(self, value) -> None:
        self._s.setValue("window/state", value)

    @property
    def splitter_state(self):
        return self._s.value("window/splitter_state")

    @splitter_state.setter
    def splitter_state(self, value) -> None:
        self._s.setValue("window/splitter_state", value)

    # ── Last used paths ───────────────────────────────────────────────────────

    @property
    def last_import_dir(self) -> str:
        from pathlib import Path
        return self._s.value("paths/last_import_dir", str(Path.home()))

    @last_import_dir.setter
    def last_import_dir(self, value: str) -> None:
        self._s.setValue("paths/last_import_dir", value)

    def sync(self) -> None:
        self._s.sync()


# Module-level singleton
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings
