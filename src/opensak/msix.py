"""
src/opensak/msix.py — MSIX/Desktop Bridge packaging detection (issue #820).

Windows silently virtualizes writes to %AppData%/%LocalAppData% for
MSIX-packaged (Desktop Bridge) apps, redirecting them to a private
per-package folder:

    %LocalAppData%\\Packages\\<PackageFamilyName>\\LocalCache\\Roaming\\...

This is invisible to the packaged process itself — reads/writes at the
logical %APPDATA%\\opensak path succeed normally — but Explorer or any
other external tool only ever sees the physical location, which is why a
user browsing to the path OpenSAK displays finds nothing there. This
applies regardless of which API is used to do the writing (plain Win32
file I/O included) — it's an OS-level redirection tied to the process's
package identity, not something an app opts into.

This module provides:
  - get_package_family_name() / is_msix_packaged(): detect whether the
    current process is running as an MSIX package (vs. the plain .exe or
    portable build).
  - resolve_physical_appdata_path(): translate a logical %APPDATA%-based
    path into the real, physical location Explorer would show, when
    running packaged.

Windows-only. Both functions degrade gracefully (False / path unchanged)
on any other platform, so they're safe to call unconditionally from
cross-platform code (settings_store.py, database_dialog.py, etc.).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# APPMODEL_ERROR_NO_PACKAGE — returned by GetCurrentPackageFamilyName when
# the calling process has no package identity, i.e. it's the plain .exe,
# not an MSIX-packaged one. Any other non-zero result is treated the same
# way here (fail safe towards "not packaged") since this is a display-only
# feature — under-detecting packaging just means a legacy path is shown
# as-is, not a crash or data-loss risk.
_APPMODEL_ERROR_NO_PACKAGE = 15700

# Cache: computed once per process, since packaging identity can't change
# during a single run. Use a dict rather than a sentinel-typed module
# global so mypy doesn't need `str | None | object`.
_family_name_cache: dict[str, str | None] = {}


def get_package_family_name() -> str | None:
    """
    Return the current process's MSIX Package Family Name, or None if the
    process isn't running as a packaged (MSIX/Desktop Bridge) app, or if
    this isn't Windows at all.
    """
    if "value" in _family_name_cache:
        return _family_name_cache["value"]

    result = _query_package_family_name()
    _family_name_cache["value"] = result
    return result


def _query_package_family_name() -> str | None:
    """The actual (uncached) Windows API query — split out for testability."""
    if sys.platform != "win32":
        return None

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        length = ctypes.c_uint32(0)

        # First call with a zero-length buffer to get the required size.
        # An unpackaged process returns APPMODEL_ERROR_NO_PACKAGE here
        # (length stays 0); a packaged one returns ERROR_INSUFFICIENT_BUFFER
        # with the real required length in `length`.
        kernel32.GetCurrentPackageFamilyName(ctypes.byref(length), None)
        if length.value == 0:
            return None

        buffer = ctypes.create_unicode_buffer(length.value)
        result = kernel32.GetCurrentPackageFamilyName(ctypes.byref(length), buffer)
        if result != 0:
            return None

        return buffer.value
    except (OSError, AttributeError, ValueError):
        # Best-effort: any unexpected failure here should degrade to
        # "not packaged" rather than crash the app over a display-only
        # feature.
        return None


def is_msix_packaged() -> bool:
    """Return True if running as an MSIX-packaged (Desktop Bridge) app."""
    return get_package_family_name() is not None


def resolve_physical_appdata_path(logical_path: Path) -> Path:
    """
    Translate a logical path under %APPDATA% into the real, physical
    location Windows actually stores it at, when running MSIX-packaged.

    Returns `logical_path` unchanged if:
      - not running packaged (or not on Windows at all), or
      - %APPDATA%/%LOCALAPPDATA% aren't set, or
      - `logical_path` isn't actually under %APPDATA%
    — i.e. there's nothing to translate.

    See issue #820 for the confirmed redirection scheme this mirrors:
    %LocalAppData%\\Packages\\<PackageFamilyName>\\LocalCache\\Roaming\\...
    """
    family_name = get_package_family_name()
    if family_name is None:
        return logical_path

    appdata = os.environ.get("APPDATA")
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not appdata or not local_appdata:
        return logical_path

    try:
        relative = logical_path.relative_to(Path(appdata))
    except ValueError:
        return logical_path  # not under %APPDATA% — nothing to translate

    return (
        Path(local_appdata) / "Packages" / family_name / "LocalCache"
        / "Roaming" / relative
    )


def reset_cache() -> None:
    """Clear the cached package family name — for tests only."""
    _family_name_cache.clear()
