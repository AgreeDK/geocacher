"""
src/opensak/geocoder.py — Reverse geocoding via Nominatim (OpenStreetMap).

Converts (lat, lon) → (country, state, county) using the public Nominatim API.
Uses the same OSM boundary data as project-gc.

Rate limit: callers must wait at least 1 second between requests per Nominatim ToS.
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


def reverse_geocode(lat: float, lon: float) -> GeoLocation | None:
    """
    Query Nominatim for (country, state, county) at the given coordinates.

    Returns a GeoLocation namedtuple, or None on network/parse failure.
    All three fields may be None if Nominatim has no data for that level.

    Raises no exceptions — errors are caught and return None so callers
    can handle them as skipped entries.
    """
    params = urllib.parse.urlencode({
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,  # county level
        "addressdetails": 1,
    })
    url = f"{NOMINATIM_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    address = data.get("address", {})

    country = address.get("country") or None
    # "state" covers US states, German Länder, etc.
    state = (
        address.get("state")
        or address.get("province")
        or address.get("region")
        or None
    )
    # "county" covers US counties, UK districts, French départements, etc.
    county = (
        address.get("county")
        or address.get("district")
        or address.get("municipality")
        or None
    )

    return GeoLocation(country=country, state=state, county=county)
