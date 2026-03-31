"""
src/opensak/coords.py — Coordinate format conversion utilities.

Supported formats:
  DD   — Decimal Degrees:        55.78750, 12.41667
  DMM  — Degrees Decimal Minutes: N55 47.250 E012 25.000
  DMS  — Degrees Minutes Seconds: N55° 47' 15" E012° 25' 00"
"""

from __future__ import annotations

FORMAT_DD  = "dd"
FORMAT_DMM = "dmm"
FORMAT_DMS = "dms"

FORMATS = {
    FORMAT_DMM: "DMM  —  N55 47.250 E012 25.000",
    FORMAT_DMS: "DMS  —  N55° 47' 15\" E012° 25' 00\"",
    FORMAT_DD:  "DD   —  55.78750, 12.41667",
}


def _dd_to_dmm(lat: float, lon: float) -> str:
    """Convert decimal degrees to DMM string (geocaching standard)."""
    lat_h = "N" if lat >= 0 else "S"
    lon_h = "E" if lon >= 0 else "W"
    lat_abs = abs(lat)
    lon_abs = abs(lon)
    lat_deg = int(lat_abs)
    lon_deg = int(lon_abs)
    lat_min = (lat_abs - lat_deg) * 60
    lon_min = (lon_abs - lon_deg) * 60
    return f"{lat_h}{lat_deg:02d} {lat_min:06.3f}  {lon_h}{lon_deg:03d} {lon_min:06.3f}"


def _dd_to_dms(lat: float, lon: float) -> str:
    """Convert decimal degrees to DMS string."""
    lat_h = "N" if lat >= 0 else "S"
    lon_h = "E" if lon >= 0 else "W"
    lat_abs = abs(lat)
    lon_abs = abs(lon)
    lat_deg = int(lat_abs)
    lon_deg = int(lon_abs)
    lat_min = int((lat_abs - lat_deg) * 60)
    lon_min = int((lon_abs - lon_deg) * 60)
    lat_sec = (lat_abs - lat_deg - lat_min / 60) * 3600
    lon_sec = (lon_abs - lon_deg - lon_min / 60) * 3600
    return (
        f"{lat_h}{lat_deg:02d}° {lat_min:02d}' {lat_sec:05.2f}\"  "
        f"{lon_h}{lon_deg:03d}° {lon_min:02d}' {lon_sec:05.2f}\""
    )


def _dd_to_dd(lat: float, lon: float) -> str:
    """Format decimal degrees."""
    return f"{lat:.5f}, {lon:.5f}"


def format_coords(lat: float, lon: float, fmt: str) -> str:
    """Return a coordinate string in the requested format."""
    if fmt == FORMAT_DMS:
        return _dd_to_dms(lat, lon)
    if fmt == FORMAT_DD:
        return _dd_to_dd(lat, lon)
    return _dd_to_dmm(lat, lon)   # default: DMM


# ── Parsing (for the converter dialog input) ──────────────────────────────────

def parse_coords(text: str) -> tuple[float, float] | None:
    """
    Try to parse a coordinate string in any of the three supported formats.
    Returns (lat, lon) as decimal degrees, or None if parsing fails.
    """
    import re
    text = text.strip()

    # DD: "55.78750, 12.41667" or "55.78750 12.41667"
    m = re.match(
        r'^([+-]?\d+\.\d+)[,\s]+([+-]?\d+\.\d+)$', text
    )
    if m:
        return float(m.group(1)), float(m.group(2))

    # DMM: "N55 47.250 E012 25.000" / "S12 30.500 W077 02.300"
    m = re.match(
        r'^([NSns])\s*(\d{1,3})\s+(\d+\.\d+)\s+([EWew])\s*(\d{1,3})\s+(\d+\.\d+)$',
        text
    )
    if m:
        lat_h, lat_d, lat_m, lon_h, lon_d, lon_m = m.groups()
        lat = int(lat_d) + float(lat_m) / 60
        lon = int(lon_d) + float(lon_m) / 60
        if lat_h.upper() == "S":
            lat = -lat
        if lon_h.upper() == "W":
            lon = -lon
        return lat, lon

    # DMS: "N55° 47' 15.00" E012° 25' 00.00""
    m = re.match(
        r'^([NSns])\s*(\d{1,3})[°\s]\s*(\d{1,2})[\'′\s]\s*(\d+(?:\.\d+)?)["\s]*'
        r'\s+([EWew])\s*(\d{1,3})[°\s]\s*(\d{1,2})[\'′\s]\s*(\d+(?:\.\d+)?)["\s]*$',
        text
    )
    if m:
        lat_h, lat_d, lat_m, lat_s, lon_h, lon_d, lon_m, lon_s = m.groups()
        lat = int(lat_d) + int(lat_m) / 60 + float(lat_s) / 3600
        lon = int(lon_d) + int(lon_m) / 60 + float(lon_s) / 3600
        if lat_h.upper() == "S":
            lat = -lat
        if lon_h.upper() == "W":
            lon = -lon
        return lat, lon

    return None
