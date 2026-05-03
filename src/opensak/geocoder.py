"""
src/opensak/geocoder.py — Offline reverse geocoding for OpenSAK.

Uses the bundled reverse_geocoder KD-tree (GeoNames data).
Processes tens of thousands of points in under a second with no
network dependency, no API key, and no rate limits.
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
