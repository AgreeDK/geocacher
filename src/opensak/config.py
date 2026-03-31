"""
config.py — Application configuration and path management.
All paths use pathlib.Path so they work identically on Linux and Windows.
"""
from pathlib import Path
import os


def get_app_data_dir() -> Path:
    """
    Return the platform-appropriate directory for storing app data.
    - Linux:   ~/.local/share/opensak
    - Windows: %APPDATA%\\opensak
    - macOS:   ~/Library/Application Support/opensak
    """
    if os.name == "nt":
        # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif os.name == "posix":
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            base = Path(xdg)
        else:
            base = Path.home() / ".local" / "share"
    else:
        base = Path.home()

    app_dir = base / "opensak"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_db_path() -> Path:
    """Return the full path to the SQLite database file."""
    return get_app_data_dir() / "opensak.db"


def get_gpx_import_dir() -> Path:
    """Return (and create if needed) the default GPX import directory."""
    d = get_app_data_dir() / "imports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_log_path() -> Path:
    """Return the path to the application log file."""
    return get_app_data_dir() / "opensak.log"


# ── Language / Preferences ────────────────────────────────────────────────────

_PREFS_FILE = None


def _get_prefs_file() -> Path:
    """Return the path to the preferences file (JSON)."""
    global _PREFS_FILE
    if _PREFS_FILE is None:
        _PREFS_FILE = get_app_data_dir() / "preferences.json"
    return _PREFS_FILE


def get_language() -> str:
    """
    Return the saved language code.
    Default: 'en' (English) for new installations.
    Once the user selects a language it is saved and restored on next startup.
    """
    import json
    prefs_file = _get_prefs_file()
    if prefs_file.exists():
        try:
            data = json.loads(prefs_file.read_text(encoding="utf-8"))
            return data.get("language", "en")
        except (json.JSONDecodeError, OSError):
            pass
    return "en"


def set_language(lang_code: str) -> None:
    """Save the language code to disk."""
    import json
    prefs_file = _get_prefs_file()
    # Read existing preferences (to avoid overwriting other settings)
    data: dict = {}
    if prefs_file.exists():
        try:
            data = json.loads(prefs_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    data["language"] = lang_code
    prefs_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Convenience summary (useful for debug / startup banner) ──────────────────

def print_config() -> None:
    print(f"  App data dir : {get_app_data_dir()}")
    print(f"  Database     : {get_db_path()}")
    print(f"  GPX imports  : {get_gpx_import_dir()}")
    print(f"  Log file     : {get_log_path()}")
    print(f"  Language     : {get_language()}")


if __name__ == "__main__":
    print("OpenSAK configuration paths:")
    print_config()
