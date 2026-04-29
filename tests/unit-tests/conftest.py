"""
tests/unit-tests/conftest.py — Shared fixtures for unit tests.
"""

import json

import pytest

import opensak.utils.flags as flags_module


def _reload_flags() -> None:
    """Reload flags module state from the current _FEATURES_FILE."""
    flags_module._flags = flags_module._load()
    flags_module.where_filter = flags_module._flags["where-filter"]


@pytest.fixture(autouse=True)
def reset_flags():
    """Restore flags module state after every test."""
    yield
    _reload_flags()


@pytest.fixture()
def patch_features_file(tmp_path, monkeypatch):
    """Write a features.json to a temp path and wire it into the flags module."""

    def _write(data: dict) -> None:
        f = tmp_path / "features.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(flags_module, "_FEATURES_FILE", f)
        _reload_flags()

    return _write


@pytest.fixture()
def no_features_file(tmp_path, monkeypatch):
    """Point the flags module at a path where features.json does not exist."""
    monkeypatch.setattr(flags_module, "_FEATURES_FILE", tmp_path / "features.json")
    _reload_flags()
