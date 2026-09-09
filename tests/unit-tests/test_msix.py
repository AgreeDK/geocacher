# tests/unit-tests/test_msix.py — MSIX/Desktop Bridge detection (issue #820).
#
# The real Windows API call (GetCurrentPackageFamilyName) can only be
# meaningfully exercised inside an actual MSIX-packaged process on real
# Windows — not something CI can do. These tests cover:
#   - graceful degradation on non-Windows / when the API is unavailable
#   - caching behaviour
#   - the pure path-translation logic in resolve_physical_appdata_path(),
#     which is the part that's actually fully testable cross-platform
#
# Path-translation tests deliberately use forward-slash test paths rather
# than realistic Windows backslash paths: pathlib.Path() always builds a
# PosixPath on a posix test runner regardless of string content, so a
# backslash-style string wouldn't parse as path segments here anyway (see
# test_settings_store.py's `posix_only` marker for the same underlying
# pathlib limitation). The join/relative_to logic under test is separator-
# agnostic; only real backslash realism needs a real Windows machine.

from pathlib import Path

import pytest

from opensak import msix


@pytest.fixture(autouse=True)
def _clear_cache():
    """Every test starts with a clean cache — packaging identity caching
    must not leak between tests that mock different scenarios."""
    msix.reset_cache()
    yield
    msix.reset_cache()


class TestGetPackageFamilyName:
    def test_returns_none_on_non_windows(self, monkeypatch):
        monkeypatch.setattr(msix.sys, "platform", "linux")
        assert msix.get_package_family_name() is None

    def test_degrades_gracefully_when_ctypes_windll_unavailable(self, monkeypatch):
        # Simulates the exception-handling path: even if something claims
        # to be Windows, a missing/broken ctypes.windll (as on this test
        # runner) must degrade to "not packaged", not raise.
        monkeypatch.setattr(msix.sys, "platform", "win32")
        assert msix.get_package_family_name() is None

    def test_caches_after_first_call(self, monkeypatch):
        calls = {"n": 0}

        def fake_query():
            calls["n"] += 1
            return "Fake.Package_abc123"

        monkeypatch.setattr(msix, "_query_package_family_name", fake_query)
        assert msix.get_package_family_name() == "Fake.Package_abc123"
        assert msix.get_package_family_name() == "Fake.Package_abc123"
        assert calls["n"] == 1  # only queried once, second call hit the cache

    def test_reset_cache_forces_requery(self, monkeypatch):
        calls = {"n": 0}

        def fake_query():
            calls["n"] += 1
            return None

        monkeypatch.setattr(msix, "_query_package_family_name", fake_query)
        msix.get_package_family_name()
        msix.reset_cache()
        msix.get_package_family_name()
        assert calls["n"] == 2


class TestIsMsixPackaged:
    def test_true_when_family_name_present(self, monkeypatch):
        monkeypatch.setattr(msix, "get_package_family_name", lambda: "Fake.Package_abc123")
        assert msix.is_msix_packaged() is True

    def test_false_when_no_family_name(self, monkeypatch):
        monkeypatch.setattr(msix, "get_package_family_name", lambda: None)
        assert msix.is_msix_packaged() is False


class TestResolvePhysicalAppdataPath:
    def _patch_packaged(self, monkeypatch, family_name, appdata, local_appdata):
        monkeypatch.setattr(msix, "get_package_family_name", lambda: family_name)
        if appdata is not None:
            monkeypatch.setenv("APPDATA", str(appdata))
        else:
            monkeypatch.delenv("APPDATA", raising=False)
        if local_appdata is not None:
            monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
        else:
            monkeypatch.delenv("LOCALAPPDATA", raising=False)

    def test_unchanged_when_not_packaged(self, monkeypatch, tmp_path):
        appdata = tmp_path / "AppData" / "Roaming"
        self._patch_packaged(monkeypatch, None, appdata, tmp_path / "AppData" / "Local")
        logical = appdata / "opensak"
        assert msix.resolve_physical_appdata_path(logical) == logical

    def test_translates_path_when_physical_location_exists(self, monkeypatch, tmp_path):
        # Real-world finding (#820, 8 Sep 2026): translation is only shown
        # when the guessed physical path actually checks out on disk — so
        # this test creates it for real, rather than asserting on a bare
        # string computation.
        appdata = tmp_path / "AppData" / "Roaming"
        local_appdata = tmp_path / "AppData" / "Local"
        family_name = "AgreeDK.OpenSAK_8wekyb3d8bbwe"
        self._patch_packaged(monkeypatch, family_name, appdata, local_appdata)

        physical_dir = (
            local_appdata / "Packages" / family_name / "LocalCache"
            / "Roaming" / "opensak"
        )
        physical_dir.mkdir(parents=True)

        logical = appdata / "opensak"
        result = msix.resolve_physical_appdata_path(logical)
        assert result == physical_dir

    def test_preserves_nested_subdirectories(self, monkeypatch, tmp_path):
        appdata = tmp_path / "AppData" / "Roaming"
        local_appdata = tmp_path / "AppData" / "Local"
        family_name = "AgreeDK.OpenSAK_8wekyb3d8bbwe"
        self._patch_packaged(monkeypatch, family_name, appdata, local_appdata)

        physical_dir = (
            local_appdata / "Packages" / family_name / "LocalCache"
            / "Roaming" / "opensak"
        )
        physical_dir.mkdir(parents=True)
        (physical_dir / "MyCaches.db").write_text("dummy", encoding="utf-8")

        logical = appdata / "opensak" / "MyCaches.db"
        result = msix.resolve_physical_appdata_path(logical)
        assert result == physical_dir / "MyCaches.db"

    def test_falls_back_to_logical_path_when_physical_location_does_not_exist(
        self, monkeypatch, tmp_path
    ):
        # The core safety-net case: packaged, path under %APPDATA%, but the
        # guessed physical location doesn't actually exist (e.g. a
        # sideloaded/self-signed build where no virtualization actually
        # occurred, per the real-hardware test on 8 Sep 2026). Must show
        # the original logical path rather than a confident-looking guess
        # that turns out to be fictional.
        appdata = tmp_path / "AppData" / "Roaming"
        local_appdata = tmp_path / "AppData" / "Local"
        self._patch_packaged(
            monkeypatch, "AgreeDK.OpenSAK_8wekyb3d8bbwe", appdata, local_appdata
        )
        logical = appdata / "opensak"
        # Deliberately not creating anything under local_appdata/Packages/...
        assert msix.resolve_physical_appdata_path(logical) == logical

    def test_unchanged_when_path_not_under_appdata(self, monkeypatch, tmp_path):
        # e.g. a user-chosen Documents path, or the new #820-part-B default
        appdata = tmp_path / "AppData" / "Roaming"
        self._patch_packaged(
            monkeypatch, "AgreeDK.OpenSAK_8wekyb3d8bbwe", appdata,
            tmp_path / "AppData" / "Local",
        )
        logical = tmp_path / "Documents" / "opensak"
        assert msix.resolve_physical_appdata_path(logical) == logical

    def test_unchanged_when_env_vars_missing(self, monkeypatch, tmp_path):
        self._patch_packaged(monkeypatch, "AgreeDK.OpenSAK_8wekyb3d8bbwe", None, None)
        logical = tmp_path / "AppData" / "Roaming" / "opensak"
        assert msix.resolve_physical_appdata_path(logical) == logical
