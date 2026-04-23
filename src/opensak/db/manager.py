"""
src/opensak/db/manager.py — Database manager.

Håndterer flere lokale SQLite databaser.
Gemmer liste over kendte databaser i QSettings.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings


class DatabaseInfo:
    """Metadata om en enkelt database."""

    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = Path(path)

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def size_mb(self) -> float:
        if self.path.exists():
            return self.path.stat().st_size / (1024 * 1024)
        return 0.0

    @property
    def modified(self) -> Optional[datetime]:
        if self.path.exists():
            return datetime.fromtimestamp(self.path.stat().st_mtime)
        return None

    def to_dict(self) -> dict:
        return {"name": self.name, "path": str(self.path)}

    @classmethod
    def from_dict(cls, data: dict) -> "DatabaseInfo":
        return cls(data["name"], Path(data["path"]))

    def __repr__(self) -> str:
        return f"<DatabaseInfo {self.name!r} @ {self.path}>"


class DatabaseManager:
    """
    Håndterer liste over kendte databaser og aktiv database.

    Databaser gemmes som separate .db filer i app data mappen.
    Listen over kendte databaser gemmes i QSettings.
    """

    def __init__(self):
        self._settings = QSettings("OpenSAK Project", "OpenSAK")
        self._databases: list[DatabaseInfo] = []
        self._active: Optional[DatabaseInfo] = None
        self._load_from_settings()

    # ── Interne helpers ───────────────────────────────────────────────────────

    def _default_db_path(self) -> Path:
        """Returner stien til standard databasen."""
        from opensak.config import get_app_data_dir
        return get_app_data_dir() / "Default.db"

    @staticmethod
    def _migrate_path(path: Path) -> Path:
        """
        Flyt databaser fra den gamle 'geocacher'-mappe til 'opensak'-mappen.
        Kaldes automatisk ved indlæsning af QSettings.
        Selve .db-filen flyttes fysisk hvis den gamle sti stadig eksisterer.
        """
        from opensak.config import get_app_data_dir
        str_path = str(path)

        # Tjek om stien indeholder den gamle app-mappe
        old_markers = ["/geocacher/", "\\geocacher\\", "/geocacher\\", "\\geocacher/"]
        if not any(m in str_path for m in old_markers):
            return path  # allerede korrekt

        app_dir = get_app_data_dir()  # ~/.local/share/opensak
        new_path = app_dir / path.name

        # Flyt filen hvis den gamle eksisterer og den nye ikke gør
        if path.exists() and not new_path.exists():
            import shutil
            shutil.move(str(path), str(new_path))
            print(f"Migration: flyttede database {path.name} → opensak/")
        elif path.exists() and new_path.exists():
            # Begge eksisterer — brug den nye, ignorer den gamle
            pass

        return new_path

    def _load_from_settings(self) -> None:
        """Indlæs liste over kendte databaser fra QSettings."""
        count = self._settings.beginReadArray("databases")
        for i in range(count):
            self._settings.setArrayIndex(i)
            name = self._settings.value("name")
            path = self._settings.value("path")
            if name and path:
                migrated = self._migrate_path(Path(path))
                info = DatabaseInfo(name, migrated)
                self._databases.append(info)
        self._settings.endArray()

        # Aktiv database
        active_path = self._settings.value("active_database")
        if active_path:
            migrated_active = self._migrate_path(Path(active_path))
            found = self._find_by_path(migrated_active)
            if found:
                self._active = found

        # Gem migrerede stier tilbage til QSettings (én gang)
        self._save_to_settings()

        # Hvis ingen databaser kendes, opret Default
        if not self._databases:
            default_path = self._default_db_path()
            default = DatabaseInfo("Default", default_path)
            self._databases.append(default)
            self._active = default
            self._save_to_settings()
        elif self._active is None:
            # Databaser kendes men ingen aktiv — brug den første
            self._active = self._databases[0]
            self._save_to_settings()

    def _save_to_settings(self) -> None:
        """Gem liste over kendte databaser til QSettings."""
        self._settings.beginWriteArray("databases")
        for i, db in enumerate(self._databases):
            self._settings.setArrayIndex(i)
            self._settings.setValue("name", db.name)
            self._settings.setValue("path", str(db.path))
        self._settings.endArray()

        if self._active:
            self._settings.setValue("active_database", str(self._active.path))

        self._settings.sync()

    def _find_by_path(self, path: Path) -> Optional[DatabaseInfo]:
        for db in self._databases:
            if db.path == path:
                return db
        return None

    def _find_by_name(self, name: str) -> Optional[DatabaseInfo]:
        for db in self._databases:
            if db.name == name:
                return db
        return None

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def databases(self) -> list[DatabaseInfo]:
        return list(self._databases)

    @property
    def active(self) -> Optional[DatabaseInfo]:
        return self._active

    @property
    def active_path(self) -> Optional[Path]:
        return self._active.path if self._active else None

    def ensure_active_initialised(self) -> None:
        """
        Sørg for at den aktive database er initialiseret.
        Kaldes ved opstart — åbner den samme DB som sidst.
        """
        if self._active:
            from opensak.db.database import init_db
            init_db(db_path=self._active.path)

    def new_database(self, name: str, path: Optional[Path] = None) -> "DatabaseInfo":
        """Opret en ny tom database."""
        if self._find_by_name(name):
            raise ValueError(f"En database med navnet '{name}' eksisterer allerede")

        if path is None:
            from opensak.config import get_app_data_dir
            safe_name = "".join(
                c if c.isalnum() or c in "-_ " else "_" for c in name
            ).strip()
            path = get_app_data_dir() / f"{safe_name}.db"

        path = Path(path)
        from opensak.db.database import init_db
        init_db(db_path=path)

        # Genaktiver den nuværende database bagefter
        if self._active:
            init_db(db_path=self._active.path)

        info = DatabaseInfo(name, path)
        self._databases.append(info)
        self._save_to_settings()
        return info

    def open_database(self, path: Path) -> "DatabaseInfo":
        """Åbn en eksisterende .db fil og tilføj til listen."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Database ikke fundet: {path}")

        existing = self._find_by_path(path)
        if existing:
            return existing

        name = path.stem
        base_name = name
        counter = 2
        while self._find_by_name(name):
            name = f"{base_name} ({counter})"
            counter += 1

        info = DatabaseInfo(name, path)
        self._databases.append(info)
        self._save_to_settings()
        return info

    def switch_to(self, db_info: "DatabaseInfo") -> None:
        """Skift aktiv database og initialiser den."""
        from opensak.db.database import init_db
        self._active = db_info
        init_db(db_path=db_info.path)
        self._save_to_settings()

    def rename(self, db_info: "DatabaseInfo", new_name: str) -> None:
        """Omdøb en database (kun navnet)."""
        if self._find_by_name(new_name) and new_name != db_info.name:
            raise ValueError(f"En database med navnet '{new_name}' eksisterer allerede")
        db_info.name = new_name
        self._save_to_settings()

    def copy_database(self, db_info: "DatabaseInfo", new_name: str,
                      new_path: Optional[Path] = None) -> "DatabaseInfo":
        """Lav en kopi af en database."""
        if self._find_by_name(new_name):
            raise ValueError(f"En database med navnet '{new_name}' eksisterer allerede")

        if new_path is None:
            from opensak.config import get_app_data_dir
            safe_name = "".join(
                c if c.isalnum() or c in "-_ " else "_" for c in new_name
            ).strip()
            new_path = get_app_data_dir() / f"{safe_name}.db"

        shutil.copy2(db_info.path, new_path)
        info = DatabaseInfo(new_name, new_path)
        self._databases.append(info)
        self._save_to_settings()
        return info

    def remove_from_list(self, db_info: "DatabaseInfo") -> None:
        """Fjern database fra listen uden at slette filen."""
        if db_info == self._active:
            raise ValueError("Kan ikke fjerne den aktive database fra listen")
        self._databases.remove(db_info)
        self._save_to_settings()

    def delete_database(self, db_info: "DatabaseInfo") -> None:
        """Slet database permanent."""
        if db_info == self._active:
            raise ValueError(
                "Kan ikke slette den aktive database — skift til en anden først"
            )
        if db_info.path.exists():
            db_info.path.unlink()
        self._databases.remove(db_info)
        self._save_to_settings()


# ── Module-level singleton ────────────────────────────────────────────────────

_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    global _manager
    if _manager is None:
        _manager = DatabaseManager()
    return _manager
