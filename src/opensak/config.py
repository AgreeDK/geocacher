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
    - Windows: %APPDATA%\\opensak   (ready for later)
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


# ── Convenience summary (useful for debug / startup banner) ──────────────────

def print_config() -> None:
    print(f"  App data dir : {get_app_data_dir()}")
    print(f"  Database     : {get_db_path()}")
    print(f"  GPX imports  : {get_gpx_import_dir()}")
    print(f"  Log file     : {get_log_path()}")


if __name__ == "__main__":
    print("OpenSAK configuration paths:")
    print_config()
