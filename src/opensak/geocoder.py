"""
src/opensak/geocoder.py — Reverse geocoding for OpenSAK.

Phase 1 — fast_batch_geocode(): offline, KD-tree (GeoNames), no network,
processes tens of thousands of points in under a second.

Phase 2 — nominatim_reverse(): single-point lookup via Nominatim/OSM,
higher accuracy (polygon-based), requires internet, 1 request/second limit.
Caller is responsible for enforcing the rate limit.
"""

from __future__ import annotations

from typing import NamedTuple


class GeoLocation(NamedTuple):
    country: str | None
    state: str | None
    county: str | None


def fast_batch_geocode(coords: list[tuple[float, float]]) -> list[GeoLocation]:
    """
    Batch reverse-geocode a list of (lat, lon) pairs using the local
    reverse_geocoder KD-tree (GeoNames data, bundled with the library).

    Returns one GeoLocation per input coordinate.
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


def nominatim_reverse(lat: float, lon: float, *, timeout: int = 10) -> GeoLocation:
    """
    Query Nominatim reverse geocoding API for a single (lat, lon) coordinate.

    Caller must enforce the 1 request/second rate limit (Nominatim usage policy).
    Returns whatever fields Nominatim provides; missing fields become None.
    Falls back to GeoLocation(None, None, None) on any network or parse error.
    """
    import json
    import urllib.parse
    import urllib.request
    import pycountry

    params = urllib.parse.urlencode({
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1,
        "zoom": 10,
    })
    url = f"https://nominatim.openstreetmap.org/reverse?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OpenSAK/1.0 (https://github.com/AgreeDK/opensak)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return GeoLocation(None, None, None)

    address = data.get("address", {})

    cc = address.get("country_code", "").upper()
    try:
        country = pycountry.countries.get(alpha_2=cc).name if cc else None
    except AttributeError:
        country = address.get("country") or None

    state = address.get("state") or None

    # OSM uses several fields for sub-state regions depending on the country
    county = (
        address.get("county")
        or address.get("district")
        or address.get("municipality")
        or address.get("city_district")
        or None
    )

    return GeoLocation(country=country, state=state, county=county)
