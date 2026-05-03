"""
tests/unit-tests/test_geocoder.py — Unit tests for the offline reverse geocoder.

reverse_geocoder and pycountry are injected into sys.modules so the tests
work even when neither library is installed in the test environment.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from opensak.geocoder import GeoLocation, fast_batch_geocode


def _mocks(search_results: list[dict], country_name: str | None = ""):
    """
    Context manager that injects fake reverse_geocoder and pycountry modules.

    country_name=None  → pycountry.countries.get returns None (unknown cc)
    country_name=""    → not patched (use when country lookup is irrelevant)
    country_name=str   → pycountry.countries.get returns an object with .name
    """
    mock_rg = MagicMock()
    mock_rg.search.return_value = search_results

    mock_pc = MagicMock()
    if country_name is None:
        mock_pc.countries.get.return_value = None
    elif country_name:
        country_obj = MagicMock()
        country_obj.name = country_name
        mock_pc.countries.get.return_value = country_obj

    return patch.dict(sys.modules, {"reverse_geocoder": mock_rg, "pycountry": mock_pc})


def _mocks_map(search_results: list[dict], cc_to_name: dict[str, str]):
    """Variant for tests that need different country names per result."""
    mock_rg = MagicMock()
    mock_rg.search.return_value = search_results

    mock_pc = MagicMock()
    def _get(alpha_2):
        name = cc_to_name.get(alpha_2)
        if name is None:
            return None
        obj = MagicMock()
        obj.name = name
        return obj
    mock_pc.countries.get.side_effect = _get

    return patch.dict(sys.modules, {"reverse_geocoder": mock_rg, "pycountry": mock_pc})


# ── Happy-path tests ──────────────────────────────────────────────────────────

def test_single_full_result():
    raw = [{"cc": "US", "admin1": "California", "admin2": "Los Angeles County"}]
    with _mocks(raw, "United States"):
        result = fast_batch_geocode([(34.05, -118.24)])

    assert result == [GeoLocation(country="United States", state="California", county="Los Angeles County")]


def test_batch_returns_one_per_coord():
    raw = [
        {"cc": "US", "admin1": "Texas",       "admin2": "Travis County"},
        {"cc": "DK", "admin1": "Midtjylland", "admin2": "Aarhus"},
    ]
    with _mocks_map(raw, {"US": "United States", "DK": "Denmark"}):
        result = fast_batch_geocode([(30.26, -97.74), (56.15, 10.21)])

    assert len(result) == 2
    assert result[0].country == "United States"
    assert result[1].state == "Midtjylland"
    assert result[1].county == "Aarhus"


def test_missing_admin2_gives_none_county():
    raw = [{"cc": "DK", "admin1": "Capital Region of Denmark", "admin2": ""}]
    with _mocks(raw, "Denmark"):
        result = fast_batch_geocode([(55.67, 12.56)])

    assert result[0].county is None


def test_missing_admin1_gives_none_state():
    raw = [{"cc": "US", "admin1": "", "admin2": "Some County"}]
    with _mocks(raw, "United States"):
        result = fast_batch_geocode([(0.0, 0.0)])

    assert result[0].state is None
    assert result[0].county == "Some County"


def test_unknown_country_code_falls_back_to_raw_cc():
    raw = [{"cc": "XX", "admin1": "Region", "admin2": "District"}]
    with _mocks(raw, None):
        result = fast_batch_geocode([(0.0, 0.0)])

    assert result[0].country == "XX"


def test_empty_cc_gives_none_country():
    raw = [{"cc": "", "admin1": "State", "admin2": "County"}]
    with _mocks(raw, ""):
        result = fast_batch_geocode([(0.0, 0.0)])

    assert result[0].country is None


# ── Error-handling tests ──────────────────────────────────────────────────────

def test_search_exception_returns_all_none():
    mock_rg = MagicMock()
    mock_rg.search.side_effect = Exception("boom")
    with patch.dict(sys.modules, {"reverse_geocoder": mock_rg, "pycountry": MagicMock()}):
        result = fast_batch_geocode([(1.0, 2.0), (3.0, 4.0)])

    assert result == [GeoLocation(None, None, None), GeoLocation(None, None, None)]


def test_empty_input_returns_empty_list():
    mock_rg = MagicMock()
    mock_rg.search.return_value = []
    with patch.dict(sys.modules, {"reverse_geocoder": mock_rg, "pycountry": MagicMock()}):
        result = fast_batch_geocode([])

    assert result == []
