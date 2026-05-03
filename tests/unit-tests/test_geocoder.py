"""
tests/unit-tests/test_geocoder.py — Unit tests for the offline reverse geocoder.

reverse_geocoder.search and pycountry are patched so no real lookups occur.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from opensak.geocoder import GeoLocation, fast_batch_geocode


def _mock_search(results: list[dict]):
    """Patch reverse_geocoder.search to return a fixed list of dicts."""
    return patch("reverse_geocoder.search", return_value=results)


def _mock_country(name: str | None):
    """Patch pycountry.countries.get to return a simple object."""
    if name is None:
        return patch("pycountry.countries.get", return_value=None)
    country_obj = MagicMock()
    country_obj.name = name
    return patch("pycountry.countries.get", return_value=country_obj)


# ── Happy-path tests ──────────────────────────────────────────────────────────

def test_single_full_result():
    raw = [{"cc": "US", "admin1": "California", "admin2": "Los Angeles County"}]
    with _mock_search(raw), _mock_country("United States"):
        result = fast_batch_geocode([(34.05, -118.24)])

    assert result == [GeoLocation(country="United States", state="California", county="Los Angeles County")]


def test_batch_returns_one_per_coord():
    raw = [
        {"cc": "US", "admin1": "Texas",   "admin2": "Travis County"},
        {"cc": "DK", "admin1": "Midtjylland", "admin2": "Aarhus"},
    ]
    country_obj = MagicMock()
    country_obj.name = "Denmark"
    countries_map = {"US": MagicMock(name="United States"), "DK": country_obj}

    with _mock_search(raw):
        with patch("pycountry.countries.get", side_effect=lambda alpha_2: countries_map.get(alpha_2)):
            result = fast_batch_geocode([(30.26, -97.74), (56.15, 10.21)])

    assert len(result) == 2
    assert result[1].state == "Midtjylland"
    assert result[1].county == "Aarhus"


def test_missing_admin2_gives_none_county():
    raw = [{"cc": "DK", "admin1": "Capital Region of Denmark", "admin2": ""}]
    with _mock_search(raw), _mock_country("Denmark"):
        result = fast_batch_geocode([(55.67, 12.56)])

    assert result[0].county is None


def test_missing_admin1_gives_none_state():
    raw = [{"cc": "US", "admin1": "", "admin2": "Some County"}]
    with _mock_search(raw), _mock_country("United States"):
        result = fast_batch_geocode([(0.0, 0.0)])

    assert result[0].state is None
    assert result[0].county == "Some County"


def test_unknown_country_code_falls_back_to_raw_cc():
    raw = [{"cc": "XX", "admin1": "Region", "admin2": "District"}]
    with _mock_search(raw), _mock_country(None):
        result = fast_batch_geocode([(0.0, 0.0)])

    assert result[0].country == "XX"


def test_empty_cc_gives_none_country():
    raw = [{"cc": "", "admin1": "State", "admin2": "County"}]
    with _mock_search(raw):
        result = fast_batch_geocode([(0.0, 0.0)])

    assert result[0].country is None


# ── Error-handling tests ──────────────────────────────────────────────────────

def test_search_exception_returns_all_none():
    with patch("reverse_geocoder.search", side_effect=Exception("boom")):
        result = fast_batch_geocode([(1.0, 2.0), (3.0, 4.0)])

    assert result == [GeoLocation(None, None, None), GeoLocation(None, None, None)]


def test_empty_input_returns_empty_list():
    with _mock_search([]):
        result = fast_batch_geocode([])

    assert result == []
