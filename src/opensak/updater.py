"""
src/opensak/updater.py — Version check mod GitHub Releases API.

Tjekker i baggrunden om der er en ny version af OpenSAK tilgængelig.
Bruger kun Python stdlib — ingen eksterne afhængigheder.
"""

from __future__ import annotations

import json
import urllib.request
from urllib.error import URLError

from PySide6.QtCore import QThread, Signal


GITHUB_API_URL = "https://api.github.com/repos/AgreeDK/opensak/releases/latest"
RELEASES_PAGE   = "https://github.com/AgreeDK/opensak/releases/latest"
REQUEST_TIMEOUT = 10  # sekunder


def _parse_version(tag: str) -> tuple[int, ...]:
    """Konverter 'v1.11.4' eller '1.11.4' til (1, 11, 4) til sammenligning."""
    cleaned = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in cleaned.split("."))
    except ValueError:
        return (0,)


def fetch_latest_release() -> dict | None:
    """
    Hent seneste release fra GitHub API.

    Returnerer dict med keys 'tag_name', 'html_url', 'name' eller None ved fejl.
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "OpenSAK-version-check"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.load(resp)
        return {
            "tag_name": data.get("tag_name", ""),
            "html_url": data.get("html_url", RELEASES_PAGE),
            "name":     data.get("name", ""),
        }
    except (URLError, OSError, json.JSONDecodeError, KeyError):
        return None


class UpdateCheckWorker(QThread):
    """
    Baggrundsthread der tjekker for nye versioner.

    Signals:
        update_available(latest_tag, release_url):
            Ny version fundet — nyere end den installerede.
        check_done():
            Tjekket er færdigt (uanset resultat).
    """

    update_available = Signal(str, str)   # (tag, url)
    check_done       = Signal()

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self._current = current_version

    def run(self) -> None:
        try:
            release = fetch_latest_release()
            if release:
                latest_tag = release["tag_name"]
                if _parse_version(latest_tag) > _parse_version(self._current):
                    self.update_available.emit(latest_tag, release["html_url"])
        finally:
            self.check_done.emit()
