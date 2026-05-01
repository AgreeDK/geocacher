"""
opensak/gui/icon.py
-------------------
Cross-platform icon loader for OpenSAK.

Usage (in app.py or mainwindow.py):
    from opensak.gui.icon import get_app_icon
    app.setWindowIcon(get_app_icon())

QMessageBox med OpenSAK-ikon:
    from opensak.gui.icon import OpenSAKMessageBox as QMessageBox
    QMessageBox.information(self, "Titel", "Besked")   # samme API som før
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMessageBox


def _icon_dir() -> Path:
    """
    Return the directory that contains the icon files.

    Works in three contexts:
    1. Running from source:    <repo>/assets/icons/
    2. PyInstaller bundle:     sys._MEIPASS/assets/icons/
    3. Linux system install:   /usr/share/pixmaps/ or XDG hicolor
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "icons"

    this_file = Path(__file__).resolve()
    repo_root = this_file.parent.parent.parent.parent
    candidate = repo_root / "assets" / "icons"
    if candidate.exists():
        return candidate

    return this_file.parent


def get_app_icon() -> QIcon:
    """
    Return a QIcon with multiple resolutions for the current platform.
    Falls back gracefully if icon files are missing.
    """
    icon_dir = _icon_dir()
    icon = QIcon()

    if sys.platform == "win32":
        ico_path = icon_dir / "opensak.ico"
        if ico_path.exists():
            icon = QIcon(str(ico_path))
            if not icon.isNull():
                return icon

    elif sys.platform == "darwin":
        icns_path = icon_dir / "opensak.icns"
        if icns_path.exists():
            icon = QIcon(str(icns_path))
            if not icon.isNull():
                return icon

    png_files = {
        16:   icon_dir / "opensak_16.png",
        32:   icon_dir / "opensak_32.png",
        48:   icon_dir / "opensak_48.png",
        64:   icon_dir / "opensak_64.png",
        128:  icon_dir / "opensak_128.png",
        256:  icon_dir / "opensak.png",
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


# ── QMessageBox med OpenSAK-ikon ──────────────────────────────────────────────

def _make_msgbox(parent, title: str, text: str,
                 box_icon: QMessageBox.Icon,
                 buttons: QMessageBox.StandardButton,
                 default_button: QMessageBox.StandardButton) -> QMessageBox:
    """Intern hjælpefunktion: opret en QMessageBox med OpenSAK windowIcon."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(box_icon)
    msg.setStandardButtons(buttons)
    msg.setWindowIcon(get_app_icon())
    if default_button != QMessageBox.StandardButton.NoButton:
        msg.setDefaultButton(default_button)
    return msg


class OpenSAKMessageBox(QMessageBox):
    """
    Drop-in erstatning for QMessageBox der automatisk bruger OpenSAK-ikonet.

    Brug:
        from opensak.gui.icon import OpenSAKMessageBox as QMessageBox

    Alle eksisterende kald virker uændret — både statiske og instans-kald.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowIcon(get_app_icon())

    @staticmethod
    def information(parent, title, text,
                    buttons=QMessageBox.StandardButton.Ok,
                    default_button=QMessageBox.StandardButton.NoButton):
        msg = _make_msgbox(parent, title, text,
                           QMessageBox.Icon.Information, buttons, default_button)
        return msg.exec()

    @staticmethod
    def warning(parent, title, text,
                buttons=QMessageBox.StandardButton.Ok,
                default_button=QMessageBox.StandardButton.NoButton):
        msg = _make_msgbox(parent, title, text,
                           QMessageBox.Icon.Warning, buttons, default_button)
        return msg.exec()

    @staticmethod
    def critical(parent, title, text,
                 buttons=QMessageBox.StandardButton.Ok,
                 default_button=QMessageBox.StandardButton.NoButton):
        msg = _make_msgbox(parent, title, text,
                           QMessageBox.Icon.Critical, buttons, default_button)
        return msg.exec()

    @staticmethod
    def question(parent, title, text,
                 buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                 default_button=QMessageBox.StandardButton.NoButton):
        msg = _make_msgbox(parent, title, text,
                           QMessageBox.Icon.Question, buttons, default_button)
        return msg.exec()

    @staticmethod
    def about(parent, title, text):
        msg = _make_msgbox(parent, title, text,
                           QMessageBox.Icon.Information,
                           QMessageBox.StandardButton.Ok,
                           QMessageBox.StandardButton.NoButton)
        msg.exec()
