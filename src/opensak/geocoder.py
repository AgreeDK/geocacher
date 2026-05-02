"""
src/opensak/geocoder.py — Reverse geocoding for OpenSAK.

Two-phase hybrid approach:
  1. fast_batch_geocode()  — offline, instant for any number of caches.
                             Uses the bundled reverse_geocoder KD-tree.
                             Returns country + state + county (GeoNames data).
  2. nominatim_county()   — online, 1 req/sec (Nominatim ToS).
                             Returns a more accurate county using OSM polygons.
                             Used as a refinement pass after the fast phase.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import NamedTuple

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "OpenSAK/1.0 (https://github.com/OpenSAK/OpenSAK; geocoding feature)"
REQUEST_TIMEOUT = 10


class GeoLocation(NamedTuple):
    country: str | None
    state: str | None
    county: str | None


# ── Phase 1: fast offline batch geocoding ─────────────────────────────────────

def fast_batch_geocode(coords: list[tuple[float, float]]) -> list[GeoLocation]:
    """
    Batch reverse-geocode a list of (lat, lon) pairs using the local
    reverse_geocoder KD-tree (GeoNames data, bundled with the library).

    Returns one GeoLocation per input coordinate.
    Processes tens of thousands of points in under a second.
    Falls back to GeoLocation(None, None, None) on any error.
    """
    import reverse_geocoder
    import pycountry

    try:
        results = reverse_geocoder.search(coords, verbose=False)
    except Exception:
        return [GeoLocation(None, None, None)] * len(coords)

    out: list[GeoLocation] = []
    for r in results:
        cc = r.get("cc", "")
        try:
            country = pycountry.countries.get(alpha_2=cc).name if cc else None
        except AttributeError:
            country = cc or None

        state  = r.get("admin1") or None
        county = r.get("admin2") or None
        out.append(GeoLocation(country=country, state=state, county=county))

    return out


# ── Phase 2: Nominatim refinement for county ──────────────────────────────────

def nominatim_county(lat: float, lon: float) -> str | None:
    """
    Query Nominatim for the county at (lat, lon).

    Returns the county string, or None on failure or if no county exists.
    Caller must enforce the 1 req/sec rate limit.
    """
    params = urllib.parse.urlencode({
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1,
    })
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    address = data.get("address", {})
    return (
        address.get("county")
        or address.get("district")
        or address.get("municipality")
        or None
    )


# ── Legacy single-call helper (kept for tests) ────────────────────────────────

def reverse_geocode(lat: float, lon: float) -> GeoLocation | None:
    """Single Nominatim call returning all three fields. Used by unit tests."""
    params = urllib.parse.urlencode({
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1,
    })
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    address = data.get("address", {})
    country = address.get("country") or None
    state = (
        address.get("state")
        or address.get("province")
        or address.get("region")
        or None
    )
    county = (
        address.get("county")
        or address.get("district")
        or address.get("municipality")
        or None
    )
    return GeoLocation(country=country, state=state, county=county)
