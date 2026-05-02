"""
tests/unit-tests/test_geocoder.py — Unit tests for the reverse geocoder.

urllib.request.urlopen is patched so no real HTTP calls are made.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from opensak.geocoder import GeoLocation, reverse_geocode


def _mock_response(payload: dict) -> MagicMock:
    """Return a context-manager mock that yields JSON bytes."""
    body = json.dumps(payload).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read = MagicMock(return_value=body)
    return mock_resp


# ── Happy-path tests ──────────────────────────────────────────────────────────

def test_full_address():
    payload = {
        "address": {
            "country": "United States",
            "state": "California",
            "county": "Los Angeles County",
        }
    }
    with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
        result = reverse_geocode(34.05, -118.24)

    assert result == GeoLocation(
        country="United States",
        state="California",
        county="Los Angeles County",
    )


def test_state_falls_back_to_province():
    payload = {
        "address": {
            "country": "Canada",
            "province": "Ontario",
            "county": "York Region",
        }
    }
    with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
        result = reverse_geocode(43.65, -79.38)

    assert result is not None
    assert result.country == "Canada"
    assert result.state == "Ontario"
    assert result.county == "York Region"


def test_county_falls_back_to_district():
    payload = {
        "address": {
            "country": "Germany",
            "state": "Bavaria",
            "district": "Munich",
        }
    }
    with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
        result = reverse_geocode(48.13, 11.57)

    assert result is not None
    assert result.county == "Munich"


def test_partial_address_missing_county():
    payload = {
        "address": {
            "country": "Denmark",
            "state": "Capital Region of Denmark",
        }
    }
    with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
        result = reverse_geocode(55.67, 12.56)

    assert result is not None
    assert result.country == "Denmark"
    assert result.state == "Capital Region of Denmark"
    assert result.county is None


def test_empty_address():
    payload = {"address": {}}
    with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
        result = reverse_geocode(0.0, 0.0)

    assert result == GeoLocation(country=None, state=None, county=None)


# ── Error-handling tests ───────────────────────────────────────────────────────

def test_network_error_returns_none():
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("timeout"),
    ):
        result = reverse_geocode(55.0, 12.0)

    assert result is None


def test_timeout_returns_none():
    with patch(
        "urllib.request.urlopen",
        side_effect=TimeoutError(),
    ):
        result = reverse_geocode(55.0, 12.0)

    assert result is None


def test_invalid_json_returns_none():
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read = MagicMock(return_value=b"not json {{{")
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = reverse_geocode(55.0, 12.0)

    assert result is None


# ── Request construction tests ─────────────────────────────────────────────────

def test_correct_url_and_user_agent():
    """Verify the request targets Nominatim with required headers."""
    payload = {"address": {}}
    captured_req = []

    def fake_urlopen(req, timeout=None):
        captured_req.append(req)
        return _mock_response(payload)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        reverse_geocode(48.85, 2.35)

    assert len(captured_req) == 1
    req = captured_req[0]
    assert "nominatim.openstreetmap.org" in req.full_url
    assert "lat=48.85" in req.full_url
    assert "lon=2.35" in req.full_url
    assert "OpenSAK" in req.get_header("User-agent")
