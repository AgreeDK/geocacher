"""
src/opensak/gps/garmin.py — Garmin GPS device detection og GPX export.

Understøtter alle Garmin enheder der monteres som USB drev og
accepterer GPX filer i /Garmin/GPX/ mappen.

Testet med: GPSMAP64s, Oregon750
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Optional


# ── Garmin GPX mappe på enheden ───────────────────────────────────────────────

GARMIN_GPX_SUBPATH = Path("Garmin") / "GPX"
GARMIN_MARKERS = [
    Path("Garmin") / "GarminDevice.xml",
    Path("Garmin") / "GPX",
    Path(".is_garmin"),
]


# ── Enhed detektion ───────────────────────────────────────────────────────────

def find_garmin_devices() -> list[Path]:
    """
    Find alle monterede Garmin GPS enheder.
    Returnerer liste af rod-stier (mount points).

    Virker på Linux, Windows og macOS.
    """
    candidates = _get_mount_points()
    devices = []

    for mount in candidates:
        if _is_garmin(mount):
            devices.append(mount)

    return devices


def _is_garmin(path: Path) -> bool:
    """Tjek om en mappe er en Garmin enhed."""
    for marker in GARMIN_MARKERS:
        if (path / marker).exists():
            return True
    return False


def _get_mount_points() -> list[Path]:
    """Returner liste af mulige mount points afhængig af OS."""
    system = platform.system()

    if system == "Linux":
        return _linux_mounts()
    elif system == "Windows":
        return _windows_drives()
    elif system == "Darwin":
        return _macos_volumes()
    return []


def _linux_mounts() -> list[Path]:
    """
    Find USB mount points på Linux.

    Strategi (i prioriteret rækkefølge):
    1. lsblk — den mest pålidelige metode (returnerer kun faktiske mount points)
    2. /proc/mounts — fallback med korrekt operator-prioritet
    3. Direkte scanning af /media og /run/media — kun ét niveau dybt
    """
    candidates: set[Path] = set()

    # ── Metode 1: lsblk (bedst) ───────────────────────────────────────────────
    try:
        result = subprocess.run(
            ["lsblk", "--output", "MOUNTPOINT", "--raw", "--noheadings"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line == "/":
                continue
            mount = Path(line)
            if mount.is_dir() and _is_removable_path(mount):
                candidates.add(mount)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # ── Metode 2: /proc/mounts (fallback) ─────────────────────────────────────
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                device, mountpoint, fstype = parts[0], parts[1], parts[2]
                mount = Path(mountpoint)
                # VIGTIGT: korrekt operator-prioritet med parenteser
                if mount.is_dir() and (
                    device.startswith("/dev/sd")
                    or device.startswith("/dev/sdb")
                    or fstype in ("vfat", "exfat", "ntfs", "msdos")
                ):
                    if _is_removable_path(mount):
                        candidates.add(mount)
    except (OSError, PermissionError):
        pass

    # ── Metode 3: Direkte scanning — kun ét niveau dybt ───────────────────────
    # /media/username/DEVICE  eller  /run/media/username/DEVICE
    import getpass
    username = getpass.getuser()

    for base in [
        Path("/media") / username,
        Path("/run/media") / username,
        Path("/media"),
        Path("/mnt"),
    ]:
        if not base.exists():
            continue
        for item in base.iterdir():          # iterdir() = kun ét niveau (ikke rglob!)
            if item.is_dir() and item != base:
                candidates.add(item)
        # Tjek også ét niveau dybere (f.eks. /media/username/DEVICE)
        for sub in base.glob("*/"):
            if sub.is_dir():
                candidates.add(sub)

    return list(candidates)


def _is_removable_path(path: Path) -> bool:
    """Returner True hvis stien ser ud til at være et flytbart medie."""
    path_str = str(path)
    removable_prefixes = (
        "/media/",
        "/run/media/",
        "/mnt/",
    )
    # Udeluk systemstier
    system_paths = ("/", "/boot", "/home", "/usr", "/var", "/etc", "/tmp",
                    "/proc", "/sys", "/dev", "/run/user")
    if path_str in system_paths:
        return False
    # Accepter kendte flytbare stier
    if any(path_str.startswith(p) for p in removable_prefixes):
        return True
    # Tjek via /sys/block om det er en flytbar enhed
    try:
        result = subprocess.run(
            ["lsblk", "--output", "MOUNTPOINT,RM", "--raw", "--noheadings"],
            capture_output=True, text=True, timeout=3,
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and parts[0] == path_str and parts[1] == "1":
                return True
    except Exception:
        pass
    return False


def _windows_drives() -> list[Path]:
    """Find alle drevbogstaver på Windows."""
    import string
    drives = []
    for letter in string.ascii_uppercase:
        p = Path(f"{letter}:\\")
        if p.exists():
            drives.append(p)
    return drives


def _macos_volumes() -> list[Path]:
    """Find monterede volumes på macOS."""
    volumes = Path("/Volumes")
    if not volumes.exists():
        return []
    return [v for v in volumes.iterdir() if v.is_dir()]


def get_garmin_gpx_path(device_root: Path) -> Path:
    """Returner stien til GPX mappen på en Garmin enhed."""
    return device_root / GARMIN_GPX_SUBPATH


# ── Debug hjælper ─────────────────────────────────────────────────────────────

def debug_scan() -> str:
    """
    Returnerer en tekststreng med debug-info om hvad der scannes.
    Bruges fra GUI til at vise fejlsøgnings-info.
    """
    lines = ["=== Garmin scan debug ===", f"OS: {platform.system()}"]

    mounts = _get_mount_points()
    lines.append(f"\nFundne mount points ({len(mounts)}):")
    for m in sorted(mounts):
        is_g = _is_garmin(m)
        lines.append(f"  {'✓ GARMIN' if is_g else '○'} {m}")

    lines.append(f"\nGarmin enheder: {find_garmin_devices() or 'ingen fundet'}")
    return "\n".join(lines)


# ── GPX generator ─────────────────────────────────────────────────────────────

def generate_gpx(caches: list, filename: str = "opensak_export") -> str:
    """
    Generer GPX 1.1 indhold fra en liste af Cache objekter.
    Returnerer GPX som en streng klar til at skrive til fil.
    """
    from xml.etree.ElementTree import Element, SubElement
    import xml.etree.ElementTree as ET
    from datetime import datetime, timezone

    # Root element
    gpx = Element("gpx")
    gpx.set("version", "1.1")
    gpx.set("creator", "OpenSAK")
    gpx.set("xmlns", "http://www.topografix.com/GPX/1/1")
    gpx.set("xmlns:groundspeak", "http://www.groundspeak.com/cache/1/0/1")
    gpx.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")

    # Metadata
    metadata = SubElement(gpx, "metadata")
    name_el = SubElement(metadata, "name")
    name_el.text = filename
    time_el = SubElement(metadata, "time")
    time_el.text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for cache in caches:
        if cache.latitude is None or cache.longitude is None:
            continue

        wpt = SubElement(gpx, "wpt")
        wpt.set("lat", f"{cache.latitude:.6f}")
        wpt.set("lon", f"{cache.longitude:.6f}")

        if cache.hidden_date:
            time_wpt = SubElement(wpt, "time")
            time_wpt.text = cache.hidden_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        name_wpt = SubElement(wpt, "name")
        name_wpt.text = cache.gc_code or ""

        desc_wpt = SubElement(wpt, "desc")
        desc_wpt.text = (
            f"{cache.name} by {cache.placed_by or '?'}, "
            f"{cache.cache_type or ''} "
            f"({cache.difficulty or '?'}/{cache.terrain or '?'})"
        )

        sym = SubElement(wpt, "sym")
        sym.text = _cache_symbol(cache.cache_type or "")

        type_el = SubElement(wpt, "type")
        type_el.text = f"Geocache|{cache.cache_type or 'Traditional Cache'}"

        # Groundspeak extension
        gs_cache = SubElement(wpt, "groundspeak:cache")
        gs_cache.set("id", str(cache.id or "0"))
        gs_cache.set("available", "True" if cache.available else "False")
        gs_cache.set("archived", "True" if cache.archived else "False")

        gs_name = SubElement(gs_cache, "groundspeak:name")
        gs_name.text = cache.name or ""

        gs_placed = SubElement(gs_cache, "groundspeak:placed_by")
        gs_placed.text = cache.placed_by or ""

        gs_type = SubElement(gs_cache, "groundspeak:type")
        gs_type.text = cache.cache_type or "Traditional Cache"

        gs_container = SubElement(gs_cache, "groundspeak:container")
        gs_container.text = cache.container or "Regular"

        gs_diff = SubElement(gs_cache, "groundspeak:difficulty")
        gs_diff.text = str(cache.difficulty or 1.0)

        gs_terr = SubElement(gs_cache, "groundspeak:terrain")
        gs_terr.text = str(cache.terrain or 1.0)

        if cache.country:
            gs_country = SubElement(gs_cache, "groundspeak:country")
            gs_country.text = cache.country

        if cache.encoded_hints:
            gs_hints = SubElement(gs_cache, "groundspeak:encoded_hints")
            gs_hints.text = cache.encoded_hints

        # Logs (max 5)
        if cache.logs:
            gs_logs = SubElement(gs_cache, "groundspeak:logs")
            for log in sorted(
                cache.logs,
                key=lambda l: l.log_date or 0,
                reverse=True,
            )[:5]:
                gs_log = SubElement(gs_logs, "groundspeak:log")
                gs_log.set("id", log.log_id or "0")
                gs_date = SubElement(gs_log, "groundspeak:date")
                gs_date.text = (
                    log.log_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if log.log_date else "2000-01-01T00:00:00Z"
                )
                gs_ltype = SubElement(gs_log, "groundspeak:type")
                gs_ltype.text = log.log_type or ""
                gs_finder = SubElement(gs_log, "groundspeak:finder")
                gs_finder.text = log.finder or ""
                gs_text = SubElement(gs_log, "groundspeak:text")
                gs_text.set("encoded", "False")
                gs_text.text = (log.text or "")[:500]

    _indent(gpx)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(
        gpx, encoding="unicode"
    )


def _cache_symbol(cache_type: str) -> str:
    """Returner Garmin symbol navn for en cache type."""
    symbols = {
        "Traditional Cache": "Geocache",
        "Multi-cache":        "Geocache",
        "Unknown Cache":      "Geocache",
        "Letterbox Hybrid":   "Geocache",
        "Wherigo Cache":      "Geocache",
        "Event Cache":        "Geocache",
        "Earthcache":         "Geocache",
        "Virtual Cache":      "Geocache",
    }
    return symbols.get(cache_type, "Geocache")


def _indent(elem, level: int = 0) -> None:
    """Tilføj indrykning til XML elementet for læsbarhed."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


# ── Export til enhed ──────────────────────────────────────────────────────────

class ExportResult:
    """Resultat af en GPS export."""

    def __init__(self):
        self.device:      Optional[Path] = None
        self.file_path:   Optional[Path] = None
        self.cache_count: int = 0
        self.error:       Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None

    def __str__(self) -> str:
        if self.success:
            return (
                f"✓ {self.cache_count} caches eksporteret\n"
                f"  Enhed: {self.device}\n"
                f"  Fil: {self.file_path.name}"
            )
        return f"✗ Fejl: {self.error}"


def export_to_device(
    caches: list,
    device_root: Path,
    filename: str = "opensak",
) -> ExportResult:
    """
    Eksportér caches til en Garmin GPS enhed.

    Parameters
    ----------
    caches      : Liste af Cache objekter
    device_root : Rod-sti til GPS enheden
    filename    : Filnavn (uden .gpx extension)
    """
    result = ExportResult()
    result.device = device_root

    try:
        gpx_dir = get_garmin_gpx_path(device_root)
        gpx_dir.mkdir(parents=True, exist_ok=True)

        gpx_content = generate_gpx(caches, filename)

        output_path = gpx_dir / f"{filename}.gpx"
        output_path.write_text(gpx_content, encoding="utf-8")

        result.file_path   = output_path
        result.cache_count = len([c for c in caches if c.latitude is not None])

    except PermissionError:
        result.error = "Adgang nægtet — er GPS enheden skrivebeskyttet?"
    except OSError as e:
        result.error = f"Fil fejl: {e}"
    except Exception as e:
        result.error = f"Uventet fejl: {e}"

    return result


def export_to_file(
    caches: list,
    output_path: Path,
) -> ExportResult:
    """
    Eksportér caches til en GPX fil (valgfri placering).
    Bruges når GPS ikke er tilsluttet.
    """
    result = ExportResult()

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        gpx_content = generate_gpx(caches, output_path.stem)
        output_path.write_text(gpx_content, encoding="utf-8")
        result.file_path   = output_path
        result.cache_count = len([c for c in caches if c.latitude is not None])
    except Exception as e:
        result.error = str(e)

    return result
