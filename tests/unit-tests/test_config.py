"""
tests/unit-tests/test_config.py — Phase 4: config path and language preference tests.
"""

import json

import pytest

import opensak.config as config_module
from opensak.config import get_language, set_language


@pytest.fixture(autouse=True)
def isolate_prefs(tmp_path):
    """Point the module-level prefs-file cache at a fresh temp path each test."""
    original = config_module._PREFS_FILE
    config_module._PREFS_FILE = tmp_path / "preferences.json"
    yield config_module._PREFS_FILE
    config_module._PREFS_FILE = original


# ── get_language / set_language ───────────────────────────────────────────────


class TestGetLanguage:
    def test_default_is_english_when_file_absent(self):
        assert get_language() == "en"

    def test_returns_saved_value(self, isolate_prefs):
        isolate_prefs.write_text(json.dumps({"language": "pt"}), encoding="utf-8")
        assert get_language() == "pt"

    def test_missing_language_key_falls_back_to_default(self, isolate_prefs):
        isolate_prefs.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
        assert get_language() == "en"

    def test_malformed_json_falls_back_to_default(self, isolate_prefs):
        isolate_prefs.write_text("{ not valid json }", encoding="utf-8")
        assert get_language() == "en"

    def test_empty_file_falls_back_to_default(self, isolate_prefs):
        isolate_prefs.write_text("", encoding="utf-8")
        assert get_language() == "en"


class TestSetLanguage:
    def test_write_read_roundtrip(self):
        set_language("de")
        assert get_language() == "de"

    def test_overwrites_previous_language(self):
        set_language("fr")
        set_language("es")
        assert get_language() == "es"

    def test_preserves_other_prefs_keys(self, isolate_prefs):
        isolate_prefs.write_text(json.dumps({"theme": "dark", "language": "en"}), encoding="utf-8")
        set_language("pt")
        data = json.loads(isolate_prefs.read_text(encoding="utf-8"))
        assert data["theme"] == "dark"
        assert data["language"] == "pt"

    def test_creates_file_if_absent(self, isolate_prefs):
        assert not isolate_prefs.exists()
        set_language("it")
        assert isolate_prefs.exists()

    def test_file_contains_valid_json(self, isolate_prefs):
        set_language("nl")
        data = json.loads(isolate_prefs.read_text(encoding="utf-8"))
        assert data["language"] == "nl"
