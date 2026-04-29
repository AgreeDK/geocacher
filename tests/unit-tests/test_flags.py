"""
tests/unit-tests/test_flags.py — Feature flag resolution tests.
"""

import pytest

import opensak.utils.flags as flags_module


# ── _load() ───────────────────────────────────────────────────────────────────


class TestLoad:
    def test_absent_file_returns_release_defaults(self, no_features_file):
        assert flags_module._flags == {"where-filter": False}

    def test_present_file_overrides_defaults(self, patch_features_file):
        patch_features_file({"where-filter": True})
        assert flags_module._flags["where-filter"] is True

    def test_malformed_json_falls_back_to_defaults(self, tmp_path, monkeypatch):
        f = tmp_path / "features.json"
        f.write_text("{ not valid", encoding="utf-8")
        monkeypatch.setattr(flags_module, "_FEATURES_FILE", f)
        result = flags_module._load()
        assert result == {"where-filter": False}

    def test_unknown_keys_in_file_are_ignored(self, patch_features_file):
        patch_features_file({"where-filter": True, "future-flag": True})
        assert "future-flag" not in flags_module._flags

    def test_partial_file_keeps_unset_flags_as_defaults(self, patch_features_file):
        patch_features_file({})
        assert flags_module._flags["where-filter"] is False


# ── Module-level attribute ────────────────────────────────────────────────────


class TestWhereFilter:
    def test_false_when_file_absent(self, no_features_file):
        assert flags_module.where_filter is False

    def test_true_when_enabled_in_file(self, patch_features_file):
        patch_features_file({"where-filter": True})
        assert flags_module.where_filter is True

    def test_false_when_explicitly_disabled_in_file(self, patch_features_file):
        patch_features_file({"where-filter": False})
        assert flags_module.where_filter is False


# ── _parse_argv() ─────────────────────────────────────────────────────────────


class TestParseArgv:
    def test_space_separated_true(self, monkeypatch, no_features_file):
        monkeypatch.setattr("sys.argv", ["run.py", "--feature", "where-filter=true"])
        assert flags_module._parse_argv() == {"where-filter": True}

    def test_space_separated_false(self, monkeypatch, no_features_file):
        monkeypatch.setattr("sys.argv", ["run.py", "--feature", "where-filter=false"])
        assert flags_module._parse_argv() == {"where-filter": False}

    def test_equals_form(self, monkeypatch, no_features_file):
        monkeypatch.setattr("sys.argv", ["run.py", "--feature=where-filter=true"])
        assert flags_module._parse_argv() == {"where-filter": True}

    def test_multiple_features_last_wins(self, monkeypatch, no_features_file):
        monkeypatch.setattr(
            "sys.argv",
            ["run.py", "--feature", "where-filter=true", "--feature", "where-filter=false"],
        )
        assert flags_module._parse_argv() == {"where-filter": False}

    def test_unknown_flag_name_ignored(self, monkeypatch, no_features_file):
        monkeypatch.setattr("sys.argv", ["run.py", "--feature", "nonexistent=true"])
        assert flags_module._parse_argv() == {}

    def test_argv_overrides_features_file(self, monkeypatch, patch_features_file):
        patch_features_file({"where-filter": False})
        monkeypatch.setattr("sys.argv", ["run.py", "--feature", "where-filter=true"])
        flags_module._flags = flags_module._load()
        flags_module.where_filter = flags_module._flags["where-filter"]
        assert flags_module.where_filter is True

    def test_falsy_values(self, monkeypatch, no_features_file):
        for val in ("0", "false", "no", "False", "NO"):
            monkeypatch.setattr("sys.argv", ["run.py", "--feature", f"where-filter={val}"])
            assert flags_module._parse_argv() == {"where-filter": False}, f"failed for '{val}'"

    def test_truthy_values(self, monkeypatch, no_features_file):
        for val in ("1", "true", "yes", "True", "YES", "on"):
            monkeypatch.setattr("sys.argv", ["run.py", "--feature", f"where-filter={val}"])
            assert flags_module._parse_argv() == {"where-filter": True}, f"failed for '{val}'"
