"""
app.py — Application entry point for OpenSAK.
"""

import sys
from pathlib import Path


def _migrate_legacy_db() -> None:
    """
    Migrer gammel opensak.db til Default.db.

    Scenarier:
    - opensak.db eksisterer, Default.db ikke → omdøb
    - Begge eksisterer → slet den tomme Default.db, behold opensak.db
    - Kun Default.db → ingenting at gøre
    """
    from opensak.config import get_app_data_dir
    app_dir = get_app_data_dir()
    legacy = app_dir / "opensak.db"
    default = app_dir / "Default.db"

    if legacy.exists() and not default.exists():
        # Simpel migration
        legacy.rename(default)
        print(f"Migrerede {legacy.name} → {default.name}")

    elif legacy.exists() and default.exists():
        # Begge eksisterer — tjek hvilken der er størst (har data)
        legacy_size = legacy.stat().st_size
        default_size = default.stat().st_size
        if legacy_size > default_size:
            # opensak.db har data, Default.db er tom — erstat
            default.unlink()
            # Slet også WAL/SHM filer for Default hvis de findes
            for ext in [".db-shm", ".db-wal"]:
                p = app_dir / f"Default{ext}"
                if p.exists():
                    p.unlink()
            legacy.rename(default)
            print(f"Migrerede {legacy.name} → {default.name} (erstattede tom Default.db)")
        else:
            # Default.db har data — slet den tomme opensak.db
            legacy.unlink()
            for ext in [".db-shm", ".db-wal"]:
                p = app_dir / f"opensak{ext}"
                if p.exists():
                    p.unlink()
            print(f"Slettede tom {legacy.name}")


def main() -> None:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName("OpenSAK")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("OpenSAK Project")
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # Migrer gammel database hvis nødvendigt
    _migrate_legacy_db()

    # Initialiser database manager — åbner samme DB som sidst
    from opensak.db.manager import get_db_manager
    manager = get_db_manager()
    manager.ensure_active_initialised()

    from opensak.gui.mainwindow import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    main()
