"""
opensak/gui/icon.py
-------------------
Cross-platform icon loader for OpenSAK.

Usage (in app.py or mainwindow.py):
    from opensak.gui.icon import get_app_icon
    app.setWindowIcon(get_app_icon())
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap


def _icon_dir() -> Path:
    """
    Return the directory that contains the icon files.

    Works in three contexts:
    1. Running from source:    <repo>/assets/icons/
    2. PyInstaller bundle:     sys._MEIPASS/assets/icons/
    3. Linux system install:   /usr/share/pixmaps/ or XDG hicolor
    """
    # PyInstaller sets sys._MEIPASS to the temp extraction dir
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "icons"

    # Running from source — find repo root relative to this file
    # this file is at src/opensak/gui/icon.py
    # repo root is 4 levels up
    this_file = Path(__file__).resolve()
    repo_root = this_file.parent.parent.parent.parent
    candidate = repo_root / "assets" / "icons"
    if candidate.exists():
        return candidate

    # Fallback: same directory as this file
    return this_file.parent


def get_app_icon() -> QIcon:
    """
    Return a QIcon with multiple resolutions for the current platform.
    Falls back gracefully if icon files are missing.
    """
    icon_dir = _icon_dir()
    icon = QIcon()

    if sys.platform == "win32":
        # Windows: prefer .ico (embeds all sizes)
        ico_path = icon_dir / "opensak.ico"
        if ico_path.exists():
            icon = QIcon(str(ico_path))
            if not icon.isNull():
                return icon

    elif sys.platform == "darwin":
        # macOS: .icns via QIcon, or fall through to PNGs
        icns_path = icon_dir / "opensak.icns"
        if icns_path.exists():
            icon = QIcon(str(icns_path))
            if not icon.isNull():
                return icon

    # Linux + fallback: load individual PNGs into QIcon for best quality
    png_files = {
        16:   icon_dir / "opensak_16.png",
        32:   icon_dir / "opensak_32.png",
        48:   icon_dir / "opensak_48.png",
        64:   icon_dir / "opensak_64.png",
        128:  icon_dir / "opensak_128.png",
        256:  icon_dir / "opensak.png",        # primary / 256px
        512:  icon_dir / "opensak_512.png",
    }

    added = 0
    for size, path in png_files.items():
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                icon.addPixmap(pixmap)
                added += 1

    if added == 0:
        # Last resort: try any .png in the icon dir
        for png in sorted(icon_dir.glob("opensak*.png")):
            pixmap = QPixmap(str(png))
            if not pixmap.isNull():
                icon.addPixmap(pixmap)

    return icon


def set_taskbar_icon(window) -> None:
    """
    Convenience function: set icon on a QMainWindow.
    Call this once after the window is created.
    """
    icon = get_app_icon()
    window.setWindowIcon(icon)
